from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from relocation.cli.helpers import resolve_category, resolve_location
from relocation.database import SessionLocal
from relocation.models import Research

console = Console()
app = typer.Typer(help="Manage research notes.")


@app.command()
def add(
    location: str = typer.Argument(help="Location ID or name substring"),
    content: str = typer.Option(..., help="Research content"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Category"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Source"),
):
    """Add a research entry for a location."""
    with SessionLocal() as session:
        loc = resolve_location(session, location)
        cat_id = None
        if category:
            cat_id = resolve_category(session, category).id

        entry = Research(
            location_id=loc.id,
            category_id=cat_id,
            content=content,
            source=source,
        )
        session.add(entry)
        session.commit()
        console.print(f"Added research for [bold]{loc.name}[/bold] (id={entry.id})")


@app.command("list")
def list_research(
    location: Optional[str] = typer.Option(None, "--location", "-l", help="Filter by location"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category"),
):
    """List research entries."""
    with SessionLocal() as session:
        query = session.query(Research)
        if location:
            loc = resolve_location(session, location)
            query = query.filter(Research.location_id == loc.id)
        if category:
            cat = resolve_category(session, category)
            query = query.filter(Research.category_id == cat.id)

        entries = query.order_by(Research.created_at.desc()).all()
        if not entries:
            console.print("No research entries found.")
            return

        for e in entries:
            cat_name = e.category.name if e.category else "General"
            source_str = f" (source: {e.source})" if e.source else ""
            console.print(f"\n[dim]#{e.id}[/dim] [bold]{e.location.name}[/bold] / {cat_name}{source_str}")
            console.print(f"  {e.content[:200]}{'...' if len(e.content) > 200 else ''}")


@app.command()
def show(id: int = typer.Argument(help="Research entry ID")):
    """Show full research entry."""
    with SessionLocal() as session:
        entry = session.get(Research, id)
        if not entry:
            console.print(f"[red]No research entry with id={id}[/red]")
            raise typer.Exit(1)
        cat_name = entry.category.name if entry.category else "General"
        console.print(f"\n[bold]{entry.location.name}[/bold] / {cat_name}")
        if entry.source:
            console.print(f"Source: {entry.source}")
        console.print(f"\n{entry.content}\n")


@app.command()
def remove(id: int = typer.Argument(help="Research entry ID")):
    """Delete a research entry."""
    with SessionLocal() as session:
        entry = session.get(Research, id)
        if not entry:
            console.print(f"[red]No research entry with id={id}[/red]")
            raise typer.Exit(1)
        session.delete(entry)
        session.commit()
        console.print(f"Deleted research entry #{id}")
