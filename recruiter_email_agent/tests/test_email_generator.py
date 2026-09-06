import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.email_generator import generate_email, render_template, split_subject_and_body
from database.models import RecruiterRecord

TEMPLATE = (
    "Subject: Application for {JOB_ROLE} – {YOUR_NAME}\n"
    "\n"
    "Hi {HR_NAME},\n"
    "\n"
    "I came across the {JOB_ROLE} opportunity at {COMPANY_NAME}.\n"
    "\n"
    "Best Regards,\n"
    "{YOUR_NAME}\n"
)


def make_record(**overrides):
    defaults = dict(
        hr_name="Priya Sharma",
        company="Google",
        job_role="Data Scientist",
        email="priya@google.com",
        linkedin_url="https://linkedin.com/jobs/1",
    )
    defaults.update(overrides)
    return RecruiterRecord(**defaults)


def test_placeholders_are_replaced():
    record = make_record()
    rendered = render_template(TEMPLATE, record, sender_name="Ashish Singh")

    assert "{HR_NAME}" not in rendered
    assert "{COMPANY_NAME}" not in rendered
    assert "{JOB_ROLE}" not in rendered
    assert "{YOUR_NAME}" not in rendered

    assert "Priya Sharma" in rendered
    assert "Google" in rendered
    assert "Data Scientist" in rendered
    assert "Ashish Singh" in rendered


def test_rest_of_template_is_unchanged():
    record = make_record()
    rendered = render_template(TEMPLATE, record, sender_name="Ashish Singh")
    assert "Best Regards," in rendered
    assert "I came across the Data Scientist opportunity at Google." in rendered


def test_generate_email_splits_subject_and_body():
    record = make_record()
    generated = generate_email(record, TEMPLATE, sender_name="Ashish Singh")
    assert generated.subject == "Application for Data Scientist – Ashish Singh"
    assert "Hi Priya Sharma," in generated.body
    assert "Subject:" not in generated.body


def test_split_subject_and_body_requires_subject_line():
    import pytest

    with pytest.raises(ValueError):
        split_subject_and_body("No subject line here\n\nBody text")
