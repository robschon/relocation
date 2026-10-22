"""Structured outputs the pipeline asks the model for. Top level must be an object."""

from __future__ import annotations

from pydantic import BaseModel


class KeyFact(BaseModel):
    fact: str
    value: str | None = None
    source_url: str | None = None


class EvidenceResponse(BaseModel):
    """One call researches a category and scores it."""

    summary: str
    key_facts: list[KeyFact]
    score: int
    score_rationale: str
    confidence: float
    source_note: str


class RescoreResponse(BaseModel):
    score: int
    score_rationale: str


class VisaItem(BaseModel):
    visa_type: str
    description: str | None = None
    residency_pathway: str | None = None
    requirements: str | None = None
    timeline: str | None = None
    cost: str | None = None
    notes: str | None = None
    source_urls: list[str] | None = None
    confidence: float | None = None


class VisaResponse(BaseModel):
    visas: list[VisaItem]


class VisaEvidenceResponse(EvidenceResponse):
    """Visa/residency: the category evidence and score plus the country's visa pathways, in one call."""

    visas: list[VisaItem]


class ProConItem(BaseModel):
    category_key: str
    text: str


class SynthesisResponse(BaseModel):
    """Pros/cons and the shortlist description in one call."""

    description: str
    pros: list[ProConItem]
    cons: list[ProConItem]
