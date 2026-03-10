"""Placeholder runtime for a future Daytona-backed execution environment."""

from __future__ import annotations

from pathlib import Path

from farm.runtime.paths import issue_slug
from farm.runtime.task_runtime import (
    TaskRuntimeLaunchRequest,
    TaskRuntimeMetadata,
)
from farm.support.errors import UnsupportedRuntimeError


def _workspace_name(*, repo: str, issue_id: str) -> str:
    return f"farm-{repo}-{issue_slug(issue_id)}"


class DaytonaTaskRuntime:
    """Future runtime backend for remote task execution."""

    runtime_name = "daytona"

    def start(self, request: TaskRuntimeLaunchRequest) -> TaskRuntimeMetadata:
        raise UnsupportedRuntimeError(
            "DaytonaTaskRuntime is not implemented yet. Configure `task_runtime.provider: tmux`."
        )

    def describe(self, *, issue_id: str, repo: str, task_dir: Path) -> TaskRuntimeMetadata:
        _ = task_dir
        workspace = _workspace_name(repo=repo, issue_id=issue_id)
        return TaskRuntimeMetadata(
            runtime=self.runtime_name,
            workspace=workspace,
            handle=workspace,
            branch=None,
        )

    def is_alive(self, *, issue_id: str, repo: str, task_dir: Path) -> bool:
        _ = issue_id
        _ = repo
        _ = task_dir
        return False

    def tail(self, *, issue_id: str, repo: str, task_dir: Path, lines: int) -> list[str]:
        _ = issue_id
        _ = repo
        _ = task_dir
        _ = lines
        return []

    def stop(self, *, issue_id: str, repo: str, task_dir: Path) -> None:
        raise UnsupportedRuntimeError(
            "DaytonaTaskRuntime is not implemented yet. Configure `task_runtime.provider: tmux`."
        )
