"""Structured worker status contract for monitoring and completion decisions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

WORKER_STATUS_SCHEMA_VERSION = 1
WORKER_STATUS_FILENAME = ".farm_worker_status.json"


class WorkerPhase(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    BLOCKED = "blocked"
    READY_FOR_REVIEW = "ready_for_review"
    FAILED = "failed"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkerStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: int = WORKER_STATUS_SCHEMA_VERSION
    task_id: str | None = None
    phase: WorkerPhase = WorkerPhase.RUNNING
    summary: str | None = None
    ready_for_review: bool = False
    blocked: bool = False
    blocked_reason: str | None = None
    updated_at: datetime = Field(default_factory=_utc_now)


def worker_status_path(worktree_path: Path) -> Path:
    return worktree_path / WORKER_STATUS_FILENAME


def load_worker_status(path: Path) -> WorkerStatus | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        status = WorkerStatus.model_validate(payload)
    except ValidationError:
        return None
    if status.schema_version != WORKER_STATUS_SCHEMA_VERSION:
        return None
    return status


def write_worker_status(path: Path, status: WorkerStatus) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = status.model_dump(mode="json", exclude_none=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def status_age_seconds(status: WorkerStatus, *, now_epoch: int) -> int:
    return max(0, now_epoch - int(status.updated_at.timestamp()))


def status_is_ready(status: WorkerStatus) -> bool:
    return status.ready_for_review or status.phase == WorkerPhase.READY_FOR_REVIEW


def status_is_blocked(status: WorkerStatus) -> bool:
    return status.blocked or status.phase in {WorkerPhase.BLOCKED, WorkerPhase.FAILED}

