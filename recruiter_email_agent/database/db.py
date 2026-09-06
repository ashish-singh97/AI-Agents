"""
SQLite persistence layer for tracking recruiter contacts.

Responsibilities:
    * Create/upgrade the `recruiter_contacts` table.
    * Insert new contact attempts.
    * Update status after send/skip/fail.
    * Answer "have we already contacted this email?" queries.
    * Provide simple stats for --status and --history CLI commands.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator, Optional

from database.models import ContactStatus, RecruiterRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS recruiter_contacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    hr_name         TEXT NOT NULL,
    company         TEXT NOT NULL,
    job_role        TEXT NOT NULL,
    email           TEXT NOT NULL,
    linkedin_url    TEXT,
    subject         TEXT,
    email_body      TEXT,
    status          TEXT NOT NULL DEFAULT 'PENDING',
    sent_at         TEXT,
    error_message   TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_recruiter_contacts_email
    ON recruiter_contacts (email);
"""


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    # ------------------------------------------------------------------
    # Duplicate detection
    # ------------------------------------------------------------------
    def already_contacted(self, email: str) -> bool:
        """True if this email already has a SENT record."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM recruiter_contacts WHERE email = ? AND status = ? LIMIT 1",
                (email.strip().lower(), ContactStatus.SENT.value),
            ).fetchone()
            return row is not None

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def record_contact(self, record: RecruiterRecord) -> int:
        """Insert a new row for this attempt and return its id."""
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO recruiter_contacts
                    (hr_name, company, job_role, email, linkedin_url,
                     subject, email_body, status, sent_at, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.hr_name,
                    record.company,
                    record.job_role,
                    record.email.strip().lower(),
                    record.linkedin_url,
                    record.subject,
                    record.email_body,
                    record.status.value if isinstance(record.status, ContactStatus) else record.status,
                    record.sent_at.isoformat() if record.sent_at else None,
                    record.error_message,
                    datetime.utcnow().isoformat(),
                ),
            )
            return cur.lastrowid

    def update_status(
        self,
        row_id: int,
        status: ContactStatus,
        error_message: Optional[str] = None,
        sent_at: Optional[datetime] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE recruiter_contacts
                SET status = ?, error_message = ?, sent_at = ?
                WHERE id = ?
                """,
                (
                    status.value if isinstance(status, ContactStatus) else status,
                    error_message,
                    sent_at.isoformat() if sent_at else None,
                    row_id,
                ),
            )

    # ------------------------------------------------------------------
    # Reads / stats
    # ------------------------------------------------------------------
    def count_sent_today(self) -> int:
        today = date.today().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c FROM recruiter_contacts
                WHERE status = ? AND substr(sent_at, 1, 10) = ?
                """,
                (ContactStatus.SENT.value, today),
            ).fetchone()
            return row["c"] if row else 0

    def get_stats(self) -> dict:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS c FROM recruiter_contacts GROUP BY status"
            ).fetchall()
            stats = {s.value: 0 for s in ContactStatus}
            for row in rows:
                stats[row["status"]] = row["c"]
            stats["sent_today"] = self.count_sent_today()
            stats["total"] = sum(stats[s.value] for s in ContactStatus)
            return stats

    def get_latest_status(self, email: str) -> Optional[str]:
        """Most recent status recorded for this email, or None if never contacted."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT status FROM recruiter_contacts
                WHERE email = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (email.strip().lower(),),
            ).fetchone()
            return row["status"] if row else None

    def get_history(self, limit: int = 50) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT id, hr_name, company, job_role, email, status, sent_at, error_message, created_at
                FROM recruiter_contacts
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
