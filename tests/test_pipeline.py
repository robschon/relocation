"""Pipeline v2 with a fake OpenAI client: no network, no API key."""

from datetime import date
from types import SimpleNamespace as NS

import httpx
import pytest
from openai import BadRequestError
from sqlalchemy.orm import sessionmaker

from relocation.models import Category, Location, LlmCall, ProCon, ProfileResponse, Research, ResearchRun, VisaInfo
from relocation.pipeline import schemas
from relocation.pipeline.context import Profile, category_input, location_block
from relocation.pipeline.llm import LlmClient, LlmRequest, extract_web_evidence
from relocation.pipeline.runner import run_location, run_rescore
from relocation.services.effective_scores import effective_scores
from relocation.services.llm_usage import record_llm_call
from relocation.settings import PipelineSettings, get_settings

CITED = "https://www.gob.pe/migraciones"
SOURCE = "https://example.org/guide"


def _usage():
    return NS(input_tokens=1000, output_tokens=200, total_tokens=1200,
              input_tokens_details=NS(cached_tokens=0), output_tokens_details=NS(reasoning_tokens=0))


def _response(parsed, *, web=False, status="completed", reason=None, text=None):
    output = []
    if web:
        output.append(NS(type="web_search_call", action=NS(type="search", sources=[NS(url=SOURCE), NS(url=CITED)])))
    output.append(NS(type="message", content=[NS(type="output_text", text="{}",
                                                   annotations=[NS(type="url_citation", url=CITED, title="Migraciones")] if web else [])]))
    return NS(output_parsed=parsed, output=output, status=status, usage=_usage(), output_text=text,
              incomplete_details=NS(reason=reason) if reason else None)


class FakeResponses:
    def __init__(self, owner):
        self.owner = owner

    def parse(self, **kwargs):
        self.owner.calls.append(kwargs)
        if self.owner.reject_web_with_format and kwargs.get("tools"):
            raise BadRequestError("web_search is not supported with text.format json_schema",
                                  response=httpx.Response(400, request=httpx.Request("POST", "https://x")), body=None)
        fmt = kwargs["text_format"]
        web = bool(kwargs.get("tools"))
        if issubclass(fmt, schemas.EvidenceResponse):
            fields = dict(summary="Short summary.", key_facts=[schemas.KeyFact(fact="Rent", value="$900", source_url=CITED if web else "https://remembered.example")],
                          score=self.owner.score, score_rationale="Because.", confidence=0.7,
                          source_note="Web search 2026-10-22: Britannica")  # models claim this even without search
            if fmt is schemas.VisaEvidenceResponse:
                fields["visas"] = [schemas.VisaItem(visa_type="Rentista", source_urls=[CITED], confidence=0.7)]
            parsed = fmt(**fields)
        elif fmt is schemas.VisaResponse:
            parsed = fmt(visas=[schemas.VisaItem(visa_type="Rentista", source_urls=[CITED], confidence=0.7)])
        elif fmt is schemas.RescoreResponse:
            parsed = fmt(score=3, score_rationale="Rescored.")
        elif fmt is schemas.SynthesisResponse:
            items = [schemas.ProConItem(category_key="food", text=f"item {i}") for i in range(8)]
            parsed = fmt(description="A bright coastal city.", pros=items, cons=items)
        else:
            raise AssertionError(fmt)
        return _response(parsed, web=web)

    def create(self, **kwargs):
        self.owner.calls.append(kwargs)
        return _response(None, web=bool(kwargs.get("tools")), text="notes with citations")


class FakeOpenAI:
    def __init__(self, score=7, reject_web_with_format=False):
        self.calls = []
        self.score = score
        self.reject_web_with_format = reject_web_with_format
        self.responses = FakeResponses(self)


@pytest.fixture
def pipeline_env(db_session, monkeypatch):
    monkeypatch.setenv("RELOCATION_LLM_USAGE_LOG", "1")
    TestSession = sessionmaker(bind=db_session.get_bind())
    fake = FakeOpenAI()

    def make_llm():
        return LlmClient(fake, recorder=lambda **kw: record_llm_call(**kw, session_factory=TestSession),
                         sleep=lambda _: None)

    lima = db_session.query(Location).filter_by(name="Lima").one()
    return NS(session=db_session, Session=TestSession, fake=fake, make_llm=make_llm, lima=lima)


