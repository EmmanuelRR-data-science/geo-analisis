"""Overture Maps client for open geospatial place data."""

from __future__ import annotations

import logging
import uuid

import httpx

from app.models.schemas import BoundingBox, Business

logger = logging.getLogger(__name__)

# Timeout and retry configuration
_TIMEOUT = 15.0
_MAX_RETRIES = 1

# For MVP we query the Overture Maps API via the public endpoint.
# This can be swapped for a DuckDB-based local query later.
_OVERTURE_API_URL = "https://api.overturedata.org/v0/places"


class OvertureMapsClient:
    """Client for Overture Maps places data."""

    async def get_places(
        self,
        bbox: BoundingBox,
        category: str,
    ) -> list[Business]:
        """Fetch places within a bounding box from Overture Maps.

        Args:
            bbox: Geographic bounding box to search within.
            category: Category keyword to filter places.

        Returns an empty list on any failure.
        """
        params = {
            "bbox": f"{bbox.min_lng},{bbox.min_lat},{bbox.max_lng},{bbox.max_lat}",
            "category": category,
            "limit": 50,
        }

        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.get(_OVERTURE_API_URL, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    return self._parse_results(data)
            except Exception:
                if attempt < _MAX_RETRIES:
                    logger.warning(
                        "Overture Maps attempt %d failed, retrying…",
                        attempt + 1,
                    )
                    continue
                logger.exception("Overture Maps query failed after retries")
                return []

        return []  # pragma: no cover

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_results(data: dict | list) -> list[Business]:
        """Convert Overture API response into Business models."""
        features: list[dict] = []
        if isinstance(data, dict):
            features = data.get("features", data.get("results", []))
        elif isinstance(data, list):
            features = data

        businesses: list[Business] = []
        for feat in features:
            props = feat.get("properties", feat) if isinstance(feat, dict) else {}
            geometry = feat.get("geometry", {}) if isinstance(feat, dict) else {}
            coords = geometry.get("coordinates", [0, 0])

            name = props.get("name", props.get("names", {}).get("primary", "Sin nombre"))
            if isinstance(name, dict):
                name = name.get("primary", "Sin nombre")

            try:
                lng = float(coords[0]) if len(coords) > 0 else 0.0
                lat = float(coords[1]) if len(coords) > 1 else 0.0
            except (ValueError, TypeError, IndexError):
                lat, lng = 0.0, 0.0

            category = ""
            cats = props.get("categories", {})
            if isinstance(cats, dict):
                category = cats.get("primary", "")
            elif isinstance(cats, list) and cats:
                category = cats[0] if isinstance(cats[0], str) else ""

            businesses.append(
                Business(
                    id=props.get("id", str(uuid.uuid4())),
                    name=name,
                    lat=lat,
                    lng=lng,
                    category=category,
                    source="overture",
                    verified_google=False,
                )
            )
        return businesses
