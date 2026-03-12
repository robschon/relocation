from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

VerificationStatus = Literal["verified", "needs_review", "stale"]


# --- Locations ---


class LocationCreate(BaseModel):
    name: str
    country: str
    region: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    population: Optional[int] = None
    description: Optional[str] = None
    notes: Optional[str] = None


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
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
    region: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    population: Optional[int]
    description: Optional[str]
    notes: Optional[str]
    full_research_ran_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Categories ---


class CategoryOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    sort_order: int

    model_config = {"from_attributes": True}


# --- Scores ---


class ScoreCreate(BaseModel):
    location_id: int
    category_id: int
    score: int = Field(ge=0, le=10)
    notes: Optional[str] = None


class ScoreOut(BaseModel):
    id: int
    location_id: int
    category_id: int
    score: int
    notes: Optional[str]
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


class ResearchCreate(BaseModel):
    location_id: int
    category_id: Optional[int] = None
    content: str
    source: Optional[str] = None
    source_published_at: Optional[date] = None
    source_urls: Optional[list[str]] = None
    source_checked_at: Optional[date] = None
    verification_status: VerificationStatus = "needs_review"
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class ResearchOut(BaseModel):
    id: int
    location_id: int
    category_id: Optional[int]
    content: str
    source: Optional[str]
    source_published_at: Optional[date]
    source_urls: Optional[list[str]]
    source_checked_at: Optional[date]
    verification_status: VerificationStatus
    confidence: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Pros/Cons ---


class ProConCreate(BaseModel):
    location_id: int
    category_id: Optional[int] = None
    type: str = Field(pattern="^(pro|con)$")
    content: str


class ProConOut(BaseModel):
    id: int
    location_id: int
    category_id: Optional[int]
    type: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Visa ---


class VisaCreate(BaseModel):
    country: str
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
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class VisaUpdate(BaseModel):
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
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class VisaOut(BaseModel):
    id: int
    country: str
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

    model_config = {"from_attributes": True}


# --- Rankings ---


class CategoryDetailOut(BaseModel):
    category_name: str
    score: int
    husband_weight: float
    wife_weight: float
    husband_weighted: float
    wife_weighted: float


class RankingOut(BaseModel):
    location_name: str
    country: str
    overall_score: float
    husband_score: float
    wife_score: float
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
