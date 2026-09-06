"""
LinkedIn job-post parser using a local open-source LLM via Ollama.

The model extracts:
    - HR / recruiter name
    - Job role
    - Company name
    - Recruiter email

The output is constrained using a Pydantic JSON schema.
"""

from __future__ import annotations

import re

from ollama import chat
from pydantic import BaseModel, ConfigDict, Field


# -------------------------------------------------------------------
# Structured output schema
# -------------------------------------------------------------------

class RecruiterExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hr_name: str | None = Field(
        default=None,
        description=(
            "Name of the recruiter or HR person explicitly associated "
            "with this job post. Do not guess."
        ),
    )

    job_role: str | None = Field(
        default=None,
        description=(
            "Exact job title/role being advertised. Do not return "
            "locations, departments, skills, hashtags, or company names."
        ),
    )

    company: str | None = Field(
        default=None,
        description=(
            "Company or organization hiring for the role. "
            "Return the company name only."
        ),
    )

    email: str | None = Field(
        default=None,
        description=(
            "Recruiter's contact email explicitly present in the post. "
            "Do not invent an email address."
        ),
    )


# -------------------------------------------------------------------
# Model configuration
# -------------------------------------------------------------------

OLLAMA_MODEL = "gpt-oss"


# -------------------------------------------------------------------
# Email cleanup / validation
# -------------------------------------------------------------------

EMAIL_REGEX = re.compile(
    r"(?i)(?<![\w.+-])"
    r"[A-Z0-9._%+-]+"
    r"@[A-Z0-9.-]+\.[A-Z]{2,}"
    r"(?![\w.-])"
)


def _clean_email(email: str | None) -> str | None:
    """
    Validate and clean an extracted email.

    The LLM is responsible for identifying the correct email.
    Regex is only used as a safety validation layer.
    """

    if not email:
        return None

    email = email.strip().lower()

    match = EMAIL_REGEX.search(email)

    if not match:
        return None

    return match.group(0)


# -------------------------------------------------------------------
# Text cleanup
# -------------------------------------------------------------------

def _clean_text(value: str | None) -> str | None:
    """
    Basic cleanup without changing the semantic content.
    """

    if not value:
        return None

    value = re.sub(r"\s+", " ", value).strip()

    if value.lower() in {
        "unknown",
        "not found",
        "n/a",
        "none",
        "null",
    }:
        return None

    return value


# -------------------------------------------------------------------
# Main parser
# -------------------------------------------------------------------

def extract_recruiter_details(
    linkedin_post: str,
    model: str = OLLAMA_MODEL,
) -> RecruiterExtraction:
    """
    Extract recruiter information from a LinkedIn job post.

    Returns:
        RecruiterExtraction
    """

    if not linkedin_post or not linkedin_post.strip():
        raise ValueError("LinkedIn post cannot be empty.")

    system_prompt = """
You are a highly accurate information extraction system.

Your task is to extract recruiter/job information from LinkedIn job posts.

IMPORTANT RULES:

1. Extract ONLY information explicitly present in the post.
2. NEVER invent or infer missing information.
3. If a field cannot be determined with reasonable confidence, return null.
4. Do NOT confuse location with company or job title.
5. Do NOT confuse skills, hashtags, departments, domains, or technologies with the job role.
6. Prefer the explicit job title from phrases such as:
   - Hiring | ...
   - We're Hiring | ...
   - We are hiring for ...
   - Hiring for ...
   - Job Title:
   - Job Role:
   - Position:
   - Designation:
   - Role:
   - looking for a ...
   - seeking a ...
   - opening for ...
7. Company can appear:
   - in a LinkedIn company link
   - near "is hiring"
   - after "at"
   - in text such as "join <company>"
   - elsewhere in the post
8. Recruiter name should ONLY be extracted when a person's name is clearly associated
   with recruiting/contacting for this role.
9. Do NOT use the company name as the recruiter name.
10. Email must be explicitly present in the post.
11. Return the actual job title, not a shortened interpretation.
12. Ignore LinkedIn markdown formatting, hashtags, URLs, emojis and escaped characters.
13. If multiple locations appear, they are NOT job roles.
14. If multiple companies are mentioned, identify the company actually hiring for the role.
15. If multiple email addresses appear, choose the recruiter/application contact email.
16. Do not include explanations in the output. Return only the requested structured fields.
"""

    user_prompt = f"""
Extract the recruiter/job information from the following LinkedIn post.

LinkedIn post:

---------------- BEGIN POST ----------------

{linkedin_post}

----------------- END POST -----------------

Return:
- hr_name
- job_role
- company
- email

Use null when a value is not explicitly identifiable.
"""

    response = chat(
        model=model,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        format=RecruiterExtraction.model_json_schema(),
        options={
            "temperature": 0,
        },
    )

    result = RecruiterExtraction.model_validate_json(
        response.message.content
    )

    # Final deterministic cleanup
    result.hr_name = _clean_text(result.hr_name)
    result.job_role = _clean_text(result.job_role)
    result.company = _clean_text(result.company)
    result.email = _clean_email(result.email)

    return result