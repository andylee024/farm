"""Typed models shared across Farm services."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

REGISTRY_SCHEMA_VERSION = 1


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class AgentKind(str, Enum):
    CODEX = "codex"
    CLAUDE = "claude"


class TaskState(str, Enum):
    DRAFTED = "drafted"
    QUEUED = "queued"
    RUNNING = "running"
    PR_OPEN = "pr_open"
    TESTS_PASSED = "tests_passed"
    TESTS_FAILED = "tests_failed"
    RETRYING = "retrying"
    READY_FOR_REVIEW = "ready_for_review"
    BLOCKED_NEEDS_HUMAN = "blocked_needs_human"
    MERGED = "merged"
    CHANGES_REQUESTED = "changes_requested"
    CANCELED = "canceled"


class TestStatus(str, Enum):
    UNKNOWN = "unknown"
    PASS = "pass"
    FAIL = "fail"


class EventType(str, Enum):
    STATE_TRANSITION = "state_transition"
    INFO = "info"
    ERROR = "error"


class TaskError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class TaskRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    repo: str
    linear_issue_id: str
    state: TaskState = TaskState.DRAFTED
    attempt: int = 0
    max_retries: int = 2
    agent: AgentKind = AgentKind.CODEX
    worktree_path: str | None = None
    branch: str | None = None
    tmux_session: str | None = None
    pr_number: int | None = None
    test_status: TestStatus = TestStatus.UNKNOWN
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_error: TaskError | None = None
    schema_version: int = REGISTRY_SCHEMA_VERSION

    def touch(self) -> None:
        self.updated_at = utc_now()


class TaskEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: uuid4().hex)
    task_id: str
    event_type: EventType
    message: str
    from_state: TaskState | None = None
    to_state: TaskState | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class RegistryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = REGISTRY_SCHEMA_VERSION
    tasks: dict[str, TaskRecord] = Field(default_factory=dict)
    events: list[TaskEvent] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class LaunchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    started: bool
    message: str = ""
    task_id: str | None = None
    pr_number: int | None = None
