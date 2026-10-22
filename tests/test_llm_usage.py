"""Token-usage recording for LLM calls."""

from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from relocation.database import Base, enable_sqlite_foreign_keys
from relocation.models import LlmCall
from relocation.services.llm_usage import extract_usage, record_llm_call



def _fake_response(**overrides):
    usage = SimpleNamespace(
        input_tokens=1200,
        output_tokens=900,
        total_tokens=2100,
        input_tokens_details=SimpleNamespace(cached_tokens=1024),
        output_tokens_details=SimpleNamespace(reasoning_tokens=300),
    )
    fields = {
        "usage": usage,
        "status": "completed",
        "incomplete_details": None,
        "output": [SimpleNamespace(type="web_search_call"), SimpleNamespace(type="message")],
        "output_parsed": None,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def test_extract_usage_reads_responses_api_fields():
    usage = extract_usage(_fake_response())
    assert usage == {
        "input_tokens": 1200,
        "cached_input_tokens": 1024,
        "output_tokens": 900,
        "reasoning_tokens": 300,
        "total_tokens": 2100,
        "web_search_calls": 1,
        "finish_reason": "completed",
    }


def test_extract_usage_tolerates_missing_usage():
    usage = extract_usage(SimpleNamespace(output_parsed="x"))
    assert usage["input_tokens"] is None
    assert usage["web_search_calls"] == 0


def test_extract_usage_reports_incomplete_reason():
    response = _fake_response(status="incomplete", incomplete_details=SimpleNamespace(reason="max_output_tokens"))
    assert extract_usage(response)["finish_reason"] == "max_output_tokens"


def test_record_llm_call_writes_row(monkeypatch):
    monkeypatch.setenv("RELOCATION_LLM_USAGE_LOG", "1")
    engine = enable_sqlite_foreign_keys(
        create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    record_llm_call(
        route="research",
        model="test-model",
        status="ok",
        response=_fake_response(),
        prompt_chars=5000,
        session_factory=Session,
    )

    with Session() as session:
        row = session.query(LlmCall).one()
    assert (row.route, row.model, row.status) == ("research", "test-model", "ok")
    assert (row.input_tokens, row.cached_input_tokens, row.output_tokens, row.reasoning_tokens) == (1200, 1024, 900, 300)
    assert row.web_search_calls == 1
    assert row.prompt_chars == 5000


def test_record_llm_call_disabled_by_env(monkeypatch):
    monkeypatch.setenv("RELOCATION_LLM_USAGE_LOG", "0")

    def boom():
        raise AssertionError("session should not be opened when logging is disabled")

    record_llm_call(route="x", model="m", status="ok", session_factory=boom)
