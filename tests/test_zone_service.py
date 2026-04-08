"""Unit tests for ZoneService."""

import pytest

from app.services.zone_service import ZoneService


@pytest.fixture
def svc() -> ZoneService:
    return ZoneService()


class TestValidateZone:
    def test_known_zone_exact_case(self, svc: ZoneService):
        assert svc.validate_zone("Del Valle Centro") is True

    def test_known_zone_lowercase(self, svc: ZoneService):
        assert svc.validate_zone("del valle centro") is True

    def test_known_zone_uppercase(self, svc: ZoneService):
        assert svc.validate_zone("POLANCO") is True

    def test_unknown_zone(self, svc: ZoneService):
        assert svc.validate_zone("Atlantis") is False

    def test_empty_string(self, svc: ZoneService):
        assert svc.validate_zone("") is False

    def test_whitespace_only(self, svc: ZoneService):
        assert svc.validate_zone("   ") is False

    def test_leading_trailing_spaces(self, svc: ZoneService):
        assert svc.validate_zone("  Condesa  ") is True


class TestGetZone:
    def test_returns_zone_model(self, svc: ZoneService):
        zone = svc.get_zone("Condesa")
        assert zone is not None
        assert zone.name == "Condesa"
        assert len(zone.ageb_ids) > 0

    def test_case_insensitive(self, svc: ZoneService):
        zone = svc.get_zone("condesa")
        assert zone is not None
        assert zone.name == "Condesa"

    def test_not_found_returns_none(self, svc: ZoneService):
        assert svc.get_zone("Atlantis") is None

    def test_zone_has_bbox(self, svc: ZoneService):
        zone = svc.get_zone("Polanco")
        assert zone is not None
        assert zone.bbox.min_lat < zone.bbox.max_lat
        assert zone.bbox.min_lng < zone.bbox.max_lng


class TestSearchZones:
    def test_exact_match(self, svc: ZoneService):
        results = svc.search_zones("Roma Norte")
        names = [z.name for z in results]
        assert "Roma Norte" in names

    def test_partial_match(self, svc: ZoneService):
        results = svc.search_zones("roma")
        names = [z.name for z in results]
        assert "Roma Norte" in names
        assert "Roma Sur" in names

    def test_empty_query_returns_empty(self, svc: ZoneService):
        assert svc.search_zones("") == []

    def test_whitespace_query_returns_empty(self, svc: ZoneService):
        assert svc.search_zones("   ") == []

    def test_returns_zone_models(self, svc: ZoneService):
        results = svc.search_zones("Del Valle")
        assert all(hasattr(z, "ageb_ids") for z in results)


class TestSuggestSimilarZones:
    def test_typo_suggests_correct(self, svc: ZoneService):
        suggestions = svc.suggest_similar_zones("Polanko")
        assert "Polanco" in suggestions

    def test_partial_name_suggests(self, svc: ZoneService):
        suggestions = svc.suggest_similar_zones("del val")
        assert any("Del Valle" in s for s in suggestions)

    def test_empty_returns_empty(self, svc: ZoneService):
        assert svc.suggest_similar_zones("") == []

    def test_returns_strings(self, svc: ZoneService):
        suggestions = svc.suggest_similar_zones("narvar")
        assert all(isinstance(s, str) for s in suggestions)


class TestValidateInput:
    def test_both_empty(self, svc: ZoneService):
        valid, errors = svc.validate_input("", "")
        assert valid is False
        assert len(errors) == 2

    def test_business_empty(self, svc: ZoneService):
        valid, errors = svc.validate_input("", "Polanco")
        assert valid is False
        assert any("tipo de negocio" in e for e in errors)

    def test_zone_empty(self, svc: ZoneService):
        valid, errors = svc.validate_input("cafetería", "")
        assert valid is False
        assert any("zona es requerida" in e for e in errors)

    def test_zone_not_found_with_suggestions(self, svc: ZoneService):
        valid, errors = svc.validate_input("cafetería", "Polanko")
        assert valid is False
        assert any("no fue encontrada" in e for e in errors)
        assert any("Quisiste decir" in e for e in errors)

    def test_valid_input(self, svc: ZoneService):
        valid, errors = svc.validate_input("cafetería", "Polanco")
        assert valid is True
        assert errors == []

    def test_whitespace_business_type(self, svc: ZoneService):
        valid, errors = svc.validate_input("   ", "Polanco")
        assert valid is False
        assert any("tipo de negocio" in e for e in errors)

    def test_whitespace_zone(self, svc: ZoneService):
        valid, errors = svc.validate_input("cafetería", "   ")
        assert valid is False
        assert any("zona es requerida" in e for e in errors)
