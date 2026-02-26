import typer
from rich.console import Console

from relocation.database import SessionLocal, init_db
from relocation.seed import seed_database

console = Console()
app = typer.Typer(help="Relocation planning tool for retirement destination research.")


@app.command()
def init():
    """Initialize the database and seed with default data."""
    console.print("Initializing database...", style="bold blue")
    init_db()
    with SessionLocal() as session:
        counts = seed_database(session)
    console.print("Database initialized!", style="bold green")
    for item, count in counts.items():
        if count > 0:
            console.print(f"  Created {count} {item}")


# Import and register subcommands
from relocation.cli.locations import app as locations_app  # noqa: E402
from relocation.cli.categories import app as categories_app  # noqa: E402
from relocation.cli.scores import app as scores_app  # noqa: E402
from relocation.cli.weights import app as weights_app  # noqa: E402
from relocation.cli.research import app as research_app  # noqa: E402
from relocation.cli.pros_cons import app as pros_cons_app  # noqa: E402
from relocation.cli.visa import app as visa_app  # noqa: E402
from relocation.cli.profile import app as profile_app  # noqa: E402
from relocation.cli.rank import app as rank_app  # noqa: E402

app.add_typer(locations_app, name="location")
app.add_typer(categories_app, name="category")
app.add_typer(scores_app, name="score")
app.add_typer(weights_app, name="weight")
app.add_typer(research_app, name="research")
app.add_typer(pros_cons_app, name="pros-cons")
app.add_typer(visa_app, name="visa")
app.add_typer(profile_app, name="profile")
app.add_typer(rank_app, name="rank")
