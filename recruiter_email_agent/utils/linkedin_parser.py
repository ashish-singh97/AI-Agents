#!/usr/bin/env python3
"""
LinkedIn job-post parser.

Extracts:
    - recruiter name
    - company name
    - job role
    - recruiter email

The parser uses multiple regex patterns and fallbacks because LinkedIn
posts can have many different formats.
"""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import unquote


# -------------------------------------------------------------------
# Generic patterns
# -------------------------------------------------------------------

EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])"
    r"([A-Za-z0-9][A-Za-z0-9._%+-]*"
    r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
    r"(?![\w.-])",
    re.IGNORECASE,
)


# Common locations used to identify where a job title ends.
LOCATION_PATTERN = (
    r"(?:Bangalore|Bengaluru|Mumbai|Pune|Delhi|"
    r"New Delhi|Hyderabad|Chennai|Noida|Gurgaon|Gurugram|"
    r"Kolkata|Ahmedabad|Jaipur|Chandigarh|Mohali|Indore|"
    r"Lucknow|Remote|India|US|USA|UK|London|Singapore|"
    r"Dublin|Toronto|Canada)"
)


GENERIC_EMAIL_NAMES = {
    "hr",
    "career",
    "careers",
    "jobs",
    "job",
    "recruitment",
    "recruiter",
    "recruiters",
    "hiring",
    "talent",
    "talentacquisition",
    "info",
    "contact",
    "admin",
    "support",
    "resume",
    "resumes",
    "cv",
    "cvs",
}


def clean_linkedin_text(post: str) -> str:
    """
    Remove LinkedIn/Markdown formatting while preserving visible text.
    """

    text = unescape(post)
    text = unquote(text)

    # Convert:
    # [Company Name](https://linkedin.com/...)
    # into:
    # Company Name
    text = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        text,
        flags=re.MULTILINE,
    )

    # Remove bold / italic markdown
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)

    # Remove LinkedIn hashtag symbol
    text = re.sub(
        r"(?<!\w)#([A-Za-z][A-Za-z0-9_-]*)",
        r"\1",
        text,
    )

    # Remove escaped markdown characters
    text = text.replace(r"\-", "-")
    text = text.replace(r"\_", "_")
    text = text.replace(r"\&", "&")
    text = text.replace(r"\.", ".")

    # Normalize spaces
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)

    return text.strip()


def extract_email(text: str) -> str | None:
    """
    Extract the first valid email address.

    Handles:
        person@company.com
        mailto:person@company.com
        [person@company.com](mailto:person@company.com)
        EMAIL: person@company.com
        Send CV to person@company.com
    """

    # First look for mailto specifically.
    mailto = re.search(
        r"mailto[:\\]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
        text,
        re.IGNORECASE,
    )

    if mailto:
        return mailto.group(1).strip()

    match = EMAIL_PATTERN.search(text)

    if match:
        return match.group(1).strip()

    return None


