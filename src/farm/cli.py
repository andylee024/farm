"""CLI entrypoint for Farm V0 runtime commands."""

from __future__ import annotations

import datetime as dt
import subprocess
import time
from collections import Counter
from collections import deque
from pathlib import Path

from farm.adapters.linear_api import LinearApiClient
from farm.adapters.storage_json import JsonRegistryStore
from farm.config import FarmConfig, load_config, load_dotenv_file
from farm.core.errors import LinearApiError, TaskNotFoundError
from farm.core.events import transition_event
from farm.core.models import AgentKind, TaskRecord, TaskState
from farm.core.state_machine import transition
from farm.services.orchestrator import Orchestrator
from farm.services.skill_runtime import SkillRuntime
from farm.services.worker_status import WorkerPhase
from farm.services.worker_status import WorkerStatus
from farm.services.worker_status import load_worker_status
from farm.services.worker_status import status_age_seconds
from farm.services.worker_status import status_is_blocked
from farm.services.worker_status import status_is_ready
from farm.services.worker_status import worker_status_path
from farm.services.worker_status import write_worker_status
from farm.workflows.execution_workflow import run_decide_workflow
from farm.workflows.execution_workflow import run_execution_cycle_workflow
from farm.workflows.intake_workflow import run_intake_workflow

import typer

def _echo(message: str) -> None:
    typer.echo(message)


def _resolve_path_from_cwd_or_parents(path: Path, *, allow_nonexistent: bool) -> Path:
    if path.is_absolute():
        return path
    search_roots = [Path.cwd(), *Path.cwd().parents]
    for root in search_roots:
        candidate = root / path
        if candidate.exists():
            return candidate
    if allow_nonexistent:
        for root in search_roots:
            candidate = root / path
            if candidate.parent.exists():
                return candidate
    return path


def _resolve_config_path(path: Path) -> Path:
    return _resolve_path_from_cwd_or_parents(path, allow_nonexistent=False)


def _resolve_registry_path(path: Path) -> Path:
    return _resolve_path_from_cwd_or_parents(path, allow_nonexistent=True)


def _load_config_or_raise(config: Path) -> FarmConfig:
    try:
        return load_config(_resolve_config_path(config))
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
    resolved_config = _resolve_config_path(config)
    cfg = _load_config_or_raise(config)
    registry = _resolve_registry_path(registry)
    skill_runtime = SkillRuntime.discover_from(resolved_config.parent)
    try:
        linear_client = _build_linear_api_client(cfg)
    except ValueError as exc:
        _echo(f"linear: unavailable ({exc})")
        return
    selected_repo = _resolve_repo_or_raise(cfg, repo)
    status_name = _normalize_status_name(status)

    try:
        result = run_intake_workflow(
            linear_client=linear_client,
            registry_path=registry,
            title=title,
            description=description,
            selected_repo=selected_repo,
            parent_id=parent_id,
            status_name=status_name,
            agent=agent,
            skill_runtime=skill_runtime,
        )
    except LinearApiError as exc:
        raise ValueError(str(exc)) from exc
    _echo(f"Created {result.issue_kind} issue {result.issue_id} in Linear status={status_name}")


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
    cfg = _load_config_or_raise(config)
    registry = _resolve_registry_path(registry)
    linear_client = _build_linear_api_client(cfg)
    store = JsonRegistryStore(registry)
    try:
        result = run_decide_workflow(
            linear_client=linear_client,
            store=store,
            issue_id=issue_id,
            approve=approve,
            cancel=cancel,
            repo=repo,
            agent=agent,
            configured_repos=set(cfg.repos.keys()),
        )
    except LinearApiError as exc:
        raise ValueError(str(exc)) from exc
    _echo(result.text)


def _cmd_run(config: Path, repo: str | None, registry: Path) -> None:
    cfg = _load_config_or_raise(config)
    registry = _resolve_registry_path(registry)
    store = JsonRegistryStore(registry)
    orchestrator = Orchestrator(store=store, config=cfg)
    linear_client = _build_linear_api_client(cfg)
    try:
        result = run_execution_cycle_workflow(
            orchestrator=orchestrator,
            linear_client=linear_client,
            repo=repo,
        )
    except LinearApiError as exc:
        raise ValueError(f"Task launched, but failed to update Linear status: {exc}") from exc
    _echo(result.text)


