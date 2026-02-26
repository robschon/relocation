import typer
from rich.console import Console
from rich.table import Table

from relocation.database import SessionLocal
from relocation.models import Category

console = Console()
app = typer.Typer(help="Manage scoring categories.")


@app.command("list")
def list_categories():
    """List all scoring categories."""
    with SessionLocal() as session:
        categories = session.query(Category).order_by(Category.sort_order).all()
    if not categories:
        console.print("No categories yet. Run 'relocation init' to seed data.")
        return
    table = Table(title="Scoring Categories")
    table.add_column("#", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    for cat in categories:
        table.add_row(str(cat.sort_order), cat.name, cat.description or "")
    console.print(table)
