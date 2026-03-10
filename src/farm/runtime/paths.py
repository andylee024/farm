"""Deterministic filesystem helpers for task artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from farm.support.config import FarmConfig


UPDATE_FILENAME = "task_updates.jsonl"
RESULT_FILENAME = "task_result.json"


@dataclass(slots=True, frozen=True)
class TaskPaths:
    task_dir: Path
    farm_dir: Path
    updates: Path
    result: Path



def issue_slug(issue_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", issue_id).strip("-").lower()



def task_paths(*, config: FarmConfig, repo: str, issue_id: str) -> TaskPaths:
    task_dir = Path(config.worktree_root) / repo / issue_id
    farm_dir = task_dir / ".farm"
    return TaskPaths(
        task_dir=task_dir,
        farm_dir=farm_dir,
        updates=farm_dir / UPDATE_FILENAME,
        result=farm_dir / RESULT_FILENAME,
    )
