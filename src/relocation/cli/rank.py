from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from relocation.database import SessionLocal
from relocation.services.ranking import compute_rankings

console = Console()
app = typer.Typer(help="View weighted rankings.")


@app.callback(invoke_without_command=True)
def rank(
    user: Optional[str] = typer.Option(None, "--user", "-u", help="husband, wife, or combined (default)"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show per-category breakdown"),
):
    """Show weighted rankings for all locations."""
    if user and user not in ("husband", "wife", "combined"):
        console.print("[red]--user must be 'husband', 'wife', or 'combined'[/red]")
        raise typer.Exit(1)

    if user == "combined":
        user = None

    with SessionLocal() as session:
        rankings = compute_rankings(session, user=user)

    if not rankings:
        console.print("No locations to rank. Add locations and scores first.")
        return

    label = user.title() if user else "Combined"

    # Summary table
    table = Table(title=f"Rankings ({label})")
    table.add_column("#", style="dim")
    table.add_column("Location", style="bold")
    table.add_column("Country")
    table.add_column("Overall", justify="right", style="bold")
    table.add_column("Husband", justify="right")
    table.add_column("Wife", justify="right")

    for i, r in enumerate(rankings, 1):
        table.add_row(
            str(i),
            r.location_name,
            r.country,
            f"{r.overall_score:.1f}",
            f"{r.husband_score:.1f}",
            f"{r.wife_score:.1f}",
        )
    console.print(table)

    if detailed:
        for r in rankings:
            if not r.details:
                continue
            console.print(f"\n[bold]{r.location_name}, {r.country}[/bold]")
            console.print(f"Overall: {r.overall_score:.1f} (husband: {r.husband_score:.1f}, wife: {r.wife_score:.1f})")

            dt = Table()
            dt.add_column("Category")
            dt.add_column("Score", justify="right")
            dt.add_column("H-Wt", justify="right")
            dt.add_column("W-Wt", justify="right")
            dt.add_column("H-Wtd", justify="right")
            dt.add_column("W-Wtd", justify="right")

            for d in r.details:
                dt.add_row(
                    d.category_name,
                    str(d.score),
                    f"{d.husband_weight:.0f}",
                    f"{d.wife_weight:.0f}",
                    f"{d.husband_weighted:.0f}",
                    f"{d.wife_weighted:.0f}",
                )
            console.print(dt)
