from datetime import date

from sqlalchemy.orm import Session

from relocation.models import ProfileResponse
from relocation.profile_builder.questions import QUESTIONS


def format_profile(session: Session) -> str:
    """Format profile responses as a markdown document for research context."""
    responses = {
        r.question_key: r.answer
        for r in session.query(ProfileResponse).all()
        if r.answer
    }

    if not responses:
        return "No profile data yet. Run `relocation profile build` first."

    sections: dict[str, list[tuple[str, str]]] = {}
    for q in QUESTIONS:
        answer = responses.get(q.key)
        if answer:
            sections.setdefault(q.section, []).append((q.question, answer))

    lines = ["# Relocation Profile\n"]

    for section_name, items in sections.items():
        lines.append(f"## {section_name}\n")
        for question, answer in items:
            if "\n" in answer:
                lines.append(f"**{question}**")
                lines.append(answer)
                lines.append("")
            else:
                lines.append(f"- **{question}** {answer}")
        lines.append("")

    # Key requirements summary
    must_haves = responses.get("must_haves")
    deal_breakers = responses.get("deal_breakers")
    if must_haves or deal_breakers:
        lines.append("## Key Requirements Summary\n")
        if must_haves:
            lines.append("### Must-Haves")
            lines.append(must_haves)
            lines.append("")
        if deal_breakers:
            lines.append("### Deal-Breakers")
            lines.append(deal_breakers)
            lines.append("")

    lines.append("---")
    lines.append(
        f"*Generated on {date.today().isoformat()}. Use this document as context "
        "when requesting location research from Claude or other AI assistants.*"
    )

    return "\n".join(lines)
