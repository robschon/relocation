from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from relocation.cli.helpers import resolve_category, resolve_location
from relocation.database import SessionLocal
from relocation.models import Category, Location, Score

console = Console()
app = typer.Typer(help="Manage location scores.")


@app.command()
def set(
    location: str = typer.Argument(help="Location ID or name substring"),
    category: str = typer.Argument(help="Category ID or name substring"),
    score: int = typer.Argument(help="Score (1-10)"),
    notes: Optional[str] = typer.Option(None, help="Notes about this score"),
):
    """Set a score for a location/category (creates or updates)."""
    if score < 1 or score > 10:
        console.print("[red]Score must be between 1 and 10[/red]")
        raise typer.Exit(1)

    with SessionLocal() as session:
        loc = resolve_location(session, location)
        cat = resolve_category(session, category)

        existing = (
            session.query(Score)
            .filter_by(location_id=loc.id, category_id=cat.id)
            .first()
        )
        if existing:
            old = existing.score
            existing.score = score
            if notes is not None:
                existing.notes = notes
            session.commit()
            console.print(
                f"Updated: [bold]{loc.name}[/bold] / {cat.name}: {old} → {score}"
            )
        else:
            new_score = Score(
                location_id=loc.id, category_id=cat.id, score=score, notes=notes
            )
            session.add(new_score)
            session.commit()
            console.print(
                f"Set: [bold]{loc.name}[/bold] / {cat.name}: {score}/10"
            )


@app.command("list")
def list_scores(
    location: Optional[str] = typer.Option(None, "--location", "-l", help="Filter by location"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category"),
):
    """List scores, optionally filtered."""
    with SessionLocal() as session:
        query = session.query(Score)
        if location:
            loc = resolve_location(session, location)
            query = query.filter(Score.location_id == loc.id)
        if category:
            cat = resolve_category(session, category)
            query = query.filter(Score.category_id == cat.id)

        scores = query.all()
        if not scores:
            console.print("No scores found.")
            return

        table = Table(title="Scores")
        table.add_column("Location", style="bold")
        table.add_column("Category")
        table.add_column("Score", justify="right")
        table.add_column("Notes")
        for s in scores:
            table.add_row(
                s.location.name, s.category.name, str(s.score), s.notes or ""
            )
        console.print(table)


@app.command()
def matrix():
    """Display a location x category score matrix."""
    with SessionLocal() as session:
        locations = session.query(Location).order_by(Location.name).all()
        categories = session.query(Category).order_by(Category.sort_order).all()
        scores = {
            (s.location_id, s.category_id): s.score for s in session.query(Score).all()
        }

    if not locations:
        console.print("No locations yet.")
        return

    table = Table(title="Score Matrix")
    table.add_column("Location", style="bold")
    for cat in categories:
        # Use abbreviated names for column headers
        short = cat.name.split("/")[0].strip()[:15]
        table.add_column(short, justify="center")

    for loc in locations:
        row = [loc.name]
        for cat in categories:
            val = scores.get((loc.id, cat.id))
            row.append(str(val) if val else "·")
        table.add_row(*row)

    console.print(table)
