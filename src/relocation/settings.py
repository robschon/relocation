"""Pipeline settings, read from the environment and an optional .env file at the project root.

    OPENAI_API_KEY                   required for research runs
    RELOCATION_RESEARCH_MODEL        research + scoring model (falls back to OPENAI_MODEL, then gpt-5.4)
    RELOCATION_SYNTHESIS_MODEL       pros/cons + description model (default gpt-5.4-mini)
    RELOCATION_RESEARCH_EFFORT       reasoning effort for research (unset = model default)
    RELOCATION_SYNTHESIS_EFFORT      reasoning effort for synthesis (unset = model default)
    RELOCATION_SERVICE_TIER          e.g. "flex" for ~half-price, slower bulk runs (unset = default)
    RELOCATION_WEB_SEARCH            "1" (default) to use web search for categories with needs_web
    RELOCATION_WEB_CONTEXT_SIZE      web search context: low (default) / medium / high
    RELOCATION_MAX_SEARCHES          web searches allowed per call (default 1; visa calls: RELOCATION_MAX_VISA_SEARCHES, 2)
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from relocation.config import PROJECT_ROOT


class PipelineSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    # Shell environment wins over .env (pydantic-settings precedence).
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY", repr=False)
    research_model: str = Field(
        default="gpt-5.4", validation_alias=AliasChoices("RELOCATION_RESEARCH_MODEL", "OPENAI_MODEL")
    )
    synthesis_model: str = Field(default="gpt-5.4-mini", validation_alias="RELOCATION_SYNTHESIS_MODEL")
    research_effort: str | None = Field(default=None, validation_alias="RELOCATION_RESEARCH_EFFORT")
    synthesis_effort: str | None = Field(default=None, validation_alias="RELOCATION_SYNTHESIS_EFFORT")
    service_tier: str | None = Field(default=None, validation_alias="RELOCATION_SERVICE_TIER")
    web_search: bool = Field(default=True, validation_alias="RELOCATION_WEB_SEARCH")
    web_context_size: str = Field(default="low", validation_alias="RELOCATION_WEB_CONTEXT_SIZE")
    # Each search's results come back as input tokens (~8-10k each), so cap searches per call.
    max_searches_per_call: int = Field(default=1, validation_alias="RELOCATION_MAX_SEARCHES")
    max_visa_searches_per_call: int = Field(default=2, validation_alias="RELOCATION_MAX_VISA_SEARCHES")

    # Output budgets. Retries after a length cut-off raise these by 50%.
    research_max_output_tokens: int = 2000
    visa_max_output_tokens: int = 3000
    synthesis_max_output_tokens: int = 1800
    rescore_max_output_tokens: int = 300
    max_attempts: int = 3

    prompt_version: str = "v2"
    summary_words: int = 250


@lru_cache
def get_settings() -> PipelineSettings:
    return PipelineSettings()
