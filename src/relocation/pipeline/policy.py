"""When to (re)research, and simple profile-derived rules."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from relocation.countries import US_CITIZEN_HOME_JURISDICTIONS


def _age_days(stamp) -> float | None:
    if not stamp:
        return None
    try:
        when = stamp if isinstance(stamp, datetime) else datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - when).total_seconds() / 86400


def evidence_age_days(entry) -> float | None:
    """Age of a research row or visa row (dict or ORM object), by source_checked_at then created_at."""
    get = entry.get if isinstance(entry, dict) else lambda key: getattr(entry, key, None)
    checked = get("source_checked_at")
    if checked is not None and not isinstance(checked, (str, datetime)):
        checked = datetime(checked.year, checked.month, checked.day)  # a date
    return _age_days(checked or get("created_at"))


def research_decision(refresh_after_days: int | None, existing, force: bool) -> tuple[bool, str]:
    """Whether to (re)research a category, and why."""
    if force:
        return True, "forced"
    if existing is None:
        return True, "no research yet"
    if refresh_after_days is not None:
        age = evidence_age_days(existing)
        if age is None or age > refresh_after_days:
            return True, f"older than {refresh_after_days} days"
    return False, "current"


def visa_info_is_fresh(existing_visa: list, refresh_after_days: int | None) -> bool:
    if not existing_visa or refresh_after_days is None:
        return bool(existing_visa)
    ages = [age for age in (evidence_age_days(v) for v in existing_visa) if age is not None]
    return bool(ages) and min(ages) <= refresh_after_days


_US_CITIZEN_PATTERNS = [
    r"\bus citizens?\b",
    r"\bu\.s\. citizens?\b",
    r"\bus citizenship\b",
    r"\bu\.s\. citizenship\b",
    r"\bamerican citizens?\b",
    r"\bunited states citizens?\b",
    r"\bus passports?\b",
    r"\bu\.s\. passports?\b",
    r"\bnever lived outside of the us\b",
    r"\bnever lived outside of the u\.s\.\b",
    r"\bcurrently live in (new york|nyc|san francisco|bay area)\b",
]


def profile_suggests_us_citizens(answers: dict[str, str]) -> bool:
    combined = " ".join(answers.values()).lower()
    return any(re.search(pattern, combined) for pattern in _US_CITIZEN_PATTERNS)


def in_us_jurisdiction(country_code: str | None) -> bool:
    return (country_code or "").upper() in US_CITIZEN_HOME_JURISDICTIONS
