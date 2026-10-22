"""OpenAI Responses API calls with structured output, optional web search, retries and usage logging."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from relocation.services.llm_usage import record_llm_call
from relocation.settings import PipelineSettings, get_settings


@dataclass
class LlmRequest:
    route: str  # research / rescore / visa / synthesis
    model: str
    instructions: str  # stable across a run: the cacheable prefix
    input: str  # varies per call: goes after the prefix
    text_format: type[BaseModel]
    max_output_tokens: int
    effort: str | None = None
    web_search: bool = False
    max_searches: int | None = None
    usage_context: dict = field(default_factory=dict)


@dataclass
class LlmResult:
    parsed: Any
    cited_urls: list[str]
    source_urls: list[str]
    web_search_calls: int
    response: Any


class LlmCallFailed(RuntimeError):
    pass


def _get(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def _dedupe(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for url in urls:
        if url and url.startswith(("http://", "https://")) and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def extract_web_evidence(response: Any) -> tuple[list[str], list[str], int]:
    """(cited URLs from url_citation annotations, all consulted source URLs, number of searches)."""
    cited: list[str] = []
    sources: list[str] = []
    searches = 0
    for item in _get(response, "output") or []:
        kind = _get(item, "type")
        if kind == "web_search_call":
            searches += 1
            for source in _get(_get(item, "action"), "sources") or []:
                sources.append(_get(source, "url") or "")
        elif kind == "message":
            for content in _get(item, "content") or []:
                for annotation in _get(content, "annotations") or []:
                    if _get(annotation, "type") == "url_citation":
                        cited.append(_get(annotation, "url") or "")
    return _dedupe(cited), _dedupe(sources), searches


def _is_incomplete_for_length(response: Any) -> bool:
    return _get(response, "status") == "incomplete" and _get(_get(response, "incomplete_details"), "reason") == "max_output_tokens"


def _looks_truncated(exc: Exception) -> bool:
    """The SDK parses before we can look at response.status, so a cut-off answer shows up as bad JSON."""
    text = str(exc)
    return "EOF while parsing" in text or ("json_invalid" in text and "EOF" in text)


def _looks_like_tool_format_conflict(exc: Exception) -> bool:
    text = str(exc).lower()
    return "web_search" in text or ("tool" in text and ("json_schema" in text or "text.format" in text or "structured" in text))


class LlmClient:
    """Thin wrapper around ``client.responses.parse``.

    - Records every attempt in llm_calls (tokens, cached tokens, searches, finish reason).
    - Retries invalid/empty output; after a length cut-off it raises the output budget by 50%.
    - If the API rejects web search combined with structured output, it switches to a
      two-step call (search as free text, then format without tools) for the rest of the run.
    """

    def __init__(
        self,
        client: Any = None,
        settings: PipelineSettings | None = None,
        *,
        provider: str = "openai",
        run_id: int | None = None,
        recorder: Callable[..., None] = record_llm_call,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.settings = settings or get_settings()
        if client is None:
            from openai import OpenAI

            # Pass the key explicitly so OPENAI_API_KEY in .env works, not only in the shell.
            client = OpenAI(api_key=self.settings.openai_api_key) if self.settings.openai_api_key else OpenAI()
        self.client = client
        self.provider = provider
        self.run_id = run_id
        self.recorder = recorder
        self.sleep = sleep
        self.two_step_web_search = False
        self.max_tool_calls_supported = True

    # -- public -----------------------------------------------------------
    def call(self, request: LlmRequest) -> LlmResult:
        if request.web_search and self.two_step_web_search:
            return self._two_step(request)
        try:
            return self._attempts(request, web=request.web_search)
        except _ToolFormatConflict:
            self.two_step_web_search = True
            return self._two_step(request)

    # -- internals ----------------------------------------------------------
    def _kwargs(self, request: LlmRequest, *, budget: int, web: bool, structured: bool, input_text: str) -> dict:
        kwargs: dict[str, Any] = {
            "model": request.model,
            "instructions": request.instructions,
            "input": input_text,
            "max_output_tokens": budget,
        }
        if structured:
            kwargs["text_format"] = request.text_format
        if request.effort:
            kwargs["reasoning"] = {"effort": request.effort}
        if self.settings.service_tier:
            kwargs["service_tier"] = self.settings.service_tier
        if web:
            kwargs["tools"] = [{"type": "web_search", "search_context_size": self.settings.web_context_size}]
            kwargs["include"] = ["web_search_call.action.sources"]
            searches = request.max_searches or self.settings.max_searches_per_call
            if searches and self.max_tool_calls_supported:
                kwargs["max_tool_calls"] = searches
        return kwargs

    def _record(self, request: LlmRequest, *, attempt: int, status: str, started: float, prompt: str,
                budget: int, response: Any = None, error: Exception | None = None, route: str | None = None) -> None:
        ctx = request.usage_context
        self.recorder(
            route=route or request.route,
            model=request.model,
            status=status,
            response=response,
            provider=self.provider,
            attempt=attempt,
            prompt_chars=len(request.instructions) + len(prompt),
            max_output_tokens=budget,
            latency_ms=int((time.monotonic() - started) * 1000),
            error=f"{type(error).__name__}: {error}" if error else None,
            location_id=ctx.get("location_id"),
            category_id=ctx.get("category_id"),
            country_code=ctx.get("country_code"),
            run_id=ctx.get("run_id", self.run_id),
        )

    def _attempts(self, request: LlmRequest, *, web: bool, structured: bool = True,
                  input_text: str | None = None, route: str | None = None) -> LlmResult:
        from openai import BadRequestError, LengthFinishReasonError, RateLimitError

        prompt = request.input if input_text is None else input_text
        budget = request.max_output_tokens
        last_error: Exception | None = None
        for attempt in range(1, self.settings.max_attempts + 1):
            started = time.monotonic()
            response = None
            try:
                kwargs = self._kwargs(request, budget=budget, web=web, structured=structured, input_text=prompt)
                if structured:
                    response = self.client.responses.parse(**kwargs)
                else:
                    response = self.client.responses.create(**kwargs)
                if _is_incomplete_for_length(response):
                    self._record(request, attempt=attempt, status="truncated", started=started, prompt=prompt,
                                 budget=budget, response=response, route=route)
                    budget = int(budget * 1.5)
                    continue
                parsed = response.output_parsed if structured else (_get(response, "output_text") or "")
                if structured and parsed is None:
                    raise ValueError("Structured output was empty")
                self._record(request, attempt=attempt, status="ok", started=started, prompt=prompt,
                             budget=budget, response=response, route=route)
                cited, sources, searches = extract_web_evidence(response)
                return LlmResult(parsed, cited, sources, searches, response)
            except LengthFinishReasonError as exc:
                self._record(request, attempt=attempt, status="truncated", started=started, prompt=prompt,
                             budget=budget, response=response, error=exc, route=route)
                budget = int(budget * 1.5)
                last_error = exc
            except (ValidationError, ValueError) as exc:
                truncated = _looks_truncated(exc)
                self._record(request, attempt=attempt, status="truncated" if truncated else "invalid_output",
                             started=started, prompt=prompt, budget=budget, response=response, error=exc, route=route)
                if truncated:
                    budget = int(budget * 1.5)
                last_error = exc
            except RateLimitError as exc:
                self._record(request, attempt=attempt, status="rate_limited", started=started, prompt=prompt,
                             budget=budget, error=exc, route=route)
                self.sleep(min(60.0, 4.0 * 2 ** (attempt - 1)))
                last_error = exc
            except BadRequestError as exc:
                self._record(request, attempt=attempt, status="error", started=started, prompt=prompt,
                             budget=budget, error=exc, route=route)
                if web and self.max_tool_calls_supported and "max_tool_calls" in str(exc):
                    self.max_tool_calls_supported = False  # model doesn't accept the cap; carry on without it
                    last_error = exc
                    continue
                if web and structured and _looks_like_tool_format_conflict(exc):
                    raise _ToolFormatConflict() from exc
                raise LlmCallFailed(str(exc)) from exc
            except Exception as exc:
                self._record(request, attempt=attempt, status="error", started=started, prompt=prompt,
                             budget=budget, response=response, error=exc, route=route)
                raise
        raise LlmCallFailed(f"{request.route}: no usable output after {self.settings.max_attempts} attempts: {last_error}")

    def _two_step(self, request: LlmRequest) -> LlmResult:
        """Search with free-text output, then turn the notes into the schema without tools."""
        notes = self._attempts(
            request,
            web=True,
            structured=False,
            input_text=request.input + "\n\nWrite concise research notes with dated facts and cite sources inline.",
            route=f"{request.route}_search",
        )
        formatted = self._attempts(
            request,
            web=False,
            input_text=f"{request.input}\n\nUse only these research notes:\n{notes.parsed}",
        )
        return LlmResult(formatted.parsed, notes.cited_urls, notes.source_urls, notes.web_search_calls, formatted.response)


class _ToolFormatConflict(Exception):
    pass
