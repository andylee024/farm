"""Git adapter utilities."""

from __future__ import annotations

import subprocess
from pathlib import Path

from farm.support.errors import ExternalCommandError


def run_git(repo_path: str | Path, args: list[str]) -> str:
    cmd = ["git", "-C", str(repo_path), *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ExternalCommandError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()
