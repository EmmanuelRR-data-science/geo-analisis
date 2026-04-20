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


class TargetCriteria(BaseModel):
    """Criterios demográficos extraídos del perfil objetivo."""

    gender: Literal["male", "female", "all"] = "all"
    age_min: int = 0
    age_max: int = 99
    socioeconomic_level: Literal["Alto", "Medio-Alto", "Medio", "Bajo", "all"] = "all"
    min_schooling_years: float | None = None


class TargetMatchResult(BaseModel):
    """Resultado del cálculo de coincidencia demográfica."""

    percentage: float  # 0.0 - 100.0
    estimated_population: int
    breakdown: dict  # {"gender_factor": 0.52, "age_factor": 0.41, "socioeconomic_factor": 1.0}


class ValuePoint(BaseModel):
    """Punto de valor extraído de reseñas de competidores."""

    title: str
    description: str
    source_type: Literal["positive", "negative"]


class ImprovementOpportunity(BaseModel):
    """Oportunidad de mejora con recomendación accionable."""

    issue: str
    recommendation: str


class TargetCustomerInsight(BaseModel):
    """Insight cruzado entre reseñas y perfil objetivo."""

    title: str
    explanation: str


class CompetitorReviewAnalysis(BaseModel):
    """Resultado completo del análisis de reseñas de competidores."""

    value_points: list[ValuePoint] = []
    improvement_opportunities: list[ImprovementOpportunity] = []
    target_customer_insights: list[TargetCustomerInsight] = []
    insufficient_data: bool = False


class FootTrafficForecast(BaseModel):
    """Pronóstico de tráfico peatonal para un establecimiento."""
    venue_id: str
    venue_name: str
    venue_category: str | None = None
    opening_hours_by_day: dict[str, str] = {}
    day_raw: dict[str, list[int]]  # {"Monday": [24 values 0-100], ...}
    peak_hours: list[dict] = []
    quiet_hours: list[dict] = []
    surge_hours: list[dict] = []
    dwell_time_min: int = 0
    dwell_time_max: int = 0
    dwell_time_avg: int = 0


class ZoneTrafficProfile(BaseModel):
    """Perfil de tráfico peatonal agregado de la zona."""
    hourly_matrix: dict[str, list[float]]
    peak_hours_by_day: dict[str, list[int]]
    quiet_hours_by_day: dict[str, list[int]]
    busiest_day: str
    quietest_day: str
    avg_dwell_time_minutes: float
    venues_with_data: int
    venues_total: int
    source_venues: list[dict] = []


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
    # Target market analysis fields (optional)
    target_profile: str | None = None
    target_criteria: dict | None = None
    target_match_percentage: float | None = None
    target_match_population: int | None = None
    target_match_breakdown: dict | None = None
    competitor_value_points: list[dict] | None = None
    competitor_improvement_opportunities: list[dict] | None = None
    target_customer_insights: list[dict] | None = None
    zone_traffic_profile: dict | None = None  # ZoneTrafficProfile serialized


class APIError(BaseModel):
    """API error response format."""

    error: str
    message: str
    details: str | None = None
    warnings: list[str] = []
