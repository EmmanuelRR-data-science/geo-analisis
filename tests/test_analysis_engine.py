"""Unit tests for the AnalysisEngine."""

import pytest

from app.models.schemas import AGEBData, ClassifiedBusiness, ViabilityResult
from app.services.analysis_engine import AnalysisEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_business(**overrides) -> ClassifiedBusiness:
    defaults = {
        "id": "b1",
        "name": "Test Biz",
        "lat": 19.4,
        "lng": -99.1,
        "category": "restaurant",
        "source": "google",
        "verified_google": True,
        "classification": "complementary",
        "relevance": "high",
    }
    defaults.update(overrides)
    return ClassifiedBusiness(**defaults)


def _make_ageb(**overrides) -> AGEBData:
    defaults = {
        "total_population": 10000,
        "population_density": 8000.0,
        "economically_active_population": 5000,
        "socioeconomic_level": "Medio",
        "ageb_count": 3,
        "raw_indicators": {},
    }
    defaults.update(overrides)
    return AGEBData(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScoreRange:
    """Score is always in [0, 100]."""

    def test_score_with_typical_data(self):
        engine = AnalysisEngine()
        businesses = [_make_business(classification="competitor", id=f"c{i}") for i in range(3)]
        businesses += [_make_business(classification="complementary", id=f"p{i}") for i in range(4)]
        result = engine.calculate_viability(businesses, _make_ageb())
        assert 0 <= result.score <= 100

    def test_score_with_no_businesses(self):
        engine = AnalysisEngine()
        result = engine.calculate_viability([], _make_ageb())
        assert 0 <= result.score <= 100

    def test_score_with_many_competitors(self):
        engine = AnalysisEngine()
        businesses = [_make_business(classification="competitor", id=f"c{i}") for i in range(50)]
        result = engine.calculate_viability(businesses, _make_ageb())
        assert 0 <= result.score <= 100

    def test_score_with_many_complementary(self):
        engine = AnalysisEngine()
        businesses = [_make_business(classification="complementary", id=f"p{i}") for i in range(50)]
        result = engine.calculate_viability(businesses, _make_ageb())
        assert 0 <= result.score <= 100


class TestUnclassifiedExclusion:
    """Unclassified businesses are excluded from the calculation."""

    def test_unclassified_ignored(self):
        engine = AnalysisEngine()
        ageb = _make_ageb()

        only_classified = [
            _make_business(classification="competitor", id="c1"),
            _make_business(classification="complementary", id="p1"),
        ]
        with_unclassified = only_classified + [
            _make_business(classification="unclassified", id="u1"),
            _make_business(classification="unclassified", id="u2"),
        ]

        r1 = engine.calculate_viability(only_classified, ageb)
        r2 = engine.calculate_viability(with_unclassified, ageb)
        assert r1.score == r2.score

    def test_all_unclassified_same_as_empty(self):
        engine = AnalysisEngine()
        ageb = _make_ageb()
        all_unclassified = [_make_business(classification="unclassified", id=f"u{i}") for i in range(5)]
        r_empty = engine.calculate_viability([], ageb)
        r_unclassified = engine.calculate_viability(all_unclassified, ageb)
        assert r_empty.score == r_unclassified.score


class TestFactorInfluence:
    """Each factor influences the score."""

    def test_more_competitors_lower_score(self):
        engine = AnalysisEngine()
        ageb = _make_ageb()
        few = [_make_business(classification="competitor", id=f"c{i}") for i in range(1)]
        many = [_make_business(classification="competitor", id=f"c{i}") for i in range(20)]
        r_few = engine.calculate_viability(few, ageb)
        r_many = engine.calculate_viability(many, ageb)
        assert r_few.score > r_many.score

    def test_more_complementary_higher_score(self):
        engine = AnalysisEngine()
        ageb = _make_ageb()
        few = [_make_business(classification="complementary", id=f"p{i}") for i in range(1)]
        many = [_make_business(classification="complementary", id=f"p{i}") for i in range(6)]
        r_few = engine.calculate_viability(few, ageb)
        r_many = engine.calculate_viability(many, ageb)
        assert r_many.score > r_few.score

    def test_higher_density_higher_score(self):
        engine = AnalysisEngine()
        businesses = [_make_business(classification="competitor", id="c1")]
        low = _make_ageb(population_density=1000.0)
        high = _make_ageb(population_density=20000.0)
        r_low = engine.calculate_viability(businesses, low)
        r_high = engine.calculate_viability(businesses, high)
        assert r_high.score > r_low.score

    def test_socioeconomic_level_affects_score(self):
        engine = AnalysisEngine()
        businesses = [_make_business(classification="competitor", id="c1")]
        low = _make_ageb(socioeconomic_level="Bajo")
        high = _make_ageb(socioeconomic_level="Alto")
        r_low = engine.calculate_viability(businesses, low)
        r_high = engine.calculate_viability(businesses, high)
        assert r_high.score > r_low.score


class TestCategorization:
    """Category matches score range."""

    def test_recomendable(self):
        engine = AnalysisEngine()
        # Many complementary, no competitors, high density, high socioeconomic
        businesses = [_make_business(classification="complementary", id=f"p{i}") for i in range(7)]
        ageb = _make_ageb(population_density=20000.0, economically_active_population=40000, socioeconomic_level="Alto")
        result = engine.calculate_viability(businesses, ageb)
        assert result.category == "Recomendable"
        assert result.score >= 70

    def test_no_recomendable(self):
        engine = AnalysisEngine()
        # Many competitors, no complementary, low density, low socioeconomic
        businesses = [_make_business(classification="competitor", id=f"c{i}") for i in range(30)]
        ageb = _make_ageb(population_density=500.0, economically_active_population=200, socioeconomic_level="Bajo")
        result = engine.calculate_viability(businesses, ageb)
        assert result.category == "No recomendable"
        assert result.score < 40

    def test_category_consistency(self):
        """Category always matches the score range."""
        engine = AnalysisEngine()
        ageb = _make_ageb()
        for n_comp in range(0, 15, 3):
            for n_compl in range(0, 10, 2):
                biz = (
                    [_make_business(classification="competitor", id=f"c{i}") for i in range(n_comp)]
                    + [_make_business(classification="complementary", id=f"p{i}") for i in range(n_compl)]
                )
                result = engine.calculate_viability(biz, ageb)
                if result.score >= 70:
                    assert result.category == "Recomendable"
                elif result.score >= 40:
                    assert result.category == "Viable con reservas"
                else:
                    assert result.category == "No recomendable"


class TestEdgeCases:
    """Edge cases: no businesses, no AGEB data."""

    def test_empty_businesses(self):
        engine = AnalysisEngine()
        result = engine.calculate_viability([], _make_ageb())
        assert isinstance(result, ViabilityResult)
        assert 0 <= result.score <= 100

    def test_zero_population_ageb(self):
        engine = AnalysisEngine()
        ageb = _make_ageb(total_population=0, population_density=0.0, economically_active_population=0)
        result = engine.calculate_viability([], ageb)
        assert 0 <= result.score <= 100

    def test_unknown_socioeconomic_level(self):
        engine = AnalysisEngine()
        ageb = _make_ageb(socioeconomic_level="Desconocido")
        result = engine.calculate_viability([], ageb)
        # Should use default score (50) for unknown level
        assert 0 <= result.score <= 100


class TestDataCompleteness:
    """data_completeness reflects available sources."""

    def test_full_data(self):
        engine = AnalysisEngine()
        businesses = [
            _make_business(verified_google=True, denue_scian_code="461110", id="b1"),
        ]
        ageb = _make_ageb(total_population=10000)
        result = engine.calculate_viability(businesses, ageb)
        assert result.data_completeness == 1.0

    def test_no_businesses(self):
        engine = AnalysisEngine()
        result = engine.calculate_viability([], _make_ageb(total_population=10000))
        # No businesses → missing 3 of 4 sources
        assert result.data_completeness == 0.25

    def test_no_google_no_denue(self):
        engine = AnalysisEngine()
        businesses = [
            _make_business(verified_google=False, denue_scian_code=None, id="b1"),
        ]
        ageb = _make_ageb(total_population=10000)
        result = engine.calculate_viability(businesses, ageb)
        # Has businesses + AGEB, but no google verified and no DENUE
        assert result.data_completeness == 0.5

    def test_zero_population(self):
        engine = AnalysisEngine()
        businesses = [
            _make_business(verified_google=True, denue_scian_code="461110", id="b1"),
        ]
        ageb = _make_ageb(total_population=0)
        result = engine.calculate_viability(businesses, ageb)
        # Has businesses + google + denue, but no AGEB population
        assert result.data_completeness == 0.75