def _run(env, **kwargs):
    return run_location(env.lima.id, session_factory=env.Session, llm=env.make_llm(), log=lambda line: None,
                        write_markdown=False, **kwargs)


def test_full_run_researches_scores_and_synthesizes(pipeline_env):
    env = pipeline_env
    summary = _run(env)
    s = env.session
    s.expire_all()

    researched = s.query(Category).filter(Category.kind == "researched").count()
    assert len(summary.researched) == researched and not summary.failures
    assert summary.synthesized

    run = s.query(ResearchRun).filter_by(location_id=env.lima.id).order_by(ResearchRun.id.desc()).first()
    assert (run.status, run.prompt_version) == ("completed", "v2")

    visa = s.query(Category).filter_by(key="visa").one()
    country_row = s.query(Research).filter_by(category_id=visa.id, country_code="PE", is_current=True).one()
    assert country_row.location_id is None and country_row.source_urls == [CITED]

    food = s.query(Category).filter_by(key="food").one()  # needs_web=False
    food_row = s.query(Research).filter_by(category_id=food.id, location_id=env.lima.id, is_current=True).one()
    assert food_row.key_facts[0]["fact"] == "Rent"
    assert food_row.source_urls == ["https://remembered.example"]  # model-provided, unverified

    scores = {e.category_id: e for e in effective_scores(s, location_id=env.lima.id)}
    assert scores[food.id].method == "llm" and scores[food.id].research_id == food_row.id
    assert scores[visa.id].scope == "country" and scores[visa.id].research_id == country_row.id

    assert s.query(VisaInfo).filter_by(country_code="PE").count() == 1
    assert s.query(ProCon).filter_by(location_id=env.lima.id).count() == 16
    assert s.get(Location, env.lima.id).description  # set because it was empty

    routes = sorted({c.route for c in s.query(LlmCall).filter_by(run_id=run.id)})
    assert routes == ["research", "synthesis"]  # visa pathways come from the visa research call

    assert food_row.source.startswith("Model knowledge (not web-verified)")  # model's "Web search" claim ignored
    assert country_row.source.startswith("Web search")


def test_calls_share_a_cacheable_prefix_and_web_only_where_needed(pipeline_env):
    env = pipeline_env
    _run(env)
    research_calls = [c for c in env.fake.calls if issubclass(c["text_format"], schemas.EvidenceResponse)]
    assert len({c["instructions"] for c in research_calls}) == 1  # identical prefix across categories
    location_calls = [c for c in research_calls if c["input"].startswith("Place (use this exact one")]
    assert location_calls  # location block first, category text after
    s = env.session
    web_names = {c.name for c in s.query(Category).filter_by(needs_web=True, kind="researched")}
    for call in research_calls:
        named = next(n for n in (c.name for c in s.query(Category)) if f"Category: {n}" in call["input"])
        assert bool(call.get("tools")) == (named in web_names), named


def test_second_run_skips_everything_current(pipeline_env):
    env = pipeline_env
    _run(env)
    env.fake.calls.clear()
    summary = _run(env)
    assert env.fake.calls == []
    assert not summary.researched and not summary.rescored and not summary.synthesized


def test_rescore_uses_stored_evidence_without_web(pipeline_env):
    env = pipeline_env
    _run(env)
    env.fake.calls.clear()
    run_rescore(category_keys=["food"], location_ids=[env.lima.id], session_factory=env.Session,
                llm=env.make_llm(), log=lambda line: None)
    assert [c["text_format"] for c in env.fake.calls] == [schemas.RescoreResponse]
    assert not env.fake.calls[0].get("tools")
    food = env.session.query(Category).filter_by(key="food").one()
    score = next(e for e in effective_scores(env.session, location_id=env.lima.id) if e.category_id == food.id)
    assert score.score == 3


