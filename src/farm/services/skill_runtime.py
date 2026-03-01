"""File-based skill runtime boundary for workflow-to-skill integration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SkillInvocationResult:
    skill_name: str
    status: str
    message: str = ""


class SkillRuntime:
    """Validates skill availability and records workflow invocation points."""

    def __init__(self, *, skills_root: Path):
        self.skills_root = skills_root

    @classmethod
    def discover_from(cls, start: Path | None = None) -> SkillRuntime | NoopSkillRuntime:
        root = start or Path.cwd()
        search_roots = [root, *root.parents]
        for candidate_root in search_roots:
            skills_dir = candidate_root / "skills"
            if skills_dir.exists() and skills_dir.is_dir():
                return cls(skills_root=skills_dir)
        return NoopSkillRuntime()

    def invoke(self, *, skill_name: str, context: dict[str, Any]) -> SkillInvocationResult:
        _ = context
        skill_file = self.skills_root / skill_name / "SKILL.md"
        if not skill_file.exists():
            return SkillInvocationResult(
                skill_name=skill_name,
                status="missing",
                message=f"Skill not found: {skill_file}",
            )
        return SkillInvocationResult(skill_name=skill_name, status="ok")


class NoopSkillRuntime:
    """Fallback runtime used when skills directory is not available."""

    def invoke(self, *, skill_name: str, context: dict[str, Any]) -> SkillInvocationResult:
        _ = context
        return SkillInvocationResult(
            skill_name=skill_name,
            status="noop",
            message="Skills directory not discovered; skipping skill invocation.",
        )

