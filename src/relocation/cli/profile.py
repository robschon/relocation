from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown

from relocation.database import SessionLocal
from relocation.models import ProfileResponse
from relocation.profile_builder.builder import run_interactive
from relocation.profile_builder.formatter import format_profile

console = Console()
app = typer.Typer(help="Build and manage your relocation profile.")


@app.command()
def build():
    """Interactive profile questionnaire."""
    with SessionLocal() as session:
        run_interactive(session)


@app.command()
def show():
    """Display the current profile."""
    with SessionLocal() as session:
        responses = (
            session.query(ProfileResponse)
            .filter(ProfileResponse.answer.isnot(None))
            .order_by(ProfileResponse.section, ProfileResponse.id)
            .all()
        )
    if not responses:
        console.print("No profile data yet. Run [bold]relocation profile build[/bold] first.")
        return

    current_section = None
    for r in responses:
        if r.section != current_section:
            current_section = r.section
            console.print(f"\n[bold blue]{current_section}[/bold blue]")
        console.print(f"  [bold]{r.question}[/bold]")
        console.print(f"  {r.answer}\n")


@app.command()
def export(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Export profile as formatted markdown."""
    with SessionLocal() as session:
        md = format_profile(session)

    if output:
        Path(output).write_text(md)
        console.print(f"Profile exported to [bold]{output}[/bold]")
    else:
        console.print(Markdown(md))
