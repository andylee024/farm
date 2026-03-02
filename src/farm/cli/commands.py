"""CLI entrypoint for the Farm runtime kernel."""

from __future__ import annotations

from pathlib import Path

import typer

from farm.adapters.linear import LinearClient
from farm.runtime.models import AgentKind
from farm.runtime.runner import TaskRunner
from farm.support.config import FarmConfig, load_config, load_dotenv_file
from farm.support.errors import LinearApiError

app = typer.Typer(no_args_is_help=True, help="Farm single-task runtime kernel.")


def _echo(message: str) -> None:
    typer.echo(message)


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


def build_runner(config: Path) -> TaskRunner:
    cfg = load_config_or_raise(config)
    return TaskRunner(config=cfg, linear_client=build_linear_client(cfg))


@app.command()
def run(
    issue: str = typer.Option(..., "--issue", help="Linear issue id."),
    repo: str = typer.Option(..., "--repo", help="Repo key from config."),
    agent: AgentKind = typer.Option(AgentKind.CODEX, "--agent", help="Agent model family."),
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config yaml."),
) -> None:
    """Launch a single approved issue into Coding and start a task session."""
    try:
        result = build_runner(config).run(issue_id=issue, repo=repo, agent=agent)
    except (ValueError, LinearApiError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _echo(f"run: issue={result['issue_id']} repo={result['repo']}")
    _echo(f"run: worktree={result['worktree']}")
    _echo(f"run: branch={result['branch']}")
    _echo(f"run: session={result['session']}")
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
        path = build_runner(config).update(issue_id=issue, repo=repo, phase=phase, summary=summary)
    except (ValueError, LinearApiError) as exc:
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
        path = build_runner(config).finish(
            issue_id=issue,
            repo=repo,
            outcome=outcome,
            summary=summary,
            pr_url=pr_url,
        )
    except (ValueError, LinearApiError) as exc:
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
        snapshot = build_runner(config).status(issue_id=issue, repo=repo)
    except (ValueError, LinearApiError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    _echo(f"status: issue={snapshot['issue_id']} repo={snapshot['repo']}")
    _echo(f"status: linear_state={snapshot['linear_state'] or '-'}")
    _echo(f"status: update_phase={snapshot['update_phase'] or '-'}")
    _echo(f"status: update_ts={snapshot['update_ts'] or '-'}")
    _echo(f"status: update_summary={snapshot['update_summary'] or '-'}")
    _echo(f"status: outcome={snapshot['outcome'] or '-'}")
    _echo(f"status: result_ended_at={snapshot['result_ended_at'] or '-'}")
    _echo(f"status: result_summary={snapshot['result_summary'] or '-'}")
    _echo(f"status: updates={snapshot['updates']}")
    _echo(f"status: result={snapshot['result']}")


def main() -> None:
    dotenv_path = resolve_path_from_cwd_or_parents(Path(".env"))
    load_dotenv_file(dotenv_path)
    app()


if __name__ == "__main__":
    main()
