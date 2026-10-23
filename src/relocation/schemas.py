from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

VerificationStatus = Literal["verified", "needs_review", "stale"]
ScoreMethod = Literal["manual", "llm", "derived"]
ProviderName = Field(default="openai", pattern=r"^[a-z0-9][a-z0-9_.-]{0,31}$")


# --- Locations ---


class LocationCreate(BaseModel):
    name: str
    country: str
    country_code: Optional[str] = None
    region: Optional[str] = None
    admin1: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    population: Optional[int] = None
    description: Optional[str] = None
    notes: Optional[str] = None


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    region: Optional[str] = None
    admin1: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    population: Optional[int] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    full_research_ran_at: Optional[datetime] = None


class LocationOut(BaseModel):
    id: int
    name: str
    country: str
    country_code: str
    slug: Optional[str] = None
    region: Optional[str]
    admin1: Optional[str] = None
    latitude: Optional[float]
    longitude: Optional[float]
    population: Optional[int]
    description: Optional[str]
    notes: Optional[str]
    full_research_ran_at: Optional[datetime]
    # True when every researched category comes from the current pipeline prompt version.
    research_current: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LocationCandidateOut(BaseModel):
    name: str
    display_name: str
    country: Optional[str] = None
    region: Optional[str] = None
    admin1: Optional[str] = None
    admin2: Optional[str] = None
    admin3: Optional[str] = None
    latitude: float
    longitude: float
    population: Optional[int] = None
    feature_code: Optional[str] = None
    query: str
    score: int
    provider: Optional[str] = None
    region_match: bool = True


class LocationCandidateSearchOut(BaseModel):
    candidates: list[LocationCandidateOut]
    warnings: list[str] = Field(default_factory=list)


# --- Categories ---


class CategoryOut(BaseModel):
    id: int
    key: str
    name: str
    description: Optional[str]
    sort_order: int
    scope: Literal["location", "country"]
    kind: Literal["researched", "derived"]
    needs_web: bool
    requires_citation: bool
    refresh_after_days: Optional[int]

    model_config = {"from_attributes": True}


# --- Countries ---


class CountryOut(BaseModel):
    code: str
    name: str
    parent_code: Optional[str]

    model_config = {"from_attributes": True}


class _SubjectMixin(BaseModel):
    """Research/scores belong to a location, or to a country for country-scope categories.

    For country-scope categories a location_id is accepted and resolved to its country.
    """

    @model_validator(mode="after")
    def _has_subject(self):
        if getattr(self, "location_id", None) is None and getattr(self, "country_code", None) is None:
            raise ValueError("Provide location_id or country_code.")
        return self


# --- Scores ---


class ScoreCreate(_SubjectMixin):
    location_id: Optional[int] = None
    country_code: Optional[str] = Field(default=None, min_length=2, max_length=2)
    category_id: int
    score: int = Field(ge=0, le=10)
    notes: Optional[str] = None
    provider: str = ProviderName
    # Anything not sent by a pipeline (UI sliders, CLI) is a manual score.
    method: ScoreMethod = "manual"
    research_id: Optional[int] = None
    run_id: Optional[int] = None


class ScoreOut(BaseModel):
    id: int
    location_id: Optional[int]
    category_id: int
    score: int
    notes: Optional[str]
    provider: str
    method: ScoreMethod
    scope: Literal["location", "country"] = "location"
    country_code: Optional[str] = None
    research_id: Optional[int]
    run_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Weights ---


class WeightCreate(BaseModel):
    user_id: int
    category_id: int
    weight: float = Field(ge=0, le=10)


class WeightOut(BaseModel):
    id: int
    user_id: int
    category_id: int
    weight: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Research ---


class ResearchCreate(_SubjectMixin):
    location_id: Optional[int] = None
    country_code: Optional[str] = Field(default=None, min_length=2, max_length=2)
    category_id: Optional[int] = None
    content: str
    key_facts: Optional[list[dict]] = None
    source: Optional[str] = None
    source_published_at: Optional[date] = None
    source_urls: Optional[list[str]] = None
    source_checked_at: Optional[date] = None
    verification_status: VerificationStatus = "needs_review"
    verified_by: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    provider: str = ProviderName
    run_id: Optional[int] = None


