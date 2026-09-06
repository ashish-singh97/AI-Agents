"""
Validation logic for recruiter records and generated emails.

All validators return a `ValidationResult` (ok / list of errors) rather
than raising, so the caller can decide whether to skip-and-continue
(batch mode) or halt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from database.models import RecruiterRecord

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

REQUIRED_PLACEHOLDERS = ("{HR_NAME}", "{COMPANY_NAME}", "{JOB_ROLE}")


@dataclass
class ValidationResult:
    ok: bool
    errors: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok


def is_valid_email(email: str) -> bool:
    if not email:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def validate_record(record: RecruiterRecord) -> ValidationResult:
    """Validate that a recruiter record has everything needed to send."""
    errors: List[str] = []

    if not record.hr_name or not record.hr_name.strip():
        errors.append("Missing HR/recruiter name.")
    if not record.company or not record.company.strip():
        errors.append("Missing company name.")
    if not record.job_role or not record.job_role.strip():
        errors.append("Missing job role.")
    if not record.email or not record.email.strip():
        errors.append(f"Missing recruiter email for {record.hr_name or 'unknown recruiter'}.")
    elif not is_valid_email(record.email):
        errors.append(f"Invalid email address: {record.email}")

    return ValidationResult(ok=not errors, errors=errors)


def validate_no_unresolved_placeholders(rendered_text: str) -> ValidationResult:
    """Ensure none of the template placeholders survived rendering."""
    remaining = [p for p in REQUIRED_PLACEHOLDERS if p in rendered_text]
    # Also catch any other stray {UPPER_CASE} style placeholder.
    stray = re.findall(r"\{[A-Z0-9_]+\}", rendered_text)
    all_unresolved = sorted(set(remaining) | set(stray))
    if all_unresolved:
        return ValidationResult(
            ok=False,
            errors=[f"Unresolved placeholder(s) in email: {', '.join(all_unresolved)}"],
        )
    return ValidationResult(ok=True)
