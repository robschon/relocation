from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from relocation.database import SessionLocal
from relocation.services.ranking import COMBINED, compute_rankings, resolve_users

console = Console()
app = typer.Typer(help="View weighted rankings.")


@app.callback(invoke_without_command=True)
def rank(
    user: Optional[str] = typer.Option(None, "--user", "-u", help="A user's name (e.g. partner_a), or 'combined' (default)"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show per-category breakdown"),
):
    """Show weighted rankings for all locations."""
    with SessionLocal() as session:
        users = resolve_users(session)
        try:
            rankings = compute_rankings(session, user=None if user in (None, COMBINED) else user)
        except ValueError:
            names = ", ".join(u.name for u in users)
            console.print(f"[red]--user must be one of: {names}, or 'combined'[/red]")
            raise typer.Exit(1)

    if not rankings:
        console.print("No locations to rank. Add locations and scores first.")
        return

    label = next((u.display_name for u in users if user and u.name.lower() == user.lower()), "Combined")

    table = Table(title=f"Rankings ({label})")
    table.add_column("#", style="dim")
    table.add_column("Location", style="bold")
    table.add_column("Country")
    table.add_column("Overall", justify="right", style="bold")
    for u in users:
        table.add_column(u.display_name, justify="right")

    for i, r in enumerate(rankings, 1):
        table.add_row(
            str(i),
            r.location_name,
            r.country,
            f"{r.overall_score:.1f}",
            *(f"{r.user_scores.get(u.id, 0.0):.1f}" for u in users),
        )
    console.print(table)

    if detailed:
        for r in rankings:
            if not r.details:
                continue
            console.print(f"\n[bold]{r.location_name}, {r.country}[/bold]")
            per_user = ", ".join(f"{u.display_name}: {r.user_scores.get(u.id, 0.0):.1f}" for u in users)
            console.print(f"Overall: {r.overall_score:.1f} ({per_user})")

            dt = Table()
            dt.add_column("Category")
            dt.add_column("Score", justify="right")
            for u in users:
                dt.add_column(f"{u.display_name} wt", justify="right")
            for u in users:
                dt.add_column(f"{u.display_name} wtd", justify="right")

            for d in r.details:
                dt.add_row(
                    d.category_name,
                    str(d.score),
                    *(f"{d.weights.get(u.id, 0):.0f}" for u in users),
                    *(f"{d.weighted.get(u.id, 0):.0f}" for u in users),
                )
            console.print(dt)
