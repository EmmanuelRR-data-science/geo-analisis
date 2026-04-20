"""BestTime.app API client for foot traffic forecasts."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx

from app.models.schemas import FootTrafficForecast

logger = logging.getLogger(__name__)

_BESTTIME_URL = "https://besttime.app/api/v1/forecasts"
_TIMEOUT = 15.0
_MAX_RETRIES = 1
_CACHE_DAYS = 14

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def _normalize_category(raw_category: str | None, raw_categories: list | None) -> str | None:
    """Normalize BestTime category labels for presentation."""
    if raw_category:
        return str(raw_category).replace("_", " ").title()
    if raw_categories and isinstance(raw_categories, list):
        first = next((c for c in raw_categories if c), None)
        if first:
            return str(first).replace("_", " ").title()
    return None


def _parse_hour(value) -> int | None:
    """Parse an hour value returned by BestTime into 0-23 range."""
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized or normalized in {"closed", "cerrado", "none", "null"}:
            return None
    try:
        return int(float(value)) % 24
    except (TypeError, ValueError):
        return None


def _format_opening_range(open_hour, close_hour) -> str | None:
    """Format BestTime opening/closing hours into HH:00 range."""
    open_parsed = _parse_hour(open_hour)
    close_parsed = _parse_hour(close_hour)

    if open_parsed is None and close_parsed is None:
        return "Cerrado"
    if open_parsed is None or close_parsed is None:
        return None
    if open_parsed == close_parsed:
        return "24 horas"
    return f"{open_parsed:02d}:00–{close_parsed:02d}:00"


def _extract_opening_hours_by_day(analysis: list[dict]) -> dict[str, str]:
    """Extract opening-hour ranges by day from BestTime analysis payload."""
    opening_hours: dict[str, str] = {}
    for day_data in analysis:
        day_info = day_data.get("day_info", {})
        day_text = day_info.get("day_text", "")
        if day_text:
            day_text = day_text.capitalize()
        if day_text not in DAYS:
            continue
        formatted_range = _format_opening_range(day_info.get("venue_open"), day_info.get("venue_closed"))
        if formatted_range:
            opening_hours[day_text] = formatted_range
    return opening_hours


class BestTimeClient:
    """Client for BestTime.app foot traffic API."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("BEST_TIME_API_KEY", "")
        if not self._api_key:
            logger.warning("BEST_TIME_API_KEY not configured — foot traffic data unavailable")

    async def get_forecast(self, venue_name: str, venue_address: str) -> FootTrafficForecast | None:
        """Get foot traffic forecast, checking cache first."""
        if not self._api_key:
            return None

        # Check cache
        cached = self._get_from_cache(venue_name, venue_address)
        if cached:
            return cached

        # Fetch from API
        data = await self._fetch_forecast(venue_name, venue_address)
        if not data:
            return None

        forecast = self._parse_forecast(data)
        if forecast:
            self._save_to_cache(forecast, venue_address, data)
        return forecast

    async def get_forecasts_batch(
        self, venues: list[dict], max_concurrent: int = 5
    ) -> list[FootTrafficForecast | None]:
        """Get forecasts for multiple venues with concurrency limit."""
        if not self._api_key:
            return [None] * len(venues)

        semaphore = asyncio.Semaphore(max_concurrent)

        async def _limited_fetch(v: dict) -> FootTrafficForecast | None:
            async with semaphore:
                return await self.get_forecast(v["name"], v["address"])

        return await asyncio.gather(*[_limited_fetch(v) for v in venues])

    async def _fetch_forecast(self, venue_name: str, venue_address: str) -> dict | None:
        """Make HTTP request to BestTime API with retries."""
        params = {
            "api_key_private": self._api_key,
            "venue_name": venue_name,
            "venue_address": venue_address,
        }

        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.post(_BESTTIME_URL, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("status") == "OK":
                            return data
                        logger.warning("BestTime API returned status: %s for %s", data.get("status"), venue_name)
                        return None
                    logger.warning("BestTime API HTTP %d for %s", resp.status_code, venue_name)
                    if resp.status_code < 500 and resp.status_code != 429:
                        return None  # Don't retry client errors
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                logger.warning("BestTime API attempt %d failed for %s: %s", attempt + 1, venue_name, e)
                if attempt >= _MAX_RETRIES:
                    return None
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning("BestTime API unexpected error for %s: %s", venue_name, e)
                return None
        return None

    def _parse_forecast(self, data: dict) -> FootTrafficForecast | None:
        """Parse BestTime API response into FootTrafficForecast."""
        try:
            venue_info = data.get("venue_info", {})
            analysis = data.get("analysis", [])
            opening_hours_by_day = _extract_opening_hours_by_day(analysis)
            venue_category = _normalize_category(
                venue_info.get("venue_type"),
                venue_info.get("venue_types"),
            )

            day_raw = {}
            peak_hours = []
            quiet_hours = []
            surge_hours = []

            for day_data in analysis:
                day_info = day_data.get("day_info", {})
                day_text = day_info.get("day_text", "")
                if day_text:
                    # Capitalize first letter for consistency
                    day_text = day_text.capitalize()
                    if day_text in DAYS:
                        day_raw[day_text] = day_data.get("day_raw", [0] * 24)

                        # Collect peak hours
                        for peak in day_data.get("peak_hours", []):
                            peak_hours.append({
                                "day": day_text,
                                "start": peak.get("peak_start", 0),
                                "max": peak.get("peak_max", 0),
                                "end": peak.get("peak_end", 0),
                                "intensity": peak.get("peak_intensity", 0),
                            })

                        # Collect quiet hours
                        for qh in day_data.get("quiet_hours", []):
                            quiet_hours.append({"day": day_text, "hour": qh})

                        # Collect surge hours
                        sh = day_data.get("surge_hours", {})
                        if sh:
                            surge_hours.append({
                                "day": day_text,
                                "most_people_come": sh.get("most_people_come", 0),
                                "most_people_leave": sh.get("most_people_leave", 0),
                            })

            if not day_raw:
                return None

            return FootTrafficForecast(
                venue_id=venue_info.get("venue_id", ""),
                venue_name=venue_info.get("venue_name", ""),
                venue_category=venue_category,
                opening_hours_by_day=opening_hours_by_day,
                day_raw=day_raw,
                peak_hours=peak_hours,
                quiet_hours=quiet_hours,
                surge_hours=surge_hours,
                dwell_time_min=venue_info.get("venue_dwell_time_min", 0),
                dwell_time_max=venue_info.get("venue_dwell_time_max", 0),
                dwell_time_avg=venue_info.get("venue_dwell_time_avg", 0),
            )
        except Exception as e:
            logger.warning("Failed to parse BestTime forecast: %s", e)
            return None

    def _get_from_cache(self, venue_name: str, venue_address: str) -> FootTrafficForecast | None:
        """Check PostgreSQL cache for valid forecast."""
        try:
            from sqlalchemy import text

            from app.db import get_engine
            engine = get_engine()
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT forecast_data FROM besttime_cache "
                        "WHERE venue_name = :name AND venue_address = :addr "
                        "AND expires_at > NOW() "
                        "ORDER BY created_at DESC LIMIT 1"
                    ),
                    {"name": venue_name, "addr": venue_address},
                ).fetchone()
                if row:
                    data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                    return self._parse_forecast(data)
        except Exception as e:
            logger.warning("Cache lookup failed: %s", e)
        return None

    def _save_to_cache(self, forecast: FootTrafficForecast, venue_address: str, raw_data: dict) -> None:
        """Save forecast to PostgreSQL cache."""
        try:
            from sqlalchemy import text

            from app.db import get_engine
            engine = get_engine()
            now = datetime.now(timezone.utc)
            expires = now + timedelta(days=_CACHE_DAYS)
            with engine.connect() as conn:
                conn.execute(
                    text(
                        "INSERT INTO besttime_cache (venue_id, venue_name, venue_address, forecast_data, created_at, expires_at) "
                        "VALUES (:vid, :name, :addr, :data, :created, :expires) "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {
                        "vid": forecast.venue_id,
                        "name": forecast.venue_name,
                        "addr": venue_address,
                        "data": json.dumps(raw_data),
                        "created": now,
                        "expires": expires,
                    },
                )
                conn.commit()
        except Exception as e:
            logger.warning("Cache save failed: %s", e)
