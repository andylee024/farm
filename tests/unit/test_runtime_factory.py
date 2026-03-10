from __future__ import annotations

import pytest

from farm.runtime.daytona_task_runtime import DaytonaTaskRuntime
from farm.runtime.runtime_factory import build_task_runtime
from farm.runtime.tmux_task_runtime import TmuxTaskRuntime
from farm.support.config import FarmConfig


def _build_config(provider: str) -> FarmConfig:
    return FarmConfig.model_validate(
        {
            "repos": {},
            "worktree_root": "/tmp/worktrees",
            "task_runtime": {"provider": provider},
        }
    )


def test_build_task_runtime_returns_tmux_runtime() -> None:
    runtime = build_task_runtime(_build_config("tmux"))
    assert isinstance(runtime, TmuxTaskRuntime)


def test_build_task_runtime_returns_daytona_runtime() -> None:
    runtime = build_task_runtime(_build_config("daytona"))
    assert isinstance(runtime, DaytonaTaskRuntime)


def test_build_task_runtime_rejects_unknown_provider() -> None:
    cfg = _build_config("tmux")
    cfg.task_runtime.provider = "nope"  # type: ignore[assignment]

    with pytest.raises(ValueError, match="Unsupported task runtime"):
        build_task_runtime(cfg)
