"""Foot traffic service — orchestrates BestTime data and builds zone profiles."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.clients.besttime_client import DAYS, BestTimeClient
from app.models.schemas import FootTrafficForecast, ZoneTrafficProfile

if TYPE_CHECKING:
    from app.models.schemas import ClassifiedBusiness

logger = logging.getLogger(__name__)


def _index_to_hour(i: int) -> int:
    """Convert BestTime day_raw index (0=6AM) to hour of day (0-23)."""
    return (i + 6) % 24


class FootTrafficService:
    """Service for fetching and aggregating foot traffic data."""

    def __init__(self) -> None:
        self._client = BestTimeClient()

    async def get_zone_traffic_profile(
        self,
        competitors: list[ClassifiedBusiness],
        zone_name: str,
        max_venues: int = 10,
    ) -> tuple[ZoneTrafficProfile | None, list[str]]:
        """Get forecasts and build zone traffic profile."""
        warnings: list[str] = []

        if not competitors:
            return None, warnings

        # Limit to max_venues
        selected = competitors[:max_venues]

        # Build venue list
        venues = []
        for c in selected:
            addr = self._build_venue_address(c, zone_name)
            venues.append({"name": c.name, "address": addr})

        # Fetch forecasts
        forecasts_raw = await self._client.get_forecasts_batch(venues)
        forecasts = []
        for idx, forecast in enumerate(forecasts_raw):
            if forecast is None:
                continue
            if not forecast.venue_category and idx < len(selected):
                forecast.venue_category = selected[idx].category
            forecasts.append(forecast)

        if not forecasts:
            warnings.append("No se pudieron obtener datos de tráfico peatonal. El análisis continúa sin esta información.")
            return None, warnings

        if len(forecasts) < len(selected):
            warnings.append(
                f"Se obtuvieron datos de tráfico para {len(forecasts)} de {len(selected)} competidores."
            )

        profile = self.build_zone_profile(forecasts, len(selected))
        return profile, warnings

    @staticmethod
    def build_zone_profile(
        forecasts: list[FootTrafficForecast],
        total_competitors: int,
    ) -> ZoneTrafficProfile:
        """Aggregate individual forecasts into a zone profile."""
        # Average day_raw hour by hour, day by day
        hourly_matrix: dict[str, list[float]] = {}
        for day in DAYS:
            day_values: list[list[int]] = []
            for f in forecasts:
                if day in f.day_raw and len(f.day_raw[day]) == 24:
                    day_values.append(f.day_raw[day])

            if day_values:
                avg = [
                    round(sum(vals[h] for vals in day_values) / len(day_values), 1)
                    for h in range(24)
                ]
            else:
                avg = [0.0] * 24
            hourly_matrix[day] = avg

        # Peak hours by day (top 3 hours with highest values)
        peak_hours_by_day: dict[str, list[int]] = {}
        quiet_hours_by_day: dict[str, list[int]] = {}

        for day, hours in hourly_matrix.items():
            indexed = [(i, v) for i, v in enumerate(hours)]
            # Sort by value descending for peaks
            sorted_desc = sorted(indexed, key=lambda x: x[1], reverse=True)
            peak_hours_by_day[day] = [_index_to_hour(i) for i, v in sorted_desc[:3]]

            # Quiet hours: top 3 lowest non-zero values
            non_zero = [(i, v) for i, v in indexed if v > 0]
            sorted_asc = sorted(non_zero, key=lambda x: x[1])
            quiet_hours_by_day[day] = [_index_to_hour(i) for i, v in sorted_asc[:3]]

        # Busiest and quietest day
        day_sums = {day: sum(hours) for day, hours in hourly_matrix.items()}
        busiest_day = max(day_sums, key=day_sums.get) if day_sums else "Monday"
        quietest_day = min(day_sums, key=day_sums.get) if day_sums else "Sunday"

        # Average dwell time
        dwell_times = [f.dwell_time_avg for f in forecasts if f.dwell_time_avg > 0]
        avg_dwell = round(sum(dwell_times) / len(dwell_times), 1) if dwell_times else 0.0

        source_venues = []
        for f in forecasts:
            source_venues.append(
                {
                    "venue_name": f.venue_name,
                    "venue_category": f.venue_category,
                    "opening_hours_by_day": f.opening_hours_by_day or {},
                }
            )

        return ZoneTrafficProfile(
            hourly_matrix=hourly_matrix,
            peak_hours_by_day=peak_hours_by_day,
            quiet_hours_by_day=quiet_hours_by_day,
            busiest_day=busiest_day,
            quietest_day=quietest_day,
            avg_dwell_time_minutes=avg_dwell,
            venues_with_data=len(forecasts),
            venues_total=total_competitors,
            source_venues=source_venues,
        )

    @staticmethod
    def _build_venue_address(competitor, zone_name: str) -> str:
        """Build venue address for BestTime lookup."""
        if competitor.denue_address:
            return f"{competitor.denue_address}, Ciudad de México, México"
        # Fallback: use coordinates + zone name
        return f"{competitor.name}, {zone_name}, Ciudad de México, México"
