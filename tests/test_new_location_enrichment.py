import subprocess

from relocation.services import new_location_enrichment


class DummySession:
    def __init__(self, location):
        self._location = location

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, model, location_id):  # noqa: ARG002
        return self._location


def test_pipeline_skips_when_disabled(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        calls.append(args[0])
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")

    monkeypatch.setenv(new_location_enrichment.AUTO_ENRICH_ENV_VAR, "0")
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        new_location_enrichment,
        "SessionLocal",
        lambda: DummySession(type("Loc", (), {"latitude": 1.0, "longitude": 2.0})()),
    )

    new_location_enrichment.run_location_post_create_pipeline(123)

    assert calls == []


def test_pipeline_runs_ocean_then_swimming_then_beach_access(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        calls.append(args[0])
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="ok", stderr="")

    monkeypatch.setenv(new_location_enrichment.AUTO_ENRICH_ENV_VAR, "1")
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        new_location_enrichment,
        "SessionLocal",
        lambda: DummySession(type("Loc", (), {"latitude": 1.0, "longitude": 2.0})()),
    )

    new_location_enrichment.run_location_post_create_pipeline(456)

    assert len(calls) == 3
    assert "update_ocean_temperatures.py" in calls[0][1]
    assert calls[0][2:6] == ["--location-id", "456", "--request-interval-seconds", "0"]
    assert calls[0][-1] == "--only-missing"
    assert "update_swimming_scores.py" in calls[1][1]
    assert calls[1][-2:] == ["--location-id", "456"]
    assert "update_beach_accessibility_scores.py" in calls[2][1]
    assert calls[2][-2:] == ["--location-id", "456"]


def test_pipeline_skips_when_coordinates_are_missing(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        calls.append(args[0])
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="ok", stderr="")

    monkeypatch.setenv(new_location_enrichment.AUTO_ENRICH_ENV_VAR, "1")
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        new_location_enrichment,
        "SessionLocal",
        lambda: DummySession(type("Loc", (), {"latitude": None, "longitude": None})()),
    )

    new_location_enrichment.run_location_post_create_pipeline(789)

    assert calls == []
