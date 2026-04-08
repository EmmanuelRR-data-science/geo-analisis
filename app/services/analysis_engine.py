"""Viability analysis engine for the Business Viability Map application."""

from __future__ import annotations

import math

from app.models.schemas import AGEBData, ClassifiedBusiness, ViabilityResult


# Sigmoid parameters for competition factor
_SIGMOID_MIDPOINT = 5  # midpoint: ~5 competitors is "average"
_SIGMOID_K = 0.6       # steepness of the sigmoid curve

# Scaling factor for complementary businesses
_COMPLEMENTARY_SCALE = 15.0  # score of 100 at ~7 complementary businesses

# CDMX benchmarks for demographic normalization
_MAX_POPULATION_DENSITY = 25000.0  # people per km² (high-density CDMX benchmark)
_MAX_PEA = 50000                   # economically active population benchmark

# Socioeconomic level score mapping
_SOCIOECONOMIC_SCORES: dict[str, float] = {
    "Alto": 90.0,
    "Medio-Alto": 75.0,
    "Medio": 60.0,
    "Medio-Bajo": 40.0,
    "Bajo": 25.0,
}

# Weights (must sum to 1.0)
_W_COMPETITION = 0.30
_W_COMPLEMENTARY = 0.25
_W_DEMOGRAPHIC = 0.25
_W_SOCIOECONOMIC = 0.20


class AnalysisEngine:
    """Calculates business viability scores from classified businesses and AGEB data."""

    def calculate_viability(
        self,
        classified_businesses: list[ClassifiedBusiness],
        ageb_data: AGEBData,
    ) -> ViabilityResult:
        """Calculate a viability result from classified businesses and demographic data.

        Businesses with classification="unclassified" are excluded from the calculation.
        """
        # Filter out unclassified businesses
        relevant = [
            b for b in classified_businesses if b.classification != "unclassified"
        ]

        competitors = [b for b in relevant if b.classification == "competitor"]
        complementary = [b for b in relevant if b.classification == "complementary"]

        n_competitors = len(competitors)
        n_complementary = len(complementary)

        # Calculate individual factors (each 0-100)
        factor_competencia = self._competition_factor(n_competitors)
        factor_complementarios = self._complementary_factor(n_complementary)
        factor_demografico = self._demographic_factor(ageb_data)
        factor_socioeconomico = self._socioeconomic_factor(ageb_data)

        # Weighted sum
        raw_score = (
            _W_COMPETITION * factor_competencia
            + _W_COMPLEMENTARY * factor_complementarios
            + _W_DEMOGRAPHIC * factor_demografico
            + _W_SOCIOECONOMIC * factor_socioeconomico
        )

        # Clamp to [0, 100]
        score = max(0.0, min(100.0, raw_score))

        category = self._categorize(score)
        data_completeness = self._data_completeness(classified_businesses, ageb_data)

        return ViabilityResult(
            score=round(score, 2),
            category=category,
            factor_scores={
                "competencia": round(factor_competencia, 2),
                "complementarios": round(factor_complementarios, 2),
                "demografico": round(factor_demografico, 2),
                "socioeconomico": round(factor_socioeconomico, 2),
            },
            data_completeness=round(data_completeness, 2),
        )

    # ------------------------------------------------------------------
    # Factor calculations
    # ------------------------------------------------------------------

    @staticmethod
    def _competition_factor(n_competitors: int) -> float:
        """Inversely proportional to competitor count, normalized with sigmoid.

        Few competitors → high score, many competitors → low score.
        Uses: 100 * (1 / (1 + exp(k * (n - midpoint))))
        """
        return 100.0 * (1.0 / (1.0 + math.exp(_SIGMOID_K * (n_competitors - _SIGMOID_MIDPOINT))))

    @staticmethod
    def _complementary_factor(n_complementary: int) -> float:
        """Directly proportional to complementary business count.

        More complementary businesses → higher score, capped at 100.
        """
        return min(100.0, n_complementary * _COMPLEMENTARY_SCALE)

    @staticmethod
    def _demographic_factor(ageb_data: AGEBData) -> float:
        """Based on population density and PEA, normalized to 0-100."""
        density_score = min(100.0, (ageb_data.population_density / _MAX_POPULATION_DENSITY) * 100.0)
        pea_score = min(100.0, (ageb_data.economically_active_population / _MAX_PEA) * 100.0)
        # Equal weight between density and PEA
        return (density_score + pea_score) / 2.0

    @staticmethod
    def _socioeconomic_factor(ageb_data: AGEBData) -> float:
        """Map socioeconomic level string to a 0-100 score."""
        return _SOCIOECONOMIC_SCORES.get(ageb_data.socioeconomic_level, 50.0)

    # ------------------------------------------------------------------
    # Categorization
    # ------------------------------------------------------------------

    @staticmethod
    def _categorize(score: float) -> str:
        """Assign viability category based on score."""
        if score >= 70:
            return "Recomendable"
        if score >= 40:
            return "Viable con reservas"
        return "No recomendable"

    # ------------------------------------------------------------------
    # Data completeness
    # ------------------------------------------------------------------

    @staticmethod
    def _data_completeness(
        classified_businesses: list[ClassifiedBusiness],
        ageb_data: AGEBData,
    ) -> float:
        """Estimate how complete the input data is (0-1).

        Checks for:
        - presence of businesses (any source)
        - google-verified businesses
        - DENUE-enriched businesses
        - AGEB demographic data availability
        """
        sources_present = 0
        total_sources = 4

        # 1. Any businesses at all
        if classified_businesses:
            sources_present += 1

        # 2. Google-verified businesses
        if any(b.verified_google for b in classified_businesses):
            sources_present += 1

        # 3. DENUE-enriched businesses
        if any(b.denue_scian_code is not None for b in classified_businesses):
            sources_present += 1

        # 4. AGEB data available (non-zero population as proxy)
        if ageb_data.total_population > 0:
            sources_present += 1

        return sources_present / total_sources
