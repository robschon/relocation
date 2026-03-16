from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import research_location_openai as research_openai


class DummyParsedResponse:
    def __init__(self, parsed):
        self.output_parsed = parsed


class DummyResponses:
    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    def parse(self, **kwargs):
        self.calls += 1
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return DummyParsedResponse(result)


class DummyClient:
    def __init__(self, results):
        self.responses = DummyResponses(results)


def test_generate_structured_output_returns_parsed_model():
    parsed = research_openai.CategoryResearchResponse(
        content="Research notes",
        source="Checked March 2026",
    )
    client = DummyClient([parsed])

    result = research_openai.generate_structured_output(
        client,
        "prompt",
        text_format=research_openai.CategoryResearchResponse,
    )

    assert result == parsed
    assert client.responses.calls == 1


def test_generate_structured_output_retries_on_validation_error(monkeypatch):
    monkeypatch.setattr(research_openai, "MAX_RETRIES", 1)
    monkeypatch.setattr(research_openai.time, "sleep", lambda _: None)

    parsed = research_openai.BespokeDescriptionResponse(description="A bright coastal city.")
    client = DummyClient([ValueError("invalid structured output"), parsed])

    result = research_openai.generate_structured_output(
        client,
        "prompt",
        text_format=research_openai.BespokeDescriptionResponse,
    )

    assert result == parsed
    assert client.responses.calls == 2
