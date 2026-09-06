"""
Deterministic email generation.

No LLM involved: this is pure, boring string substitution of exactly
three per-recruiter placeholders (plus the sender's name, which comes
from configuration, not from the recruiter row). The rest of the
template is passed through byte-for-byte.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from database.models import RecruiterRecord


@dataclass
class GeneratedEmail:
    subject: str
    body: str


def load_template(template_path: str | Path) -> str:
    path = Path(template_path)
    if not path.exists():
        raise FileNotFoundError(f"Email template not found at: {path}")
    return path.read_text(encoding="utf-8")


def render_template(template_text: str, record: RecruiterRecord, sender_name: str) -> str:
    """Replace the sanctioned placeholders only. Nothing else is touched."""
    rendered = template_text
    rendered = rendered.replace("{HR_NAME}", record.hr_name.strip())
    rendered = rendered.replace("{COMPANY_NAME}", record.company.strip())
    rendered = rendered.replace("{JOB_ROLE}", record.job_role.strip())
    rendered = rendered.replace("{YOUR_NAME}", sender_name.strip())
    return rendered


def split_subject_and_body(rendered_text: str) -> GeneratedEmail:
    """
    The template's first line is expected to be `Subject: ...`.
    Everything after the first blank line is the body.
    """
    lines = rendered_text.splitlines()
    if not lines or not lines[0].lower().startswith("subject:"):
        raise ValueError(
            "Email template must start with a line of the form 'Subject: ...'."
        )
    subject = lines[0][len("subject:"):].strip()
    # Skip the subject line and the blank line(s) immediately after it.
    body_lines = lines[1:]
    while body_lines and body_lines[0].strip() == "":
        body_lines.pop(0)
    body = "\n".join(body_lines).strip("\n")
    return GeneratedEmail(subject=subject, body=body)


def generate_email(
    record: RecruiterRecord,
    template_text: str,
    sender_name: str,
) -> GeneratedEmail:
    rendered = render_template(template_text, record, sender_name)
    return split_subject_and_body(rendered)
