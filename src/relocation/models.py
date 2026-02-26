from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from relocation.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    weights: Mapped[list["Weight"]] = relationship(back_populates="user")


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("name", "country", name="uq_location_name_country"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str | None] = mapped_column(String(100))
    population: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    scores: Mapped[list["Score"]] = relationship(back_populates="location", cascade="all, delete-orphan")
    research_entries: Mapped[list["Research"]] = relationship(back_populates="location", cascade="all, delete-orphan")
    pros_cons: Mapped[list["ProCon"]] = relationship(back_populates="location", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint("location_id", "category_id", name="uq_score_loc_cat"),
        CheckConstraint("score >= 1 AND score <= 10", name="ck_score_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    location: Mapped["Location"] = relationship(back_populates="scores")
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(500))
    source_date: Mapped[datetime | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    location: Mapped["Location"] = relationship(back_populates="research_entries")
    category: Mapped["Category | None"] = relationship()


class ProCon(Base):
    __tablename__ = "pros_cons"
    __table_args__ = (
        CheckConstraint("type IN ('pro', 'con')", name="ck_procon_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    type: Mapped[str] = mapped_column(String(4), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    location: Mapped["Location"] = relationship(back_populates="pros_cons")
    category: Mapped["Category | None"] = relationship()


class VisaInfo(Base):
    __tablename__ = "visa_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    visa_type: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    residency_pathway: Mapped[str | None] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text)
    timeline: Mapped[str | None] = mapped_column(String(200))
    cost: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
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