class ResearchOut(BaseModel):
    id: int
    location_id: Optional[int]
    country_code: Optional[str]
    category_id: Optional[int]
    content: str
    key_facts: Optional[list[dict]] = None
    source: Optional[str]
    source_published_at: Optional[date]
    source_urls: Optional[list[str]]
    source_checked_at: Optional[date]
    verification_status: VerificationStatus
    verified_by: Optional[str]
    confidence: Optional[float]
    provider: str
    run_id: Optional[int]
    is_current: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Pros/Cons ---


class ProConCreate(BaseModel):
    location_id: int
    category_id: Optional[int] = None
    type: str = Field(pattern="^(pro|con)$")
    content: str
    provider: str = ProviderName
    run_id: Optional[int] = None


class ProConOut(BaseModel):
    id: int
    location_id: int
    category_id: Optional[int]
    type: str
    content: str
    provider: str
    run_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Visa ---


class VisaCreate(BaseModel):
    country: str
    country_code: Optional[str] = None
    visa_type: str
    description: Optional[str] = None
    residency_pathway: Optional[str] = None
    requirements: Optional[str] = None
    timeline: Optional[str] = None
    cost: Optional[str] = None
    notes: Optional[str] = None
    source_urls: Optional[list[str]] = None
    source_published_at: Optional[date] = None
    source_checked_at: Optional[date] = None
    verification_status: VerificationStatus = "needs_review"
    verified_by: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    provider: str = ProviderName
    run_id: Optional[int] = None


class VisaUpdate(BaseModel):
    country: Optional[str] = None
    country_code: Optional[str] = None
    visa_type: Optional[str] = None
    description: Optional[str] = None
    residency_pathway: Optional[str] = None
    requirements: Optional[str] = None
    timeline: Optional[str] = None
    cost: Optional[str] = None
    notes: Optional[str] = None
    source_urls: Optional[list[str]] = None
    source_published_at: Optional[date] = None
    source_checked_at: Optional[date] = None
    verification_status: Optional[VerificationStatus] = None
    verified_by: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class VisaOut(BaseModel):
    id: int
    country: str
    country_code: Optional[str]
    visa_type: str
    description: Optional[str]
    residency_pathway: Optional[str]
    requirements: Optional[str]
    timeline: Optional[str]
    cost: Optional[str]
    notes: Optional[str]
    source_urls: Optional[list[str]]
    source_published_at: Optional[date]
    source_checked_at: Optional[date]
    verification_status: VerificationStatus
    verified_by: Optional[str]
    provider: str
    run_id: Optional[int]
    confidence: Optional[float]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Profile ---


class ProfileResponseCreate(BaseModel):
    question_key: str
    answer: Optional[str] = None


class ProfileResponseOut(BaseModel):
    id: int
    section: str
    question_key: str
    question: str
    answer: Optional[str]

    model_config = {"from_attributes": True}


# --- Users ---


class UserOut(BaseModel):
    id: int
    name: str
    display_name: str

    model_config = {"from_attributes": True}


# --- Rankings ---


class CategoryDetailOut(BaseModel):
    category_id: int
    category_name: str
    score: int
    # Keyed by user id (JSON object keys are strings).
    weights: dict[int, float]
    weighted: dict[int, float]


class RankingOut(BaseModel):
    location_id: int
    location_name: str
    country: str
    overall_score: float
    # Weighted score per user, keyed by user id.
    user_scores: dict[int, float]
    scored_categories: int
    total_categories: int
    coverage: float
    details: list[CategoryDetailOut]


# --- Ocean temperatures ---


class OceanTemperatureMonthlyOut(BaseModel):
    id: int
    location_id: int
    month: int
    avg_temp_c: float
    min_temp_c: Optional[float]
    max_temp_c: Optional[float]
    sample_count: int
    baseline_start_year: int
    baseline_end_year: int
    source_dataset: str
    source_url: Optional[str]
    source_checked_at: date
    grid_lat: Optional[float]
    grid_lon: Optional[float]
    grid_distance_km: Optional[float]
    quality_flag: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
