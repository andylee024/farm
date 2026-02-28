"""Domain errors for the Farm runtime."""

from __future__ import annotations


class FarmError(Exception):
    """Base class for all farm runtime failures."""


class InvalidTransitionError(FarmError):
    """Raised when a task transition violates the state machine."""


class TaskNotFoundError(FarmError):
    """Raised when a task is requested but not present in the registry."""


class StorageError(FarmError):
    """Raised for storage persistence and retrieval failures."""


class ExternalCommandError(FarmError):
    """Raised when a git/tmux/CI shell command fails."""


class LinearApiError(FarmError):
    """Raised when Linear direct API requests fail or return invalid payloads."""
