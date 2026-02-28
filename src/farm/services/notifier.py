"""Operator-facing notifications."""

from __future__ import annotations


class Notifier:
    """Sends concise status updates to the operator."""

    def notify(self, message: str) -> None:
        raise NotImplementedError(f"Notifier is not implemented yet: {message}")

