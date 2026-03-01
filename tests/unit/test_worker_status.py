from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from farm.services.worker_status import WorkerPhase
from farm.services.worker_status import WorkerStatus
from farm.services.worker_status import load_worker_status
from farm.services.worker_status import status_age_seconds
from farm.services.worker_status import status_is_blocked
from farm.services.worker_status import status_is_ready
from farm.services.worker_status import worker_status_path
from farm.services.worker_status import write_worker_status


def test_worker_status_round_trip(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    path = worker_status_path(worktree)
    status = WorkerStatus(
        task_id="task-1",
        phase=WorkerPhase.RUNNING,
        summary="Compiling and running tests",
    )

    write_worker_status(path, status)
    loaded = load_worker_status(path)

    assert loaded is not None
    assert loaded.task_id == "task-1"
    assert loaded.phase == WorkerPhase.RUNNING
    assert loaded.summary == "Compiling and running tests"


def test_status_ready_and_blocked_helpers() -> None:
    ready = WorkerStatus(phase=WorkerPhase.READY_FOR_REVIEW)
    blocked = WorkerStatus(phase=WorkerPhase.BLOCKED)
    failed = WorkerStatus(phase=WorkerPhase.FAILED)

    assert status_is_ready(ready) is True
    assert status_is_blocked(blocked) is True
    assert status_is_blocked(failed) is True


def test_status_age_seconds_uses_updated_at() -> None:
    updated_at = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    status = WorkerStatus(updated_at=updated_at)

    now_epoch = int(datetime(2026, 3, 1, 12, 5, tzinfo=timezone.utc).timestamp())
    age = status_age_seconds(status, now_epoch=now_epoch)

    assert age == 300

