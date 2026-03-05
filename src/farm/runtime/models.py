"""Runtime models for single-task Farm execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Agent(str, Enum):
    CODEX = "codex"
    CLAUDE = "claude"


@dataclass(slots=True)
class TaskUpdate:
    issue_id: str
    repo: str
    phase: str
    summary: str
    ts: str


@dataclass(slots=True)
class TaskResult:
    issue_id: str
    repo: str
    outcome: str
    summary: str
    started_at: str
    ended_at: str
    pr_url: str | None
