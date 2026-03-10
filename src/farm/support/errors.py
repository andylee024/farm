"""Shared runtime errors for Farm."""

from __future__ import annotations


class FarmError(Exception):
    """Base class for all farm runtime failures."""


class ExternalCommandError(FarmError):
    """Raised when a git/tmux shell command fails."""


class LinearApiError(FarmError):
    """Raised when Linear API requests fail or return invalid payloads."""


class UnsupportedRuntimeError(FarmError):
    """Raised when a configured task runtime is not available yet."""
