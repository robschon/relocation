from relocation.enrichment import beach, ocean, runner, swimming
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


def _record_steps(monkeypatch, codes=None):
    calls: list[tuple[str, list[str]]] = []
    codes = codes or {}
    for name, module in (("ocean", ocean), ("swimming", swimming), ("beach", beach)):
        def fake_main(argv=None, _name=name):
            calls.append((_name, list(argv or [])))
            return codes.get(_name, 0)
        monkeypatch.setattr(module, "main", fake_main)
    return calls


def _with_location(monkeypatch, latitude=1.0, longitude=2.0):
    monkeypatch.setattr(
        new_location_enrichment,
        "SessionLocal",
        lambda: DummySession(type("Loc", (), {"latitude": latitude, "longitude": longitude})()),
    )


def test_pipeline_skips_when_disabled(monkeypatch):
    calls = _record_steps(monkeypatch)
    monkeypatch.setenv(new_location_enrichment.AUTO_ENRICH_ENV_VAR, "0")
    _with_location(monkeypatch)
    new_location_enrichment.run_location_post_create_pipeline(123)
    assert calls == []


def test_pipeline_runs_ocean_then_swimming_then_beach_access(monkeypatch):
    calls = _record_steps(monkeypatch)
    monkeypatch.setenv(new_location_enrichment.AUTO_ENRICH_ENV_VAR, "1")
    _with_location(monkeypatch)
    new_location_enrichment.run_location_post_create_pipeline(456)
    assert [name for name, _ in calls] == ["ocean", "swimming", "beach"]
    assert calls[0][1] == ["--location-id", "456", "--request-interval-seconds", "0"]
    assert calls[1][1] == ["--location-id", "456"]
    assert calls[2][1] == ["--location-id", "456", "--request-interval-seconds", "0", "--only-missing"]


def test_pipeline_skips_when_coordinates_are_missing(monkeypatch):
    calls = _record_steps(monkeypatch)
    monkeypatch.setenv(new_location_enrichment.AUTO_ENRICH_ENV_VAR, "1")
    _with_location(monkeypatch, latitude=None, longitude=None)
    new_location_enrichment.run_location_post_create_pipeline(789)
    assert calls == []


def test_ocean_failure_skips_dependent_steps(monkeypatch):
    calls = _record_steps(monkeypatch, codes={"ocean": 2})
    result = runner.enrich_locations([5], log=lambda _msg: None)
    assert [name for name, _ in calls] == ["ocean"]
    assert not result.ok


def test_ocean_nothing_to_do_still_scores(monkeypatch):
    calls = _record_steps(monkeypatch, codes={"ocean": 1})  # 1 = no locations missing ocean data
    result = runner.enrich_locations([5], log=lambda _msg: None)
    assert [name for name, _ in calls] == ["ocean", "swimming", "beach"]
    assert result.ok


def test_step_exception_is_contained(monkeypatch):
    _record_steps(monkeypatch)

    def boom(argv=None):
        raise RuntimeError("overpass down")

    monkeypatch.setattr(beach, "main", boom)
    result = runner.enrich_locations([5], log=lambda _msg: None)
    assert result.exit_codes == {"ocean": 0, "swimming": 0, "beach": 1}
