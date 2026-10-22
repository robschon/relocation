"""Pipeline steps. Each writes through the service layer, so API rules apply to pipeline writes too."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from relocation.models import Category, Country, Location, ProCon, Research, VisaInfo
from relocation.pipeline.context import Profile, category_input, country_block, location_block
from relocation.pipeline.llm import LlmClient, LlmRequest, _dedupe
from relocation.pipeline.policy import in_us_jurisdiction, visa_info_is_fresh
from relocation.pipeline.schemas import (
    EvidenceResponse,
    RescoreResponse,
    SynthesisResponse,
    VisaEvidenceResponse,
    VisaResponse,
)
from relocation.services.effective_scores import effective_scores
from relocation.services.errors import ValidationFailed
from relocation.services.research_records import create_research
from relocation.services.scores import upsert_score
from relocation.services.visa import replace_country_visa
from relocation.settings import PipelineSettings

US_RULE_URLS = ["https://www.usa.gov/citizenship", "https://www.uscis.gov/citizenship"]


@dataclass
class RunContext:
    llm: LlmClient
    settings: PipelineSettings
    profile: Profile
    instructions: str
    run_id: int | None
    provider: str
    today: date
    us_citizens: bool
    log: Callable[[str], None] = print


@dataclass
class RunSummary:
    researched: list[str] = field(default_factory=list)
    rescored: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    visa_refreshed: bool = False
    synthesized: bool = False

    @property
    def scores_changed(self) -> int:
        return len(self.researched) + len(self.rescored)


def _clamp_score(value) -> int:
    return max(0, min(10, int(value)))


def _clamp_confidence(value) -> float | None:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def current_research(session: Session, location: Location, provider: str) -> dict[int, Research]:
    """category_id -> current research row (the country's row for country-scope categories)."""
    country_ids = [cid for (cid,) in session.query(Category.id).filter(Category.scope == "country")]
    condition = Research.location_id == location.id
    if country_ids:
        condition = or_(
            condition,
            and_(Research.location_id.is_(None), Research.country_code == location.country_code,
                 Research.category_id.in_(country_ids)),
        )
    rows = session.query(Research).filter(condition, Research.is_current.is_(True), Research.provider == provider).all()
    return {r.category_id: r for r in rows if r.category_id is not None}


def _usage(ctx: RunContext, location: Location, category: Category | None = None, **extra) -> dict:
    return {"location_id": location.id, "category_id": category.id if category else None,
            "country_code": location.country_code, "run_id": ctx.run_id, **extra}


def _us_citizens_at_home(ctx: RunContext, location: Location) -> bool:
    return ctx.us_citizens and in_us_jurisdiction(location.country_code)


def research_and_score(ctx: RunContext, session: Session, location: Location, category: Category) -> Research:
    """One call: research the category (web search if it needs current facts) and score it."""
    country = session.get(Country, location.country_code)
    is_country = category.scope == "country"

    if category.key == "visa" and _us_citizens_at_home(ctx, location):
        return _us_citizen_visa_evidence(ctx, session, location, category)

    web = ctx.settings.web_search and category.needs_web
    if category.requires_citation and not web:
        raise ValidationFailed(f"{category.name} needs web search (RELOCATION_WEB_SEARCH is off).")

    subject = country_block(country) if (is_country and country) else location_block(location, country)
    with_visas = category.key == "visa"  # one call: visa score + the country's visa pathways
    prompt = category_input(subject_block=subject, category=category, profile=ctx.profile, web_search=web,
                            us_citizens_at_home=_us_citizens_at_home(ctx, location))
    if with_visas:
        prompt += "\n\n" + VISA_PATHWAYS_ASK
    request = LlmRequest(
        route="research",
        model=ctx.settings.research_model,
        instructions=ctx.instructions,
        input=prompt,
        text_format=VisaEvidenceResponse if with_visas else EvidenceResponse,
        max_output_tokens=ctx.settings.visa_max_output_tokens if with_visas else ctx.settings.research_max_output_tokens,
        effort=ctx.settings.research_effort,
        web_search=web,
        max_searches=ctx.settings.max_visa_searches_per_call if with_visas else None,
        usage_context=_usage(ctx, location, category),
    )
    result = ctx.llm.call(request)
    evidence: EvidenceResponse = result.parsed

    model_urls = _dedupe([fact.source_url or "" for fact in evidence.key_facts])
    if web:
        consulted = set(result.cited_urls) | set(result.source_urls)
        source_urls = result.cited_urls or [u for u in model_urls if u in consulted] or result.source_urls[:5]
        if category.requires_citation and not source_urls:
            raise ValidationFailed(f"{category.name}: web search returned no citable sources.")
    else:
        source_urls = model_urls  # unverified: the model's own recollection

    # Don't trust the model to describe its own evidence: we know whether it searched.
    if web:
        source_note = (evidence.source_note or "").strip() or f"Web search {ctx.today.isoformat()}"
        if not source_note.lower().startswith("web"):
            source_note = f"Web search {ctx.today.isoformat()}: {source_note}"
    else:
        source_note = f"Model knowledge (not web-verified), {ctx.today.isoformat()}"

    research = create_research(
        session,
        {
            "location_id": location.id,  # routed to the country for country-scope categories
            "category_id": category.id,
            "content": evidence.summary.strip(),
            "key_facts": [fact.model_dump() for fact in evidence.key_facts],
            "source": source_note[:500],
            "source_urls": source_urls or None,
            "source_checked_at": ctx.today,
            "verification_status": "needs_review",
            "confidence": _clamp_confidence(evidence.confidence),
            "provider": ctx.provider,
            "run_id": ctx.run_id,
        },
    )
    upsert_score(
        session,
        category_id=category.id,
        location_id=location.id,
        provider=ctx.provider,
        score=_clamp_score(evidence.score),
        notes=evidence.score_rationale.strip(),
        method="llm",
        research_id=research.id,
        run_id=ctx.run_id,
    )
    if with_visas:
        _store_visa_items(ctx, session, location, evidence.visas, result)
    return research


VISA_PATHWAYS_ASK = (
    "Also list in `visas` the 2-5 visa or residency pathways most relevant to these people (retiring, not working), "
    "with requirements, timeline, cost and notes, and source_urls for each from the official pages you used."
)


def _store_visa_items(ctx: RunContext, session: Session, location: Location, items, result) -> int:
    consulted = set(result.cited_urls) | set(result.source_urls)
    fallback_urls = result.cited_urls[:3] or result.source_urls[:3]
    entries = []
    for item in items:
        urls = [u for u in _dedupe(item.source_urls or []) if u in consulted] or fallback_urls
        if not urls:
            continue
        data = item.model_dump()
        data.update(source_urls=urls, source_checked_at=ctx.today, verification_status="needs_review",
                    confidence=_clamp_confidence(item.confidence) or 0.65)
        entries.append(data)
    if entries:
        replace_country_visa(session, country=location.country, country_code=location.country_code,
                             entries=entries, provider=ctx.provider, run_id=ctx.run_id)
        ctx.log(f"  [done] {len(entries)} visa type(s) for {location.country}")
    return len(entries)


def _us_citizen_visa_evidence(ctx: RunContext, session: Session, location: Location, category: Category) -> Research:
    research = create_research(
        session,
        {
            "location_id": location.id,
            "category_id": category.id,
            "content": (
                f"U.S. citizens need no visa or residency permit to live in {location.country}. "
                "What matters instead is practical: domicile and state/territory tax residency, "
                "driver's licence and vehicle registration, and health-insurance coverage."
            ),
            "key_facts": [{"fact": "Visa or residency permit needed for U.S. citizens", "value": "None", "source_url": US_RULE_URLS[0]}],
            "source": f"Rule: U.S. citizens may reside in U.S. states and territories (checked {ctx.today.isoformat()})",
            "source_urls": US_RULE_URLS,
            "source_checked_at": ctx.today,
            "verification_status": "verified",
            "verified_by": "rule:us-citizen",
            "confidence": 0.98,
            "provider": ctx.provider,
            "run_id": ctx.run_id,
        },
    )
    upsert_score(session, category_id=category.id, location_id=location.id, provider=ctx.provider, score=10,
                 notes="No visa or residency barrier for U.S. citizens.", method="derived",
                 research_id=research.id, run_id=ctx.run_id)
    return research


def rescore_from_evidence(ctx: RunContext, session: Session, location: Location, category: Category,
                          research: Research) -> None:
    """Re-score from stored evidence (no web search): cheap, for prompt or profile changes."""
    if research.key_facts:
        facts = "\n".join(f"- {f.get('fact')}: {f.get('value') or ''}".rstrip(": ") for f in research.key_facts)
        evidence = f"{research.content}\n\nKey facts:\n{facts}"
    else:  # pre-v2 rows: long free text
        evidence = research.content[:4000]
    country = session.get(Country, location.country_code)
    subject = country_block(country) if (category.scope == "country" and country) else location_block(location, country)
    request = LlmRequest(
        route="rescore",
        model=ctx.settings.research_model,
        instructions=ctx.instructions,
        input=f"{subject}\n\nCategory: {category.name}\n\nScore only from this evidence (return score and score_rationale):\n{evidence}",
        text_format=RescoreResponse,
        max_output_tokens=ctx.settings.rescore_max_output_tokens,
        effort=ctx.settings.research_effort,
        usage_context=_usage(ctx, location, category),
    )
    result: RescoreResponse = ctx.llm.call(request).parsed
    upsert_score(session, category_id=category.id, location_id=location.id, provider=ctx.provider,
                 score=_clamp_score(result.score), notes=result.score_rationale.strip(), method="llm",
                 research_id=research.id, run_id=ctx.run_id)


def refresh_visa_info(ctx: RunContext, session: Session, location: Location, *, force: bool) -> bool:
    """Visa pathways per country; refreshed when older than the visa category's refresh_after_days."""
    country = session.get(Country, location.country_code)
    visa_category = session.query(Category).filter_by(key="visa").first()
    existing = session.query(VisaInfo).filter_by(country_code=location.country_code, provider=ctx.provider).all()
    refresh_days = visa_category.refresh_after_days if visa_category else 90
    if not force and visa_info_is_fresh(existing, refresh_days):
        ctx.log(f"  [skip] Visa info for {location.country} (current)")
        return False

    if _us_citizens_at_home(ctx, location):
        entries = [{
            "visa_type": "No visa required (U.S. citizen, domestic move)",
            "description": f"A U.S. citizen does not need a visa or residency permit to live in {location.country}.",
            "residency_pathway": "Not applicable: citizenship already gives the right to reside.",
            "requirements": "Proof of U.S. citizenship/identity for normal administrative processes.",
            "timeline": "Immediate", "cost": "No visa fees",
            "notes": "Look at domicile, state/territory tax residency and local registration instead.",
            "source_urls": US_RULE_URLS, "source_checked_at": ctx.today,
            "verification_status": "verified", "verified_by": "rule:us-citizen", "confidence": 0.98,
        }]
    else:
        if not ctx.settings.web_search:
            raise ValidationFailed("Visa info needs web search (RELOCATION_WEB_SEARCH is off).")
        extras = ctx.profile.extras_for("visa")
        request = LlmRequest(
            route="visa",
            model=ctx.settings.research_model,
            instructions=ctx.instructions,
            input=(
                f"{country_block(country) if country else location.country}\n\n"
                "List the 2-5 visa or residency pathways most relevant to these people (retiring, not working), "
                "with requirements, timeline, cost and notes. Use current official immigration sources found by "
                "web search; give source_urls for each pathway."
                + (f"\n\nRelevant profile details:\n{extras}" if extras else "")
            ),
            text_format=VisaResponse,
            max_output_tokens=ctx.settings.visa_max_output_tokens,
            effort=ctx.settings.research_effort,
            web_search=True,
            max_searches=ctx.settings.max_visa_searches_per_call,
            usage_context=_usage(ctx, location),
        )
        result = ctx.llm.call(request)
        if not _store_visa_items(ctx, session, location, result.parsed.visas, result):
            raise ValidationFailed(f"No visa pathways with usable sources for {location.country}.")
        return True

    replace_country_visa(session, country=location.country, country_code=location.country_code,
                         entries=entries, provider=ctx.provider, run_id=ctx.run_id)
    ctx.log(f"  [done] {len(entries)} visa type(s) for {location.country}")
    return True


SYNTHESIS_INSTRUCTIONS = """You write the shortlist card for one place a couple is considering for retirement.

Return:
- description: one sentence, 28-42 words, in a glossy travel-magazine voice that is still specific and credible. No numeric scores or ratings.
- pros: exactly 8 strengths, 12-24 words each, most important first.
- cons: exactly 8 honest tradeoffs or risks, 12-24 words each, most important first.
Each pro and con names the category_key it comes from, using only keys listed in the evidence.
Use only the evidence given; do not bring in facts about other places with the same name."""


def synthesize(ctx: RunContext, session: Session, location: Location, *, force_description: bool) -> None:
    """Pros/cons and description in one call (cheaper model)."""
    categories = {c.id: c for c in session.query(Category).order_by(Category.sort_order)}
    research = current_research(session, location, ctx.provider)
    rows = []
    for score in sorted(effective_scores(session, provider=ctx.provider, location_id=location.id),
                        key=lambda s: categories[s.category_id].sort_order):
        category = categories[score.category_id]
        entry = research.get(category.id)
        if entry is not None and entry.key_facts:
            facts = "; ".join(f"{f.get('fact')}: {f.get('value')}" if f.get("value") else str(f.get("fact"))
                              for f in entry.key_facts[:3])
        elif entry is not None:
            facts = entry.content.replace("\n", " ")[:220]
        else:
            facts = ""
        rationale = (score.notes or "").replace("\n", " ")[:240]
        rows.append(f"- {category.key} | {category.name} | score {score.score} | {rationale} | {facts}")
    if not rows:
        raise ValidationFailed("No scores to synthesize from.")

    country = session.get(Country, location.country_code)
    request = LlmRequest(
        route="synthesis",
        model=ctx.settings.synthesis_model,
        instructions=SYNTHESIS_INSTRUCTIONS,
        input=f"{location_block(location, country)}\n\nEvidence (category_key | category | score | why | key facts):\n" + "\n".join(rows),
        text_format=SynthesisResponse,
        max_output_tokens=ctx.settings.synthesis_max_output_tokens,
        effort=ctx.settings.synthesis_effort,
        usage_context=_usage(ctx, location),
    )
    result: SynthesisResponse = ctx.llm.call(request).parsed
    by_key = {c.key: c for c in categories.values()}

    def items(raw, kind):
        out = []
        for item in raw:
            category = by_key.get(item.category_key)
            text = item.text.strip()
            if category is not None and text:
                out.append(ProCon(location_id=location.id, category_id=category.id, type=kind, content=text,
                                  provider=ctx.provider, run_id=ctx.run_id))
        return out[:8]

    pros, cons = items(result.pros, "pro"), items(result.cons, "con")
    if len(pros) < 8 or len(cons) < 8:
        raise ValidationFailed(f"Synthesis returned too few usable items (pros={len(pros)}, cons={len(cons)}).")
    session.query(ProCon).filter_by(location_id=location.id, provider=ctx.provider).delete(synchronize_session=False)
    session.add_all(pros + cons)
    if force_description or not (location.description or "").strip():
        location.description = result.description.strip()
    session.commit()
