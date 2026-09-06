"""
Abstract email provider interface.

Any concrete provider (Gmail today, others later) implements this so the
rest of the application never depends on a specific vendor SDK.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class EmailProvider(ABC):
    @abstractmethod
    def send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        attachment: Optional[str] = None,
    ) -> None:
        """
        Send an email. Should raise an exception on failure so the caller
        can catch it and mark the contact as FAILED with the error message.
        """
        raise NotImplementedError
