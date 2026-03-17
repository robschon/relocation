from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import full_research_location_openai as full_research_openai
import research_location_openai as research_openai


class DummyParsedResponse:
    def __init__(self, parsed):
        self.output_parsed = parsed


class DummyResponses:
    def __init__(self, results):
        self._results = list(results)
        self.calls = 0
        self.kwargs_history = []

    def parse(self, **kwargs):
        self.calls += 1
        self.kwargs_history.append(kwargs)
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


def test_generate_structured_output_adds_retry_instructions(monkeypatch):
    monkeypatch.setattr(research_openai, "MAX_RETRIES", 1)
    monkeypatch.setattr(research_openai.time, "sleep", lambda _: None)

    parsed = research_openai.BespokeDescriptionResponse(description="A bright coastal city.")
    client = DummyClient([ValueError("invalid structured output"), parsed])

    research_openai.generate_structured_output(
        client,
        "prompt",
        text_format=research_openai.BespokeDescriptionResponse,
    )

    assert client.responses.calls == 2
    assert client.responses.kwargs_history[0]["input"] == "prompt"
    assert "Return only valid JSON matching the schema exactly." in client.responses.kwargs_history[1]["input"]


def test_format_location_context_includes_region_and_coordinates():
    location = {
        "name": "Alcalá",
        "country": "Spain",
        "region": "Tenerife, Canary Islands",
        "latitude": 28.20201,
        "longitude": -16.82779,
    }

    context = research_openai.format_location_context(location)

    assert "Tenerife, Canary Islands" in context
    assert "28.20201, -16.82779" in context
    assert "do not substitute another same-name place" in context


def test_research_category_prompt_anchors_exact_location(monkeypatch):
    captured: dict[str, str] = {}

    def fake_generate_structured_output(client, prompt, **kwargs):
        captured["prompt"] = prompt
        return research_openai.CategoryResearchResponse(
            content="Coastal climate with mild winters.",
            source="Checked March 2026",
        )

    monkeypatch.setattr(research_openai, "generate_structured_output", fake_generate_structured_output)

    location = {
        "name": "Alcalá",
        "country": "Spain",
        "region": "Tenerife, Canary Islands",
        "latitude": 28.20201,
        "longitude": -16.82779,
    }
    category = {"name": "Climate / weather", "description": "Temperature and seasons"}

    result = research_openai.research_category(client=object(), location=location, category=category)

    assert result["content"] == "Coastal climate with mild winters."
    assert "Region: Tenerife, Canary Islands" in captured["prompt"]
    assert "Coordinates: 28.20201, -16.82779" in captured["prompt"]
    assert "Do not switch to another city/town/municipality" in captured["prompt"]


def test_score_category_prompt_anchors_exact_location(monkeypatch):
    captured: dict[str, str] = {}

    def fake_generate_structured_output(client, prompt, **kwargs):
        captured["prompt"] = prompt
        return full_research_openai.ScoreCategoryResponse(score=8, notes="Strong climate.")

    monkeypatch.setattr(full_research_openai, "generate_structured_output", fake_generate_structured_output)

    location = {
        "name": "Alcalá",
        "country": "Spain",
        "region": "Tenerife, Canary Islands",
        "latitude": 28.20201,
        "longitude": -16.82779,
    }
    category = {"name": "Climate / weather", "description": "Temperature and seasons"}

    result = full_research_openai.score_category(
        client=object(),
        location=location,
        category=category,
        research_content="Mild coastal climate with no regular frost.",
    )

    assert result == {"score": 8, "notes": "Strong climate."}
    assert "Target location (use this exact place" in captured["prompt"]
    assert "Region: Tenerife, Canary Islands" in captured["prompt"]
    assert "Score only the exact location above" in captured["prompt"]
