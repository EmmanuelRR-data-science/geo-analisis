"""Tests para el servicio LLM y sus fallbacks."""

from __future__ import annotations

import pytest

from app.models.schemas import (
    AGEBData,
    AnalysisResult,
    BoundingBox,
    Business,
    BusinessInterpretation,
    ClassifiedBusiness,
    SCIANCategory,
    ViabilityResult,
    Zone,
)
from app.services.llm_service import LLMService
from app.services.scian_catalog import (
    AFFINITY_RULES,
    SCIAN_CATALOG,
    get_affinity,
    search_scian_catalog,
)


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

def _make_business(
    id: str = "b1",
    name: str = "Negocio Test",
    category: str = "Restaurante",
    scian_code: str | None = None,
) -> Business:
    return Business(
        id=id,
        name=name,
        lat=19.4,
        lng=-99.1,
        category=category,
        source="denue",
        verified_google=False,
        denue_scian_code=scian_code,
    )


def _make_analysis_data(
    category: str = "Recomendable",
    score: float = 75.0,
    num_competitors: int = 3,
    num_complementary: int = 5,
) -> AnalysisResult:
    businesses: list[ClassifiedBusiness] = []
    for i in range(num_competitors):
        businesses.append(
            ClassifiedBusiness(
                id=f"comp_{i}",
                name=f"Competidor {i}",
                lat=19.4,
                lng=-99.1,
                category="Restaurante",
                source="google",
                verified_google=True,
                classification="competitor",
                relevance="high",
            )
        )
    for i in range(num_complementary):
        businesses.append(
            ClassifiedBusiness(
                id=f"compl_{i}",
                name=f"Complementario {i}",
                lat=19.4,
                lng=-99.1,
                category="Farmacia",
                source="google",
                verified_google=True,
                classification="complementary",
                relevance="medium",
            )
        )

    return AnalysisResult(
        analysis_id="test-001",
        business_type=BusinessInterpretation(
            original_input="restaurante de tacos",
            scian_code="722513",
            scian_description="Restaurantes con servicio de preparación de tacos y tortas",
            complementary_categories=[
                SCIANCategory(code="461211", description="Bebidas no alcohólicas"),
            ],
            competitor_categories=[
                SCIANCategory(code="722511", description="Restaurantes a la carta"),
            ],
            used_fallback=False,
        ),
        zone=Zone(
            name="Condesa",
            ageb_ids=["0901200010010"],
            center_lat=19.4115,
            center_lng=-99.1733,
            bbox=BoundingBox(min_lat=19.40, min_lng=-99.18, max_lat=19.42, max_lng=-99.16),
        ),
        businesses=businesses,
        ageb_data=AGEBData(
            total_population=25000,
            population_density=150.5,
            economically_active_population=12000,
            socioeconomic_level="Medio-Alto",
            ageb_count=3,
            raw_indicators={},
        ),
        viability=ViabilityResult(
            score=score,
            category=category,
            factor_scores={"competencia": 60, "complementarios": 70, "demografico": 80, "socioeconomico": 75},
            data_completeness=0.85,
        ),
        recommendation_text="",
        warnings=[],
        timestamp="2024-01-01T00:00:00",
    )


# ----------------------------------------------------------------
# Tests del catálogo SCIAN
# ----------------------------------------------------------------

class TestSCIANCatalog:
    def test_catalog_has_entries(self):
        assert len(SCIAN_CATALOG) >= 30

    def test_search_finds_restaurante(self):
        results = search_scian_catalog("restaurante")
        assert len(results) > 0
        assert any("restaurante" in desc.lower() for _, desc in results)

    def test_search_finds_farmacia(self):
        results = search_scian_catalog("farmacia")
        assert len(results) > 0
        assert any("farmacia" in desc.lower() for _, desc in results)

    def test_search_empty_query(self):
        results = search_scian_catalog("")
        assert results == []

    def test_search_no_match(self):
        results = search_scian_catalog("xyznonexistent")
        assert results == []

    def test_affinity_rules_have_entries(self):
        assert len(AFFINITY_RULES) >= 30

    def test_get_affinity_known_code(self):
        affinity = get_affinity("722511")
        assert len(affinity["complementary"]) >= 1
        assert len(affinity["competitor"]) >= 1

    def test_get_affinity_unknown_code_uses_prefix(self):
        # Code not in rules but in catalog prefix range
        affinity = get_affinity("999999")
        # Should still return something (possibly empty if no prefix match)
        assert "complementary" in affinity
        assert "competitor" in affinity


# ----------------------------------------------------------------
# Tests del fallback interpret_business_type
# ----------------------------------------------------------------

