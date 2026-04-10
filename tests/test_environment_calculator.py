"""Unit tests for EnvironmentCalculator."""

import math

from app.models.schemas import ClassifiedBusiness
from app.services.environment_calculator import EnvironmentCalculator


def _make_business(
    *,
    verified_google: bool = False,
    scian_code: str | None = None,
    classification: str = "competitor",
) -> ClassifiedBusiness:
    """Helper to create a minimal ClassifiedBusiness."""
    return ClassifiedBusiness(
        id="test-1",
        name="Test Business",
        lat=19.4,
        lng=-99.1,
        category="test",
        source="denue",
        verified_google=verified_google,
        denue_scian_code=scian_code,
        classification=classification,
        relevance="high",
    )


class TestCalculatePoiDensity:
    def test_basic_calculation(self):
        result = EnvironmentCalculator.calculate_poi_density(10, 1.0)
        expected = round(10 / (math.pi * 1.0**2), 2)
        assert result == expected

    def test_larger_radius(self):
        result = EnvironmentCalculator.calculate_poi_density(50, 3.0)
        expected = round(50 / (math.pi * 9.0), 2)
        assert result == expected

    def test_zero_radius_returns_zero(self):
        assert EnvironmentCalculator.calculate_poi_density(10, 0) == 0.0

    def test_negative_radius_returns_zero(self):
        assert EnvironmentCalculator.calculate_poi_density(10, -1.0) == 0.0

    def test_zero_businesses_returns_zero(self):
        assert EnvironmentCalculator.calculate_poi_density(0, 1.0) == 0.0

    def test_negative_businesses_returns_zero(self):
        assert EnvironmentCalculator.calculate_poi_density(-5, 1.0) == 0.0


class TestCalculateCommercialActivityIndex:
    def test_all_verified(self):
        businesses = [_make_business(verified_google=True) for _ in range(5)]
        assert EnvironmentCalculator.calculate_commercial_activity_index(businesses) == 100.0

    def test_none_verified(self):
        businesses = [_make_business(verified_google=False) for _ in range(5)]
        assert EnvironmentCalculator.calculate_commercial_activity_index(businesses) == 0.0

    def test_partial_verified(self):
        businesses = [
            _make_business(verified_google=True),
            _make_business(verified_google=False),
            _make_business(verified_google=True),
            _make_business(verified_google=False),
        ]
        assert EnvironmentCalculator.calculate_commercial_activity_index(businesses) == 50.0

    def test_empty_list(self):
        assert EnvironmentCalculator.calculate_commercial_activity_index([]) == 0.0


class TestCalculateSectorConcentration:
    def test_single_sector(self):
        businesses = [_make_business(scian_code="461110") for _ in range(3)]
        result = EnvironmentCalculator.calculate_sector_concentration(businesses)
        assert len(result) == 1
        assert result[0]["code_2d"] == "46"
        assert result[0]["count"] == 3
        assert result[0]["percentage"] == 100.0

    def test_multiple_sectors(self):
        businesses = [
            _make_business(scian_code="461110"),
            _make_business(scian_code="461121"),
            _make_business(scian_code="722511"),
        ]
        result = EnvironmentCalculator.calculate_sector_concentration(businesses)
        assert len(result) == 2
        # Sorted by count descending
        assert result[0]["code_2d"] == "46"
        assert result[0]["count"] == 2
        assert result[1]["code_2d"] == "72"
        assert result[1]["count"] == 1

    def test_no_scian_codes(self):
        businesses = [_make_business(scian_code=None) for _ in range(3)]
        assert EnvironmentCalculator.calculate_sector_concentration(businesses) == []

    def test_empty_list(self):
        assert EnvironmentCalculator.calculate_sector_concentration([]) == []

    def test_skips_businesses_without_scian(self):
        businesses = [
            _make_business(scian_code="461110"),
            _make_business(scian_code=None),
        ]
        result = EnvironmentCalculator.calculate_sector_concentration(businesses)
        assert len(result) == 1
        assert result[0]["count"] == 1
        assert result[0]["percentage"] == 100.0

    def test_sorted_by_count_descending(self):
        businesses = [
            _make_business(scian_code="722511"),
            _make_business(scian_code="461110"),
            _make_business(scian_code="461121"),
            _make_business(scian_code="461130"),
        ]
        result = EnvironmentCalculator.calculate_sector_concentration(businesses)
        assert result[0]["code_2d"] == "46"
        assert result[0]["count"] == 3
        assert result[1]["code_2d"] == "72"
        assert result[1]["count"] == 1


class TestCalculateAll:
    def test_returns_all_keys(self):
        businesses = [
            _make_business(verified_google=True, scian_code="461110"),
            _make_business(verified_google=False, scian_code="722511"),
        ]
        result = EnvironmentCalculator.calculate_all(businesses, 1.0)
        assert "poi_density" in result
        assert "commercial_activity_index" in result
        assert "sector_concentration" in result

    def test_values_match_individual_methods(self):
        businesses = [
            _make_business(verified_google=True, scian_code="461110"),
            _make_business(verified_google=False, scian_code="722511"),
        ]
        radius = 3.0
        result = EnvironmentCalculator.calculate_all(businesses, radius)
        assert result["poi_density"] == EnvironmentCalculator.calculate_poi_density(2, radius)
        assert result["commercial_activity_index"] == EnvironmentCalculator.calculate_commercial_activity_index(businesses)
        assert result["sector_concentration"] == EnvironmentCalculator.calculate_sector_concentration(businesses)

    def test_empty_businesses(self):
        result = EnvironmentCalculator.calculate_all([], 1.0)
        assert result["poi_density"] == 0.0
        assert result["commercial_activity_index"] == 0.0
        assert result["sector_concentration"] == []
