"""CLI entrypoint for Farm V0 runtime commands."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from farm.adapters.linear_api import LinearApiClient
from farm.adapters.storage_json import JsonRegistryStore
from farm.config import FarmConfig, load_config, load_dotenv_file
from farm.core.errors import LinearApiError, TaskNotFoundError
from farm.core.events import info_event, transition_event
from farm.core.models import AgentKind, TaskRecord, TaskState
from farm.core.state_machine import can_transition, transition
from farm.services.orchestrator import Orchestrator

try:
    import typer
except ModuleNotFoundError:  # pragma: no cover - exercised only in minimal envs
    typer = None


def _echo(message: str) -> None:
    if typer is None:
        print(message)
        return
    typer.echo(message)


def _load_config_or_raise(config: Path) -> FarmConfig:
    try:
        return load_config(config)
    except (FileNotFoundError, ValueError) as exc:
        raise ValueError(str(exc)) from exc


def _build_linear_api_client(cfg: FarmConfig) -> LinearApiClient:
    if cfg.linear is None:
        raise ValueError("Linear config missing. Add a `linear` section in config.")
    return LinearApiClient.from_settings(
        api_url=cfg.linear.api_url,
        api_key=cfg.linear.api_key,
        api_key_env=cfg.linear.api_key_env,
        team_id=cfg.linear.team_id,
        team_id_env=cfg.linear.team_id_env,
    )


def _resolve_repo_or_raise(cfg: FarmConfig, repo: str | None) -> str:
    if repo is not None:
        if repo not in cfg.repos:
            raise ValueError(f"Unknown repo in config: {repo}")
        return repo
    repo_names = sorted(cfg.repos.keys())
    if not repo_names:
        raise ValueError("No repos configured. Add at least one repo in config.")
    if len(repo_names) > 1:
        raise ValueError("Multiple repos configured. Specify --repo explicitly.")
    return repo_names[0]


def _normalize_status_name(value: str) -> str:
    normalized = value.strip().lower()
    mapping = {
        "backlog": "Backlog",
        "approved": "Approved",
        "coding": "Coding",
        "completed": "Completed",
        "canceled": "Canceled",
    }
    status_name = mapping.get(normalized)
    if status_name is None:
        allowed = ", ".join(sorted(mapping.keys()))
        raise ValueError(f"Unsupported status `{value}`. Allowed values: {allowed}")
    return status_name


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


def _cmd_intake(
    *,
    title: str,
    description: str,
    config: Path,
    repo: str | None,
    parent_id: str | None,
    status: str,
    agent: AgentKind,
    registry: Path,
) -> None:
    cfg = _load_config_or_raise(config)
    try:
        linear_client = _build_linear_api_client(cfg)
    except ValueError as exc:
        _echo(f"linear: unavailable ({exc})")
        return
    selected_repo = _resolve_repo_or_raise(cfg, repo)
    status_name = _normalize_status_name(status)

    issue_id: str
    try:
        if parent_id:
            child_issue = linear_client.create_child_issue(
                parent_issue_id=parent_id,
                title=title,
                description=description,
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
    except LinearApiError as exc:
        raise ValueError(str(exc)) from exc

    if parent_id:
        store = JsonRegistryStore(registry)
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

    issue_kind = "child" if parent_id else "parent"
    _echo(f"Created {issue_kind} issue {issue_id} in Linear status={status_name}")


def _cmd_decide(
    *,
    issue_id: str,
    approve: bool,
    cancel: bool,
    config: Path,
    registry: Path,
    repo: str | None,
    agent: AgentKind,
) -> None:
    if approve == cancel:
        raise ValueError("Specify exactly one action: --approve or --cancel.")
    cfg = _load_config_or_raise(config)
    linear_client = _build_linear_api_client(cfg)
    store = JsonRegistryStore(registry)

    if approve:
        try:
            linear_client.move_issue_to_status(issue_id, "Approved")
        except LinearApiError as exc:
            raise ValueError(str(exc)) from exc

        task_repo = repo
        if task_repo is None:
            try:
                issue = linear_client.get_issue(issue_id)
            except LinearApiError as exc:
                raise ValueError(str(exc)) from exc
            if issue.project_name is None:
                raise ValueError(
                    "Could not infer repo from Linear issue project. Pass --repo explicitly."
                )
            inferred_repo = issue.project_name.strip().lower()
            if inferred_repo not in cfg.repos:
                available = ", ".join(sorted(cfg.repos.keys()))
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
        _echo(f"Approved Linear issue {issue_id} and queued local task.")
        return

    try:
        linear_client.move_issue_to_status(issue_id, "Canceled")
    except LinearApiError as exc:
        raise ValueError(str(exc)) from exc

    try:
        task = store.get_task(issue_id)
    except TaskNotFoundError:
        _echo(f"Canceled Linear issue {issue_id}. No local task found.")
        return
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
    _echo(f"Canceled Linear issue {issue_id}.")


def _cmd_run(config: Path, repo: str | None, registry: Path) -> None:
    cfg = _load_config_or_raise(config)
    store = JsonRegistryStore(registry)
    orchestrator = Orchestrator(store=store, config=cfg)
    result = orchestrator.run_cycle(repo=repo)
    if result is None:
        _echo("No queued tasks.")
        return
    if not result.started:
        _echo(f"Launch skipped: {result.message}")
        return

    if result.task_id:
        linear_client = _build_linear_api_client(cfg)
        try:
            linear_client.move_issue_to_status(result.task_id, "Coding")
        except LinearApiError as exc:
            raise ValueError(f"Task launched, but failed to update Linear status: {exc}") from exc
    _echo(f"Launched task successfully. task_id={result.task_id}")


def _cmd_status(config: Path, registry: Path) -> None:
    cfg = _load_config_or_raise(config)
    store = JsonRegistryStore(registry)
    tasks = store.list_tasks()
    _echo(f"Registry: {registry}")
    if not tasks:
        _echo("local: no tasks")
    else:
        counts = Counter(task.state.value for task in tasks)
        for state in TaskState:
            count = counts.get(state.value, 0)
            if count > 0:
                _echo(f"local:{state.value}={count}")

    try:
        linear_client = _build_linear_api_client(cfg)
    except ValueError as exc:
        _echo(f"linear: unavailable ({exc})")
        return
    try:
        board_counts = linear_client.list_child_issue_counts(project_names=set(cfg.repos.keys()))
    except LinearApiError as exc:
        _echo(f"linear: unavailable ({exc})")
        return

    board_statuses = ["Backlog", "Approved", "Coding", "Completed", "Canceled"]
    _echo("linear:child-issues")
    for status_name in board_statuses:
        _echo(f"linear:{status_name.lower()}={board_counts.get(status_name, 0)}")


if typer is not None:
    app = typer.Typer(no_args_is_help=True, help="Farm runtime CLI.")

    @app.command()
    def intake(
        title: str = typer.Option(..., help="Issue title."),
        description: str = typer.Option(..., help="Issue description."),
        config: Path = typer.Option(Path("config.yaml"), help="Path to config yaml."),
        repo: str | None = typer.Option(None, help="Repo key from config."),
        parent_id: str | None = typer.Option(None, "--parent-id", help="Parent issue id for child issue."),
        status: str = typer.Option("backlog", help="Linear status: backlog|approved."),
        agent: AgentKind = typer.Option(AgentKind.CODEX, help="Agent model family to run task."),
        registry: Path = typer.Option(Path("data/registry.json"), "--registry", help="Local registry path."),
    ) -> None:
        """Create a Linear issue. Use --parent-id to create a child issue."""
        try:
            _cmd_intake(
                title=title,
                description=description,
                config=config,
                repo=repo,
                parent_id=parent_id,
                status=status,
                agent=agent,
                registry=registry,
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

    @app.command()
    def decide(
        issue: str = typer.Option(..., "--issue", help="Linear issue id."),
        approve: bool = typer.Option(False, "--approve", help="Move issue to Approved."),
        cancel: bool = typer.Option(False, "--cancel", help="Move issue to Canceled."),
        config: Path = typer.Option(Path("config.yaml"), help="Path to config yaml."),
        registry: Path = typer.Option(Path("data/registry.json"), "--registry", help="Local registry path."),
        repo: str | None = typer.Option(None, help="Repo key when approving and repo cannot be inferred."),
        agent: AgentKind = typer.Option(AgentKind.CODEX, help="Default agent when creating local tasks."),
    ) -> None:
        """Apply human decision: approve or cancel a Linear issue."""
        try:
            _cmd_decide(
                issue_id=issue,
                approve=approve,
                cancel=cancel,
                config=config,
                registry=registry,
                repo=repo,
                agent=agent,
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

    @app.command()
    def run(
        config: Path = typer.Option(Path("config.yaml"), help="Path to config yaml."),
        registry: Path = typer.Option(Path("data/registry.json"), "--registry", help="Local registry path."),
        repo: str | None = typer.Option(None, help="Optional repo filter for queue selection."),
    ) -> None:
        """Run one execution cycle from locally queued tasks."""
        try:
            _cmd_run(config, repo, registry)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

    @app.command()
    def status(
        config: Path = typer.Option(Path("config.yaml"), help="Path to config yaml."),
        registry: Path = typer.Option(Path("data/registry.json"), "--registry", help="Local registry path."),
    ) -> None:
        """Print concise Linear board + local runtime summary."""
        try:
            _cmd_status(config, registry)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc


def _argparse_main() -> None:
    parser = argparse.ArgumentParser(prog="farm")
    subparsers = parser.add_subparsers(dest="command")

    intake_parser = subparsers.add_parser("intake")
    intake_parser.add_argument("--title", required=True)
    intake_parser.add_argument("--description", required=True)
    intake_parser.add_argument("--config", default="config.yaml")
    intake_parser.add_argument("--repo", default=None)
    intake_parser.add_argument("--parent-id", default=None)
    intake_parser.add_argument("--status", default="backlog")
    intake_parser.add_argument("--agent", default=AgentKind.CODEX.value, choices=[a.value for a in AgentKind])
    intake_parser.add_argument("--registry", default="data/registry.json")

    decide_parser = subparsers.add_parser("decide")
    decide_parser.add_argument("--issue", required=True)
    decide_parser.add_argument("--approve", action="store_true")
    decide_parser.add_argument("--cancel", action="store_true")
    decide_parser.add_argument("--config", default="config.yaml")
    decide_parser.add_argument("--registry", default="data/registry.json")
    decide_parser.add_argument("--repo", default=None)
    decide_parser.add_argument("--agent", default=AgentKind.CODEX.value, choices=[a.value for a in AgentKind])

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--config", default="config.yaml")
    run_parser.add_argument("--registry", default="data/registry.json")
    run_parser.add_argument("--repo", default=None)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--config", default="config.yaml")
    status_parser.add_argument("--registry", default="data/registry.json")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return

    if args.command == "intake":
        try:
            _cmd_intake(
                title=args.title,
                description=args.description,
                config=Path(args.config),
                repo=args.repo,
                parent_id=args.parent_id,
                status=args.status,
                agent=AgentKind(args.agent),
                registry=Path(args.registry),
            )
        except ValueError as exc:
            parser.error(str(exc))
        return
    if args.command == "decide":
        try:
            _cmd_decide(
                issue_id=args.issue,
                approve=args.approve,
                cancel=args.cancel,
                config=Path(args.config),
                registry=Path(args.registry),
                repo=args.repo,
                agent=AgentKind(args.agent),
            )
        except ValueError as exc:
            parser.error(str(exc))
        return
    if args.command == "run":
        try:
            _cmd_run(Path(args.config), args.repo, Path(args.registry))
        except ValueError as exc:
            parser.error(str(exc))
        return
    if args.command == "status":
        try:
            _cmd_status(Path(args.config), Path(args.registry))
        except ValueError as exc:
            parser.error(str(exc))
        return

    parser.error(f"Unsupported command: {args.command}")


def main() -> None:
    load_dotenv_file()
    if typer is None:
        _argparse_main()
        return
    app()


if __name__ == "__main__":
    main()
