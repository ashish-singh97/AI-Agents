"""
Application configuration loader.

Reads configuration from environment variables (populated from a `.env`
file via python-dotenv) and exposes them as a single, typed `Settings`
object that the rest of the application imports.

Nothing here talks to the network or the filesystem beyond reading the
`.env` file and checking that the resume/template paths make sense.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a .env file in the project root, if present.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default


@dataclass
class Settings:
    # --- Identity / template ---
    sender_name: str = field(default_factory=lambda: os.getenv("SENDER_NAME", "Your Name"))
    email_template_path: Path = field(
        default_factory=lambda: PROJECT_ROOT / "config" / "email_template.txt"
    )

    # --- Provider ---
    email_provider: str = field(default_factory=lambda: os.getenv("EMAIL_PROVIDER", "gmail"))

    # --- Resume ---
    resume_path: str = field(default_factory=lambda: os.getenv("RESUME_PATH", ""))

    # --- Sending behavior ---
    auto_send: bool = field(default_factory=lambda: _get_bool("AUTO_SEND", False))
    dry_run_default: bool = field(default_factory=lambda: _get_bool("DRY_RUN", False))

    # --- Rate limiting ---
    min_delay_seconds: int = field(default_factory=lambda: _get_int("MIN_DELAY_SECONDS", 30))
    max_delay_seconds: int = field(default_factory=lambda: _get_int("MAX_DELAY_SECONDS", 90))
    daily_email_limit: int = field(default_factory=lambda: _get_int("DAILY_EMAIL_LIMIT", 30))
    disable_rate_limit: bool = field(
        default_factory=lambda: _get_bool("DISABLE_RATE_LIMIT", False)
    )

    # --- Gmail OAuth ---
    gmail_credentials_path: str = field(
        default_factory=lambda: os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
    )
    gmail_token_path: str = field(
        default_factory=lambda: os.getenv("GMAIL_TOKEN_PATH", "token.json")
    )

    # --- Storage / logging ---
    database_path: str = field(
        default_factory=lambda: os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "database" / "recruiter_agent.db"))
    )
    log_path: str = field(
        default_factory=lambda: os.getenv("LOG_PATH", str(PROJECT_ROOT / "logs" / "agent.log"))
    )

    # --- Web UI ---
    recruiters_csv_path: str = field(
        default_factory=lambda: os.getenv(
            "RECRUITERS_CSV_PATH", str(PROJECT_ROOT / "data" / "recruiters.csv")
        )
    )
    web_ui_host: str = field(default_factory=lambda: os.getenv("WEB_UI_HOST", "127.0.0.1"))
    web_ui_port: int = field(default_factory=lambda: _get_int("WEB_UI_PORT", 5000))

    def validate_delays(self) -> None:
        if self.min_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("Delay values must be non-negative.")
        if self.min_delay_seconds > self.max_delay_seconds:
            raise ValueError("MIN_DELAY_SECONDS cannot be greater than MAX_DELAY_SECONDS.")


def get_settings() -> Settings:
    """Return a freshly constructed Settings instance (env is re-read)."""
    s = Settings()
    s.validate_delays()
    return s
