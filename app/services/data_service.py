"""Data consolidation service — orchestrates multiple data sources."""

from __future__ import annotations

import logging
import math
import uuid
from typing import Sequence

from fuzzywuzzy import fuzz

from app.clients.denue_client import DENUEClient
from app.clients.google_places_client import GooglePlacesClient
from app.clients.overture_client import OvertureMapsClient
from app.models.schemas import (
    AGEBData,
    Business,
    BusinessInterpretation,
    Zone,
)
from app.services.ageb_reader import AGEBReader
from app.services.zone_service import ZoneService

logger = logging.getLogger(__name__)

# Consolidation thresholds
_FUZZY_MATCH_THRESHOLD = 80  # minimum fuzzywuzzy score (0-100)
_PROXIMITY_THRESHOLD_M = 50  # maximum distance in metres

# Default search radius in metres for API queries
_DEFAULT_RADIUS_M = 1000


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return the distance in metres between two geographic points (haversine formula)."""
    R = 6_371_000  # Earth radius in metres
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _is_match(biz_a: Business, biz_b: Business) -> bool:
    """Return True if two businesses match by name similarity AND proximity."""
    name_score = fuzz.token_sort_ratio(biz_a.name.lower(), biz_b.name.lower())
    if name_score < _FUZZY_MATCH_THRESHOLD:
        return False
    dist = haversine_distance(biz_a.lat, biz_a.lng, biz_b.lat, biz_b.lng)
    return dist < _PROXIMITY_THRESHOLD_M


def consolidate_businesses(
    google_results: list[Business],
    denue_results: list[Business],
    overture_results: list[Business],
) -> list[Business]:
    """Merge businesses from three sources.

    Strategy:
    1. Google Places results form the base list.
    2. For each DENUE result, find a matching Google result (fuzzy name ≥80% + <50 m).
       If matched → enrich the Google record with DENUE metadata and update source.
       If not matched → add as a new business with verified_google=False.
    3. Same for Overture results.
    """
    # Work on copies so we don't mutate the originals
    merged: list[Business] = [b.model_copy() for b in google_results]

    # Track which secondary businesses have been matched
    matched_denue: set[int] = set()
    matched_overture: set[int] = set()

    # --- Enrich with DENUE ---
    for d_idx, denue_biz in enumerate(denue_results):
        for m_idx, base_biz in enumerate(merged):
            if _is_match(base_biz, denue_biz):
                # Enrich the base record
                merged[m_idx] = base_biz.model_copy(
                    update={
                        "denue_scian_code": denue_biz.denue_scian_code,
                        "denue_employee_stratum": denue_biz.denue_employee_stratum,
                        "denue_registration_date": denue_biz.denue_registration_date,
                        "denue_legal_name": denue_biz.denue_legal_name,
                        "denue_address": denue_biz.denue_address,
                        "source": _merge_source(base_biz.source, "denue"),
                    }
                )
                matched_denue.add(d_idx)
                break

    # --- Enrich with Overture ---
    for o_idx, overture_biz in enumerate(overture_results):
        for m_idx, base_biz in enumerate(merged):
            if _is_match(base_biz, overture_biz):
                merged[m_idx] = base_biz.model_copy(
                    update={
                        "source": _merge_source(base_biz.source, "overture"),
                    }
                )
                matched_overture.add(o_idx)
                break

    # --- Add unmatched DENUE businesses ---
    for d_idx, denue_biz in enumerate(denue_results):
        if d_idx not in matched_denue:
            merged.append(
                denue_biz.model_copy(
                    update={
                        "verified_google": False,
                        "source": "denue",
                    }
                )
            )

    # --- Add unmatched Overture businesses ---
    for o_idx, overture_biz in enumerate(overture_results):
        if o_idx not in matched_overture:
            merged.append(
                overture_biz.model_copy(
                    update={
                        "verified_google": False,
                        "source": "overture",
                    }
                )
            )

    return merged


def _merge_source(existing: str, new_source: str) -> str:
    """Combine source labels, e.g. 'google' + 'denue' → 'google+denue'."""
    parts = set(existing.split("+"))
    parts.add(new_source)
    return "+".join(sorted(parts))


class DataService:
    """Orchestrates data retrieval from multiple sources and consolidation."""

    def __init__(
        self,
        zone_service: ZoneService | None = None,
        ageb_reader: AGEBReader | None = None,
        google_client: GooglePlacesClient | None = None,
        denue_client: DENUEClient | None = None,
        overture_client: OvertureMapsClient | None = None,
    ) -> None:
        self._zone_service = zone_service or ZoneService()
        self._ageb_reader = ageb_reader or AGEBReader()
        self._google = google_client or GooglePlacesClient()
        self._denue = denue_client or DENUEClient()
        self._overture = overture_client or OvertureMapsClient()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search_zones(self, query: str) -> list[Zone]:
        """Delegate zone search to ZoneService."""
        return self._zone_service.search_zones(query)

    async def get_businesses_in_zone(
        self,
        zone: Zone,
        business_type: BusinessInterpretation,
        radius_m: int = 5000,
    ) -> tuple[list[Business], list[str]]:
        """Fetch and consolidate businesses from all sources.

        Args:
            zone: The geographic zone to search in.
            business_type: Interpreted business type with SCIAN info.
            radius_m: Search radius in metres (default 5000 = 5 km).

        Returns:
            A tuple of (consolidated_businesses, warnings).
        """
        warnings: list[str] = []

        # Build search keywords from the interpretation
        keyword = business_type.scian_description or business_type.original_input
        scian_code = business_type.scian_code

        # --- Query all sources concurrently-ish (sequential for simplicity) ---
        google_results = await self._fetch_google(zone, keyword, warnings, radius_m)
        denue_results = await self._fetch_denue(zone, scian_code, keyword, warnings, radius_m)
        overture_results = await self._fetch_overture(zone, keyword, warnings)

        # --- Consolidate ---
        consolidated = consolidate_businesses(
            google_results, denue_results, overture_results
        )

        if not google_results and (denue_results or overture_results):
            warnings.append(
                "Google Places no disponible — los datos de negocios pueden no reflejar el estado actual de operación"
            )

        return consolidated, warnings

    async def search_by_google_categories(
        self,
        zone: Zone,
        categories: list[str],
        radius_m: int = 5000,
    ) -> list[Business]:
        """Search businesses by Google Places categories, one search per category.

        Deduplicates results by place_id (Business.id).

        Args:
            zone: The geographic zone (used for center coordinates).
            categories: List of Google Places types (e.g. ["restaurant", "cafe"]).
            radius_m: Search radius in metres.

        Returns:
            Deduplicated list of Business models.
        """
        if not categories:
            return []

        seen_ids: set[str] = set()
        results: list[Business] = []

        for cat in categories:
            try:
                cat_results = await self._google.search_by_category(
                    lat=zone.center_lat,
                    lng=zone.center_lng,
                    radius=radius_m,
                    included_type=cat,
                )
                for biz in cat_results:
                    if biz.id not in seen_ids:
                        seen_ids.add(biz.id)
                        results.append(biz)
            except Exception:
                logger.exception("Google category search failed for '%s'", cat)

        return results

    async def get_ageb_data(self, ageb_ids: list[str]) -> AGEBData:
        """Delegate AGEB data retrieval to AGEBReader."""
        try:
            return self._ageb_reader.get_zone_data(ageb_ids)
        except RuntimeError:
            # AGEB data not loaded yet (background loading still in progress)
            logger.warning("AGEB data not loaded yet — returning empty data")
            return AGEBData(
                total_population=0,
                population_density=0.0,
                economically_active_population=0,
                socioeconomic_level="Desconocido",
                ageb_count=0,
                raw_indicators={},
            )

    # ------------------------------------------------------------------
    # Private fetch helpers (each handles its own errors)
    # ------------------------------------------------------------------

    async def _fetch_google(
        self, zone: Zone, keyword: str, warnings: list[str], radius_m: int = _DEFAULT_RADIUS_M
    ) -> list[Business]:
        try:
            return await self._google.search_nearby(
                lat=zone.center_lat,
                lng=zone.center_lng,
                radius=radius_m,
                keyword=keyword,
            )
        except Exception:
            logger.exception("Google Places fetch failed")
            warnings.append("Google Places API no respondió")
            return []

    async def _fetch_denue(
        self, zone: Zone, scian_code: str, keyword: str, warnings: list[str], radius_m: int = _DEFAULT_RADIUS_M
    ) -> list[Business]:
        try:
            # DENUE /Buscar/ endpoint works better with text keywords than SCIAN codes
            activity = keyword if keyword else scian_code
            return await self._denue.search_businesses(
                lat=zone.center_lat,
                lng=zone.center_lng,
                radius=radius_m,
                activity=activity,
            )
        except Exception:
            logger.exception("DENUE fetch failed")
            warnings.append("DENUE API no respondió")
            return []

    async def _fetch_overture(
        self, zone: Zone, keyword: str, warnings: list[str]
    ) -> list[Business]:
        # Overture Maps does not have a public REST API yet.
        # For MVP, we skip this source silently.
        # TODO: Implement via DuckDB local query or when a public API becomes available.
        return []
