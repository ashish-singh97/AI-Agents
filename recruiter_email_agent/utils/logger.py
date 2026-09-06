"""
Structured logging setup.

Logs go to both stdout (for interactive use) and a rotating file at
`logs/agent.log`. Secrets (passwords, OAuth tokens) are never logged;
callers should only pass in recruiter/status metadata.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOGGER_NAME = "recruiter_email_agent"


def get_logger(log_path: str) -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.INFO)

    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def log_contact_event(
    logger: logging.Logger,
    hr_name: str,
    company: str,
    job_role: str,
    email: str,
    status: str,
    error_message: str | None = None,
) -> None:
    msg = f"recruiter={hr_name!r} company={company!r} role={job_role!r} email={email!r} status={status}"
    if error_message:
        msg += f" error={error_message!r}"
    if status == "FAILED":
        logger.error(msg)
    elif status == "SKIPPED":
        logger.warning(msg)
    else:
        logger.info(msg)
