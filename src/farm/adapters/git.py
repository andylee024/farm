"""Git adapter utilities."""

from __future__ import annotations

import subprocess
from pathlib import Path

from farm.core.errors import ExternalCommandError


def run_git(repo_path: str | Path, args: list[str]) -> str:
    cmd = ["git", "-C", str(repo_path), *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ExternalCommandError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def create_worktree_command(
    *,
    repo_path: str,
    worktree_path: str,
    branch: str,
    base_ref: str = "main",
) -> list[str]:
    return [
        "git",
        "-C",
        repo_path,
        "worktree",
        "add",
        worktree_path,
        "-b",
        branch,
        base_ref,
    ]

