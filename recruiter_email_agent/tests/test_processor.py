import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from agent.processor import RecruiterEmailProcessor
from database.db import Database
from database.models import ContactStatus, RecruiterRecord
from providers.base import EmailProvider
from utils.logger import get_logger
from utils.rate_limiter import RateLimiter


class FakeProvider(EmailProvider):
    def __init__(self):
        self.sent = []

    def send_email(self, recipient, subject, body, attachment=None):
        self.sent.append((recipient, subject, body, attachment))


TEMPLATE_TEXT = (
    "Subject: Application for {JOB_ROLE} – {YOUR_NAME}\n"
    "\n"
    "Hi {HR_NAME},\n"
    "\n"
    "I came across the {JOB_ROLE} opportunity at {COMPANY_NAME}.\n"
)


@pytest.fixture()
def workspace():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        template_path = tmp_path / "template.txt"
        template_path.write_text(TEMPLATE_TEXT, encoding="utf-8")

        resume_path = tmp_path / "resume.pdf"
        resume_path.write_bytes(b"%PDF-1.4 fake resume")

        db = Database(str(tmp_path / "test.db"))
        logger = get_logger(str(tmp_path / "agent.log"))
        provider = FakeProvider()
        rate_limiter = RateLimiter(
            min_delay_seconds=0, max_delay_seconds=0, daily_limit=2, disabled=True
        )

        yield {
            "tmp_path": tmp_path,
            "template_path": str(template_path),
            "resume_path": str(resume_path),
            "db": db,
            "logger": logger,
            "provider": provider,
            "rate_limiter": rate_limiter,
        }


def make_record(**overrides):
    defaults = dict(
        hr_name="Priya Sharma",
        company="Google",
        job_role="Data Scientist",
        email="priya@google.com",
        linkedin_url="",
    )
    defaults.update(overrides)
    return RecruiterRecord(**defaults)


def build_processor(ws, **kwargs):
    defaults = dict(
        db=ws["db"],
        provider=ws["provider"],
        rate_limiter=ws["rate_limiter"],
        logger=ws["logger"],
        template_path=ws["template_path"],
        sender_name="Ashish Singh",
        resume_path=ws["resume_path"],
        auto_send=True,
        dry_run=False,
    )
    defaults.update(kwargs)
    return RecruiterEmailProcessor(**defaults)


def test_dry_run_never_calls_provider(workspace):
    processor = build_processor(workspace, dry_run=True)
    record = make_record()
    result = processor.process_one(record)
    assert workspace["provider"].sent == []
    assert result.status == ContactStatus.SKIPPED


def test_missing_attachment_stops_sending(workspace):
    processor = build_processor(workspace, resume_path="/nonexistent/resume.pdf")
    record = make_record()
    result = processor.process_one(record)
    assert result.status == ContactStatus.FAILED
    assert "Resume not found" in result.error_message
    assert workspace["provider"].sent == []


def test_successful_send(workspace):
    processor = build_processor(workspace)
    record = make_record()
    result = processor.process_one(record)
    assert result.status == ContactStatus.SENT
    assert len(workspace["provider"].sent) == 1
    recipient, subject, body, attachment = workspace["provider"].sent[0]
    assert recipient == "priya@google.com"
    assert "Data Scientist" in subject
    assert attachment == workspace["resume_path"]


def test_duplicate_email_is_skipped(workspace):
    processor = build_processor(workspace)
    record1 = make_record()
    processor.process_one(record1)  # first send succeeds

    record2 = make_record(hr_name="Priya S. Duplicate")
    result2 = processor.process_one(record2)
    assert result2.status == ContactStatus.SKIPPED
    assert "Already contacted" in result2.error_message
    assert len(workspace["provider"].sent) == 1


def test_daily_limit_enforced(workspace):
    processor = build_processor(workspace)
    # daily_limit is 2 in the fixture's rate limiter.
    r1 = processor.process_one(make_record(email="one@x.com"))
    r2 = processor.process_one(make_record(email="two@x.com"))
    r3 = processor.process_one(make_record(email="three@x.com"))

    assert r1.status == ContactStatus.SENT
    assert r2.status == ContactStatus.SENT
    assert r3.status == ContactStatus.FAILED
    assert "Daily email limit reached" in r3.error_message
    assert len(workspace["provider"].sent) == 2


def test_invalid_record_never_sent(workspace):
    processor = build_processor(workspace)
    record = make_record(email="not-an-email")
    result = processor.process_one(record)
    assert result.status == ContactStatus.FAILED
    assert workspace["provider"].sent == []
