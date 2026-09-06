import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from database.db import Database
from database.models import ContactStatus, RecruiterRecord


@pytest.fixture()
def db():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.db")
        yield Database(db_path)


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


def test_record_and_read_back(db):
    record = make_record(status=ContactStatus.SENT)
    row_id = db.record_contact(record)
    assert row_id > 0
    stats = db.get_stats()
    assert stats["SENT"] == 1
    assert stats["total"] == 1


def test_duplicate_detection_only_flags_sent(db):
    # A FAILED attempt should not count as "already contacted".
    db.record_contact(make_record(email="dup@x.com", status=ContactStatus.FAILED))
    assert db.already_contacted("dup@x.com") is False

    db.record_contact(make_record(email="dup@x.com", status=ContactStatus.SENT))
    assert db.already_contacted("dup@x.com") is True


def test_duplicate_detection_case_insensitive(db):
    db.record_contact(make_record(email="Person@Example.com", status=ContactStatus.SENT))
    assert db.already_contacted("person@example.com") is True


def test_count_sent_today(db):
    from datetime import datetime

    record = make_record(email="a@b.com", status=ContactStatus.SENT)
    record.sent_at = datetime.utcnow()
    db.record_contact(record)
    assert db.count_sent_today() == 1


def test_history_returns_rows(db):
    db.record_contact(make_record(status=ContactStatus.SENT))
    db.record_contact(make_record(email="second@x.com", status=ContactStatus.FAILED))
    rows = db.get_history(limit=10)
    assert len(rows) == 2
