"""
Rate limiting helpers: per-send random delay + daily sending cap.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass


class DailyLimitReached(Exception):
    """Raised when the configured daily email limit has been hit."""


@dataclass
class RateLimiter:
    min_delay_seconds: int
    max_delay_seconds: int
    daily_limit: int
    disabled: bool = False

    def check_daily_limit(self, sent_today: int) -> None:
        if sent_today >= self.daily_limit:
            raise DailyLimitReached(
                f"Daily email limit reached ({sent_today}/{self.daily_limit}). "
                "No additional emails will be sent."
            )

    def wait(self) -> float:
        """Sleep a random amount between min/max delay. Returns seconds waited."""
        if self.disabled or self.max_delay_seconds <= 0:
            return 0.0
        delay = random.uniform(self.min_delay_seconds, self.max_delay_seconds)
        time.sleep(delay)
        return delay
