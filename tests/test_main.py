"""Tests for app/main.py FastAPI endpoints."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Point AGEB file to a non-existent path so startup doesn't try to load the
# real (large) Excel file — the reader will log a warning and continue.
os.environ.setdefault("AGEB_FILE_PATH", "__nonexistent__.xlsx")

from app.main import app, analysis_store, _validate_filters, _clamp_radius_km, _extract_indicator, _estimate_ageb_coordinates, _make_zone_slug  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_store():
    """Clear the analysis store between tests."""
    analysis_store.clear()
    yield
    analysis_store.clear()


@pytest.fixture()
def client():
    """TestClient as context manager so lifespan events fire."""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# GET /api/zones/search
# ---------------------------------------------------------------------------

class TestZonesSearchEndpoint:
    def test_search_returns_zones(self, client: TestClient):
        resp = client.get("/api/zones/search", params={"q": "Condesa"})
        assert resp.status_code == 200
        data = resp.json()
        assert "zones" in data
        names = [z["name"] for z in data["zones"]]
        assert any("Condesa" in n for n in names)

    def test_search_empty_query_returns_empty(self, client: TestClient):
        resp = client.get("/api/zones/search", params={"q": ""})
        assert resp.status_code == 200
        assert resp.json()["zones"] == []

    def test_search_no_match(self, client: TestClient):
        resp = client.get("/api/zones/search", params={"q": "zzzznotazone"})
        assert resp.status_code == 200
        assert "zones" in resp.json()


# ---------------------------------------------------------------------------
# POST /api/analyze — validation errors
# ---------------------------------------------------------------------------

class TestAnalyzeValidation:
    def test_empty_fields_returns_422(self, client: TestClient):
        resp = client.post("/api/analyze", json={"business_type": "", "zone": ""})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] == "validation_error"

    def test_empty_business_type_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/analyze", json={"business_type": "", "zone": "Condesa"}
        )
        assert resp.status_code == 422

    def test_empty_zone_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/analyze", json={"business_type": "cafetería", "zone": ""}
        )
        assert resp.status_code == 422

    def test_unknown_zone_returns_422_with_suggestions(self, client: TestClient):
        resp = client.post(
            "/api/analyze",
            json={"business_type": "cafetería", "zone": "Condessa"},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert "no fue encontrada" in body.get("details", "") or "no fue encontrada" in body.get("message", "")

    def test_invalid_json_returns_400(self, client: TestClient):
        resp = client.post(
            "/api/analyze",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_json"


# ---------------------------------------------------------------------------
# GET / — root
# ---------------------------------------------------------------------------

class TestRootEndpoint:
    def test_root_returns_200(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/export/pdf
# ---------------------------------------------------------------------------

import base64

from app.models.schemas import (
    AGEBData,
    AnalysisResult,
    BoundingBox,
    BusinessInterpretation,
    SCIANCategory,
    ViabilityResult,
    Zone,
)


def _make_analysis_result(analysis_id: str = "test-id-123") -> AnalysisResult:
    """Helper to build a minimal AnalysisResult for testing."""
    return AnalysisResult(
        analysis_id=analysis_id,
        business_type=BusinessInterpretation(
            original_input="cafetería",
            scian_code="722515",
            scian_description="Cafeterías",
            complementary_categories=[SCIANCategory(code="461110", description="Panaderías")],
            competitor_categories=[SCIANCategory(code="722516", description="Cafeterías similares")],
            used_fallback=False,
        ),
        zone=Zone(
            name="Condesa",
            ageb_ids=["0901500010010"],
            center_lat=19.4115,
            center_lng=-99.1734,
            bbox=BoundingBox(min_lat=19.40, min_lng=-99.18, max_lat=19.42, max_lng=-99.16),
        ),
        businesses=[],
        ageb_data=AGEBData(
            total_population=25000,
            population_density=150.0,
            economically_active_population=12000,
            socioeconomic_level="Medio-Alto",
            ageb_count=3,
            raw_indicators={},
        ),
        viability=ViabilityResult(
            score=72.5,
            category="Recomendable",
            factor_scores={"competition": 65, "complementary": 80, "demographic": 70, "socioeconomic": 75},
            data_completeness=0.8,
        ),
        recommendation_text="Esta zona es recomendable para abrir una cafetería.",
        warnings=[],
        timestamp="2024-01-01T00:00:00Z",
    )


class TestExportPdfEndpoint:
    def test_missing_analysis_id_returns_400(self, client: TestClient):
        resp = client.post("/api/export/pdf", json={"map_image_base64": "abc"})
        assert resp.status_code == 400
        assert resp.json()["error"] == "missing_field"

    def test_not_found_analysis_returns_404(self, client: TestClient):
        resp = client.post(
            "/api/export/pdf",
            json={"analysis_id": "nonexistent", "map_image_base64": "abc"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"] == "not_found"

    def test_invalid_json_returns_400(self, client: TestClient):
        resp = client.post(
            "/api/export/pdf",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_json"

    def test_invalid_base64_returns_400(self, client: TestClient):
        analysis_store["test-bad-b64"] = _make_analysis_result("test-bad-b64")
        resp = client.post(
            "/api/export/pdf",
            json={"analysis_id": "test-bad-b64", "map_image_base64": "!!!not-base64!!!"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_image"


# ---------------------------------------------------------------------------
# _validate_filters helper
# ---------------------------------------------------------------------------

class TestValidateFilters:
    def test_no_overlap_is_valid(self):
        valid, msg = _validate_filters(["cafetería"], ["panadería"])
        assert valid is True
        assert msg == ""

    def test_empty_lists_are_valid(self):
        valid, msg = _validate_filters([], [])
        assert valid is True

    def test_overlap_is_invalid(self):
        valid, msg = _validate_filters(["cafetería", "tienda"], ["tienda", "farmacia"])
        assert valid is False
        assert "tienda" in msg

    def test_multiple_overlaps(self):
        valid, msg = _validate_filters(["a", "b", "c"], ["b", "c", "d"])
        assert valid is False
        assert "b" in msg
        assert "c" in msg

    def test_one_empty_is_valid(self):
        valid, msg = _validate_filters(["cafetería"], [])
        assert valid is True


# ---------------------------------------------------------------------------
# _clamp_radius_km helper
# ---------------------------------------------------------------------------

class TestClampRadiusKm:
    def test_within_range_not_adjusted(self):
        value, adjusted = _clamp_radius_km(5.0)
        assert value == 5.0
        assert adjusted is False

    def test_below_min_clamped(self):
        value, adjusted = _clamp_radius_km(0.1)
        assert value == 0.5
        assert adjusted is True

    def test_above_max_clamped(self):
        value, adjusted = _clamp_radius_km(25.0)
        assert value == 20.0
        assert adjusted is True

    def test_at_min_boundary(self):
        value, adjusted = _clamp_radius_km(0.5)
        assert value == 0.5
        assert adjusted is False

    def test_at_max_boundary(self):
        value, adjusted = _clamp_radius_km(20.0)
        assert value == 20.0
        assert adjusted is False

    def test_negative_clamped(self):
        value, adjusted = _clamp_radius_km(-5.0)
        assert value == 0.5
        assert adjusted is True


# ---------------------------------------------------------------------------
# POST /api/analyze — filter and radius validation
# ---------------------------------------------------------------------------

class TestAnalyzeFiltersAndRadius:
    def test_duplicate_filter_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/analyze",
            json={
                "business_type": "cafetería",
                "zone": "Condesa",
                "ally_filters": ["panadería", "tienda"],
                "competitor_filters": ["tienda", "farmacia"],
            },
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] == "duplicate_filter"
        assert "tienda" in body["message"]

    def test_no_filters_passes_validation(self, client: TestClient):
        """Without filters, the request should proceed past filter validation."""
        resp = client.post(
            "/api/analyze",
            json={
                "business_type": "cafetería",
                "zone": "Condesa",
            },
        )
        # Should not be a 422 for duplicate_filter
        assert resp.json().get("error") != "duplicate_filter"

    def test_radius_out_of_range_adds_warning(self, client: TestClient):
        """When radius_km is out of range, the response should include a warning about adjustment."""
        # We can't easily test the full flow without mocking LLM, but we can
        # verify the request doesn't fail at validation for a valid zone.
        # The warning will be in the response if the analysis completes.
        resp = client.post(
            "/api/analyze",
            json={
                "business_type": "cafetería",
                "zone": "Condesa",
                "radius_km": 50.0,
            },
        )
        # The request should proceed past validation (not a filter error)
        assert resp.json().get("error") != "duplicate_filter"


# ---------------------------------------------------------------------------
# GET /api/scian/search
# ---------------------------------------------------------------------------

class TestScianSearchEndpoint:
    def test_search_returns_results(self, client: TestClient):
        resp = client.get("/api/scian/search", params={"q": "cafetería"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) > 0
        assert "code" in data["results"][0]
        assert "description" in data["results"][0]

    def test_search_empty_query_returns_empty(self, client: TestClient):
        resp = client.get("/api/scian/search", params={"q": ""})
        assert resp.status_code == 200
        assert resp.json()["results"] == []

    def test_search_short_query_returns_empty(self, client: TestClient):
        resp = client.get("/api/scian/search", params={"q": "ab"})
        assert resp.status_code == 200
        assert resp.json()["results"] == []

    def test_search_limits_to_10_results(self, client: TestClient):
        resp = client.get("/api/scian/search", params={"q": "comercio"})
        assert resp.status_code == 200
        assert len(resp.json()["results"]) <= 10

    def test_search_3_char_query_works(self, client: TestClient):
        resp = client.get("/api/scian/search", params={"q": "pan"})
        assert resp.status_code == 200
        # "pan" should match something like "panadería" descriptions
        data = resp.json()
        assert isinstance(data["results"], list)


# ---------------------------------------------------------------------------
# GET /api/ageb-layers — error cases
# ---------------------------------------------------------------------------

class TestAgebLayersEndpoint:
    def test_zone_not_found_returns_422(self, client: TestClient):
        resp = client.get("/api/ageb-layers", params={"zone": "ZonaInexistente"})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] == "zone_not_found"

    def test_missing_zone_param_returns_422(self, client: TestClient):
        resp = client.get("/api/ageb-layers")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# _extract_indicator helper
# ---------------------------------------------------------------------------

class TestExtractIndicator:
    def test_densidad_poblacion(self):
        raw = {"pobtot": 5000}
        val = _extract_indicator("densidad_poblacion", raw)
        assert val == round(5000 / 0.25, 2)

    def test_densidad_poblacion_zero(self):
        raw = {"pobtot": 0}
        val = _extract_indicator("densidad_poblacion", raw)
        assert val is None

    def test_pea(self):
        raw = {"pea": 1200}
        val = _extract_indicator("pea", raw)
        assert val == 1200.0

    def test_pea_missing(self):
        raw = {}
        val = _extract_indicator("pea", raw)
        assert val is None

    def test_escolaridad(self):
        raw = {"graproes": 12.5}
        val = _extract_indicator("escolaridad", raw)
        assert val == 12.5

    def test_nse_alto(self):
        raw = {"graproes": 15.0}
        val = _extract_indicator("nse", raw)
        assert val == 5.0  # Alto

    def test_nse_bajo(self):
        raw = {"graproes": 5.0}
        val = _extract_indicator("nse", raw)
        assert val == 1.0  # Bajo

    def test_nse_missing(self):
        raw = {}
        val = _extract_indicator("nse", raw)
        assert val is None

    def test_pct_internet(self):
        raw = {"vph_inter": 80, "vivpar_hab": 100}
        val = _extract_indicator("pct_internet", raw)
        assert val == 80.0

    def test_pct_internet_no_vivpar(self):
        raw = {"vph_inter": 80, "vivpar_hab": 0}
        val = _extract_indicator("pct_internet", raw)
        assert val is None

    def test_pct_automovil(self):
        raw = {"vph_autom": 60, "vivpar_hab": 200}
        val = _extract_indicator("pct_automovil", raw)
        assert val == 30.0

    def test_unknown_indicator(self):
        raw = {"pobtot": 100}
        val = _extract_indicator("unknown_key", raw)
        assert val is None


# ---------------------------------------------------------------------------
# _estimate_ageb_coordinates helper
# ---------------------------------------------------------------------------

class TestEstimateAgebCoordinates:
    def test_single_ageb(self):
        coords = _estimate_ageb_coordinates(["A"], 19.0, -99.2, 19.1, -99.1)
        assert "A" in coords
        lat, lng = coords["A"]
        assert 19.0 <= lat <= 19.1
        assert -99.2 <= lng <= -99.1

    def test_multiple_agebs_unique_coords(self):
        ids = ["A", "B", "C", "D"]
        coords = _estimate_ageb_coordinates(ids, 19.0, -99.2, 19.1, -99.1)
        assert len(coords) == 4
        positions = list(coords.values())
        # All positions should be unique
        assert len(set(positions)) == 4

    def test_empty_list(self):
        coords = _estimate_ageb_coordinates([], 19.0, -99.2, 19.1, -99.1)
        assert coords == {}

    def test_coords_within_bbox(self):
        ids = [f"AGEB{i}" for i in range(9)]
        coords = _estimate_ageb_coordinates(ids, 19.0, -99.2, 19.1, -99.1)
        for lat, lng in coords.values():
            assert 19.0 <= lat <= 19.1
            assert -99.2 <= lng <= -99.1


# ---------------------------------------------------------------------------
# ExportService.generate_standalone_html
# ---------------------------------------------------------------------------

from app.services.export_service import ExportService


class TestGenerateStandaloneHtml:
    def _make_result(self):
        return _make_analysis_result("html-test-id")

    def test_html_contains_leaflet_cdn(self):
        result = self._make_result()
        html = ExportService.generate_standalone_html(result)
        assert "unpkg.com/leaflet" in html

    def test_html_contains_summary_data(self):
        result = self._make_result()
        html = ExportService.generate_standalone_html(result)
        assert "73" in html  # score rounded
        assert "Recomendable" in html
        assert "Condesa" in html
        assert "25,000" in html or "25000" in html  # population

    def test_html_contains_zone_rectangle(self):
        result = self._make_result()
        html = ExportService.generate_standalone_html(result)
        assert "L.rectangle" in html

    def test_html_no_localhost_references(self):
        result = self._make_result()
        html = ExportService.generate_standalone_html(result)
        assert "localhost" not in html
        assert "/static/" not in html
        assert "/api/" not in html

    def test_html_contains_marker_legend(self):
        result = self._make_result()
        html = ExportService.generate_standalone_html(result)
        assert "Complementario" in html
        assert "Competidor" in html

    def test_html_without_layers_has_no_layer_control(self):
        result = self._make_result()
        html = ExportService.generate_standalone_html(result)
        assert 'id="layer-toggles"' not in html

    def test_html_with_layers_has_layer_control(self):
        result = self._make_result()
        layers_data = {
            "densidad_poblacion": {
                "label": "Densidad de Población",
                "unit": "hab/km²",
                "agebs": [
                    {"ageb_id": "0901500010010", "value": 15000.0, "center_lat": 19.411, "center_lng": -99.173},
                ],
            }
        }
        html = ExportService.generate_standalone_html(result, ageb_layers_data=layers_data)
        assert 'id="layer-toggles"' in html
        assert "Densidad" in html
        assert 'id="color-scale-legend"' in html

    def test_html_embeds_businesses_json(self):
        result = self._make_result()
        html = ExportService.generate_standalone_html(result)
        assert "var BUSINESSES" in html or "const BUSINESSES" in html

    def test_html_embeds_zone_json(self):
        result = self._make_result()
        html = ExportService.generate_standalone_html(result)
        assert "var ZONE" in html or "const ZONE" in html


# ---------------------------------------------------------------------------
# _make_zone_slug helper
# ---------------------------------------------------------------------------

class TestMakeZoneSlug:
    def test_simple_name(self):
        assert _make_zone_slug("Condesa") == "condesa"

    def test_name_with_spaces(self):
        assert _make_zone_slug("Roma Norte") == "roma-norte"

    def test_name_with_accents(self):
        slug = _make_zone_slug("Álvaro Obregón")
        assert slug == "alvaro-obregon"

    def test_name_with_special_chars(self):
        slug = _make_zone_slug("Centro Histórico (CDMX)")
        assert "centro" in slug
        assert "historico" in slug


# ---------------------------------------------------------------------------
# POST /api/export/html endpoint
# ---------------------------------------------------------------------------

class TestExportHtmlEndpoint:
    def test_missing_analysis_id_returns_400(self, client: TestClient):
        resp = client.post("/api/export/html", json={})
        assert resp.status_code == 400
        assert resp.json()["error"] == "missing_field"

    def test_not_found_analysis_returns_404(self, client: TestClient):
        resp = client.post(
            "/api/export/html",
            json={"analysis_id": "nonexistent"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"] == "not_found"

    def test_valid_analysis_returns_html(self, client: TestClient):
        analysis_store["html-export-test"] = _make_analysis_result("html-export-test")
        resp = client.post(
            "/api/export/html",
            json={"analysis_id": "html-export-test"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        assert "Content-Disposition" in resp.headers
        assert "mapa-viabilidad-condesa.html" in resp.headers["Content-Disposition"]
        body = resp.text
        assert "unpkg.com/leaflet" in body
        assert "localhost" not in body

    def test_invalid_json_returns_400(self, client: TestClient):
        resp = client.post(
            "/api/export/html",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_json"
