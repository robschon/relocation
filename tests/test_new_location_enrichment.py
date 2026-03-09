import subprocess

from relocation.services import new_location_enrichment


def test_pipeline_skips_when_disabled(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        calls.append(args[0])
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")

    monkeypatch.setenv(new_location_enrichment.AUTO_ENRICH_ENV_VAR, "0")
    monkeypatch.setattr(subprocess, "run", fake_run)

    new_location_enrichment.run_location_post_create_pipeline(123)

    assert calls == []


def test_pipeline_runs_ocean_then_swimming(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003
        calls.append(args[0])
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="ok", stderr="")

    monkeypatch.setenv(new_location_enrichment.AUTO_ENRICH_ENV_VAR, "1")
    monkeypatch.setattr(subprocess, "run", fake_run)

    new_location_enrichment.run_location_post_create_pipeline(456)

    assert len(calls) == 2
    assert "update_ocean_temperatures.py" in calls[0][1]
    assert calls[0][2:6] == ["--location-id", "456", "--request-interval-seconds", "0"]
    assert calls[0][-1] == "--only-missing"
    assert "update_swimming_scores.py" in calls[1][1]
    assert calls[1][-2:] == ["--location-id", "456"]
