"""Pydantic models for the Business Viability Map application."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


class BoundingBox(BaseModel):
    """Geographic bounding box."""

    min_lat: float
    min_lng: float
    max_lat: float
    max_lng: float


class SCIANCategory(BaseModel):
    """SCIAN economic activity category."""

    code: str
    description: str


class BusinessInterpretation(BaseModel):
    """Result of LLM interpretation of the user's business type."""

    original_input: str
    scian_code: str
    scian_description: str
    complementary_categories: list[SCIANCategory]
    competitor_categories: list[SCIANCategory]
    used_fallback: bool


class Zone(BaseModel):
    """Geographic zone composed of AGEBs."""

    name: str
    ageb_ids: list[str]
    center_lat: float
    center_lng: float
    bbox: BoundingBox


class GoogleReview(BaseModel):
    """Reseña individual de Google Places."""

    text: str
    rating: int  # 1-5


class Business(BaseModel):
    """Consolidated business from multiple data sources."""

    id: str
    name: str
    lat: float
    lng: float
    category: str
    source: str
    verified_google: bool
    google_rating: float | None = None
    google_reviews_count: int | None = None
    google_hours: list[str] | None = None
    google_photos: list[str] | None = None
    google_is_open: bool | None = None
    google_price_level: int | None = None
    google_types: list[str] | None = None
    google_reviews: list[GoogleReview] | None = None
    google_editorial_summary: str | None = None
    denue_scian_code: str | None = None
    denue_employee_stratum: str | None = None
    denue_registration_date: str | None = None
    denue_legal_name: str | None = None
    denue_address: str | None = None


class ClassifiedBusiness(Business):
    """Business with complementary/competitor classification."""

    classification: Literal["complementary", "competitor", "unclassified"]
    relevance: Literal["high", "medium", "low"]


class AGEBData(BaseModel):
    """Aggregated demographic data for a zone."""

    total_population: int
    population_density: float
    economically_active_population: int
    socioeconomic_level: str
    ageb_count: int
    # Extended demographic indicators
    female_population: int = 0
    male_population: int = 0
    population_0_14: int = 0
    population_15_64: int = 0
    population_65_plus: int = 0
    occupied_population: int = 0
    unemployed_population: int = 0
    inactive_population: int = 0
    avg_schooling_years: float = 0.0
    total_households: int = 0
    total_dwellings: int = 0
    avg_occupants_per_dwelling: float = 0.0
    population_with_health_services: int = 0
    population_without_health_services: int = 0
    # Housing infrastructure percentages (0-100)
    pct_with_electricity: float = 0.0
    pct_with_water: float = 0.0
    pct_with_drainage: float = 0.0
    pct_with_internet: float = 0.0
    pct_with_car: float = 0.0
    pct_with_cellphone: float = 0.0
    pct_with_computer: float = 0.0
    raw_indicators: dict
    extended_indicators: dict = {}


class MultiRadiusResult(BaseModel):
    """Result of analysis at a specific predefined radius (1, 3, or 5 km)."""

    radius_km: float
    competitors: int
    complementary: int
    total_population: int
    environment_variables: dict  # poi_density, commercial_activity_index, sector_concentration


class ViabilityResult(BaseModel):
    """Viability calculation result."""

    score: float
    category: Literal["Recomendable", "Viable con enfoque estratégico", "No recomendable"]
    factor_scores: dict
    data_completeness: float

    @field_validator("score")
    @classmethod
    def score_must_be_in_range(cls, v: float) -> float:
        if not 0 <= v <= 100:
            raise ValueError("score must be between 0 and 100")
        return v

    @field_validator("data_completeness")
    @classmethod
    def data_completeness_must_be_in_range(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("data_completeness must be between 0 and 1")
        return v


class AnalysisResult(BaseModel):
    """Complete analysis result sent to the frontend."""

    analysis_id: str
    business_type: BusinessInterpretation
    zone: Zone
    businesses: list[ClassifiedBusiness]
    ageb_data: AGEBData
    viability: ViabilityResult
    recommendation_text: str
    warnings: list[str]
    timestamp: str
    strategic_recommendations: list[str] = []
    multi_radius_results: list[MultiRadiusResult] = []


class APIError(BaseModel):
    """API error response format."""

    error: str
    message: str
    details: str | None = None
    warnings: list[str] = []