def extract_company(text: str) -> str | None:
    """
    Extract company name using multiple common LinkedIn patterns.
    """

    patterns = [
        # Credence Global Solutions is hiring
        rf"(?<!\w)"
        rf"([A-Z][A-Za-z0-9&.,'’()\- ]{{2,80}}?)"
        rf"\s+is\s+(?:now\s+)?hiring\b",

        # Company Name — Hiring
        rf"(?<!\w)"
        rf"([A-Z][A-Za-z0-9&.,'’()\- ]{{2,80}}?)"
        rf"\s*[-–—|:]\s*(?:is\s+)?hiring\b",

        # Company: ABC Technologies
        r"(?:Company|Organization|Employer|Client)"
        r"\s*[:\-]\s*([^\n|]+)",

        # Hiring at ABC
        r"(?:Hiring|Opening|Opportunity|Vacancy)"
        r"\s+(?:at|with|for)\s+"
        r"([A-Z][A-Za-z0-9&.,'’()\- ]{2,80})",

        # Work with ABC Technologies
        r"(?:work|working|opportunity)"
        r"\s+(?:with|at)\s+"
        r"([A-Z][A-Za-z0-9&.,'’()\- ]{2,80})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if not match:
            continue

        company = match.group(1).strip()

        company = re.sub(
            r"\s+(?:is\s+)?hiring.*$",
            "",
            company,
            flags=re.IGNORECASE,
        )

        company = company.strip(" -–—|:")

        if company:
            return company

    return None


def extract_job_role(text: str) -> str | None:
    """
    Extract job role from common LinkedIn job-post formats.
    """

    patterns = [
        # Hiring | Lead Data Scientist | Pune
        # We’re Hiring | AI Data Scientist
        rf"(?:We[’']?re\s+)?(?:Hiring|Hiring for|Opening for|Open position for|"
        rf"Vacancy for|Opportunity for)"
        rf"\s*[:|\-–—]\s*"
        rf"(.{{3,100}}?)"
        rf"(?:\s*[:|\-–—]\s*(?={LOCATION_PATTERN})|$)",

        # Hiring: Lead Data Scientist
        rf"(?:Hiring|Hiring for|Opening for|Open position for|"
        rf"Vacancy for|Opportunity for)"
        rf"\s*(?:an?\s+|the\s+)?"
        rf"([A-Za-z0-9][A-Za-z0-9 ,&/().+#'’\-–—]{{2,100}}?)"
        rf"(?=\s+(?:at|@|with|for|in)\s+)",

        # Job Title: Lead Data Scientist
        r"(?:Job Title|Job Role|Role|Position|Designation)"
        r"\s*[:\-]\s*"
        r"([^\n|]+)",

        # Position - Lead Data Scientist
        r"(?:Position|Role)\s*[-–—|]\s*"
        r"([^\n|]+)",

        # We are looking for a Lead Data Scientist
        r"(?:looking for|seeking|hiring)"
        r"\s+(?:an?\s+|the\s+)?"
        r"([A-Za-z0-9][A-Za-z0-9 ,&/().+#'’\-–—]{2,100}?)"
        r"\s+(?:at|with|for)\s+",

        # for the position of Lead Data Scientist
        r"(?:position of|role of)\s+"
        r"([A-Za-z0-9][A-Za-z0-9 ,&/().+#'’\-–—]{2,100})",

        # Lead Data Scientist | Pune
        rf"(?m)^\s*([A-Z][A-Za-z0-9 ,&/().+#'’\-–—]{{2,80}})"
        rf"\s*\|\s*(?={LOCATION_PATTERN})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if not match:
            continue

        role = match.group(1).strip()

        # Remove hashtags
        role = role.replace("#", "")

        # Remove leading/trailing separators
        role = role.strip(" -–—|:")

        # Remove common trailing words
        role = re.sub(
            r"\s+(?:at|with|for|in)\s*$",
            "",
            role,
            flags=re.IGNORECASE,
        )

        # Don't accept generic phrases
        if role.lower() in {
            "experienced",
            "candidates",
            "professionals",
            "talent",
            "the position",
            "this position",
        }:
            continue

        if role:
            return role

    return None


def extract_recruiter_name(
    text: str,
    email: str | None = None,
) -> str | None:
    """
    Extract recruiter name when explicitly mentioned.

    Examples:
        Contact: Anushka Kanodia
        Recruiter: Anushka Kanodia
        Hiring Manager: Rahul Sharma
        Reach out to Priya Singh
        Send your CV to Anushka Kanodia
    """

    patterns = [
        # Recruiter: Anushka Kanodia
        r"(?:Recruiter|Recruiter Name|Hiring Manager|"
        r"Talent Acquisition|HR Contact|HR)"
        r"\s*[:\-]\s*"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",

        # Contact: Anushka Kanodia
        r"(?:Contact|Contact Person|Point of Contact|POC)"
        r"\s*[:\-]?\s*"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",

        # Reach out to Anushka Kanodia
        r"(?:reach out to|connect with|contact|speak to|"
        r"talk to|send.*?to)"
        r"\s+"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",

        # Thanks / Regards, Anushka Kanodia
        r"(?:Thanks|Thank you|Regards|Best Regards|Warm Regards)"
        r"\s*[,:\-]?\s*"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            name = match.group(1).strip()

            if 2 <= len(name.split()) <= 4:
                return name

    # ---------------------------------------------------------
    # Fallback: infer name from email.
    #
    # anushka.kanodia@company.com
    #      ↓
    # Anushka Kanodia
    # ---------------------------------------------------------

    if email:
        local_part = email.split("@", 1)[0]

        parts = re.split(r"[._\-]+", local_part)

        if (
            len(parts) >= 2
            and all(re.fullmatch(r"[A-Za-z]+", p) for p in parts)
            and parts[0].lower() not in GENERIC_EMAIL_NAMES
        ):
            return " ".join(
                part.capitalize()
                for part in parts[:3]
            )

    return None


def extract_recruiter_details(post: str) -> dict[str, str | None]:
    """
    Main extraction function.
    """

    if not post or not post.strip():
        return {
            "recruiter_name": None,
            "job_role": None,
            "company_name": None,
            "recruiter_email": None,
        }

    text = clean_linkedin_text(post)

    email = extract_email(text)
    company = extract_company(text)
    job_role = extract_job_role(text)
    recruiter_name = extract_recruiter_name(text, email)

    return {
        "recruiter_name": recruiter_name,
        "job_role": job_role,
        "company_name": company,
        "recruiter_email": email,
    }