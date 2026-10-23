from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import event
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from relocation.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


DEFAULT_PROVIDER = "openai"
RUN_KINDS = ("full", "category", "country", "rescore", "backfill", "enrichment")
RUN_STATUSES = ("queued", "running", "completed", "failed", "interrupted")
SCORE_METHODS = ("manual", "llm", "derived")
CATEGORY_SCOPES = ("location", "country")
CATEGORY_KINDS = ("researched", "derived")


def slugify_key(value: str) -> str:
    return "_".join("".join(ch if ch.isalnum() else " " for ch in value.lower()).split())


def _category_key_default(context) -> str:
    return slugify_key(context.get_current_parameters()["name"])[:50]


def _provider_column() -> Mapped[str]:
    return mapped_column(
        String(32),
        nullable=False,
        default=DEFAULT_PROVIDER,
        server_default=DEFAULT_PROVIDER,
    )


def _run_id_column() -> Mapped[int | None]:
    return mapped_column(ForeignKey("research_runs.id", ondelete="SET NULL"))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # URL-safe identifier (e.g. "partner_a"); display_name is what the UI shows.
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    weights: Mapped[list["Weight"]] = relationship(back_populates="user")


class Country(Base):
    """A country or self-governing jurisdiction (e.g. Puerto Rico, parent US), keyed by ISO 3166 alpha-2."""

    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_code: Mapped[str | None] = mapped_column(ForeignKey("countries.code"))
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("name", "country", name="uq_location_name_country"),
        Index("uq_locations_slug", "slug", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.code"), nullable=False)
    # Free-text display label ("Hawaii, the Big Island"); admin1 is the geocoder's state/province.
    region: Mapped[str | None] = mapped_column(String(100))
    admin1: Mapped[str | None] = mapped_column(String(100))
    # Stable, accent-folded identifier ("rincon-puerto-rico"); set automatically on flush.
    slug: Mapped[str | None] = mapped_column(String(240))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    population: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    full_research_ran_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    scores: Mapped[list["Score"]] = relationship(back_populates="location", cascade="all, delete-orphan")
    research_entries: Mapped[list["Research"]] = relationship(back_populates="location", cascade="all, delete-orphan")
    pros_cons: Mapped[list["ProCon"]] = relationship(back_populates="location", cascade="all, delete-orphan")
    ocean_temperatures: Mapped[list["OceanTemperatureMonthly"]] = relationship(
        back_populates="location",
        cascade="all, delete-orphan",
    )


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("scope IN ('location', 'country')", name="ck_category_scope"),
        CheckConstraint("kind IN ('researched', 'derived')", name="ck_category_kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Stable identifier for code to use instead of matching display names.
    key: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, default=_category_key_default)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # country: one research row and score per country, shared by its locations (visa/residency).
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="location", server_default="location")
    # derived: computed from data (ocean temperatures, mapped beaches), never researched or scored by an LLM.
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="researched", server_default="researched")
    needs_web: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("0"))
    requires_citation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("0"))
    # Re-research once evidence is older than this; NULL = keep until forced.
    refresh_after_days: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint("location_id", "category_id", "provider", name="uq_score_loc_cat_provider"),
        CheckConstraint("score >= 0 AND score <= 10", name="ck_score_range"),
        CheckConstraint("method IN ('manual', 'llm', 'derived')", name="ck_score_method"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    provider: Mapped[str] = _provider_column()
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    # How the score was produced, and from what.
    method: Mapped[str] = mapped_column(String(16), nullable=False, default="manual", server_default="manual")
    research_id: Mapped[int | None] = mapped_column(ForeignKey("research.id", ondelete="SET NULL"))
    run_id: Mapped[int | None] = _run_id_column()
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    location: Mapped["Location"] = relationship(back_populates="scores")
    category: Mapped["Category"] = relationship()


class CountryScore(Base):
    """Score for a country-scope category (e.g. visa/residency), shared by every location in that country."""

    __tablename__ = "country_scores"
    __table_args__ = (
        UniqueConstraint("country_code", "category_id", "provider", name="uq_country_score_country_cat_provider"),
        CheckConstraint("score >= 0 AND score <= 10", name="ck_country_score_range"),
        CheckConstraint("method IN ('manual', 'llm', 'derived')", name="ck_country_score_method"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.code"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    provider: Mapped[str] = _provider_column()
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(16), nullable=False, default="manual", server_default="manual")
    research_id: Mapped[int | None] = mapped_column(ForeignKey("research.id", ondelete="SET NULL"))
    run_id: Mapped[int | None] = _run_id_column()
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    category: Mapped["Category"] = relationship()


class Weight(Base):
    __tablename__ = "weights"
    __table_args__ = (
        UniqueConstraint("user_id", "category_id", name="uq_weight_user_cat"),
        CheckConstraint("weight >= 0", name="ck_weight_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    user: Mapped["User"] = relationship(back_populates="weights")
    category: Mapped["Category"] = relationship()


class Research(Base):
    __tablename__ = "research"
    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('verified', 'needs_review', 'stale')",
            name="ck_research_verification_status",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_research_confidence_range",
        ),
        CheckConstraint(
            "(location_id IS NULL) != (country_code IS NULL)",
            name="ck_research_subject",
        ),
        Index("ix_research_location_category", "location_id", "category_id"),
        Index("ix_research_country_category", "country_code", "category_id"),
        # One current country-level row per country/category/provider.
        Index(
            "uq_research_country_current",
            "country_code",
            "category_id",
            "provider",
            unique=True,
            sqlite_where=text("is_current = 1 AND location_id IS NULL"),
        ),
        # At most one current evidence row per location/category/provider.
        Index(
            "uq_research_current",
            "location_id",
            "category_id",
            "provider",
            unique=True,
            sqlite_where=text("is_current = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Exactly one subject: a location, or a country for country-scope categories.
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    country_code: Mapped[str | None] = mapped_column(ForeignKey("countries.code"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    provider: Mapped[str] = _provider_column()
    run_id: Mapped[int | None] = _run_id_column()
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("1"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # v2 research: [{"fact": ..., "value": ..., "source_url": ...}, ...]; NULL for older rows.
    key_facts: Mapped[list[dict] | None] = mapped_column(JSON)
    source: Mapped[str | None] = mapped_column(String(500))
    source_published_at: Mapped[date | None] = mapped_column("source_date", Date)
    source_urls: Mapped[list[str] | None] = mapped_column(JSON)
    source_checked_at: Mapped[date | None] = mapped_column(Date)
    verification_status: Mapped[str] = mapped_column(String(32), default="needs_review", nullable=False)
    # Who marked it verified/reviewed: a person, a rule, or "model-legacy" for pre-Phase-1 model claims.
    verified_by: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    location: Mapped["Location | None"] = relationship(back_populates="research_entries")
    category: Mapped["Category | None"] = relationship()


class ProCon(Base):
    __tablename__ = "pros_cons"
    __table_args__ = (
        CheckConstraint("type IN ('pro', 'con')", name="ck_procon_type"),
        Index("ix_pros_cons_location", "location_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    provider: Mapped[str] = _provider_column()
    run_id: Mapped[int | None] = _run_id_column()
    type: Mapped[str] = mapped_column(String(4), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    location: Mapped["Location"] = relationship(back_populates="pros_cons")
    category: Mapped["Category | None"] = relationship()


class VisaInfo(Base):
    __tablename__ = "visa_info"
    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('verified', 'needs_review', 'stale')",
            name="ck_visa_verification_status",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_visa_confidence_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.code"), nullable=False)
    provider: Mapped[str] = _provider_column()
    run_id: Mapped[int | None] = _run_id_column()
    visa_type: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    residency_pathway: Mapped[str | None] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text)
    timeline: Mapped[str | None] = mapped_column(String(200))
    cost: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    source_urls: Mapped[list[str] | None] = mapped_column(JSON)
    source_published_at: Mapped[date | None] = mapped_column(Date)
    source_checked_at: Mapped[date | None] = mapped_column(Date)
    verification_status: Mapped[str] = mapped_column(String(32), default="needs_review", nullable=False)
    verified_by: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)


class ProfileResponse(Base):
    __tablename__ = "profile_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    section: Mapped[str] = mapped_column(String(100), nullable=False)
    question_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)


class OceanTemperatureMonthly(Base):
    __tablename__ = "ocean_temperature_monthly"
    __table_args__ = (
        UniqueConstraint(
            "location_id",
            "month",
            "baseline_start_year",
            "baseline_end_year",
            "source_dataset",
            name="uq_ocean_temp_loc_month_baseline_source",
        ),
        CheckConstraint("month >= 1 AND month <= 12", name="ck_ocean_temp_month_range"),
        CheckConstraint("avg_temp_c >= -2 AND avg_temp_c <= 40", name="ck_ocean_temp_avg_range"),
        CheckConstraint(
            "min_temp_c IS NULL OR (min_temp_c >= -2 AND min_temp_c <= 40)",
            name="ck_ocean_temp_min_range",
        ),
        CheckConstraint(
            "max_temp_c IS NULL OR (max_temp_c >= -2 AND max_temp_c <= 40)",
            name="ck_ocean_temp_max_range",
        ),
        CheckConstraint("sample_count >= 0", name="ck_ocean_temp_sample_count_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_temp_c: Mapped[float] = mapped_column(Float, nullable=False)
    min_temp_c: Mapped[float | None] = mapped_column(Float)
    max_temp_c: Mapped[float | None] = mapped_column(Float)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_end_year: Mapped[int] = mapped_column(Integer, nullable=False)
    source_dataset: Mapped[str] = mapped_column(String(120), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))
    source_checked_at: Mapped[date] = mapped_column(Date, nullable=False)
    grid_lat: Mapped[float | None] = mapped_column(Float)
    grid_lon: Mapped[float | None] = mapped_column(Float)
    grid_distance_km: Mapped[float | None] = mapped_column(Float)
    quality_flag: Mapped[str] = mapped_column(String(32), nullable=False, default="ok")
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    location: Mapped["Location"] = relationship(back_populates="ocean_temperatures")


class LlmCall(Base):
    """One request to an LLM provider, with token usage, for cost tracking."""

    __tablename__ = "llm_calls"
    __table_args__ = (
        Index("ix_llm_calls_route_created", "route", "created_at"),
        Index("ix_llm_calls_location", "location_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int | None] = _run_id_column()
    route: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="openai")
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    country_code: Mapped[str | None] = mapped_column(String(2))
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    finish_reason: Mapped[str | None] = mapped_column(String(64))
    prompt_chars: Mapped[int | None] = mapped_column(Integer)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    cached_input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    web_search_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class ResearchRun(Base):
    """One execution of a research/scoring pipeline step: who ran what, with which model, and how it went.

    Research, scores, pros/cons, visa rows and LLM calls point back to the run that produced them.
    Full-research jobs started from the UI are runs with kind="full".
    """

    __tablename__ = "research_runs"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('full', 'category', 'country', 'rescore', 'backfill', 'enrichment')",
            name="ck_research_run_kind",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'interrupted')",
            name="ck_research_run_status",
        ),
        Index("ix_research_runs_location_started", "location_id", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"))
    country_code: Mapped[str | None] = mapped_column(String(2))
    provider: Mapped[str] = _provider_column()
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    step: Mapped[str | None] = mapped_column(String(200))
    error: Mapped[str | None] = mapped_column(Text)
    # Last few hundred lines of output, for the jobs page.
    log_tail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column()

    location: Mapped["Location | None"] = relationship()


_COUNTRY_LINKED = ("Location", "VisaInfo", "Research", "CountryScore")


@event.listens_for(Session, "before_flush")
def _ensure_country_rows(session: Session, _flush_context, _instances) -> None:
    """Create ``countries`` rows on demand for any country code being written.

    Locations, visa rows, country research and country scores reference
    countries.code; this keeps every write path (API, CLI, scripts, seed) valid
    without each one having to insert the country first.
    """
    from relocation.countries import PARENT_COUNTRY_CODE, country_name_from_code

    from sqlalchemy import inspect as sa_inspect

    new_scores = [obj for obj in session.new if isinstance(obj, Score)]
    changed_to_llm = [
        obj
        for obj in session.dirty
        if isinstance(obj, Score) and obj.method == "llm" and sa_inspect(obj).attrs.method.history.has_changes()
    ]
    if new_scores or changed_to_llm:
        with session.no_autoflush:
            for score in new_scores:
                category = session.get(Category, score.category_id)
                if category is not None and category.scope == "country":
                    raise ValueError(
                        f"{category.name} is scored per country; write a CountryScore "
                        "(the API's POST /scores does this when given a location)."
                    )
            for score in new_scores + changed_to_llm:
                category = session.get(Category, score.category_id)
                if category is not None and category.kind == "derived" and score.method == "llm":
                    raise ValueError(f"{category.name} is computed from data; LLM scores are not accepted.")

    codes: set[str] = set()
    for obj in list(session.new) + list(session.dirty):
        if type(obj).__name__ in _COUNTRY_LINKED and getattr(obj, "country_code", None):
            codes.add(obj.country_code)
    pending = {obj.code for obj in session.new if isinstance(obj, Country)}
    codes -= pending
    _assign_location_slugs(session)
    if not codes:
        return
    with session.no_autoflush:
        for code in sorted(codes):
            chain = [code]
            while PARENT_COUNTRY_CODE.get(chain[-1]):
                chain.append(PARENT_COUNTRY_CODE[chain[-1]])
            for item in reversed(chain):  # parents first
                if item in pending or session.get(Country, item) is not None:
                    continue
                session.add(
                    Country(
                        code=item,
                        name=country_name_from_code(item) or item,
                        parent_code=PARENT_COUNTRY_CODE.get(item),
                    )
                )
                pending.add(item)


def _assign_location_slugs(session: Session) -> None:
    """Give new locations, and ones whose name or country changed, a unique slug."""
    from sqlalchemy import inspect as sa_inspect, select

    from relocation.countries import country_name_from_code
    from relocation.slugs import location_slug, slugify

    targets = [obj for obj in session.new if isinstance(obj, Location)]
    for obj in session.dirty:
        if isinstance(obj, Location):
            state = sa_inspect(obj)
            if not obj.slug or any(state.attrs[name].history.has_changes() for name in ("name", "country", "country_code")):
                targets.append(obj)
    if not targets:
        return
    claimed = {obj.slug for obj in session.new if isinstance(obj, Location) and obj.slug and obj not in targets}
    with session.no_autoflush:
        for obj in targets:
            country = session.get(Country, obj.country_code) if obj.country_code else None
            country_name = country.name if country else (country_name_from_code(obj.country_code) or obj.country)
            base = location_slug(obj.name, country_name)
            if obj.slug == base:
                claimed.add(base)
                continue

            def taken(candidate: str, current=obj) -> bool:
                if candidate in claimed:
                    return True
                other = session.execute(select(Location.id).where(Location.slug == candidate)).scalar()
                return other is not None and other != current.id

            slug = base
            if taken(slug) and obj.region:
                slug = f"{base}-{slugify(obj.region)}"
            suffix = 2
            while taken(slug):
                slug = f"{base}-{suffix}"
                suffix += 1
            obj.slug = slug
            claimed.add(slug)
