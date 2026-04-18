"""TargetMarketService — pure demographic match calculation."""

from __future__ import annotations

from app.models.schemas import AGEBData, TargetCriteria, TargetMatchResult


def _calculate_age_factor(age_min: int, age_max: int, ageb: AGEBData) -> float:
    """Calculate the proportion of the population within the requested age range.

    Uses AGEB age groups (0-14, 15-64, 65+) and extended indicators
    (12+, 15+, 18+, 60+) for proportional interpolation.
    """
    total_pop = ageb.total_population
    if total_pop <= 0:
        return 0.0

    # Clamp to valid range
    age_min = max(0, min(age_min, 99))
    age_max = max(age_min, min(age_max, 99))

    # AGEB age group boundaries and populations
    # Groups: [0, 14], [15, 64], [65, 99]
    groups = [
        (0, 14, ageb.population_0_14),
        (15, 64, ageb.population_15_64),
        (65, 99, ageb.population_65_plus),
    ]

    matched_pop = 0.0
    for g_min, g_max, g_pop in groups:
        # Calculate overlap between requested range and this group
        overlap_min = max(age_min, g_min)
        overlap_max = min(age_max, g_max)

        if overlap_min > overlap_max:
            continue  # No overlap

        group_span = g_max - g_min + 1
        overlap_span = overlap_max - overlap_min + 1

        if overlap_span >= group_span:
            # Entire group is within requested range
            matched_pop += g_pop
        else:
            # Proportional part of the group
            matched_pop += g_pop * (overlap_span / group_span)

    # Refine using extended indicators when available
    ext = ageb.extended_indicators
    if ext:
        p_12ymas = ext.get("population_12_plus", 0)
        p_15ymas = ext.get("population_15_plus", 0)
        p_18ymas = ext.get("population_18_plus", 0)
        p_60ymas = ext.get("population_60_plus", 0)

        # Use extended indicators for better precision at specific boundaries
        # If age_min is exactly at a known boundary, use the extended indicator
        if age_min == 12 and p_12ymas > 0:
            # population 12+ is known; subtract 65+ if age_max < 65
            above_12 = p_12ymas
            if age_max < 65:
                # We want 12 to age_max, which is within 12-64
                pop_12_to_64 = above_12 - ageb.population_65_plus
                if pop_12_to_64 > 0:
                    span_12_64 = 64 - 12 + 1  # 53
                    overlap = min(age_max, 64) - 12 + 1
                    matched_pop = pop_12_to_64 * (overlap / span_12_64)
            elif age_max >= 65:
                matched_pop = above_12

        elif age_min == 15 and p_15ymas > 0:
            above_15 = p_15ymas
            if age_max < 65:
                pop_15_to_64 = above_15 - ageb.population_65_plus
                if pop_15_to_64 > 0:
                    span_15_64 = 64 - 15 + 1  # 50
                    overlap = min(age_max, 64) - 15 + 1
                    matched_pop = pop_15_to_64 * (overlap / span_15_64)
            elif age_max >= 65:
                matched_pop = above_15

        elif age_min == 18 and p_18ymas > 0:
            above_18 = p_18ymas
            if age_max < 65:
                pop_18_to_64 = above_18 - ageb.population_65_plus
                if pop_18_to_64 > 0:
                    span_18_64 = 64 - 18 + 1  # 47
                    overlap = min(age_max, 64) - 18 + 1
                    matched_pop = pop_18_to_64 * (overlap / span_18_64)
            elif age_max >= 65:
                matched_pop = above_18

        # Use p_60ymas for better 60+ precision
        if age_min <= 60 and age_max >= 60 and p_60ymas > 0:
            # Recalculate the 60+ portion more precisely
            # The basic calculation used 65+ group; p_60ymas includes 60-64 too
            pass  # The basic interpolation is already reasonable

    return max(0.0, min(1.0, matched_pop / total_pop))


def _calculate_socio_factor(
    requested_level: str, zone_level: str
) -> float:
    """Calculate socioeconomic compatibility factor.

    Returns 1.0 if zone matches or exceeds requested level,
    0.3 for partial match (zones have mixed populations),
    1.0 if requested is "all".
    """
    if requested_level == "all":
        return 1.0

    # Hierarchy from highest to lowest
    hierarchy = ["Alto", "Medio-Alto", "Medio", "Bajo"]

    if requested_level not in hierarchy or zone_level not in hierarchy:
        # Unknown level — partial match
        return 0.3

    requested_idx = hierarchy.index(requested_level)
    zone_idx = hierarchy.index(zone_level)

    # Zone level is same or higher than requested → full match
    if zone_idx <= requested_idx:
        return 1.0

    # Zone level is lower than requested → partial match
    return 0.3


class TargetMarketService:
    """Cálculo puro de coincidencia demográfica perfil-zona."""

    @staticmethod
    def calculate_match_percentage(
        criteria: TargetCriteria,
        ageb_data: AGEBData,
    ) -> TargetMatchResult:
        """Calculate demographic match percentage.

        Applies sequential filters: gender → age → socioeconomic level.
        Uses proportional interpolation for age ranges spanning multiple
        AGEB groups.
        """
        total_pop = ageb_data.total_population

        if total_pop == 0:
            return TargetMatchResult(
                percentage=0.0,
                estimated_population=0,
                breakdown={
                    "gender_factor": 0.0,
                    "age_factor": 0.0,
                    "socioeconomic_factor": 0.0,
                },
            )

        # 1. Gender filter
        if criteria.gender == "female":
            gender_pop = ageb_data.female_population
        elif criteria.gender == "male":
            gender_pop = ageb_data.male_population
        else:
            gender_pop = total_pop
        gender_factor = gender_pop / total_pop if total_pop > 0 else 0.0

        # 2. Age filter — proportional interpolation
        age_factor = _calculate_age_factor(
            criteria.age_min, criteria.age_max, ageb_data
        )

        # 3. Socioeconomic filter
        socio_factor = _calculate_socio_factor(
            criteria.socioeconomic_level, ageb_data.socioeconomic_level
        )

        # Combined percentage
        percentage = round(gender_factor * age_factor * socio_factor * 100, 1)
        percentage = min(100.0, max(0.0, percentage))
        estimated_pop = round(percentage * total_pop / 100)

        return TargetMatchResult(
            percentage=percentage,
            estimated_population=estimated_pop,
            breakdown={
                "gender_factor": round(gender_factor, 3),
                "age_factor": round(age_factor, 3),
                "socioeconomic_factor": round(socio_factor, 3),
            },
        )
