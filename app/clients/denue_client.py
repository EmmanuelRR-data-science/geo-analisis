"""INEGI DENUE API client for business registry search."""

from __future__ import annotations

import logging
import os
import uuid

import httpx

from app.models.schemas import Business

logger = logging.getLogger(__name__)

# Timeout and retry configuration
_TIMEOUT = 15.0
_MAX_RETRIES = 1

# DENUE API base URL
# Docs: https://www.inegi.org.mx/servicios/api_denue.html
# Endpoint: /Buscar/{condicion}/{lat},{lng}/{distancia}/{token}
_DENUE_BASE_URL = "https://www.inegi.org.mx/app/api/denue/v1/consulta/Buscar"

# Public DENUE token (fallback)
_DEFAULT_TOKEN = "b77c5028-b057-4547-80a0-4e7d83381dfb"


class DENUEClient:
    """Client for the INEGI DENUE API."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("DENUE_API_KEY", "") or os.getenv("API_KEY_INEGI", _DEFAULT_TOKEN)

    async def search_businesses(
        self,
        lat: float,
        lng: float,
        radius: int,
        activity: str,
    ) -> list[Business]:
        """Search DENUE for businesses near a location.

        Args:
            lat: Latitude of the center point.
            lng: Longitude of the center point.
            radius: Search radius in metres.
            activity: SCIAN activity keyword or code.

        Returns an empty list on any failure.
        """
        # DENUE API expects: /BuscarAreaActEstr/{condicion}/{lat},{lng}/{distancia}/{token}
        # condicion = keyword or SCIAN code
        url = (
            f"{_DENUE_BASE_URL}"
            f"/{activity}"
            f"/{lat},{lng}"
            f"/{radius}"
            f"/{self._api_key}"
        )

        for attempt in range(_MAX_RETRIES + 1):
            try:
                # Force HTTP/1.1 for INEGI API (resolves RemoteProtocolError on VPS)
                async with httpx.AsyncClient(timeout=_TIMEOUT, http2=False) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                    if not isinstance(data, list):
                        return []
                    return self._parse_results(data)
            except Exception:
                if attempt < _MAX_RETRIES:
                    logger.warning(
                        "DENUE search attempt %d failed, retrying…",
                        attempt + 1,
                    )
                    continue
                logger.exception("DENUE search failed after retries")
                return []

        return []  # pragma: no cover

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_results(data: list[dict]) -> list[Business]:
        """Convert raw DENUE API response into Business models."""
        businesses: list[Business] = []
        for entry in data:
            try:
                lat = float(entry.get("Latitud", 0))
                lng = float(entry.get("Longitud", 0))
            except (ValueError, TypeError):
                continue

            name = entry.get("Nombre", "Sin nombre")
            scian_code = entry.get("Codigo_Actividad", "")
            scian_desc = entry.get("Actividad_Economica", "")

            # Build address from available fields
            address_parts = [
                entry.get("Tipo_Vialidad", ""),
                entry.get("Nombre_Vialidad", ""),
                entry.get("Numero_Exterior", ""),
            ]
            address = " ".join(p for p in address_parts if p).strip()

            businesses.append(
                Business(
                    id=entry.get("Id", str(uuid.uuid4())),
                    name=name,
                    lat=lat,
                    lng=lng,
                    category=scian_desc,
                    source="denue",
                    verified_google=False,
                    denue_scian_code=scian_code,
                    denue_employee_stratum=entry.get("Estrato", ""),
                    denue_registration_date=entry.get("Fecha_Alta", ""),
                    denue_legal_name=entry.get("Razon_Social", ""),
                    denue_address=address or None,
                )
            )
        return businesses
