from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import case, distinct, func

from relocation.cli.helpers import resolve_location
from relocation.database import SessionLocal
from relocation.models import LlmCall

console = Console()


def _fmt(value: int | float | None) -> str:
    return f"{int(value or 0):,}"


def llm_usage(
    since: str | None = typer.Option(None, help="Only calls on/after this date (YYYY-MM-DD)."),
    location: str | None = typer.Option(None, help="Limit to one location (ID or name)."),
):
    """Summarize recorded LLM token usage by pipeline step."""
    with SessionLocal() as session:
        query = session.query(
            LlmCall.route,
            func.count(LlmCall.id),
            func.sum(case((LlmCall.status != "ok", 1), else_=0)),
            func.sum(LlmCall.input_tokens),
            func.sum(LlmCall.cached_input_tokens),
            func.sum(LlmCall.output_tokens),
            func.sum(LlmCall.reasoning_tokens),
            func.sum(LlmCall.web_search_calls),
            func.count(distinct(LlmCall.location_id)),
        )
        if since:
            query = query.filter(LlmCall.created_at >= datetime.fromisoformat(since))
        if location:
            loc = resolve_location(session, location)
            query = query.filter(LlmCall.location_id == loc.id)
        rows = query.group_by(LlmCall.route).order_by(func.sum(LlmCall.output_tokens).desc()).all()

    if not rows:
        console.print("No LLM calls recorded yet.", style="yellow")
        return

    table = Table(title="LLM usage by step")
    table.add_column("Step", no_wrap=True, min_width=11)
    for column in ("Calls", "Failed", "Input", "Cached", "Output", "Reasoning", "Searches", "Locs"):
        table.add_column(column, justify="right")

    totals = [0] * 7
    for route, calls, failed, inp, cached, out, reasoning, searches, locations in rows:
        values = (calls, failed, inp, cached, out, reasoning, searches)
        totals = [t + (v or 0) for t, v in zip(totals, values)]
        table.add_row(route, *(_fmt(v) for v in values), _fmt(locations))
    table.add_row("[bold]Total[/bold]", *(f"[bold]{_fmt(t)}[/bold]" for t in totals), "")
    console.print(table)
    console.print(
        "Output includes reasoning tokens. 'Failed' counts attempts that were retried or raised.",
        style="dim",
    )