def _cmd_heartbeat(
    *,
    task_id: str,
    phase: WorkerPhase,
    summary: str | None,
    ready_for_review: bool,
    blocked: bool,
    blocked_reason: str | None,
    config: Path,
    registry: Path,
) -> None:
    if ready_for_review and (blocked or phase in {WorkerPhase.BLOCKED, WorkerPhase.FAILED}):
        raise ValueError("Heartbeat cannot be both ready_for_review and blocked/failed.")
    if blocked_reason and not (blocked or phase in {WorkerPhase.BLOCKED, WorkerPhase.FAILED}):
        raise ValueError("`--blocked-reason` requires --blocked or phase=blocked|failed.")

    cfg = _load_config_or_raise(config)
    registry = _resolve_registry_path(registry)
    store = JsonRegistryStore(registry)
    try:
        task = store.get_task(task_id)
    except TaskNotFoundError as exc:
        raise ValueError(str(exc)) from exc

    worktree_path = _task_worktree_path(cfg, task)
    status = WorkerStatus(
        task_id=task_id,
        phase=phase,
        summary=summary,
        ready_for_review=ready_for_review or phase == WorkerPhase.READY_FOR_REVIEW,
        blocked=blocked or phase in {WorkerPhase.BLOCKED, WorkerPhase.FAILED},
        blocked_reason=blocked_reason,
    )
    path = worker_status_path(worktree_path)
    write_worker_status(path, status)
    _echo(
        "worker-status: "
        f"task={task_id} phase={status.phase.value} ready={status.ready_for_review} "
        f"blocked={status.blocked} path={path}"
    )


def _cmd_status(config: Path, registry: Path) -> None:
    cfg = _load_config_or_raise(config)
    registry = _resolve_registry_path(registry)
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


