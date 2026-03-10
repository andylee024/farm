"""Execution runtime interface for task backends."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(slots=True, frozen=True)
class TaskRuntimeLaunchRequest:
    issue_id: str
    repo: str
    repo_path: str
    default_branch: str
    task_dir: Path
    startup_command: str


@dataclass(slots=True, frozen=True)
class TaskRuntimeMetadata:
    runtime: str
    workspace: str | None = None
    handle: str | None = None
    branch: str | None = None


class TaskRuntime(Protocol):
    runtime_name: str

    def start(self, request: TaskRuntimeLaunchRequest) -> TaskRuntimeMetadata:
        """Start execution for one task."""

    def describe(self, *, issue_id: str, repo: str, task_dir: Path) -> TaskRuntimeMetadata:
        """Describe deterministic runtime metadata for one task."""

    def is_alive(self, *, issue_id: str, repo: str, task_dir: Path) -> bool:
        """Return whether the task is actively running in this runtime."""

    def tail(self, *, issue_id: str, repo: str, task_dir: Path, lines: int) -> list[str]:
        """Return recent output lines for an active task."""

    def stop(self, *, issue_id: str, repo: str, task_dir: Path) -> None:
        """Stop an active task if the runtime supports it."""
