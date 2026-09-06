"""
Data model(s) shared across the application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ContactStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class RecruiterRecord:
    """A single recruiter/job row, as read from CSV/Excel or manual input."""

    hr_name: str
    company: str
    job_role: str
    email: str
    linkedin_url: str = ""

    # Populated later in the pipeline.
    subject: Optional[str] = None
    email_body: Optional[str] = None
    status: ContactStatus = ContactStatus.PENDING
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None

    def as_dict(self) -> dict:
        return {
            "hr_name": self.hr_name,
            "company": self.company,
            "job_role": self.job_role,
            "email": self.email,
            "linkedin_url": self.linkedin_url,
            "subject": self.subject,
            "email_body": self.email_body,
            "status": self.status.value if isinstance(self.status, ContactStatus) else self.status,
            "error_message": self.error_message,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
        }