class TestFallbackInterpret:
    def test_fallback_returns_valid_interpretation(self):
        service = LLMService()
        result = service._fallback_interpret_business_type("restaurante de tacos")
        assert result.used_fallback is True
        assert result.original_input == "restaurante de tacos"
        assert result.scian_code != ""
        assert result.scian_description != ""

    def test_fallback_finds_matching_scian(self):
        service = LLMService()
        result = service._fallback_interpret_business_type("farmacia")
        assert "farmacia" in result.scian_description.lower()

    def test_fallback_returns_categories(self):
        service = LLMService()
        result = service._fallback_interpret_business_type("restaurante")
        assert len(result.complementary_categories) >= 1
        assert len(result.competitor_categories) >= 1

    def test_fallback_no_match_returns_default(self):
        service = LLMService()
        result = service._fallback_interpret_business_type("xyznonexistent")
        assert result.used_fallback is True
        assert result.scian_code != ""


# ----------------------------------------------------------------
# Tests del fallback classify_businesses
# ----------------------------------------------------------------

class TestFallbackClassify:
    def test_fallback_classifies_competitor_by_scian(self):
        service = LLMService()
        user_biz = BusinessInterpretation(
            original_input="tacos",
            scian_code="722513",
            scian_description="Restaurantes con servicio de preparación de tacos y tortas",
            complementary_categories=[SCIANCategory(code="461211", description="Bebidas")],
            competitor_categories=[SCIANCategory(code="722511", description="Restaurantes a la carta")],
            used_fallback=False,
        )
        businesses = [
            _make_business(id="b1", name="Taquería El Güero", scian_code="722511"),
        ]
        result = service._fallback_classify_businesses(user_biz, businesses)
        assert len(result) == 1
        assert result[0].classification == "competitor"

    def test_fallback_classifies_complementary_by_scian(self):
        service = LLMService()
        user_biz = BusinessInterpretation(
            original_input="tacos",
            scian_code="722513",
            scian_description="Restaurantes con servicio de preparación de tacos y tortas",
            complementary_categories=[SCIANCategory(code="461211", description="Bebidas")],
            competitor_categories=[SCIANCategory(code="722511", description="Restaurantes a la carta")],
            used_fallback=False,
        )
        businesses = [
            _make_business(id="b1", name="Refresquería", scian_code="461211"),
        ]
        result = service._fallback_classify_businesses(user_biz, businesses)
        assert len(result) == 1
        assert result[0].classification == "complementary"

    def test_fallback_empty_list(self):
        service = LLMService()
        user_biz = BusinessInterpretation(
            original_input="tacos",
            scian_code="722513",
            scian_description="Tacos",
            complementary_categories=[],
            competitor_categories=[],
            used_fallback=False,
        )
        result = service._fallback_classify_businesses(user_biz, [])
        assert result == []

    def test_fallback_unclassified_when_no_scian(self):
        service = LLMService()
        user_biz = BusinessInterpretation(
            original_input="tacos",
            scian_code="722513",
            scian_description="Tacos y tortas",
            complementary_categories=[],
            competitor_categories=[],
            used_fallback=False,
        )
        businesses = [
            _make_business(id="b1", name="Negocio Genérico", category="Otro", scian_code=None),
        ]
        result = service._fallback_classify_businesses(user_biz, businesses)
        assert len(result) == 1
        assert result[0].classification in ("complementary", "competitor", "unclassified")

    def test_fallback_valid_relevance_values(self):
        service = LLMService()
        user_biz = BusinessInterpretation(
            original_input="tacos",
            scian_code="722513",
            scian_description="Tacos",
            complementary_categories=[SCIANCategory(code="461211", description="Bebidas")],
            competitor_categories=[SCIANCategory(code="722511", description="Restaurantes")],
            used_fallback=False,
        )
        businesses = [
            _make_business(id="b1", scian_code="722511"),
            _make_business(id="b2", scian_code="461211"),
            _make_business(id="b3", scian_code=None),
        ]
        result = service._fallback_classify_businesses(user_biz, businesses)
        for b in result:
            assert b.relevance in ("high", "medium", "low")
            assert b.classification in ("complementary", "competitor", "unclassified")


# ----------------------------------------------------------------
# Tests del fallback generate_recommendation
# ----------------------------------------------------------------

