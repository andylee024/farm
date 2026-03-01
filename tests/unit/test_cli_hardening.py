from __future__ import annotations

from pathlib import Path

import pytest

from farm.cli import _cmd_heartbeat
from farm.cli import _run_check_command
from farm.services.worker_status import WorkerPhase


def test_heartbeat_rejects_ready_and_blocked_states() -> None:
    with pytest.raises(ValueError, match="cannot be both ready_for_review and blocked"):
        _cmd_heartbeat(
            task_id="task-1",
            phase=WorkerPhase.BLOCKED,
            summary=None,
            ready_for_review=True,
            blocked=True,
            blocked_reason="conflict",
            config=Path("config.yaml"),
            registry=Path("data/registry.json"),
        )


def test_heartbeat_requires_blocked_for_blocked_reason() -> None:
    with pytest.raises(ValueError, match="requires --blocked"):
        _cmd_heartbeat(
            task_id="task-1",
            phase=WorkerPhase.RUNNING,
            summary=None,
            ready_for_review=False,
            blocked=False,
            blocked_reason="needs help",
            config=Path("config.yaml"),
            registry=Path("data/registry.json"),
        )


def test_run_check_command_returns_false_for_missing_binary() -> None:
    ok, detail = _run_check_command(["farm-command-not-found-xyz", "--version"])

    assert ok is False
    assert detail

