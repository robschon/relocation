from typing import Optional

import typer
from rich.console import Console

from relocation.cli.helpers import resolve_category, resolve_location
from relocation.database import SessionLocal
from relocation.models import ProCon

console = Console()
app = typer.Typer(help="Manage pros and cons.")


@app.command("add-pro")
def add_pro(
    location: str = typer.Argument(help="Location ID or name substring"),
    content: str = typer.Argument(help="Pro description"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Category"),
):
    """Add a pro for a location."""
    _add_item(location, content, "pro", category)


@app.command("add-con")
def add_con(
    location: str = typer.Argument(help="Location ID or name substring"),
    content: str = typer.Argument(help="Con description"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Category"),
):
    """Add a con for a location."""
    _add_item(location, content, "con", category)


def _add_item(location: str, content: str, type_: str, category: Optional[str]):
    with SessionLocal() as session:
        loc = resolve_location(session, location)
        cat_id = None
        if category:
            cat_id = resolve_category(session, category).id
        item = ProCon(
            location_id=loc.id, category_id=cat_id, type=type_, content=content
        )
        session.add(item)
        session.commit()
        label = "Pro" if type_ == "pro" else "Con"
        console.print(f"{label} added for [bold]{loc.name}[/bold]: {content}")


@app.command("list")
def list_items(
    location: Optional[str] = typer.Option(None, "--location", "-l", help="Filter by location"),
):
    """List pros and cons."""
    with SessionLocal() as session:
        query = session.query(ProCon)
        if location:
            loc = resolve_location(session, location)
            query = query.filter(ProCon.location_id == loc.id)

        items = query.all()
        if not items:
            console.print("No pros/cons found.")
            return

        # Group by location
        by_location: dict[str, list[ProCon]] = {}
        for item in items:
            key = item.location.name
            by_location.setdefault(key, []).append(item)

        for loc_name, loc_items in sorted(by_location.items()):
            console.print(f"\n[bold]{loc_name}[/bold]")
            pros = [i for i in loc_items if i.type == "pro"]
            cons = [i for i in loc_items if i.type == "con"]
            if pros:
                for p in pros:
                    cat = f" [{p.category.name}]" if p.category else ""
                    console.print(f"  [green]+[/green] {p.content}{cat} [dim](#{p.id})[/dim]")
            if cons:
                for c in cons:
                    cat = f" [{c.category.name}]" if c.category else ""
                    console.print(f"  [red]-[/red] {c.content}{cat} [dim](#{c.id})[/dim]")


@app.command()
def remove(id: int = typer.Argument(help="Pro/con item ID")):
    """Delete a pro or con."""
    with SessionLocal() as session:
        item = session.get(ProCon, id)
        if not item:
            console.print(f"[red]No pro/con with id={id}[/red]")
            raise typer.Exit(1)
        session.delete(item)
        session.commit()
        console.print(f"Deleted {item.type} #{id}")
