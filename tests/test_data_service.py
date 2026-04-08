"""Unit tests for data consolidation logic (fuzzy match + proximity)."""

from __future__ import annotations

import pytest

from app.models.schemas import (
    AGEBData,
    BoundingBox,
    Business,
    BusinessInterpretation,
    Zone,
)
from app.clients.denue_client import DENUEClient
from app.clients.google_places_client import GooglePlacesClient
from app.clients.overture_client import OvertureMapsClient
from app.services.data_service import (
    DataService,
    _is_match,
    consolidate_businesses,
    haversine_distance,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _biz(
    name: str,
    lat: float = 19.37,
    lng: float = -99.17,
    source: str = "google",
    verified_google: bool = True,
    **kwargs,
) -> Business:
    return Business(
        id="test-id",
        name=name,
        lat=lat,
        lng=lng,
        category="restaurant",
        source=source,
        verified_google=verified_google,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# haversine_distance
# ---------------------------------------------------------------------------

class TestHaversineDistance:
    def test_same_point_is_zero(self):
        assert haversine_distance(19.37, -99.17, 19.37, -99.17) == 0.0

    def test_known_distance(self):
        # ~111 km per degree of latitude at the equator
        dist = haversine_distance(0.0, 0.0, 1.0, 0.0)
        assert 110_000 < dist < 112_000

    def test_short_distance(self):
        # Two points ~30 m apart (approx 0.0003 degrees lat at CDMX latitude)
        dist = haversine_distance(19.3700, -99.1700, 19.37027, -99.1700)
        assert dist < 50


# ---------------------------------------------------------------------------
# _is_match
# ---------------------------------------------------------------------------

class TestIsMatch:
    def test_exact_name_close_location(self):
        a = _biz("Café Punta del Cielo", lat=19.3700, lng=-99.1700)
        b = _biz("Café Punta del Cielo", lat=19.37002, lng=-99.17001, source="denue")
        assert _is_match(a, b) is True

    def test_similar_name_close_location(self):
        a = _biz("Starbucks Coffee Roma", lat=19.3700, lng=-99.1700)
        b = _biz("STARBUCKS COFFEE ROMA", lat=19.37002, lng=-99.17001, source="denue")
        assert _is_match(a, b) is True

    def test_different_name_close_location(self):
        a = _biz("Café Punta del Cielo", lat=19.3700, lng=-99.1700)
        b = _biz("Oxxo Tienda", lat=19.37002, lng=-99.17001, source="denue")
        assert _is_match(a, b) is False

    def test_same_name_far_location(self):
        a = _biz("Starbucks", lat=19.3700, lng=-99.1700)
        b = _biz("Starbucks", lat=19.3800, lng=-99.1800, source="denue")
        assert _is_match(a, b) is False


# ---------------------------------------------------------------------------
# consolidate_businesses
# ---------------------------------------------------------------------------

class TestConsolidateBusinesses:
    def test_google_only(self):
        google = [_biz("Café A"), _biz("Café B")]
        result = consolidate_businesses(google, [], [])
        assert len(result) == 2
        assert all(b.verified_google for b in result)

    def test_denue_match_enriches_google(self):
        google = [_biz("Starbucks Coffee Roma", lat=19.3700, lng=-99.1700)]
        denue = [
            _biz(
                "STARBUCKS COFFEE ROMA",
                lat=19.37002,
                lng=-99.17001,
                source="denue",
                verified_google=False,
                denue_scian_code="722515",
                denue_employee_stratum="11 a 30",
                denue_registration_date="2015-01",
                denue_legal_name="STARBUCKS COFFEE ROMA",
                denue_address="Av Insurgentes 123",
            )
        ]
        result = consolidate_businesses(google, denue, [])
        assert len(result) == 1
        biz = result[0]
        assert biz.denue_scian_code == "722515"
        assert biz.denue_employee_stratum == "11 a 30"
        assert "denue" in biz.source
        assert "google" in biz.source
        assert biz.verified_google is True  # base was Google

    def test_unmatched_denue_added_as_not_verified(self):
        google = [_biz("Café A", lat=19.3700, lng=-99.1700)]
        denue = [
            _biz("Tienda Oxxo", lat=19.3800, lng=-99.1800, source="denue", verified_google=False)
        ]
        result = consolidate_businesses(google, denue, [])
        assert len(result) == 2
        oxxo = [b for b in result if "Oxxo" in b.name][0]
        assert oxxo.verified_google is False
        assert oxxo.source == "denue"

    def test_unmatched_overture_added_as_not_verified(self):
        google = [_biz("Café A", lat=19.3700, lng=-99.1700)]
        overture = [
            _biz("Farmacia Guadalajara", lat=19.3800, lng=-99.1800, source="overture", verified_google=False)
        ]
        result = consolidate_businesses(google, [], overture)
        assert len(result) == 2
        farmacia = [b for b in result if "Farmacia" in b.name][0]
        assert farmacia.verified_google is False
        assert farmacia.source == "overture"

    def test_overture_match_updates_source(self):
        google = [_biz("Café Punta del Cielo", lat=19.3700, lng=-99.1700)]
        overture = [
            _biz("Cafe Punta del Cielo", lat=19.37002, lng=-99.17001, source="overture", verified_google=False)
        ]
        result = consolidate_businesses(google, [], overture)
        assert len(result) == 1
        assert "overture" in result[0].source
        assert "google" in result[0].source

    def test_all_sources_empty(self):
        result = consolidate_businesses([], [], [])
        assert result == []

    def test_no_google_only_denue_and_overture(self):
        denue = [_biz("Tienda A", source="denue", verified_google=False)]
        overture = [_biz("Tienda B", lat=19.38, source="overture", verified_google=False)]
        result = consolidate_businesses([], denue, overture)
        assert len(result) == 2
        assert all(b.verified_google is False for b in result)


# ---------------------------------------------------------------------------
# DataService — graceful degradation
# ---------------------------------------------------------------------------

class TestDataServiceDegradation:
    """Test that DataService handles source failures gracefully."""

    @staticmethod
    def _make_zone() -> Zone:
        return Zone(
            name="Del Valle Centro",
            ageb_ids=["0901500010010"],
            center_lat=19.3718,
            center_lng=-99.1710,
            bbox=BoundingBox(
                min_lat=19.3680, min_lng=-99.1770,
                max_lat=19.3760, max_lng=-99.1650,
            ),
        )

    @staticmethod
    def _make_interpretation() -> BusinessInterpretation:
        return BusinessInterpretation(
            original_input="cafetería",
            scian_code="722515",
            scian_description="Cafeterías y similares",
            complementary_categories=[],
            competitor_categories=[],
            used_fallback=False,
        )

    @pytest.mark.asyncio
    async def test_google_failure_adds_warning(self):
        """When Google client raises, DataService catches it and adds a warning."""

        class FailingGoogle(GooglePlacesClient):
            async def search_nearby(self, *a, **kw):
                raise RuntimeError("API down")

        svc = DataService(google_client=FailingGoogle())
        businesses, warnings = await svc.get_businesses_in_zone(
            self._make_zone(), self._make_interpretation()
        )
        assert any("Google" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_denue_failure_adds_warning(self):
        """When DENUE client raises, DataService catches it and adds a warning."""

        class FailingDenue(DENUEClient):
            async def search_businesses(self, *a, **kw):
                raise RuntimeError("API down")

        svc = DataService(denue_client=FailingDenue())
        businesses, warnings = await svc.get_businesses_in_zone(
            self._make_zone(), self._make_interpretation()
        )
        assert any("DENUE" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_overture_failure_adds_warning(self):
        """When Overture client raises, DataService catches it and adds a warning."""

        class FailingOverture(OvertureMapsClient):
            async def get_places(self, *a, **kw):
                raise RuntimeError("API down")

        svc = DataService(overture_client=FailingOverture())
        businesses, warnings = await svc.get_businesses_in_zone(
            self._make_zone(), self._make_interpretation()
        )
        assert any("Overture" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_all_sources_fail_returns_empty_with_warnings(self):
        """When all sources fail, return empty list with all warnings."""

        class FailGoogle(GooglePlacesClient):
            async def search_nearby(self, *a, **kw):
                raise RuntimeError("down")

        class FailDenue(DENUEClient):
            async def search_businesses(self, *a, **kw):
                raise RuntimeError("down")

        class FailOverture(OvertureMapsClient):
            async def get_places(self, *a, **kw):
                raise RuntimeError("down")

        svc = DataService(
            google_client=FailGoogle(),
            denue_client=FailDenue(),
            overture_client=FailOverture(),
        )
        businesses, warnings = await svc.get_businesses_in_zone(
            self._make_zone(), self._make_interpretation()
        )
        assert businesses == []
        assert len(warnings) >= 3

    @pytest.mark.asyncio
    async def test_google_down_denue_overture_available(self):
        """When Google is down but DENUE+Overture work, analysis continues with warning."""

        class FailGoogle(GooglePlacesClient):
            async def search_nearby(self, *a, **kw):
                raise RuntimeError("down")

        class StubDenue(DENUEClient):
            async def search_businesses(self, *a, **kw):
                return [
                    Business(
                        id="d1", name="Tienda DENUE", lat=19.37, lng=-99.17,
                        category="tienda", source="denue", verified_google=False,
                    )
                ]

        class StubOverture(OvertureMapsClient):
            async def get_places(self, *a, **kw):
                return [
                    Business(
                        id="o1", name="Tienda Overture", lat=19.38, lng=-99.18,
                        category="tienda", source="overture", verified_google=False,
                    )
                ]

        svc = DataService(
            google_client=FailGoogle(),
            denue_client=StubDenue(),
            overture_client=StubOverture(),
        )
        businesses, warnings = await svc.get_businesses_in_zone(
            self._make_zone(), self._make_interpretation()
        )
        assert len(businesses) == 2
        assert all(b.verified_google is False for b in businesses)
        assert any("Google Places no disponible" in w for w in warnings)
