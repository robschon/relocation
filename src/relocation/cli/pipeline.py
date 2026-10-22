from typing import Optional

import typer
from rich.console import Console

from relocation.cli.helpers import resolve_location
from relocation.database import SessionLocal

console = Console()
app = typer.Typer(help="Research pipeline v2: research, score, synthesize.")


@app.callback()
def _migrate_first() -> None:
    """Bring the database schema up to date before any pipeline command."""
    from relocation.database import init_db

    init_db()


def _flex(flex: bool) -> None:
    if flex:
        from relocation.settings import get_settings

        get_settings().service_tier = "flex"
        console.print("Using service_tier=flex (cheaper, slower; may queue).", style="dim")


def _location_ids(names: list[str]) -> list[int]:
    with SessionLocal() as session:
        return [resolve_location(session, name).id for name in names]


@app.command()
def run(
    location: str = typer.Argument(help="Location ID or name"),
    force: bool = typer.Option(False, "--force", help="Redo every researched category and visa info"),
    category: Optional[list[str]] = typer.Option(None, "--category", "-c", help="Only these categories (key or name part)"),
    skip_visa: bool = typer.Option(False, "--skip-visa"),
    skip_synthesis: bool = typer.Option(False, "--skip-synthesis", help="Skip pros/cons and description"),
    force_description: bool = typer.Option(False, "--force-description"),
    flex: bool = typer.Option(False, "--flex", help="Use the cheaper flex service tier"),
):
    """Research and score one location (only what's missing or stale, unless --force)."""
    from relocation.pipeline.runner import run_location

    _flex(flex)
    (location_id,) = _location_ids([location])
    summary = run_location(location_id, force=force, category_keys=category, skip_visa=skip_visa,
                           skip_synthesis=skip_synthesis, force_description=force_description,
                           kind="category" if category else "full")
    if summary.failures:
        raise typer.Exit(1)


@app.command()
def rescore(
    category: Optional[list[str]] = typer.Option(None, "--category", "-c", help="Default: visa and tax"),
    location: Optional[list[str]] = typer.Option(None, "--location", "-l", help="Default: all locations"),
    stale_only: bool = typer.Option(False, "--stale-only", help="Only scores that predate their evidence"),
    flex: bool = typer.Option(False, "--flex"),
):
    """Re-score from stored evidence (no web search)."""
    from relocation.pipeline.runner import run_rescore

    _flex(flex)
    summary = run_rescore(category_keys=category or ["visa", "tax"],
                          location_ids=_location_ids(location) if location else None, stale_only=stale_only)
    console.print(f"Rescored {len(summary.rescored)}, failed {len(summary.failures)}")


@app.command()
def backfill(
    location: Optional[list[str]] = typer.Option(None, "--location", "-l", help="Only these locations (default: all)"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Stop after this many locations"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be upgraded, make no calls"),
    flex: bool = typer.Option(False, "--flex", help="Cheaper, slower service tier (recommended)"),
):
    """Upgrade every location to the current prompt version, one location at a time.

    Only evidence from an older prompt version is redone; country-level visa research
    happens once per country. Safe to stop (Ctrl-C) and run again: finished locations
    are skipped without any calls.
    """
    from relocation.models import Location
    from relocation.pipeline.runner import needs_upgrade, run_location
    from relocation.settings import get_settings

    _flex(flex)
    ids = _location_ids(location) if location else None
    with SessionLocal() as session:
        if ids is None:
            ids = [loc_id for (loc_id,) in session.query(Location.id).order_by(Location.id)]
        todo = []
        for loc_id in ids:
            loc = session.get(Location, loc_id)
            stale = needs_upgrade(session, loc)
            if stale:
                todo.append((loc_id, loc.name, len(stale)))
    version = get_settings().prompt_version
    console.print(f"{len(todo)} of {len(ids)} locations need upgrading to prompt version {version}.")
    if limit is not None:
        todo = todo[:limit]
    if dry_run:
        for _, name, count in todo:
            console.print(f"  {name}: {count} categor{'y' if count == 1 else 'ies'}")
        return

    failed = []
    for n, (loc_id, name, _) in enumerate(todo, 1):
        console.rule(f"[{n}/{len(todo)}] {name}")
        try:
            summary = run_location(loc_id, upgrade_versions=True, kind="full")
            if summary.failures:
                failed.append(f"{name}: {', '.join(summary.failures)}")
        except Exception as exc:  # keep going; the run row records the error
            failed.append(f"{name}: {type(exc).__name__}: {exc}")
    console.print(f"\nDone: {len(todo) - len(failed)} upgraded cleanly, {len(failed)} with problems.")
    for line in failed:
        console.print(f"  {line}", style="yellow")
    if failed:
        console.print("Run the same command again to retry what's left.", style="dim")


