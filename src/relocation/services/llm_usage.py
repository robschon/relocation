"""Record token usage for every LLM request in the ``llm_calls`` table.

Recording is best-effort: a failure to write a usage row is logged and never
breaks the research pipeline. Set ``RELOCATION_LLM_USAGE_LOG=0`` to disable it
(the test suite does this).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from relocation.models import LlmCall

LOGGER = logging.getLogger(__name__)
USAGE_LOG_ENV_VAR = "RELOCATION_LLM_USAGE_LOG"
_DISABLED_VALUES = {"0", "false", "no", "off"}


def usage_logging_enabled() -> bool:
    return os.getenv(USAGE_LOG_ENV_VAR, "1").strip().lower() not in _DISABLED_VALUES


def _get(obj: Any, *path: str) -> Any:
    """Read nested attributes or dict keys, returning None if any step is missing."""
    for key in path:
        if obj is None:
            return None
        obj = obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)
    return obj


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def extract_usage(response: Any) -> dict[str, Any]:
    """Pull token counts and completion state out of an OpenAI Responses API response."""
    output_items = _get(response, "output") or []
    web_search_calls = sum(1 for item in output_items if _get(item, "type") == "web_search_call")
    return {
        "input_tokens": _as_int(_get(response, "usage", "input_tokens")),
        "cached_input_tokens": _as_int(_get(response, "usage", "input_tokens_details", "cached_tokens")),
        "output_tokens": _as_int(_get(response, "usage", "output_tokens")),
        "reasoning_tokens": _as_int(_get(response, "usage", "output_tokens_details", "reasoning_tokens")),
        "total_tokens": _as_int(_get(response, "usage", "total_tokens")),
        "web_search_calls": web_search_calls,
        "finish_reason": _get(response, "incomplete_details", "reason") or _get(response, "status"),
    }


def record_llm_call(
    *,
    route: str,
    model: str,
    status: str,
    response: Any = None,
    provider: str = "openai",
    attempt: int = 1,
    prompt_chars: int | None = None,
    max_output_tokens: int | None = None,
    latency_ms: int | None = None,
    error: str | None = None,
    location_id: int | None = None,
    category_id: int | None = None,
    country_code: str | None = None,
    run_id: int | None = None,
    session_factory: Callable[[], Session] | None = None,
) -> None:
    """Write one ``llm_calls`` row. Never raises."""
    if not usage_logging_enabled():
        return
    try:
        usage = extract_usage(response) if response is not None else {}
        if session_factory is None:
            from relocation.database import SessionLocal

            session_factory = SessionLocal
        with session_factory() as session:
            session.add(
                LlmCall(
                    run_id=run_id,
                    route=route,
                    provider=provider,
                    model=model,
                    location_id=location_id,
                    category_id=category_id,
                    country_code=country_code,
                    attempt=attempt,
                    status=status,
                    prompt_chars=prompt_chars,
                    max_output_tokens=max_output_tokens,
                    latency_ms=latency_ms,
                    error=(error or None) and error[:2000],
                    web_search_calls=usage.pop("web_search_calls", 0) or 0,
                    **usage,
                )
            )
            session.commit()
    except Exception as exc:  # pragma: no cover - defensive; logging must not break research
        LOGGER.warning("Could not record LLM usage (%s): %s", route, exc)
