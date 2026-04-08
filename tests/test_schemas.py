"""Unit tests for Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.models.schemas import ClassifiedBusiness, ViabilityResult


class TestViabilityResult:
    def _make(self, **overrides):
        defaults = {
            "score": 75.0,
            "category": "Recomendable",
            "factor_scores": {"competition": 80},
            "data_completeness": 0.9,
        }
        defaults.update(overrides)
        return ViabilityResult(**defaults)

    def test_valid_result(self):
        r = self._make()
        assert r.score == 75.0
        assert r.category == "Recomendable"

    def test_score_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            self._make(score=-1)

    def test_score_above_100_rejected(self):
        with pytest.raises(ValidationError):
            self._make(score=101)

    def test_score_boundary_zero(self):
        r = self._make(score=0)
        assert r.score == 0

    def test_score_boundary_100(self):
        r = self._make(score=100)
        assert r.score == 100

    def test_invalid_category_rejected(self):
        with pytest.raises(ValidationError):
            self._make(category="Excelente")

    def test_data_completeness_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            self._make(data_completeness=-0.1)

    def test_data_completeness_above_one_rejected(self):
        with pytest.raises(ValidationError):
            self._make(data_completeness=1.1)


class TestClassifiedBusiness:
    def _make(self, **overrides):
        defaults = {
            "id": "b1",
            "name": "Test Business",
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

    def test_valid_classified_business(self):
        b = self._make()
        assert b.classification == "complementary"
        assert b.relevance == "high"

    def test_invalid_classification_rejected(self):
        with pytest.raises(ValidationError):
            self._make(classification="ally")

    def test_invalid_relevance_rejected(self):
        with pytest.raises(ValidationError):
            self._make(relevance="critical")

    def test_all_valid_classifications(self):
        for c in ("complementary", "competitor", "unclassified"):
            b = self._make(classification=c)
            assert b.classification == c

    def test_all_valid_relevances(self):
        for r in ("high", "medium", "low"):
            b = self._make(relevance=r)
            assert b.relevance == r