def _list_farm_tmux_sessions() -> set[str]:
    try:
        result = subprocess.run(
            ["tmux", "ls"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return set()
    if result.returncode != 0:
        return set()
    sessions: set[str] = set()
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        session_name = line.split(":", 1)[0]
        if session_name.startswith("farm-"):
            sessions.add(session_name)
    return sessions


def _tail_lines(path: Path, limit: int) -> list[str]:
    if limit <= 0 or not path.exists():
        return []
    lines: deque[str] = deque(maxlen=limit)
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                text = line.rstrip()
                if text:
                    lines.append(text)
    except OSError:
        return []
    return list(lines)


def _format_age(seconds: int | None) -> str:
    if seconds is None:
        return "n/a"
    if seconds < 60:
        return f"{seconds}s"
    minutes, remaining = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{remaining:02d}s"
    hours, rem_minutes = divmod(minutes, 60)
    return f"{hours}h{rem_minutes:02d}m"


def _compact_text(text: str, *, max_len: int = 88) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 3] + "..."


def _log_has_ready_marker(lines: list[str]) -> bool:
    markers = (
        "ready for pr review",
        "ready for review",
        "ready for merge",
    )
    for raw in lines:
        line = raw.lower()
        if any(marker in line for marker in markers):
            return True
    return False


def _task_worktree_path(cfg: FarmConfig, task: TaskRecord) -> Path:
    if task.worktree_path:
        return Path(task.worktree_path)
    return Path(cfg.worktree_root) / task.repo / task.task_id


def _task_log_tail(cfg: FarmConfig, task: TaskRecord, *, limit: int) -> tuple[Path, list[str]]:
    worktree_path = _task_worktree_path(cfg, task)
    log_path = worktree_path / ".farm_agent.log"
    if limit <= 0:
        return log_path, []
    return log_path, _tail_lines(log_path, limit)


def _task_worker_status(cfg: FarmConfig, task: TaskRecord) -> tuple[Path, WorkerStatus | None]:
    worktree_path = _task_worktree_path(cfg, task)
    status_path = worker_status_path(worktree_path)
    status = load_worker_status(status_path)
    return status_path, status


def _promote_local_task_ready_for_review(store: JsonRegistryStore, task_id: str) -> bool:
    with store.lock_task(task_id):
        task = store.get_task(task_id)
        changed = False
        if task.state == TaskState.PR_OPEN:
            _transition_and_save(
                store=store,
                task=task,
                to_state=TaskState.TESTS_PASSED,
                message="Auto-promoted: worker status marked task ready",
            )
            changed = True
        if task.state == TaskState.TESTS_PASSED:
            _transition_and_save(
                store=store,
                task=task,
                to_state=TaskState.READY_FOR_REVIEW,
                message="Auto-promoted: task ready for review",
            )
            changed = True
        return changed


def _auto_complete_ready_tasks(config: Path, registry: Path) -> list[str]:
    cfg = _load_config_or_raise(config)
    registry = _resolve_registry_path(registry)
    store = JsonRegistryStore(registry)
    try:
        linear_client = _build_linear_api_client(cfg)
    except ValueError:
        return []

    moved: list[str] = []
    tasks = store.list_tasks()
    for task in tasks:
        if task.state in {TaskState.CANCELED, TaskState.MERGED, TaskState.BLOCKED_NEEDS_HUMAN}:
            continue

        _, worker_status = _task_worker_status(cfg, task)
        ready_from_status = worker_status is not None and status_is_ready(worker_status)

        _, log_tail = _task_log_tail(cfg, task, limit=200)
        ready_from_log = bool(log_tail) and _log_has_ready_marker(log_tail)
        if not ready_from_status and not ready_from_log:
            continue

        try:
            issue = linear_client.get_issue(task.task_id)
        except LinearApiError:
            continue

        state_name = (issue.state_name or "").strip().lower()
        moved_linear = False
        if state_name not in {"completed", "done"}:
            try:
                linear_client.move_issue_to_status(task.task_id, "Completed")
                moved_linear = True
            except LinearApiError:
                continue

        moved_local = _promote_local_task_ready_for_review(store, task.task_id)
        if not moved_linear and not moved_local:
            continue
        identifier = issue.identifier or task.task_id
        moved.append(f"auto-completed: {identifier} ({task.task_id})")
    return moved


def _watch_snapshot(
    config: Path,
    registry: Path,
    *,
    log_lines: int,
    stale_seconds: int,
    show_logs: bool,
    only_active: bool,
    previous_log_sizes: dict[str, int],
) -> tuple[list[str], dict[str, int], Counter[str], int]:
    cfg = _load_config_or_raise(config)
    registry = _resolve_registry_path(registry)
    store = JsonRegistryStore(registry)
    tasks = store.list_tasks()
    tasks_by_id = {task.task_id: task for task in tasks}
    tmux_sessions = _list_farm_tmux_sessions()
    now = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    now_epoch = int(time.time())

    out: list[str] = [f"farm watch  |  {now}", f"registry={registry}"]

    if not tasks:
        out.append("local: no tasks")
    else:
        counts = Counter(task.state.value for task in tasks)
        for state in TaskState:
            count = counts.get(state.value, 0)
            if count > 0:
                out.append(f"local:{state.value}={count}")

    linear_client: LinearApiClient | None = None
    try:
        linear_client = _build_linear_api_client(cfg)
    except ValueError as exc:
        out.append(f"linear: unavailable ({exc})")
    else:
        try:
            board_counts = linear_client.list_child_issue_counts(project_names=set(cfg.repos.keys()))
        except LinearApiError as exc:
            out.append(f"linear: unavailable ({exc})")
        else:
            out.append("linear:child-issues")
            for status_name in ["Backlog", "Approved", "Coding", "Completed", "Canceled"]:
                out.append(f"linear:{status_name.lower()}={board_counts.get(status_name, 0)}")

    out.append(f"workers: stale>{stale_seconds}s is considered stuck")
    if not tmux_sessions and not tasks:
        out.append("  (none)")
        return out, {}, Counter(), 0

    worker_ids = sorted({session.removeprefix("farm-") for session in tmux_sessions} | set(tasks_by_id))
    next_log_sizes: dict[str, int] = {}
    worker_lines: list[str] = []
    worker_counts: Counter[str] = Counter()
    displayed_workers = 0

    for task_id in worker_ids:
        task = tasks_by_id.get(task_id)
        session_name = f"farm-{task_id}"
        session_is_up = session_name in tmux_sessions
        session_state = "up" if session_is_up else "down"
        local_state = task.state.value if task else "untracked"
        repo = task.repo if task else "-"
        linear_issue = "-"
        linear_state = "-"
        if linear_client is not None and task is not None:
            try:
                issue = linear_client.get_issue(task.task_id)
                linear_issue = issue.identifier or issue.id
                linear_state = issue.state_name or "-"
            except LinearApiError:
                linear_issue = task.task_id
                linear_state = "unknown"

        log_path: Path | None = None
        status_path: Path | None = None
        worker_status: WorkerStatus | None = None
        worktree_path: Path | None = None
        if task:
            worktree_path = _task_worktree_path(cfg, task)
        if worktree_path is not None:
            log_path = worktree_path / ".farm_agent.log"
            status_path = worker_status_path(worktree_path)
            worker_status = load_worker_status(status_path)

        log_age_seconds: int | None = None
        log_size: int = 0
        tail_for_state: list[str] = []
        if log_path and log_path.exists():
            try:
                stat = log_path.stat()
                log_size = stat.st_size
                log_age_seconds = max(0, now_epoch - int(stat.st_mtime))
            except OSError:
                log_age_seconds = None
            tail_limit = max(log_lines, 80)
            tail_for_state = _tail_lines(log_path, tail_limit)
        next_log_sizes[task_id] = log_size

        status_age: int | None = None
        if worker_status is not None:
            status_age = status_age_seconds(worker_status, now_epoch=now_epoch)
        elif status_path is not None and status_path.exists():
            try:
                status_stat = status_path.stat()
                status_age = max(0, now_epoch - int(status_stat.st_mtime))
            except OSError:
                status_age = None

        ready_from_status = worker_status is not None and status_is_ready(worker_status)
        blocked_from_status = worker_status is not None and status_is_blocked(worker_status)
        ready_from_log = _log_has_ready_marker(tail_for_state)

        if ready_from_status or ready_from_log:
            worker_state = "ready"
        elif blocked_from_status:
            worker_state = "stuck"
        elif session_is_up:
            freshness_age = status_age if status_age is not None else log_age_seconds
            if freshness_age is not None and freshness_age > stale_seconds:
                worker_state = "stuck"
            else:
                worker_state = "running"
        else:
            worker_state = "idle"

        if only_active and worker_state == "idle":
            continue
        displayed_workers += 1
        worker_counts[worker_state] += 1

        growth = ""
        previous_size = previous_log_sizes.get(task_id)
        if previous_size is not None:
            delta = log_size - previous_size
            if delta > 0:
                growth = f" growth=+{delta}B"

        last_note = "-"
        phase = "-"
        blocked_reason = "-"
        if worker_status is not None:
            phase = worker_status.phase.value
            if worker_status.summary:
                last_note = _compact_text(worker_status.summary)
            blocked_reason = _compact_text(worker_status.blocked_reason) if worker_status.blocked_reason else "-"
        if tail_for_state:
            if worker_status is None or not worker_status.summary:
                last_note = _compact_text(tail_for_state[-1])
        worker_lines.append(
            (
                f"- {task_id}  linear={linear_issue}/{linear_state}  state={worker_state}  "
                f"local={local_state}  session={session_state}  "
                f"phase={phase}  hb_age={_format_age(status_age)}  "
                f"log_age={_format_age(log_age_seconds)}{growth}  repo={repo}"
            )
        )
        worker_lines.append(f"  note: {last_note}")
        if blocked_reason != "-":
            worker_lines.append(f"  blocked: {blocked_reason}")

        if show_logs and log_lines > 0 and tail_for_state:
            for log_line in tail_for_state[-log_lines:]:
                worker_lines.append(f"  > {_compact_text(log_line, max_len=120)}")

    out.append(
        "workers:summary "
        f"running={worker_counts.get('running', 0)} "
        f"stuck={worker_counts.get('stuck', 0)} "
        f"ready={worker_counts.get('ready', 0)} "
        f"idle={worker_counts.get('idle', 0)}"
    )
    if displayed_workers == 0:
        out.append("(no active workers)")
    out.extend(worker_lines)

    return out, next_log_sizes, worker_counts, displayed_workers


def _cmd_watch(
    config: Path,
    registry: Path,
    *,
    interval_seconds: float,
    log_lines: int,
    stale_seconds: int,
    show_logs: bool,
    clear_screen: bool,
    only_active: bool,
    until_ready: bool,
    auto_complete_ready: bool,
    once: bool,
) -> None:
    if interval_seconds <= 0:
        raise ValueError("--interval must be > 0.")
    if log_lines < 0:
        raise ValueError("--log-lines must be >= 0.")
    if stale_seconds < 0:
        raise ValueError("--stale-seconds must be >= 0.")

    previous_log_sizes: dict[str, int] = {}
    while True:
        promotions: list[str] = []
        if auto_complete_ready:
            promotions = _auto_complete_ready_tasks(config, registry)
        (
            snapshot_lines,
            previous_log_sizes,
            worker_counts,
            displayed_workers,
        ) = _watch_snapshot(
            config,
            registry,
            log_lines=log_lines,
            stale_seconds=stale_seconds,
            show_logs=show_logs,
            only_active=only_active,
            previous_log_sizes=previous_log_sizes,
        )
        if promotions:
            snapshot_lines.append(f"auto-complete:moved={len(promotions)}")
            snapshot_lines.extend(promotions)
        if clear_screen and not once:
            _echo("\033[2J\033[H")
        _echo("\n".join(snapshot_lines))
        if until_ready and displayed_workers > 0:
            if worker_counts.get("running", 0) == 0 and worker_counts.get("stuck", 0) == 0:
                _echo("all tracked workers are ready")
                return
        if once:
            return
        time.sleep(interval_seconds)


def _run_check_command(args: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True)
    except OSError as exc:
        return False, str(exc)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit={result.returncode}"
        return False, detail
    output = (result.stdout.strip() or result.stderr.strip() or "ok").splitlines()[0]
    return True, output


def _cmd_doctor(
    *,
    config: Path,
    registry: Path,
    check_linear_api: bool,
) -> None:
    checks: list[tuple[str, str, str]] = []

    def record(name: str, status: str, detail: str) -> None:
        checks.append((name, status, detail))

    cfg: FarmConfig | None = None
    resolved_config: Path | None = None
    try:
        resolved_config = _resolve_config_path(config)
        cfg = _load_config_or_raise(config)
        record("config", "ok", str(resolved_config))
    except ValueError as exc:
        record("config", "fail", str(exc))

    resolved_registry = _resolve_registry_path(registry)
    try:
        store = JsonRegistryStore(resolved_registry)
        _ = store.read_registry()
        record("registry", "ok", str(resolved_registry))
    except Exception as exc:  # pragma: no cover - defensive check path
        record("registry", "fail", str(exc))

    if cfg is not None:
        for repo_name, repo_cfg in sorted(cfg.repos.items()):
            repo_path = Path(repo_cfg.path)
            if not repo_path.exists():
                record(f"repo:{repo_name}", "fail", f"missing path {repo_path}")
                continue
            if not repo_path.is_dir():
                record(f"repo:{repo_name}", "fail", f"not a directory {repo_path}")
                continue
            git_dir = repo_path / ".git"
            if not git_dir.exists():
                record(f"repo:{repo_name}", "warn", f"no .git directory in {repo_path}")
                continue
            record(f"repo:{repo_name}", "ok", str(repo_path))

        try:
            client = _build_linear_api_client(cfg)
            record("linear:auth", "ok", "API key/team id resolved")
            if check_linear_api:
                _ = client.list_child_issue_counts(project_names=set(cfg.repos.keys()))
                record("linear:api", "ok", "query succeeded")
        except (ValueError, LinearApiError) as exc:
            level = "fail" if check_linear_api else "warn"
            record("linear", level, str(exc))

    tmux_ok, tmux_detail = _run_check_command(["tmux", "-V"])
    record("tool:tmux", "ok" if tmux_ok else "warn", tmux_detail)

    gh_ok, gh_detail = _run_check_command(["gh", "--version"])
    record("tool:gh", "ok" if gh_ok else "warn", gh_detail)

    failures = 0
    warnings = 0
    for name, status, detail in checks:
        if status == "fail":
            failures += 1
        elif status == "warn":
            warnings += 1
        _echo(f"doctor:{name}:{status} {detail}")

    _echo(f"doctor:summary fail={failures} warn={warnings} total={len(checks)}")
    if failures > 0:
        raise ValueError(f"Doctor checks failed: {failures}")


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


@app.command()
def doctor(
    config: Path = typer.Option(Path("config.yaml"), help="Path to config yaml."),
    registry: Path = typer.Option(Path("data/registry.json"), "--registry", help="Local registry path."),
    check_linear_api: bool = typer.Option(
        False,
        "--check-linear-api/--no-check-linear-api",
        help="Also run a live Linear API query.",
    ),
) -> None:
    """Run environment and configuration health checks."""
    try:
        _cmd_doctor(
            config=config,
            registry=registry,
            check_linear_api=check_linear_api,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command("heartbeat")
def heartbeat(
    task: str = typer.Option(..., "--task", help="Task id to update."),
    phase: WorkerPhase = typer.Option(WorkerPhase.RUNNING, help="Structured worker phase."),
    summary: str | None = typer.Option(None, help="Short progress summary."),
    ready_for_review: bool = typer.Option(
        False,
        "--ready-for-review",
        help="Mark worker ready for review.",
    ),
    blocked: bool = typer.Option(False, "--blocked", help="Mark worker blocked."),
    blocked_reason: str | None = typer.Option(
        None,
        "--blocked-reason",
        help="Short reason when blocked.",
    ),
    config: Path = typer.Option(Path("config.yaml"), help="Path to config yaml."),
    registry: Path = typer.Option(Path("data/registry.json"), "--registry", help="Local registry path."),
) -> None:
    """Write structured worker status for watch/pulse and auto-complete decisions."""
    try:
        _cmd_heartbeat(
            task_id=task,
            phase=phase,
            summary=summary,
            ready_for_review=ready_for_review,
            blocked=blocked,
            blocked_reason=blocked_reason,
            config=config,
            registry=registry,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def watch(
    config: Path = typer.Option(Path("config.yaml"), help="Path to config yaml."),
    registry: Path = typer.Option(Path("data/registry.json"), "--registry", help="Local registry path."),
    interval: float = typer.Option(5.0, "--interval", help="Refresh interval in seconds."),
    stale_seconds: int = typer.Option(300, "--stale-seconds", help="Mark as stuck if log unchanged for this long."),
    show_logs: bool = typer.Option(False, "--show-logs", help="Also print tail log lines per worker."),
    log_lines: int = typer.Option(2, "--log-lines", help="When --show-logs is set, tail N non-empty lines."),
    clear: bool = typer.Option(True, "--clear/--no-clear", help="Clear screen before each refresh."),
    only_active: bool = typer.Option(False, "--only-active", help="Hide idle workers."),
    until_ready: bool = typer.Option(False, "--until-ready", help="Exit when no running/stuck workers remain."),
    auto_complete_ready: bool = typer.Option(
        False,
        "--auto-complete-ready",
        help="Move ready tasks from Coding to Completed automatically.",
    ),
    once: bool = typer.Option(False, "--once", help="Print one snapshot and exit."),
) -> None:
    """Live heartbeat view for running/stuck/ready workers."""
    try:
        _cmd_watch(
            config,
            registry,
            interval_seconds=interval,
            log_lines=log_lines,
            stale_seconds=stale_seconds,
            show_logs=show_logs,
            clear_screen=clear,
            only_active=only_active,
            until_ready=until_ready,
            auto_complete_ready=auto_complete_ready,
            once=once,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def pulse(
    config: Path = typer.Option(Path("config.yaml"), help="Path to config yaml."),
    registry: Path = typer.Option(Path("data/registry.json"), "--registry", help="Local registry path."),
    once: bool = typer.Option(False, "--once", help="Print one snapshot and exit."),
    show_logs: bool = typer.Option(False, "--show-logs", help="Also print tail log lines per worker."),
    auto_complete_ready: bool = typer.Option(
        True,
        "--auto-complete-ready/--no-auto-complete-ready",
        help="Move ready tasks from Coding to Completed automatically.",
    ),
) -> None:
    """Opinionated monitor with strong defaults for active workers."""
    try:
        _cmd_watch(
            config,
            registry,
            interval_seconds=2.0,
            stale_seconds=120,
            show_logs=show_logs,
            log_lines=1,
            clear_screen=True,
            only_active=True,
            until_ready=True,
            auto_complete_ready=auto_complete_ready,
            once=once,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def main() -> None:
    dotenv_path = _resolve_path_from_cwd_or_parents(Path(".env"), allow_nonexistent=False)
    load_dotenv_file(dotenv_path)
    app()


if __name__ == "__main__":
    main()
