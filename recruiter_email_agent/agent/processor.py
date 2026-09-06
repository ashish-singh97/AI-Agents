"""
The orchestration layer: for each recruiter record, run the pipeline

    validate -> generate -> preview -> approve -> send -> track -> log

This module contains no I/O-format-specific code (CSV/Excel) and no
provider-specific code (Gmail) — it only depends on the abstractions
(EmailProvider, Database, RateLimiter) so providers/storage can be
swapped without touching this file.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from agent.email_generator import generate_email, load_template
from agent.validator import validate_no_unresolved_placeholders, validate_record
from database.db import Database
from database.models import ContactStatus, RecruiterRecord
from providers.base import EmailProvider
from utils.logger import log_contact_event
from utils.rate_limiter import DailyLimitReached, RateLimiter


@dataclass
class RunSummary:
    total: int = 0
    sent: int = 0
    skipped: int = 0
    failed: int = 0

    def as_text(self) -> str:
        return (
            "--------------------------------\n"
            "SUMMARY\n"
            "--------------------------------\n"
            f"Total: {self.total}\n"
            f"Sent: {self.sent}\n"
            f"Skipped: {self.skipped}\n"
            f"Failed: {self.failed}\n"
            "--------------------------------"
        )


def format_preview(recipient: str, subject: str, body: str) -> str:
    return (
        "----------------------------------------\n"
        "EMAIL PREVIEW\n"
        "----------------------------------------\n\n"
        f"To: {recipient}\n\n"
        f"Subject:\n{subject}\n\n"
        f"{body}\n\n"
        "----------------------------------------"
    )


class RecruiterEmailProcessor:
    def __init__(
        self,
        db: Database,
        provider: EmailProvider,
        rate_limiter: RateLimiter,
        logger: logging.Logger,
        template_path: str,
        sender_name: str,
        resume_path: str,
        auto_send: bool = False,
        dry_run: bool = False,
        confirm_callback: Optional[Callable[[str], bool]] = None,
    ):
        self.db = db
        self.provider = provider
        self.rate_limiter = rate_limiter
        self.logger = logger
        self.template_path = template_path
        self.sender_name = sender_name
        self.resume_path = resume_path
        self.auto_send = auto_send
        self.dry_run = dry_run
        # confirm_callback(preview_text) -> bool ; defaults to input() Y/N prompt
        self.confirm_callback = confirm_callback or self._default_confirm

    @staticmethod
    def _default_confirm(preview_text: str) -> bool:
        print(preview_text)
        answer = input("\nSend this email? [Y/N]: ").strip().lower()
        return answer in {"y", "yes"}

    def _resume_ok(self) -> bool:
        if not self.resume_path:
            return False
        return Path(self.resume_path).exists()

    def process_one(self, record: RecruiterRecord, preview_only: bool = False) -> RecruiterRecord:
        """
        Run the full pipeline for a single record. Mutates and returns the
        record with final status/subject/body/error populated.
        """
        # 1. Validate required fields.
        result = validate_record(record)
        if not result.ok:
            record.status = ContactStatus.FAILED
            record.error_message = " ".join(result.errors)
            self._track_and_log(record)
            return record

        # 2. Duplicate detection.
        if self.db.already_contacted(record.email):
            record.status = ContactStatus.SKIPPED
            record.error_message = f"Already contacted: {record.email}"
            self._track_and_log(record)
            return record

        # 3. Generate the email deterministically.
        template_text = load_template(self.template_path)
        generated = generate_email(record, template_text, self.sender_name)
        record.subject = generated.subject
        record.email_body = generated.body

        # 4. Ensure no placeholders survived.
        placeholder_check = validate_no_unresolved_placeholders(
            f"{record.subject}\n{record.email_body}"
        )
        if not placeholder_check.ok:
            record.status = ContactStatus.FAILED
            record.error_message = " ".join(placeholder_check.errors)
            self._track_and_log(record)
            return record

        if preview_only or self.dry_run:
            record.status = ContactStatus.SKIPPED if self.dry_run else ContactStatus.PENDING
            if self.dry_run:
                record.error_message = "Dry run — email generated but not sent."
                self._track_and_log(record)
            return record

        # 5. Resume attachment check.
        if not self._resume_ok():
            record.status = ContactStatus.FAILED
            record.error_message = "Resume not found. Emails will not be sent."
            self._track_and_log(record)
            return record

        # 6. Daily limit check.
        try:
            self.rate_limiter.check_daily_limit(self.db.count_sent_today())
        except DailyLimitReached as exc:
            record.status = ContactStatus.FAILED
            record.error_message = str(exc)
            self._track_and_log(record)
            return record

        # 7. Preview + approval.
        if not self.auto_send:
            preview_text = format_preview(record.email, record.subject, record.email_body)
            approved = self.confirm_callback(preview_text)
            if not approved:
                record.status = ContactStatus.SKIPPED
                record.error_message = "Not approved by user."
                self._track_and_log(record)
                return record

        # 8. Send.
        try:
            self.provider.send_email(
                recipient=record.email,
                subject=record.subject,
                body=record.email_body,
                attachment=self.resume_path,
            )
            record.status = ContactStatus.SENT
            record.sent_at = datetime.utcnow()
            record.error_message = None
        except Exception as exc:  # noqa: BLE001 - we want to record any provider failure
            record.status = ContactStatus.FAILED
            record.error_message = str(exc)

        self._track_and_log(record)
        return record

    def process_batch(
        self,
        records: List[RecruiterRecord],
        preview_only: bool = False,
    ) -> RunSummary:
        summary = RunSummary(total=len(records))
        print(f"Processing {len(records)} recruiters...\n")

        for i, record in enumerate(records, start=1):
            print(f"[{i}/{len(records)}] {record.hr_name} — {record.company} — {record.job_role}")
            processed = self.process_one(record, preview_only=preview_only)

            if processed.status == ContactStatus.SENT:
                summary.sent += 1
                print("✓ Email sent\n")
            elif processed.status == ContactStatus.SKIPPED:
                summary.skipped += 1
                print(f"SKIPPED — {processed.error_message}\n")
            elif processed.status == ContactStatus.FAILED:
                summary.failed += 1
                print(f"✗ FAILED — {processed.error_message}\n")
            else:
                print("(preview only — not sent)\n")

            # Rate-limit delay between sends (only after an actual send attempt).
            if (
                not preview_only
                and not self.dry_run
                and processed.status == ContactStatus.SENT
                and i < len(records)
            ):
                self.rate_limiter.wait()

        return summary

    def _track_and_log(self, record: RecruiterRecord) -> None:
        self.db.record_contact(record)
        log_contact_event(
            self.logger,
            hr_name=record.hr_name,
            company=record.company,
            job_role=record.job_role,
            email=record.email,
            status=record.status.value if isinstance(record.status, ContactStatus) else record.status,
            error_message=record.error_message,
        )
