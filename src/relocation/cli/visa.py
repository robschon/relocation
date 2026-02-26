from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from relocation.database import SessionLocal
from relocation.models import VisaInfo

console = Console()
app = typer.Typer(help="Manage visa and immigration info.")


@app.command()
def add(
    country: str = typer.Argument(help="Country name"),
    visa_type: str = typer.Argument(help="Visa type name"),
    description: Optional[str] = typer.Option(None, "--desc", help="Description"),
    requirements: Optional[str] = typer.Option(None, "--requirements", "-r", help="Requirements"),
    residency_pathway: Optional[str] = typer.Option(None, "--pathway", help="Residency pathway"),
    timeline: Optional[str] = typer.Option(None, "--timeline", "-t", help="Timeline"),
    cost: Optional[str] = typer.Option(None, "--cost", help="Cost"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Notes"),
):
    """Add visa/immigration info for a country."""
    with SessionLocal() as session:
        info = VisaInfo(
            country=country,
            visa_type=visa_type,
            description=description,
            requirements=requirements,
            residency_pathway=residency_pathway,
            timeline=timeline,
            cost=cost,
            notes=notes,
        )
        session.add(info)
        session.commit()
        console.print(f"Added: [bold]{country}[/bold] — {visa_type} (id={info.id})")


@app.command("list")
def list_visa(
    country: Optional[str] = typer.Option(None, "--country", "-c", help="Filter by country"),
):
    """List visa info."""
    with SessionLocal() as session:
        query = session.query(VisaInfo)
        if country:
            query = query.filter(VisaInfo.country.ilike(f"%{country}%"))
        entries = query.order_by(VisaInfo.country, VisaInfo.visa_type).all()

    if not entries:
        console.print("No visa info found.")
        return

    table = Table(title="Visa / Immigration Info")
    table.add_column("ID", style="dim")
    table.add_column("Country", style="bold")
    table.add_column("Visa Type")
    table.add_column("Timeline")
    table.add_column("Cost")
    for e in entries:
        table.add_row(str(e.id), e.country, e.visa_type, e.timeline or "", e.cost or "")
    console.print(table)


@app.command()
def show(id: int = typer.Argument(help="Visa info ID")):
    """Show full details of a visa entry."""
    with SessionLocal() as session:
        info = session.get(VisaInfo, id)
    if not info:
        console.print(f"[red]No visa info with id={id}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]{info.country}[/bold] — {info.visa_type}")
    if info.description:
        console.print(f"  {info.description}")
    if info.requirements:
        console.print(f"\n  [bold]Requirements:[/bold] {info.requirements}")
    if info.residency_pathway:
        console.print(f"  [bold]Pathway:[/bold] {info.residency_pathway}")
    if info.timeline:
        console.print(f"  [bold]Timeline:[/bold] {info.timeline}")
    if info.cost:
        console.print(f"  [bold]Cost:[/bold] {info.cost}")
    if info.notes:
        console.print(f"  [bold]Notes:[/bold] {info.notes}")
    console.print()
