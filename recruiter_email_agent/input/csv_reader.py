"""
CSV input reader.

Expected columns (case-insensitive, order-independent):
    hr_name, company, job_role, email, linkedin_url (optional)
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List

from database.models import RecruiterRecord

COLUMN_ALIASES = {
    "hr_name": {"hr_name", "hrname", "recruiter_name", "name"},
    "company": {"company", "company_name", "employer"},
    "job_role": {"job_role", "role", "position", "jobtitle", "job_title"},
    "email": {"email", "recruiter_email", "email_address"},
    "linkedin_url": {"linkedin_url", "linkedin", "job_url", "url"},
}


def _normalize_headers(fieldnames: list[str]) -> dict[str, str]:
    """Map actual CSV header -> canonical field name."""
    mapping: dict[str, str] = {}
    for header in fieldnames:
        key = header.strip().lower().replace(" ", "_")
        for canonical, aliases in COLUMN_ALIASES.items():
            if key in aliases:
                mapping[header] = canonical
                break
    return mapping


def read_csv(path: str | Path) -> List[RecruiterRecord]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    records: List[RecruiterRecord] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"CSV file has no header row: {path}")
        header_map = _normalize_headers(reader.fieldnames)

        for row in reader:
            values = {canonical: "" for canonical in COLUMN_ALIASES}
            for raw_header, value in row.items():
                canonical = header_map.get(raw_header)
                if canonical:
                    values[canonical] = (value or "").strip()

            # Skip fully blank rows.
            if not any(values.values()):
                continue

            records.append(
                RecruiterRecord(
                    hr_name=values["hr_name"],
                    company=values["company"],
                    job_role=values["job_role"],
                    email=values["email"],
                    linkedin_url=values["linkedin_url"],
                )
            )
    return records
