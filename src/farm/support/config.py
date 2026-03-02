"""Typed configuration loading for Farm runtime."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class RepoConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    default_branch: str = "main"
    test_command: str = "pytest -q"


class AgentDefaultsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codex_model: str = "gpt-5.3-codex"
    claude_model: str = "claude-opus-4.5"
    dangerous_bypass_permissions: bool = True


class LinearConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_url: str = "https://api.linear.app/graphql"
    api_key: str | None = None
    api_key_env: str | None = "LINEAR_API_KEY"
    team_id: str | None = None
    team_id_env: str | None = "LINEAR_TEAM_ID"


class FarmConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repos: dict[str, RepoConfig] = Field(default_factory=dict)
    worktree_root: str
    agent_defaults: AgentDefaultsConfig = Field(default_factory=AgentDefaultsConfig)
    linear: LinearConfig | None = None



def default_config_path() -> Path:
    env_path = os.getenv("FARM_CONFIG")
    if env_path:
        return Path(env_path)
    return Path("config.yaml")



def load_dotenv_file(path: str | Path = ".env", *, override: bool = False) -> bool:
    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return False

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        quoted = len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}
        if quoted:
            value = value[1:-1]
        else:
            hash_index = value.find("#")
            if hash_index >= 0:
                value = value[:hash_index].rstrip()

        if not override and key in os.environ:
            continue
        os.environ[key] = value
    return True



def load_config(path: str | Path | None = None) -> FarmConfig:
    config_path = Path(path) if path is not None else default_config_path()
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError(f"Config must be a mapping object: {config_path}")

    try:
        return FarmConfig.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid config at {config_path}: {exc}") from exc
