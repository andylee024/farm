"""Workflow logic for parent/child intake into Linear + local registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from farm.adapters.linear_api import LinearApiClient
from farm.adapters.storage_json import JsonRegistryStore
from farm.core.errors import TaskNotFoundError
from farm.core.events import info_event, transition_event
from farm.core.models import AgentKind, TaskRecord, TaskState
from farm.core.state_machine import can_transition, transition
from farm.services.skill_runtime import SkillRuntime

CHILD_REPO_CONTEXT_MARKER = "## Agent Startup Instructions"
CHILD_REPO_CONTEXT_BLOCK = (
    "## Agent Startup Instructions\n"
    "- Before making changes, read this repository to understand full project context "
    "(architecture, conventions, and constraints).\n"
    "- Then implement only the scoped task in this issue."
)


@dataclass(slots=True)
class IntakeResult:
    issue_id: str
    issue_kind: str


def ensure_child_repo_context_instruction(description: str) -> str:
    if CHILD_REPO_CONTEXT_MARKER.lower() in description.lower():
        return description.rstrip()
    base = description.rstrip()
    if not base:
        return CHILD_REPO_CONTEXT_BLOCK
    return f"{base}\n\n{CHILD_REPO_CONTEXT_BLOCK}"


def run_intake_workflow(
    *,
    linear_client: LinearApiClient,
    registry_path: Path,
    title: str,
    description: str,
    selected_repo: str,
    parent_id: str | None,
    status_name: str,
    agent: AgentKind,
    skill_runtime: SkillRuntime | None = None,
) -> IntakeResult:
    if parent_id:
        if skill_runtime is not None:
            skill_runtime.invoke(
                skill_name="feature-task-decomposition",
                context={
                    "stage": "child_intake",
                    "repo": selected_repo,
                    "status": status_name,
                },
            )
        child_description = ensure_child_repo_context_instruction(description)
        child_issue = linear_client.create_child_issue(
            parent_issue_id=parent_id,
            title=title,
            description=child_description,
            project_name=selected_repo,
            state_name=status_name,
        )
        issue_id = child_issue.id
    else:
        issue_id = linear_client.create_parent_issue(
            title=title,
            description=description,
            project_name=selected_repo,
            state_name=status_name,
        )

    if parent_id:
        _register_child_task(
            registry_path=registry_path,
            issue_id=issue_id,
            selected_repo=selected_repo,
            agent=agent,
            status_name=status_name,
        )

    issue_kind = "child" if parent_id else "parent"
    return IntakeResult(issue_id=issue_id, issue_kind=issue_kind)


def _register_child_task(
    *,
    registry_path: Path,
    issue_id: str,
    selected_repo: str,
    agent: AgentKind,
    status_name: str,
) -> None:
    store = JsonRegistryStore(registry_path)
    task = _ensure_task(
        store=store,
        issue_id=issue_id,
        repo=selected_repo,
        agent=agent,
    )
    if status_name == "Approved" and task.state != TaskState.QUEUED:
        if not can_transition(task.state, TaskState.QUEUED):
            raise ValueError(
                f"Cannot move local task {task.task_id} from {task.state.value} to queued."
            )
        _transition_and_save(
            store=store,
            task=task,
            to_state=TaskState.QUEUED,
            message="Task approved in Linear and queued locally",
        )


def _save_new_task(
    *,
    store: JsonRegistryStore,
    issue_id: str,
    repo: str,
    agent: AgentKind,
) -> TaskRecord:
    task = TaskRecord(
        task_id=issue_id,
        repo=repo,
        linear_issue_id=issue_id,
        agent=agent,
    )
    store.save_task(task)
    store.append_event(
        task.task_id,
        info_event(
            task_id=task.task_id,
            message="Task registered in local runtime registry",
            payload={"repo": repo, "agent": agent.value},
        ),
    )
    return task


def _ensure_task(
    *,
    store: JsonRegistryStore,
    issue_id: str,
    repo: str,
    agent: AgentKind,
) -> TaskRecord:
    try:
        return store.get_task(issue_id)
    except TaskNotFoundError:
        return _save_new_task(store=store, issue_id=issue_id, repo=repo, agent=agent)


def _transition_and_save(
    *,
    store: JsonRegistryStore,
    task: TaskRecord,
    to_state: TaskState,
    message: str,
) -> None:
    from_state, _ = transition(task, to_state)
    store.save_task(task)
    store.append_event(
        task.task_id,
        transition_event(
            task_id=task.task_id,
            from_state=from_state,
            to_state=to_state,
            message=message,
        ),
    )
