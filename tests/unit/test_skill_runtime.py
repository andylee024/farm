from __future__ import annotations

from pathlib import Path

from farm.services.skill_runtime import NoopSkillRuntime
from farm.services.skill_runtime import SkillRuntime


def test_discover_from_returns_noop_when_skills_dir_missing(tmp_path: Path) -> None:
    runtime = SkillRuntime.discover_from(tmp_path)

    assert isinstance(runtime, NoopSkillRuntime)


def test_invoke_returns_ok_when_skill_exists(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "feature-task-decomposition"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# test\n", encoding="utf-8")

    runtime = SkillRuntime(skills_root=tmp_path / "skills")
    result = runtime.invoke(skill_name="feature-task-decomposition", context={"stage": "intake"})

    assert result.status == "ok"
    assert result.skill_name == "feature-task-decomposition"


def test_invoke_returns_missing_when_skill_file_absent(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)
    runtime = SkillRuntime(skills_root=tmp_path / "skills")

    result = runtime.invoke(skill_name="feature-task-decomposition", context={})

    assert result.status == "missing"
    assert "Skill not found" in result.message

