"""
CSV write helpers for the web UI.

The UI treats the CSV file as the single source of truth for the
recruiter list (same file the CLI's --input flag points at). Rows are
addressed by their zero-based position in the file for simple edit/delete
from the browser.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List

from database.models import RecruiterRecord

FIELDNAMES = ["hr_name", "company", "job_role", "email", "linkedin_url"]


def ensure_csv_exists(path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()


def append_row(path: str | Path, record: RecruiterRecord) -> None:
    ensure_csv_exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow(
            {
                "hr_name": record.hr_name.strip(),
                "company": record.company.strip(),
                "job_role": record.job_role.strip(),
                "email": record.email.strip(),
                "linkedin_url": record.linkedin_url.strip(),
            }
        )


def delete_row(path: str | Path, row_index: int) -> None:
    """Delete the row at `row_index` (0-based, matching read_csv() order)."""
    from input.csv_reader import read_csv

    records = read_csv(path)
    if 0 <= row_index < len(records):
        del records[row_index]
    _rewrite(path, records)


def _rewrite(path: str | Path, records: List[RecruiterRecord]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in records:
            writer.writerow(
                {
                    "hr_name": r.hr_name,
                    "company": r.company,
                    "job_role": r.job_role,
                    "email": r.email,
                    "linkedin_url": r.linkedin_url,
                }
            )
