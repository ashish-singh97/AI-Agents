#!/usr/bin/env python3
"""
Recruiter Cold Email Agent — CLI entrypoint.

Examples:
    python main.py --input recruiters.csv --preview
    python main.py --input recruiters.csv --dry-run
    python main.py --input recruiters.csv
    python main.py --status
    python main.py --history
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent.processor import RecruiterEmailProcessor
from config.settings import get_settings
from database.db import Database
from input.csv_reader import read_csv
from input.excel_reader import read_excel
from providers.gmail import GmailProvider
from utils.logger import get_logger
from utils.rate_limiter import RateLimiter


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send personalized cold emails to recruiters from a CSV/Excel file."
    )
    parser.add_argument("--input", help="Path to a CSV or Excel (.xlsx) file of recruiters.")
    parser.add_argument(
        "--preview", action="store_true", help="Generate and print email previews only; do not send."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Generate emails but never call the email provider."
    )
    parser.add_argument(
        "--yes", action="store_true", help="Skip interactive per-email confirmation (same effect as AUTO_SEND=true)."
    )
    parser.add_argument("--status", action="store_true", help="Show sending statistics and exit.")
    parser.add_argument("--history", action="store_true", help="Show previously contacted recruiters and exit.")
    parser.add_argument("--limit", type=int, default=50, help="Row limit for --history output.")
    return parser


def read_input(path: str):
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        return read_csv(path)
    if suffix in {".xlsx", ".xlsm"}:
        return read_excel(path)
    raise ValueError(f"Unsupported input file type: {suffix}. Use .csv or .xlsx.")


def cmd_status(db: Database) -> None:
    stats = db.get_stats()
    print("--------------------------------")
    print("STATUS")
    print("--------------------------------")
    print(f"Total records:  {stats['total']}")
    print(f"Sent:           {stats['SENT']}")
    print(f"Failed:         {stats['FAILED']}")
    print(f"Skipped:        {stats['SKIPPED']}")
    print(f"Pending:        {stats['PENDING']}")
    print(f"Sent today:     {stats['sent_today']}")
    print("--------------------------------")


def cmd_history(db: Database, limit: int) -> None:
    rows = db.get_history(limit=limit)
    if not rows:
        print("No history found.")
        return
    print(f"{'ID':<5} {'HR Name':<20} {'Company':<20} {'Role':<20} {'Email':<28} {'Status':<9} Sent At")
    print("-" * 130)
    for row in rows:
        print(
            f"{row['id']:<5} {row['hr_name'][:19]:<20} {row['company'][:19]:<20} "
            f"{row['job_role'][:19]:<20} {row['email'][:27]:<28} {row['status']:<9} "
            f"{row['sent_at'] or ''}"
        )


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    settings = get_settings()
    logger = get_logger(settings.log_path)
    db = Database(settings.database_path)

    if args.status:
        cmd_status(db)
        return 0

    if args.history:
        cmd_history(db, args.limit)
        return 0

    if not args.input:
        parser.print_help()
        return 1

    try:
        records = read_input(args.input)
    except Exception as exc:
        print(f"Error reading input file: {exc}")
        return 1

    if not records:
        print("No recruiter records found in input file.")
        return 1

    auto_send = settings.auto_send or args.yes
    dry_run = args.dry_run or settings.dry_run_default

    rate_limiter = RateLimiter(
        min_delay_seconds=settings.min_delay_seconds,
        max_delay_seconds=settings.max_delay_seconds,
        daily_limit=settings.daily_email_limit,
        disabled=dry_run or args.preview,
    )

    provider = GmailProvider(
        credentials_path=settings.gmail_credentials_path,
        token_path=settings.gmail_token_path,
    )

    processor = RecruiterEmailProcessor(
        db=db,
        provider=provider,
        rate_limiter=rate_limiter,
        logger=logger,
        template_path=str(settings.email_template_path),
        sender_name=settings.sender_name,
        resume_path=settings.resume_path,
        auto_send=auto_send,
        dry_run=dry_run,
    )

    if args.preview:
        for i, record in enumerate(records, start=1):
            processed = processor.process_one(record, preview_only=True)
            print(f"[{i}/{len(records)}] {record.hr_name} — {record.company} — {record.job_role}")
            if processed.subject and processed.email_body:
                from agent.processor import format_preview

                print(format_preview(record.email, processed.subject, processed.email_body))
            else:
                print(f"Could not generate preview: {processed.error_message}")
            print()
        return 0

    summary = processor.process_batch(records, preview_only=False)
    print(summary.as_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
