from __future__ import annotations

import json
import re

from mlx_lm import load, generate
from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# MODEL CONFIGURATION
# ============================================================

MODEL_PATH = "./models/Qwen3-1.7B-MLX-4bit"

print("Loading local model...")

model, tokenizer = load(MODEL_PATH)

print("Model loaded.")


# ============================================================
# OUTPUT SCHEMA
# ============================================================

class RecruiterExtraction(BaseModel):

    model_config = ConfigDict(extra="ignore")

    hr_name: str | None = Field(default=None)

    job_role: str | None = Field(default=None)

    company: str | None = Field(default=None)

    email: str | None = Field(default=None)


# ============================================================
# EMAIL REGEX
# ============================================================

EMAIL_REGEX = re.compile(
    r"(?i)(?<![\w.+-])"
    r"[A-Z0-9._%+-]+"
    r"@[A-Z0-9.-]+\.[A-Z]{2,}"
    r"(?![\w.-])"
)


def clean_email(email: str | None) -> str | None:

    if not email:
        return None

    email = email.strip().lower()

    match = EMAIL_REGEX.search(email)

    if not match:
        return None

    return match.group(0)


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(value: str | None) -> str | None:

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


# ============================================================
# REMOVE QWEN THINKING
# ============================================================

def remove_thinking(text: str) -> str:

    # Remove complete <think>...</think>
    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Remove an incomplete <think> block
    if "<think>" in text.lower():

        text = re.split(
            r"<think>",
            text,
            flags=re.IGNORECASE,
        )[0]

    return text.strip()


# ============================================================
# EXTRACT JSON
# ============================================================

def extract_json(text: str) -> dict:

    # Remove Qwen reasoning
    text = remove_thinking(text)

    # Find JSON object
    match = re.search(
        r"\{.*?\}",
        text,
        re.DOTALL,
    )

    if not match:

        raise ValueError(
            f"Model did not return valid JSON:\n{text}"
        )

    json_text = match.group(0)

    try:

        return json.loads(json_text)

    except json.JSONDecodeError as e:

        raise ValueError(
            f"Invalid JSON returned by model:\n{json_text}"
        ) from e


# ============================================================
# MAIN EXTRACTION FUNCTION
# ============================================================

def extract_recruiter_details(
    linkedin_post: str,
) -> RecruiterExtraction:

    if not linkedin_post or not linkedin_post.strip():

        raise ValueError(
            "LinkedIn post cannot be empty."
        )

    # Limit unnecessary context
    linkedin_post = linkedin_post[:12000]

#     system_prompt = """
# You are a LinkedIn job-post information extraction system.

# DO NOT EXPLAIN YOUR ANSWER.
# DO NOT PROVIDE REASONING.
# DO NOT THINK ALOUD.

# Extract ONLY these four fields:

# 1. hr_name
# 2. job_role
# 3. company
# 4. email

# RULES:

# - Extract only information explicitly present in the post.
# - Never guess.
# - Missing information must be null.
# - Never confuse a location with a job role.
# - Never confuse skills with a job role.
# - Extract the complete job title.
# - Extract the company actually hiring.
# - Extract HR/recruiter name only when clearly associated with recruitment.
# - Email must explicitly appear in the post.
# - Never invent an email.
# - Ignore hashtags and URLs.

# Return ONLY valid JSON.

# Required format:

# {
#   "hr_name": null,
#   "job_role": null,
#   "company": null,
#   "email": null
# }
# """

    system_prompt = """
    You are a LinkedIn job-post information extraction system.

DO NOT EXPLAIN YOUR ANSWER.
DO NOT PROVIDE REASONING.
DO NOT THINK ALOUD.

Extract ONLY these four fields:

1. hr_name
2. job_role
3. company
4. email

Rules:
- Return ONLY valid JSON. No explanation or reasoning.
- Missing information = null.
- Never invent information.
- hr_name: extract ONLY the recruiter's FIRST NAME.
- First use an explicitly mentioned recruiter/HR/hiring contact.
- If no name is mentioned, infer ONLY the first name from a clearly personal email.
- Never guess or add a surname.
- Examples: priya.sharma@abc.com → "Priya"; isha.a@idfcbank.com → "Isha".
- Generic emails like careers@, hr@, jobs@, hiring@, recruitment@, info@, contact@ → hr_name = null.
- job_role: extract the complete advertised job title. Never use location or skills.
- company: extract the company actually hiring.
- Preserve the company's correct official capitalization and spacing.
- Correct obvious capitalization/spacing errors in company names.
  Example: "IDFcbank" → "IDFC Bank", "accenture" → "Accenture".
- Do not change the actual company name or invent a different company.
- email: extract the email exactly as written. Never create or modify it.
- Ignore hashtags and URLs.


Output:
{
  "hr_name": null,
  "job_role": null,
  "company": null,
  "email": null
}
"""
    user_prompt = f"""
Extract the information from this LinkedIn job post.

BEGIN POST

{linkedin_post}

END POST

Return ONLY JSON.
"""

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    # ========================================================
    # CREATE PROMPT
    # ========================================================

    prompt = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        enable_thinking=False,
    )

    # ========================================================
    # GENERATE
    # ========================================================

    response = generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=150,
        verbose=False,
    )

    print("\nRaw model response:")
    print(response)

    # ========================================================
    # PARSE JSON
    # ========================================================

    data = extract_json(response)

    result = RecruiterExtraction.model_validate(data)

    # ========================================================
    # FINAL CLEANUP
    # ========================================================

    result.hr_name = clean_text(result.hr_name)

    result.job_role = clean_text(result.job_role)

    result.company = clean_text(result.company)

    result.email = clean_email(result.email)

    return result