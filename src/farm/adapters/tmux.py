"""Tmux adapter utilities."""

from __future__ import annotations

import subprocess

from farm.core.errors import ExternalCommandError


def run_tmux(args: list[str]) -> str:
    cmd = ["tmux", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ExternalCommandError(result.stderr.strip() or "tmux command failed")
    return result.stdout.strip()


def create_session_command(*, session: str, cwd: str, command: str) -> list[str]:
    return ["tmux", "new-session", "-d", "-s", session, "-c", cwd, command]

