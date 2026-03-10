"""Factory for configuring task runtime implementations."""

from __future__ import annotations

from farm.runtime.daytona_task_runtime import DaytonaTaskRuntime
from farm.runtime.task_runtime import TaskRuntime
from farm.runtime.tmux_task_runtime import TmuxTaskRuntime
from farm.support.config import FarmConfig


def build_task_runtime(config: FarmConfig) -> TaskRuntime:
    provider = config.task_runtime.provider.strip().lower()
    if provider == "tmux":
        return TmuxTaskRuntime()
    if provider == "daytona":
        return DaytonaTaskRuntime()
    raise ValueError(
        f"Unsupported task runtime `{config.task_runtime.provider}`. Available: daytona, tmux"
    )
