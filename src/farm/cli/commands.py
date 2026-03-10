"""CLI entrypoint for the Farm runtime kernel."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import typer

from farm.adapters.linear import LinearClient
from farm.runtime.models import Agent
from farm.runtime.runtime_factory import build_task_runtime
from farm.runtime.task_service import TaskService
from farm.support.config import FarmConfig, load_config, load_dotenv_file
from farm.support.errors import FarmError

app = typer.Typer(no_args_is_help=True, help="Farm single-task runtime kernel.")


def _echo(message: str) -> None:
    typer.echo(message)


def _parse_iso_utc(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_text(value: str | None) -> str:
    if value is None:
        return "-"
    ts = _parse_iso_utc(value)
    if ts is None:
        return "-"
    age_seconds = int((datetime.now(timezone.utc) - ts).total_seconds())
    if age_seconds < 0:
        return "0s"
    if age_seconds < 60:
        return f"{age_seconds}s"
    minutes, seconds = divmod(age_seconds, 60)
    if minutes < 60:
        return f"{minutes}m{seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def resolve_path_from_cwd_or_parents(path: Path) -> Path:
    if path.is_absolute():
        return path
    for root in [Path.cwd(), *Path.cwd().parents]:
        candidate = root / path
        if candidate.exists():
            return candidate
    return path


def resolve_config_path(path: Path) -> Path:
    resolved = resolve_path_from_cwd_or_parents(path)
    if not resolved.exists():
        raise ValueError(f"Config file not found: {path}")
    return resolved


def load_config_or_raise(config: Path) -> FarmConfig:
    try:
        return load_config(resolve_config_path(config))
    except (FileNotFoundError, ValueError) as exc:
        raise ValueError(str(exc)) from exc


def build_linear_client(cfg: FarmConfig) -> LinearClient:
    if cfg.linear is None:
        raise ValueError("Linear config missing. Add a `linear` section in config.")
    return LinearClient.from_settings(
        api_url=cfg.linear.api_url,
        api_key=cfg.linear.api_key,
        api_key_env=cfg.linear.api_key_env,
        team_id=cfg.linear.team_id,
        team_id_env=cfg.linear.team_id_env,
    )


def build_task_service_from_loaded_config(
    *,
    cfg: FarmConfig,
    config_path: Path,
    linear_client: LinearClient,
) -> TaskService:
    return TaskService(
        config=cfg,
        config_path=config_path,
        linear_client=linear_client,
        task_runtime=build_task_runtime(cfg),
    )


def build_task_service(config: Path) -> TaskService:
    resolved_config = resolve_config_path(config)
    cfg = load_config_or_raise(resolved_config)
    linear_client = build_linear_client(cfg)
    return build_task_service_from_loaded_config(
        cfg=cfg,
        config_path=resolved_config,
        linear_client=linear_client,
    )


def resolve_agent_or_raise(value: str | None, *, default: str) -> Agent:
    candidate = value.strip().lower() if value else default.strip().lower()
    try:
        return Agent(candidate)
    except ValueError as exc:
        raise ValueError(f"Unsupported agent `{candidate}`. Available: claude, codex") from exc


@app.command()
def run(
    issue: str = typer.Option(..., "--issue", help="Linear issue id."),
    repo: str = typer.Option(..., "--repo", help="Repo key from config."),
    agent: Agent = typer.Option(Agent.CODEX, "--agent", help="Agent model family."),
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config yaml."),
) -> None:
    """Launch a single approved issue into Coding and start a task session."""
    try:
        result = build_task_service(config).run(issue_id=issue, repo=repo, agent=agent)
    except (ValueError, FarmError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _echo(f"run: issue={result['issue_id']} repo={result['repo']}")
    _echo(f"run: runtime={result['runtime']}")
    if "runtime_workspace" in result:
        _echo(f"run: workspace={result['runtime_workspace']}")
    if "runtime_branch" in result:
        _echo(f"run: branch={result['runtime_branch']}")
    if "runtime_handle" in result:
        _echo(f"run: handle={result['runtime_handle']}")
    _echo(f"run: updates={result['updates']}")
    _echo(f"run: result={result['result']}")


@app.command()
def update(
    issue: str = typer.Option(..., "--issue", help="Linear issue id."),
    repo: str = typer.Option(..., "--repo", help="Repo key from config."),
    phase: str = typer.Option(..., "--phase", help="Update phase."),
    summary: str = typer.Option(..., "--summary", help="Progress summary."),
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config yaml."),
) -> None:
    """Append a periodic TaskUpdate entry."""
    try:
        path = build_task_service(config).update(issue_id=issue, repo=repo, phase=phase, summary=summary)
    except (ValueError, FarmError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _echo(f"update: issue={issue} phase={phase} path={path}")


@app.command()
def finish(
    issue: str = typer.Option(..., "--issue", help="Linear issue id."),
    repo: str = typer.Option(..., "--repo", help="Repo key from config."),
    outcome: str = typer.Option(..., "--outcome", help="Outcome: completed|canceled|blocked|failed"),
    summary: str = typer.Option(..., "--summary", help="Final summary."),
    pr_url: str | None = typer.Option(None, "--pr-url", help="Optional PR URL."),
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config yaml."),
) -> None:
    """Finalize a task and write TaskResult."""
    try:
        path = build_task_service(config).finish(
            issue_id=issue,
            repo=repo,
            outcome=outcome,
            summary=summary,
            pr_url=pr_url,
        )
    except (ValueError, FarmError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _echo(f"finish: issue={issue} outcome={outcome} result={path}")


@app.command()
def status(
    issue: str = typer.Option(..., "--issue", help="Linear issue id."),
    repo: str = typer.Option(..., "--repo", help="Repo key from config."),
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config yaml."),
) -> None:
    """Show Linear state + latest TaskUpdate + TaskResult summary."""
    try:
        snapshot = build_task_service(config).status(issue_id=issue, repo=repo)
    except (ValueError, FarmError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    _echo(f"status: issue={snapshot['issue_id']} repo={snapshot['repo']}")
    _echo(f"status: linear_state={snapshot['linear_state'] or '-'}")
    _echo(f"status: runtime={snapshot['runtime']}")
    _echo(f"status: runtime_workspace={snapshot['runtime_workspace'] or '-'}")
    _echo(f"status: runtime_branch={snapshot['runtime_branch'] or '-'}")
    _echo(f"status: runtime_handle={snapshot['runtime_handle'] or '-'}")
    _echo(f"status: update_phase={snapshot['update_phase'] or '-'}")
    _echo(f"status: update_ts={snapshot['update_ts'] or '-'}")
    _echo(f"status: update_summary={snapshot['update_summary'] or '-'}")
    _echo(f"status: outcome={snapshot['outcome'] or '-'}")
    _echo(f"status: result_ended_at={snapshot['result_ended_at'] or '-'}")
    _echo(f"status: result_summary={snapshot['result_summary'] or '-'}")
    _echo(f"status: updates={snapshot['updates']}")
    _echo(f"status: result={snapshot['result']}")


@app.command()
def pulse(
    repo: str = typer.Option(..., "--repo", help="Repo key from config."),
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config yaml."),
) -> None:
    """Show lightweight task observability snapshot for a repo."""
    try:
        rows = build_task_service(config).pulse(repo=repo)
    except (ValueError, FarmError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    if not rows:
        _echo(f"pulse: repo={repo} tasks=0")
        return

    _echo(f"pulse: repo={repo} tasks={len(rows)}")
    for row in rows:
        _echo(
            "pulse: "
            f"issue={row['issue_id']} "
            f"state={row['linear_state'] or '-'} "
            f"runtime={row['runtime']} "
            f"phase={row['update_phase'] or '-'} "
            f"outcome={row['outcome'] or '-'} "
            f"runtime_alive={row['runtime_alive']}"
        )


@app.command()
def watch(
    repo: str = typer.Option(..., "--repo", help="Repo key from config."),
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config yaml."),
    interval: float = typer.Option(1.5, "--interval", min=0.2, help="Refresh interval seconds."),
    lines: int = typer.Option(3, "--lines", min=1, max=20, help="Tail lines per runtime."),
    duration: float = typer.Option(0.0, "--duration", min=0.0, help="Seconds to run; 0 = forever."),
    clear: bool = typer.Option(True, "--clear/--no-clear", help="Clear screen between refreshes."),
) -> None:
    """Watch live task snapshot with recent runtime output."""
    try:
        task_service = build_task_service(config)
    except (ValueError, FarmError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    started = time.monotonic()
    while True:
        try:
            rows = task_service.watch(repo=repo, tail_lines=lines)
        except (ValueError, FarmError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        if clear:
            _echo("\033[2J\033[H")
        now_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        _echo(f"watch: repo={repo} tasks={len(rows)} now={now_text}")
        for row in rows:
            label = row.get("issue_identifier") or row["issue_id"]
            _echo(
                f"{label} "
                f"state={row['linear_state'] or '-'} "
                f"runtime={row['runtime']} "
                f"phase={row['update_phase'] or '-'} "
                f"age={_age_text(row['update_ts'])} "
                f"outcome={row['outcome'] or '-'} "
                f"handle={row['runtime_handle'] or '-'} "
                f"runtime_state={'alive' if row['runtime_alive'] else 'dead'}"
            )
            tail_lines = row.get("tail_lines")
            if isinstance(tail_lines, list) and tail_lines:
                for line in tail_lines[-lines:]:
                    _echo(f"  > {line}")
            else:
                _echo("  > -")

        if duration > 0 and (time.monotonic() - started) >= duration:
            return
        time.sleep(interval)


@app.command()
def daemon(
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config yaml."),
    interval: float = typer.Option(0.0, "--interval", min=1.0, help="Poll interval seconds. 0 = use config."),
    max_concurrent: int = typer.Option(0, "--max-concurrent", min=0, help="Max parallel tasks. 0 = use config."),
    agent: str | None = typer.Option(None, "--agent", help="Agent model family. Omit to use config."),
    repo: str | None = typer.Option(None, "--repo", help="Limit to specific repo. Omit to poll all."),
) -> None:
    """Poll Linear for Approved issues and auto-launch them."""
    from farm.runtime.daemon import FarmDaemon

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    try:
        resolved_config = resolve_config_path(config)
        cfg = load_config_or_raise(resolved_config)
        linear = build_linear_client(cfg)
        task_service = build_task_service_from_loaded_config(
            cfg=cfg,
            config_path=resolved_config,
            linear_client=linear,
        )
        default_agent = resolve_agent_or_raise(agent, default=cfg.daemon.default_agent)
    except (ValueError, FarmError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    poll_interval = interval if interval > 0 else cfg.daemon.poll_interval
    concurrency = max_concurrent if max_concurrent > 0 else cfg.daemon.max_concurrent
    repos = [repo] if repo else None

    farm_daemon = FarmDaemon(
        config=cfg,
        linear_client=linear,
        config_path=resolved_config,
        poll_interval=poll_interval,
        max_concurrent=concurrency,
        default_agent=default_agent,
        repos=repos,
        task_service=task_service,
    )
    farm_daemon.run()


def main() -> None:
    dotenv_path = resolve_path_from_cwd_or_parents(Path(".env"))
    load_dotenv_file(dotenv_path)
    app()


if __name__ == "__main__":
    main()
