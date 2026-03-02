"""Deterministic filesystem and naming helpers for task execution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from farm.support.config import FarmConfig


UPDATE_FILENAME = "task_updates.jsonl"
RESULT_FILENAME = "task_result.json"


@dataclass(slots=True, frozen=True)
class TaskPaths:
    worktree: Path
    farm_dir: Path
    updates: Path
    result: Path
    branch: str
    session: str



def issue_slug(issue_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", issue_id).strip("-").lower()



def task_paths(*, config: FarmConfig, repo: str, issue_id: str) -> TaskPaths:
    slug = issue_slug(issue_id)
    worktree = Path(config.worktree_root) / repo / issue_id
    farm_dir = worktree / ".farm"
    return TaskPaths(
        worktree=worktree,
        farm_dir=farm_dir,
        updates=farm_dir / UPDATE_FILENAME,
        result=farm_dir / RESULT_FILENAME,
        branch=f"farm/{slug}",
        session=f"farm-{slug}",
    )
