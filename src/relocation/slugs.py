"""URL- and filename-safe slugs for locations ("Rincón", "Puerto Rico" -> "rincon-puerto-rico")."""

from __future__ import annotations

import re
import unicodedata

# Letters NFKD does not decompose into ASCII.
_EXTRA_FOLDS = str.maketrans({"ß": "ss", "ø": "o", "Ø": "o", "æ": "ae", "Æ": "ae", "ł": "l", "Ł": "l", "đ": "d", "Đ": "d", "ı": "i"})


def slugify(value: str | None) -> str:
    folded = unicodedata.normalize("NFKD", (value or "").translate(_EXTRA_FOLDS))
    ascii_only = folded.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")


def location_slug(name: str, country_name: str | None) -> str:
    return "-".join(part for part in (slugify(name), slugify(country_name)) if part) or "location"
