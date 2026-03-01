from __future__ import annotations

from pathlib import Path

from farm.adapters.linear_api import LinearChildIssue
from farm.adapters.storage_json import JsonRegistryStore
from farm.core.models import AgentKind
from farm.workflows.intake_workflow import run_intake_workflow


class FakeLinearClient:
    def __init__(self) -> None:
        self.last_parent_payload: tuple[str, str, str | None, str | None] | None = None
        self.last_child_payload: tuple[str, str, str, str | None, str | None] | None = None

    def create_parent_issue(
        self,
        title: str,
        description: str,
        *,
        project_name: str | None = None,
        state_name: str | None = None,
    ) -> str:
        self.last_parent_payload = (title, description, project_name, state_name)
        return "parent-1"

    def create_child_issue(
        self,
        *,
        parent_issue_id: str,
        title: str,
        description: str,
        project_name: str | None = None,
        state_name: str | None = None,
    ) -> LinearChildIssue:
        self.last_child_payload = (parent_issue_id, title, description, project_name, state_name)
        return LinearChildIssue(id="child-1", title=title, description=description)


class FakeSkillRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    def invoke(self, *, skill_name: str, context: dict[str, str]):
        self.calls.append((skill_name, context))
        return None


def test_run_intake_workflow_invokes_decomposition_skill_for_child(tmp_path: Path) -> None:
    client = FakeLinearClient()
    skill_runtime = FakeSkillRuntime()
    registry_path = tmp_path / "registry.json"

    result = run_intake_workflow(
        linear_client=client,
        registry_path=registry_path,
        title="child title",
        description="child description",
        selected_repo="scout",
        parent_id="parent-123",
        status_name="Backlog",
        agent=AgentKind.CODEX,
        skill_runtime=skill_runtime,
    )

    assert result.issue_kind == "child"
    assert result.issue_id == "child-1"
    assert len(skill_runtime.calls) == 1
    assert skill_runtime.calls[0][0] == "feature-task-decomposition"

    store = JsonRegistryStore(registry_path)
    saved = store.get_task("child-1")
    assert saved.repo == "scout"
