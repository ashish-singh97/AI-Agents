import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.validator import (
    is_valid_email,
    validate_no_unresolved_placeholders,
    validate_record,
)
from database.models import RecruiterRecord


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


def test_valid_record_passes():
    result = validate_record(make_record())
    assert result.ok
    assert result.errors == []


def test_missing_email_fails():
    result = validate_record(make_record(email=""))
    assert not result.ok
    assert any("Missing recruiter email" in e for e in result.errors)


def test_missing_hr_name_fails():
    result = validate_record(make_record(hr_name=""))
    assert not result.ok


def test_missing_company_fails():
    result = validate_record(make_record(company=""))
    assert not result.ok


def test_missing_job_role_fails():
    result = validate_record(make_record(job_role=""))
    assert not result.ok


def test_invalid_email_format_fails():
    result = validate_record(make_record(email="not-an-email"))
    assert not result.ok
    assert any("Invalid email address" in e for e in result.errors)


def test_email_format_checker():
    assert is_valid_email("a.b+c@example.co.in")
    assert not is_valid_email("bad@")
    assert not is_valid_email("bad.com")
    assert not is_valid_email("")


def test_unresolved_placeholder_detected():
    result = validate_no_unresolved_placeholders("Hi {HR_NAME}, welcome to {COMPANY_NAME}.")
    assert not result.ok
    assert "HR_NAME" in result.errors[0]


def test_no_unresolved_placeholder_passes():
    result = validate_no_unresolved_placeholders("Hi Priya, welcome to Google.")
    assert result.ok