def test_us_citizens_get_the_visa_rule_without_an_llm_call(pipeline_env):
    env = pipeline_env
    s = env.session
    s.add(ProfileResponse(section="Other", question_key="additional_notes", question="Anything else?",
                          answer="We are both US citizens."))
    s.add(Location(name="Kailua", country="United States", country_code="US"))
    s.commit()
    kailua = s.query(Location).filter_by(name="Kailua").one()
    run_location(kailua.id, session_factory=env.Session, llm=env.make_llm(), log=lambda line: None,
                 write_markdown=False, category_keys=["visa"], skip_synthesis=True)
    assert not any(c["text_format"] in (schemas.VisaResponse, schemas.VisaEvidenceResponse) for c in env.fake.calls)
    visa = s.query(Category).filter_by(key="visa").one()
    score = next(e for e in effective_scores(s, location_id=kailua.id) if e.category_id == visa.id)
    assert (score.score, score.method) == (10, "derived")


def test_cited_categories_fail_cleanly_without_web_search(pipeline_env, monkeypatch):
    env = pipeline_env
    monkeypatch.setattr(get_settings(), "web_search", False)
    summary = _run(env, skip_synthesis=True)
    assert {"Visa / residency feasibility", "Tax implications", "visa info"} <= set(summary.failures)
    assert summary.researched  # other categories still ran


def test_two_step_fallback_when_api_rejects_web_with_structured_output(pipeline_env):
    env = pipeline_env
    env.fake.reject_web_with_format = True
    llm = env.make_llm()
    request = LlmRequest(route="research", model="m", instructions="i", input="Category: x",
                         text_format=schemas.EvidenceResponse, max_output_tokens=100, web_search=True)
    result = llm.call(request)
    assert llm.two_step_web_search
    assert result.cited_urls == [CITED]
    assert isinstance(result.parsed, schemas.EvidenceResponse)


def test_length_cutoff_retries_with_bigger_budget(db_session):
    budgets = []

    class Truncating:
        def __init__(self):
            self.responses = self
            self.n = 0

        def parse(self, **kwargs):
            budgets.append(kwargs["max_output_tokens"])
            self.n += 1
            if self.n == 1:
                return _response(None, status="incomplete", reason="max_output_tokens")
            return _response(schemas.RescoreResponse(score=5, score_rationale="ok"))

    statuses = []
    llm = LlmClient(Truncating(), settings=PipelineSettings(), recorder=lambda **kw: statuses.append(kw["status"]))
    result = llm.call(LlmRequest(route="rescore", model="m", instructions="i", input="x",
                                 text_format=schemas.RescoreResponse, max_output_tokens=200))
    assert result.parsed.score == 5
    assert budgets == [200, 300]
    assert statuses == ["truncated", "ok"]


def test_extract_web_evidence():
    cited, sources, searches = extract_web_evidence(_response(None, web=True))
    assert cited == [CITED] and sources == [SOURCE, CITED] and searches == 1


def test_profile_brief_sends_finance_only_where_relevant(db_session):
    db_session.add_all([
        ProfileResponse(section="Financial", question_key="income_sources", question="Income?", answer="Pension 64K"),
        ProfileResponse(section="Requirements", question_key="must_haves", question="Must-haves?", answer="Swimming"),
    ])
    db_session.commit()
    profile = Profile.load(db_session)
    lima = db_session.query(Location).filter_by(name="Lima").one()
    by_key = {c.key: c for c in db_session.query(Category)}
    food = category_input(subject_block=location_block(lima, None), category=by_key["food"], profile=profile, web_search=False)
    tax = category_input(subject_block=location_block(lima, None), category=by_key["tax"], profile=profile, web_search=True)
    assert "Pension" not in food and "Pension" in tax
    assert "Pension" not in profile.base_brief() and "Swimming" in profile.base_brief()
    assert date.today().isoformat()  # sanity