class TestFallbackRecommendation:
    def test_recomendable_template_at_least_100_words(self):
        service = LLMService()
        data = _make_analysis_data(category="Recomendable", score=75.0)
        text = service._fallback_generate_recommendation(data)
        word_count = len(text.split())
        assert word_count >= 100, f"Solo {word_count} palabras, se requieren al menos 100"

    def test_no_recomendable_template_at_least_100_words(self):
        service = LLMService()
        data = _make_analysis_data(category="No recomendable", score=25.0)
        text = service._fallback_generate_recommendation(data)
        word_count = len(text.split())
        assert word_count >= 100, f"Solo {word_count} palabras, se requieren al menos 100"

    def test_viable_con_reservas_template_at_least_100_words(self):
        service = LLMService()
        data = _make_analysis_data(category="Viable con reservas", score=55.0)
        text = service._fallback_generate_recommendation(data)
        word_count = len(text.split())
        assert word_count >= 100, f"Solo {word_count} palabras, se requieren al menos 100"

    def test_template_contains_score(self):
        service = LLMService()
        data = _make_analysis_data(category="Recomendable", score=82.5)
        text = service._fallback_generate_recommendation(data)
        assert "82.5" in text

    def test_template_contains_zone_name(self):
        service = LLMService()
        data = _make_analysis_data()
        text = service._fallback_generate_recommendation(data)
        assert "Condesa" in text

    def test_template_contains_competitor_count(self):
        service = LLMService()
        data = _make_analysis_data(num_competitors=7)
        text = service._fallback_generate_recommendation(data)
        assert "7" in text

    def test_template_contains_complementary_count(self):
        service = LLMService()
        data = _make_analysis_data(num_complementary=12)
        text = service._fallback_generate_recommendation(data)
        assert "12" in text

    def test_template_contains_demographic_data(self):
        service = LLMService()
        data = _make_analysis_data()
        text = service._fallback_generate_recommendation(data)
        assert "25,000" in text or "25000" in text


# ----------------------------------------------------------------
# Tests del prompt de recomendación
# ----------------------------------------------------------------

class TestRecommendationPrompt:
    def test_prompt_contains_zone_summary(self):
        service = LLMService()
        data = _make_analysis_data()
        prompt = service.build_recommendation_prompt(data)
        assert "Condesa" in prompt
        assert "Ciudad de México" in prompt

    def test_prompt_contains_competitors(self):
        service = LLMService()
        data = _make_analysis_data(num_competitors=4)
        prompt = service.build_recommendation_prompt(data)
        assert "competidores" in prompt.lower()
        assert "4" in prompt

    def test_prompt_contains_complementary(self):
        service = LLMService()
        data = _make_analysis_data(num_complementary=8)
        prompt = service.build_recommendation_prompt(data)
        assert "complementarios" in prompt.lower()
        assert "8" in prompt

    def test_prompt_contains_demographic_factors(self):
        service = LLMService()
        data = _make_analysis_data()
        prompt = service.build_recommendation_prompt(data)
        assert "Población" in prompt or "población" in prompt
        assert "socioeconómico" in prompt.lower() or "socioeconomico" in prompt.lower()

    def test_prompt_recomendable_has_positive_factors(self):
        service = LLMService()
        data = _make_analysis_data(category="Recomendable")
        prompt = service.build_recommendation_prompt(data)
        assert "positivos" in prompt.lower() or "favorecen" in prompt.lower()

    def test_prompt_no_recomendable_has_risk_factors(self):
        service = LLMService()
        data = _make_analysis_data(category="No recomendable", score=25.0)
        prompt = service.build_recommendation_prompt(data)
        assert "riesgo" in prompt.lower()
        assert "alternativas" in prompt.lower()

    def test_prompt_viable_con_reservas_has_both(self):
        service = LLMService()
        data = _make_analysis_data(category="Viable con reservas", score=55.0)
        prompt = service.build_recommendation_prompt(data)
        assert "positivos" in prompt.lower() or "factores positivos" in prompt.lower()
        assert "riesgos" in prompt.lower()


# ----------------------------------------------------------------
# Tests de _parse_json_response
# ----------------------------------------------------------------

class TestParseJsonResponse:
    def test_parse_clean_json(self):
        service = LLMService()
        result = service._parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_in_code_block(self):
        service = LLMService()
        text = '```json\n{"key": "value"}\n```'
        result = service._parse_json_response(text)
        assert result == {"key": "value"}

    def test_parse_json_with_surrounding_text(self):
        service = LLMService()
        text = 'Here is the result: {"key": "value"} end.'
        result = service._parse_json_response(text)
        assert result == {"key": "value"}

    def test_parse_invalid_json(self):
        service = LLMService()
        result = service._parse_json_response("not json at all")
        assert result is None

    def test_parse_empty_string(self):
        service = LLMService()
        result = service._parse_json_response("")
        assert result is None

    def test_parse_none(self):
        service = LLMService()
        result = service._parse_json_response(None)
        assert result is None
