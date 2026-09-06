#!/usr/bin/env python3
"""
Local web UI for the Recruiter Email Agent.

Reuses the exact same agent/database/provider modules as main.py — this
is a thin browser front-end over the same pipeline:

    validate -> generate -> preview -> approve (button click) -> send -> track -> log

Run with:
    python webapp.py

Then open http://127.0.0.1:5000 in your browser.
"""

from __future__ import annotations

from pathlib import Path

# from flask import Flask, flash, redirect, render_template, request, url_for
#added
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from agent.email_generator import generate_email, load_template
from agent.processor import RecruiterEmailProcessor
from agent.validator import validate_record
from agent.linkedin_parser import extract_recruiter_details
from config.settings import get_settings
from database.db import Database
from database.models import ContactStatus, RecruiterRecord
from input.csv_reader import read_csv
from input.csv_writer import append_row, delete_row, ensure_csv_exists
from providers.gmail import GmailProvider
from utils.logger import get_logger
from utils.rate_limiter import RateLimiter

settings = get_settings()
logger = get_logger(settings.log_path)
db = Database(settings.database_path)
ensure_csv_exists(settings.recruiters_csv_path)

app = Flask(__name__)
app.secret_key = "recruiter-email-agent-local-ui"  # local single-user tool; not internet-facing


def _load_records() -> list[RecruiterRecord]:
    try:
        return read_csv(settings.recruiters_csv_path)
    except Exception:
        return []


def _build_processor(confirm_callback) -> RecruiterEmailProcessor:
    rate_limiter = RateLimiter(
        min_delay_seconds=settings.min_delay_seconds,
        max_delay_seconds=settings.max_delay_seconds,
        daily_limit=settings.daily_email_limit,
        disabled=True,  # UI sends are one-at-a-time, user-approved; no inter-send delay needed
    )
    provider = GmailProvider(
        credentials_path=settings.gmail_credentials_path,
        token_path=settings.gmail_token_path,
    )
    return RecruiterEmailProcessor(
        db=db,
        provider=provider,
        rate_limiter=rate_limiter,
        logger=logger,
        template_path=str(settings.email_template_path),
        sender_name=settings.sender_name,
        resume_path=settings.resume_path,
        auto_send=False,  # always require the explicit UI confirm step
        dry_run=False,
        confirm_callback=confirm_callback,
    )

def _build_rows():
    records = _load_records()
    rows = []

    for i, r in enumerate(records):
        rows.append(
            {
                "index": i,
                "hr_name": r.hr_name,
                "company": r.company,
                "job_role": r.job_role,
                "email": r.email,
                "linkedin_url": r.linkedin_url,
                "status": (
                    db.get_latest_status(r.email)
                    if r.email
                    else None
                ),
            }
        )

    return rows

@app.route("/")
def index():
    rows = _build_rows()
    stats = db.get_stats()

    return render_template(
        "index.html",
        rows=rows,
        stats=stats,
        settings=settings,
        extracted=None,
    )
#Linkdin Parser route
@app.route("/extract-linkedin", methods=["POST"])
def extract_linkedin():
    linkedin_post = request.form.get("linkedin_post", "").strip()

    if not linkedin_post:
        flash("Please paste a LinkedIn job post.", "error")
        return redirect(url_for("index"))

    try:
        extracted = extract_recruiter_details(linkedin_post)

        return render_template(
            "index.html",
            rows=_build_rows(),
            stats=db.get_stats(),
            settings=settings,
            extracted={
                "hr_name": extracted.hr_name or "",
                "company": extracted.company or "",
                "job_role": extracted.job_role or "",
                "email": extracted.email or "",
                "linkedin_post": linkedin_post,
            },
        )

    except Exception as exc:
        logger.exception("LinkedIn extraction failed")
        flash(f"Could not extract recruiter details: {exc}", "error")
        return redirect(url_for("index"))

@app.route("/add", methods=["POST"])
def add():
    record = RecruiterRecord(
        hr_name=request.form.get("hr_name", "").strip(),
        company=request.form.get("company", "").strip(),
        job_role=request.form.get("job_role", "").strip(),
        email=request.form.get("email", "").strip(),
        linkedin_url=request.form.get("linkedin_url", "").strip(),
    )
    result = validate_record(record)
    if not result.ok:
        flash("Could not add recruiter: " + " ".join(result.errors), "error")
        return redirect(url_for("index"))

    append_row(settings.recruiters_csv_path, record)
    flash(f"Added {record.hr_name} ({record.company}).", "success")
    return redirect(url_for("index"))


@app.route("/delete/<int:row_index>", methods=["POST"])
def delete(row_index: int):
    delete_row(settings.recruiters_csv_path, row_index)
    flash("Recruiter removed from list.", "success")
    return redirect(url_for("index"))


@app.route("/preview/<int:row_index>")
def preview(row_index: int):
    records = _load_records()
    if not (0 <= row_index < len(records)):
        flash("Recruiter not found.", "error")
        return redirect(url_for("index"))

    record = records[row_index]
    result = validate_record(record)
    if not result.ok:
        flash("Cannot preview: " + " ".join(result.errors), "error")
        return redirect(url_for("index"))

    template_text = load_template(str(settings.email_template_path))
    generated = generate_email(record, template_text, settings.sender_name)

    already_sent = db.get_latest_status(record.email) == ContactStatus.SENT.value
    resume_exists = bool(settings.resume_path) and Path(settings.resume_path).exists()

    return render_template(
        "preview.html",
        record=record,
        row_index=row_index,
        subject=generated.subject,
        body=generated.body,
        already_sent=already_sent,
        resume_exists=resume_exists,
        resume_path=settings.resume_path,
    )


@app.route("/send/<int:row_index>", methods=["POST"])
def send(row_index: int):
    records = _load_records()
    if not (0 <= row_index < len(records)):
        flash("Recruiter not found.", "error")
        return redirect(url_for("index"))

    record = records[row_index]

    # Clicking "Confirm & Send" on the preview page IS the explicit approval,
    # so the processor's confirm step just returns True here.
    processor = _build_processor(confirm_callback=lambda preview_text: True)
    result = processor.process_one(record, preview_only=False)

    if result.status == ContactStatus.SENT:
        flash(f"Email sent to {result.hr_name} ({result.email}).", "success")
    elif result.status == ContactStatus.SKIPPED:
        flash(f"Skipped: {result.error_message}", "error")
    else:
        flash(f"Failed to send: {result.error_message}", "error")

    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host=settings.web_ui_host, port=settings.web_ui_port, debug=False)