@app.command("smoke-test")
def smoke_test(location: str = typer.Argument("Lima", help="Location to test with (nothing is saved)")):
    """One cheap research call with web search, to check the API accepts it. Nothing is written except usage."""
    from datetime import date

    from relocation.models import Category, Country
    from relocation.pipeline.context import Profile, category_input, location_block, research_instructions
    from relocation.pipeline.llm import LlmClient, LlmRequest
    from relocation.pipeline.schemas import EvidenceResponse
    from relocation.settings import get_settings

    settings = get_settings()
    with SessionLocal() as session:
        loc = resolve_location(session, location)
        category = session.query(Category).filter_by(key="cost_of_living").one()
        profile = Profile.load(session)
        request = LlmRequest(
            route="smoke_test", model=settings.research_model,
            instructions=research_instructions(profile, summary_words=60, today=date.today()),
            input=category_input(subject_block=location_block(loc, session.get(Country, loc.country_code)),
                                 category=category, profile=profile, web_search=True),
            text_format=EvidenceResponse, max_output_tokens=settings.research_max_output_tokens,
            effort=settings.research_effort, web_search=True,
            usage_context={"location_id": loc.id, "category_id": category.id},
        )
    llm = LlmClient(settings=settings)
    result = llm.call(request)
    usage = getattr(result.response, "usage", None)
    console.print(f"[green]OK[/green] model={settings.research_model} score={result.parsed.score} "
                  f"facts={len(result.parsed.key_facts)} searches={result.web_search_calls} "
                  f"cited={len(result.cited_urls)} sources={len(result.source_urls)}")
    if llm.two_step_web_search:
        console.print("[yellow]The API rejected web search + structured output together; "
                      "the pipeline will use two calls (search, then format) for web categories.[/yellow]")
    if usage is not None:
        console.print(f"tokens: in={getattr(usage, 'input_tokens', '?')} out={getattr(usage, 'output_tokens', '?')}")
    for url in result.cited_urls[:5]:
        console.print(f"  {url}", style="dim")


@app.command()
def trial(
    location: list[str] = typer.Argument(help="Location IDs or names (e.g. 4 5 6)"),
    compare_only: bool = typer.Option(False, "--compare-only", help="Don't run; compare the latest trial copy"),
    reuse: bool = typer.Option(False, "--reuse", help="Run on the latest trial copy instead of a new one"),
    category: Optional[list[str]] = typer.Option(None, "--category", "-c", help="Only these categories (e.g. tax)"),
    flex: bool = typer.Option(False, "--flex"),
):
    """Run v2 (forced) on a copy of the database and compare tokens and scores with v1.

    To redo only categories that failed, on the same copy:
        relocation pipeline trial 4 5 6 --reuse -c tax
    """
    from relocation.pipeline.trial import compare, format_report, latest_trial, run_trial

    _flex(flex)
    ids = _location_ids(location)
    path = latest_trial() if (compare_only or reuse) else None
    if (compare_only or reuse) and path is None:
        console.print("No trial copy found in data/trials/.", style="red")
        raise typer.Exit(1)
    if not compare_only:
        path = run_trial(ids, trial_path=path, category_keys=category)
    console.print(f"\nTrial database: {path}\n")
    console.print(format_report(compare(path, ids)), markup=False, highlight=False)
