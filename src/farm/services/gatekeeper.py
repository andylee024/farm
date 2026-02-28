"""Gatekeeper for ready-for-review decisions."""

from __future__ import annotations


class Gatekeeper:
    """Applies deterministic completion criteria."""

    def evaluate(self) -> None:
        raise NotImplementedError("Gatekeeper is not implemented yet.")

