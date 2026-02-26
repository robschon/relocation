from rich.console import Console
from rich.prompt import Prompt
from sqlalchemy.orm import Session

from relocation.models import ProfileResponse
from relocation.profile_builder.questions import QUESTIONS

console = Console()


def run_interactive(session: Session):
    """Run the interactive profile questionnaire."""
    current_section = None

    for q in QUESTIONS:
        if q.section != current_section:
            current_section = q.section
            console.print(f"\n[bold blue]--- {current_section} ---[/bold blue]")

        # Check for existing answer
        existing = session.query(ProfileResponse).filter_by(question_key=q.key).first()
        default = existing.answer if existing and existing.answer else None

        if q.hint:
            console.print(f"  [dim]{q.hint}[/dim]")

        if q.multiline:
            console.print(f"[bold]{q.question}[/bold]")
            if default:
                console.print(f"  [dim]Current: {default}[/dim]")
            console.print("  [dim](Enter a blank line to finish. Press Enter to keep current.)[/dim]")
            lines = []
            first = True
            while True:
                line = Prompt.ask("  ", default="" if not first or not default else None)
                if first and default and line == default:
                    # User pressed enter to keep current
                    answer = default
                    break
                if line == "":
                    if lines:
                        answer = "\n".join(lines)
                        break
                    elif default:
                        answer = default
                        break
                    else:
                        answer = None
                        break
                lines.append(line)
                first = False
            # If we collected lines, join them
            if lines:
                answer = "\n".join(lines)
        else:
            prompt_text = f"[bold]{q.question}[/bold]"
            answer = Prompt.ask(prompt_text, default=default or "")
            if answer == "":
                answer = default

        # Save to database
        if existing:
            existing.answer = answer
        else:
            session.add(ProfileResponse(
                section=q.section,
                question_key=q.key,
                question=q.question,
                answer=answer,
            ))
        session.flush()

    session.commit()
    console.print("\n[bold green]Profile saved![/bold green]")
