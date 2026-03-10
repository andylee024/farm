"""Local task runtime backed by git worktrees and tmux sessions."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from farm.adapters.git import run_git
from farm.adapters.tmux import run_tmux
from farm.runtime.paths import issue_slug
from farm.runtime.task_runtime import (
    TaskRuntimeLaunchRequest,
    TaskRuntimeMetadata,
)

GitRunner = Callable[[str | Path, list[str]], str]
TmuxRunner = Callable[[list[str]], str]


def _branch_name(issue_id: str) -> str:
    return f"farm/{issue_slug(issue_id)}"


def _session_name(issue_id: str) -> str:
    return f"farm-{issue_slug(issue_id)}"


class TmuxTaskRuntime:
    """Current local runtime implementation."""

    runtime_name = "tmux"

    def __init__(
        self,
        *,
        git_runner: GitRunner = run_git,
        tmux_runner: TmuxRunner = run_tmux,
    ):
        self.git_runner = git_runner
        self.tmux_runner = tmux_runner

    def start(self, request: TaskRuntimeLaunchRequest) -> TaskRuntimeMetadata:
        metadata = self.describe(
            issue_id=request.issue_id,
            repo=request.repo,
            task_dir=request.task_dir,
        )
        if request.task_dir.exists():
            raise ValueError(f"Task directory already exists: {request.task_dir}")
        request.task_dir.parent.mkdir(parents=True, exist_ok=True)
        self.git_runner(
            request.repo_path,
            [
                "worktree",
                "add",
                str(request.task_dir),
                "-b",
                metadata.branch or _branch_name(request.issue_id),
                request.default_branch,
            ],
        )
        self.tmux_runner(
            [
                "new-session",
                "-d",
                "-s",
                metadata.handle or _session_name(request.issue_id),
                "-c",
                str(request.task_dir),
                request.startup_command,
            ]
        )
        return metadata

    def describe(self, *, issue_id: str, repo: str, task_dir: Path) -> TaskRuntimeMetadata:
        _ = repo
        return TaskRuntimeMetadata(
            runtime=self.runtime_name,
            workspace=str(task_dir),
            handle=_session_name(issue_id),
            branch=_branch_name(issue_id),
        )

    def is_alive(self, *, issue_id: str, repo: str, task_dir: Path) -> bool:
        _ = repo
        _ = task_dir
        try:
            self.tmux_runner(["has-session", "-t", _session_name(issue_id)])
            return True
        except Exception:  # noqa: BLE001
            return False

    def tail(self, *, issue_id: str, repo: str, task_dir: Path, lines: int) -> list[str]:
        _ = repo
        _ = task_dir
        if lines < 1:
            return []
        try:
            captured = self.tmux_runner(
                ["capture-pane", "-p", "-t", _session_name(issue_id), "-S", f"-{lines}"]
            )
        except Exception:  # noqa: BLE001
            return []
        return [line for line in captured.splitlines() if line.strip()]

    def stop(self, *, issue_id: str, repo: str, task_dir: Path) -> None:
        _ = repo
        _ = task_dir
        self.tmux_runner(["kill-session", "-t", _session_name(issue_id)])
