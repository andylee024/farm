#!/usr/bin/env python3
"""Check whether required strict Farm statuses exist in the configured Linear team."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from farm.adapters.linear import LinearClient
from farm.support.config import FarmConfig, load_config, load_dotenv_file
from farm.support.errors import LinearApiError

REQUIRED_STATUSES = ("Backlog", "Approved", "Coding", "Done", "Canceled")


def _resolve_config(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    for root in [Path.cwd(), *Path.cwd().parents, REPO_ROOT]:
        resolved = root / candidate
        if resolved.exists():
            return resolved
    raise FileNotFoundError(f"Config file not found: {path}")


def _build_client(cfg: FarmConfig) -> LinearClient:
    if cfg.linear is None:
        raise ValueError("Linear config missing in config.yaml")
    return LinearClient.from_settings(
        api_url=cfg.linear.api_url,
        api_key=cfg.linear.api_key,
        api_key_env=cfg.linear.api_key_env,
        team_id=cfg.linear.team_id,
        team_id_env=cfg.linear.team_id_env,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    config_path = _resolve_config(args.config)
    load_dotenv_file(config_path.parent / ".env")
    cfg = load_config(config_path)
    client = _build_client(cfg)

    missing: list[str] = []
    for status in REQUIRED_STATUSES:
        try:
            state_id = client.get_state_id(status)
            print(f"{status}: ok ({state_id})")
        except LinearApiError:
            missing.append(status)
            print(f"{status}: missing")

    if missing:
        raise SystemExit(f"Missing required statuses: {', '.join(missing)}")


if __name__ == "__main__":
    main()
