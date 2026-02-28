"""Prompt template helpers used by execution services."""

from __future__ import annotations


def build_task_prompt(*, task_title: str, task_scope: str, constraints: str) -> str:
    return (
        f"Task: {task_title}\n\n"
        f"Scope:\n{task_scope}\n\n"
        f"Constraints:\n{constraints}\n"
    )


def build_retry_prompt(*, previous_error: str, updated_guidance: str) -> str:
    return (
        "Previous attempt failed with:\n"
        f"{previous_error}\n\n"
        "Apply this revised guidance:\n"
        f"{updated_guidance}\n"
    )