def test_truncated_json_from_sdk_parse_retries_with_bigger_budget():
    from pydantic import ValidationError

    budgets = []

    class CutOff:
        def __init__(self):
            self.responses = self
            self.n = 0

        def parse(self, **kwargs):
            budgets.append(kwargs["max_output_tokens"])
            self.n += 1
            if self.n == 1:
                schemas.EvidenceResponse.model_validate_json('{"summary":"For U.S. ret')  # raises like the SDK does
            return _response(schemas.RescoreResponse(score=5, score_rationale="ok"))

    statuses = []
    llm = LlmClient(CutOff(), settings=PipelineSettings(), recorder=lambda **kw: statuses.append(kw["status"]))
    try:
        result = llm.call(LlmRequest(route="research", model="m", instructions="i", input="x",
                                     text_format=schemas.RescoreResponse, max_output_tokens=2000))
    except ValidationError:  # pragma: no cover
        raise AssertionError("should have retried")
    assert result.parsed.score == 5
    assert budgets == [2000, 3000]
    assert statuses == ["truncated", "ok"]


def test_category_runs_only_touch_visa_info_when_visa_is_selected(pipeline_env):
    env = pipeline_env
    _run(env, force=True, category_keys=["food"], skip_synthesis=True)
    visa_formats = (schemas.VisaResponse, schemas.VisaEvidenceResponse)
    assert not any(c["text_format"] in visa_formats for c in env.fake.calls)
    env.fake.calls.clear()
    _run(env, force=True, category_keys=["visa"], skip_synthesis=True)
    assert [c["text_format"] for c in env.fake.calls if c["text_format"] in visa_formats] == [schemas.VisaEvidenceResponse]



def test_web_calls_cap_searches(pipeline_env):
    env = pipeline_env
    _run(env, skip_synthesis=True)
    web_calls = [c for c in env.fake.calls if c.get("tools")]
    assert web_calls
    caps = {c["text_format"].__name__: c.get("max_tool_calls") for c in web_calls}
    assert caps["EvidenceResponse"] == 1
    assert caps["VisaEvidenceResponse"] == 2


def test_rejected_search_cap_is_dropped_and_retried(pipeline_env):
    env = pipeline_env
    rejected = []

    class CapRejecting(FakeResponses):
        def parse(self, **kwargs):
            if "max_tool_calls" in kwargs:
                rejected.append(True)
                raise BadRequestError("Unknown parameter: 'max_tool_calls'.",
                                      response=httpx.Response(400, request=httpx.Request("POST", "https://x")), body=None)
            return super().parse(**kwargs)

    env.fake.responses = CapRejecting(env.fake)
    llm = env.make_llm()
    result = llm.call(LlmRequest(route="research", model="m", instructions="i", input="Category: x",
                                 text_format=schemas.EvidenceResponse, max_output_tokens=100, web_search=True))
    assert rejected == [True] and not llm.max_tool_calls_supported
    assert isinstance(result.parsed, schemas.EvidenceResponse)


def test_upgrade_redoes_old_version_evidence_once_per_country(pipeline_env):
    from relocation.pipeline.runner import needs_upgrade

    env = pipeline_env
    s = env.session
    cusco = Location(name="Cusco", country="Peru", country_code="PE")
    s.add(cusco)
    s.commit()
    # Pretend everything Lima has came from an old pipeline
    _run(env, skip_synthesis=True)
    s.query(ResearchRun).update({ResearchRun.prompt_version: "v1"})
    s.commit()
    assert needs_upgrade(s, env.lima)

    env.fake.calls.clear()
    run_location(env.lima.id, session_factory=env.Session, llm=env.make_llm(), log=lambda line: None,
                 write_markdown=False, upgrade_versions=True, skip_synthesis=True)
    assert not needs_upgrade(s, env.lima)
    lima_visa_calls = sum(1 for c in env.fake.calls if c["text_format"] is schemas.VisaEvidenceResponse)
    assert lima_visa_calls == 1

    env.fake.calls.clear()
    run_location(cusco.id, session_factory=env.Session, llm=env.make_llm(), log=lambda line: None,
                 write_markdown=False, upgrade_versions=True, skip_synthesis=True)
    # Peru's visa research is already v2, so Cusco doesn't redo it
    assert not any(c["text_format"] is schemas.VisaEvidenceResponse for c in env.fake.calls)
    assert not needs_upgrade(s, cusco)
