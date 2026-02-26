from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from relocation.cli.helpers import resolve_category
from relocation.database import SessionLocal
from relocation.models import Category, User, Weight

console = Console()
app = typer.Typer(help="Manage category weights per user.")


def _resolve_user(session, name: str) -> User:
    user = session.query(User).filter(User.name.ilike(name)).first()
    if not user:
        raise SystemExit(f"No user '{name}'. Valid users: husband, wife")
    return user


@app.command()
def set(
    user_name: str = typer.Argument(help="User name (husband/wife)"),
    category: str = typer.Argument(help="Category ID or name substring"),
    weight: float = typer.Argument(help="Weight (0-10)"),
):
    """Set a category weight for a user (creates or updates)."""
    if weight < 0 or weight > 10:
        console.print("[red]Weight must be between 0 and 10[/red]")
        raise typer.Exit(1)

    with SessionLocal() as session:
        user = _resolve_user(session, user_name)
        cat = resolve_category(session, category)

        existing = (
            session.query(Weight)
            .filter_by(user_id=user.id, category_id=cat.id)
            .first()
        )
        if existing:
            old = existing.weight
            existing.weight = weight
            session.commit()
            console.print(
                f"Updated: [bold]{user.name}[/bold] / {cat.name}: {old} → {weight}"
            )
        else:
            new_weight = Weight(user_id=user.id, category_id=cat.id, weight=weight)
            session.add(new_weight)
            session.commit()
            console.print(
                f"Set: [bold]{user.name}[/bold] / {cat.name}: {weight}"
            )


@app.command("list")
def list_weights(
    user_name: Optional[str] = typer.Option(None, "--user", "-u", help="Filter by user"),
):
    """List weights, optionally filtered by user."""
    with SessionLocal() as session:
        query = session.query(Weight)
        if user_name:
            user = _resolve_user(session, user_name)
            query = query.filter(Weight.user_id == user.id)

        weights = query.all()
        if not weights:
            console.print("No weights found.")
            return

        table = Table(title="Weights")
        table.add_column("User", style="bold")
        table.add_column("Category")
        table.add_column("Weight", justify="right")
        for w in sorted(weights, key=lambda w: (w.user.name, w.category.sort_order)):
            table.add_row(w.user.name, w.category.name, str(w.weight))
        console.print(table)


@app.command()
def matrix():
    """Display a user x category weight matrix."""
    with SessionLocal() as session:
        users = session.query(User).order_by(User.name).all()
        categories = session.query(Category).order_by(Category.sort_order).all()
        weights = {
            (w.user_id, w.category_id): w.weight for w in session.query(Weight).all()
        }

    table = Table(title="Weight Matrix")
    table.add_column("Category", style="bold")
    for user in users:
        table.add_column(user.name.title(), justify="center")

    for cat in categories:
        row = [cat.name]
        for user in users:
            val = weights.get((user.id, cat.id))
            row.append(str(val) if val is not None else "·")
        table.add_row(*row)

    console.print(table)
