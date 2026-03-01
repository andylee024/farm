"""Workflow logic for execution lifecycle decisions and task launch cycles."""

from __future__ import annotations

from dataclasses import dataclass

from farm.adapters.linear_api import LinearApiClient
from farm.adapters.storage_json import JsonRegistryStore
from farm.core.errors import LinearApiError, TaskNotFoundError
from farm.core.events import info_event, transition_event
from farm.core.models import AgentKind, TaskRecord, TaskState
from farm.core.state_machine import can_transition, transition
from farm.services.orchestrator import Orchestrator


@dataclass(slots=True)
class WorkflowMessage:
    text: str


def run_decide_workflow(
    *,
    linear_client: LinearApiClient,
    store: JsonRegistryStore,
    issue_id: str,
    approve: bool,
    cancel: bool,
    repo: str | None,
    agent: AgentKind,
    configured_repos: set[str],
) -> WorkflowMessage:
    if approve == cancel:
        raise ValueError("Specify exactly one action: --approve or --cancel.")

    if approve:
        linear_client.move_issue_to_status(issue_id, "Approved")
        task_repo = repo
        if task_repo is None:
            issue = linear_client.get_issue(issue_id)
            if issue.project_name is None:
                raise ValueError(
                    "Could not infer repo from Linear issue project. Pass --repo explicitly."
                )
            inferred_repo = issue.project_name.strip().lower()
            if inferred_repo not in configured_repos:
                available = ", ".join(sorted(configured_repos))
                raise ValueError(
                    f"Inferred repo `{inferred_repo}` not found in config. Available: {available}. "
                    "Pass --repo explicitly."
                )
            task_repo = inferred_repo

        task = _ensure_task(
            store=store,
            issue_id=issue_id,
            repo=task_repo,
            agent=agent,
        )
        if task.state != TaskState.QUEUED:
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
        return WorkflowMessage(text=f"Approved Linear issue {issue_id} and queued local task.")

    linear_client.move_issue_to_status(issue_id, "Canceled")
    try:
        task = store.get_task(issue_id)
    except TaskNotFoundError:
        return WorkflowMessage(text=f"Canceled Linear issue {issue_id}. No local task found.")
    if can_transition(task.state, TaskState.CANCELED):
        _transition_and_save(
            store=store,
            task=task,
            to_state=TaskState.CANCELED,
            message="Task canceled in Linear",
        )
    else:
        store.append_event(
            task.task_id,
            info_event(
                task_id=task.task_id,
                message=(
                    f"Linear issue canceled, but local state `{task.state.value}` "
                    "cannot transition to canceled."
                ),
            ),
        )
    return WorkflowMessage(text=f"Canceled Linear issue {issue_id}.")


def run_execution_cycle_workflow(
    *,
    orchestrator: Orchestrator,
    linear_client: LinearApiClient,
    repo: str | None,
) -> WorkflowMessage:
    result = orchestrator.run_cycle(repo=repo)
    if result is None:
        return WorkflowMessage(text="No queued tasks.")
    if not result.started:
        return WorkflowMessage(text=f"Launch skipped: {result.message}")
    if result.task_id:
        linear_client.move_issue_to_status(result.task_id, "Coding")
    return WorkflowMessage(text=f"Launched task successfully. task_id={result.task_id}")


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

