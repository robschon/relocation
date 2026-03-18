from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from relocation.cli.helpers import resolve_location
from relocation.countries import normalize_country_fields
from relocation.database import SessionLocal
from relocation.models import Location

console = Console()
app = typer.Typer(help="Manage locations.")


@app.command("list")
def list_locations():
    """List all locations."""
    with SessionLocal() as session:
        locations = session.query(Location).order_by(Location.name).all()
    if not locations:
        console.print("No locations yet. Run 'relocation init' to seed data.")
        return
    table = Table(title="Locations")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Country")
    table.add_column("Region")
    table.add_column("Population", justify="right")
    for loc in locations:
        pop = f"{loc.population:,}" if loc.population else ""
        table.add_row(str(loc.id), loc.name, loc.country, loc.region or "", pop)
    console.print(table)


@app.command()
def add(
    name: str = typer.Argument(help="Location name"),
    country: str = typer.Argument(help="Country"),
    region: Optional[str] = typer.Option(None, help="Region/continent"),
    population: Optional[int] = typer.Option(None, help="Population"),
    description: Optional[str] = typer.Option(None, "--desc", help="Description"),
):
    """Add a new location."""
    normalized_country, normalized_country_code = normalize_country_fields(country=country)
    with SessionLocal() as session:
        loc = Location(
            name=name,
            country=normalized_country,
            country_code=normalized_country_code,
            region=region,
            population=population,
            description=description,
        )
        session.add(loc)
        session.commit()
        console.print(f"Added: [bold]{loc.name}[/bold], {loc.country} (id={loc.id})")


@app.command()
def show(query: str = typer.Argument(help="Location ID or name substring")):
    """Show details for a location."""
    with SessionLocal() as session:
        loc = resolve_location(session, query)
        console.print(f"\n[bold]{loc.name}[/bold], {loc.country}")
        if loc.region:
            console.print(f"  Region: {loc.region}")
        if loc.population:
            console.print(f"  Population: {loc.population:,}")
        if loc.description:
            console.print(f"  {loc.description}")
        if loc.notes:
            console.print(f"  Notes: {loc.notes}")

        if loc.scores:
            console.print("\n  [bold]Scores:[/bold]")
            for s in sorted(loc.scores, key=lambda s: s.category.sort_order):
                note = f" — {s.notes}" if s.notes else ""
                console.print(f"    {s.category.name}: {s.score}/10{note}")

        pros = [pc for pc in loc.pros_cons if pc.type == "pro"]
        cons = [pc for pc in loc.pros_cons if pc.type == "con"]
        if pros:
            console.print("\n  [bold green]Pros:[/bold green]")
            for p in pros:
                console.print(f"    + {p.content}")
        if cons:
            console.print("\n  [bold red]Cons:[/bold red]")
            for c in cons:
                console.print(f"    - {c.content}")
        console.print()


@app.command()
def remove(
    query: str = typer.Argument(help="Location ID or name substring"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Remove a location and all its associated data."""
    with SessionLocal() as session:
        loc = resolve_location(session, query)
        if not yes:
            confirm = typer.confirm(f"Delete '{loc.name}, {loc.country}' and all related data?")
            if not confirm:
                raise typer.Abort()
        session.delete(loc)
        session.commit()
        console.print(f"Deleted: [bold]{loc.name}[/bold], {loc.country}")
