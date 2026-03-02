#!/usr/bin/env python3
"""Create sample parent/child Linear tasks for Farm runtime flow testing."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from farm.adapters.linear import LinearClient
from farm.support.config import FarmConfig, load_config, load_dotenv_file
from farm.support.errors import LinearApiError

ISSUE_CREATE_MUTATION = """
mutation IssueCreate($input: IssueCreateInput!) {
  issueCreate(input: $input) {
    success
    issue {
      id
      identifier
      title
      state {
        name
      }
    }
  }
}
"""


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


def _create_issue(
    *,
    client: LinearClient,
    title: str,
    description: str,
    state_name: str,
    parent_id: str | None = None,
) -> dict[str, str]:
    state_id = client.get_state_id(state_name)
    input_payload: dict[str, Any] = {
        "teamId": client.team_id,
        "title": title,
        "description": description,
        "stateId": state_id,
    }
    if parent_id:
        input_payload["parentId"] = parent_id

    data = client._execute(  # pylint: disable=protected-access
        ISSUE_CREATE_MUTATION,
        {"input": input_payload},
    )
    payload = data.get("issueCreate")
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise LinearApiError("Linear issueCreate returned success=false.")
    issue = payload.get("issue")
    if not isinstance(issue, dict):
        raise LinearApiError("Linear issueCreate response missing issue payload.")

    issue_id = issue.get("id")
    identifier = issue.get("identifier")
    issue_title = issue.get("title")
    state = issue.get("state")
    state_value = state.get("name") if isinstance(state, dict) else None
    if not all(isinstance(value, str) for value in (issue_id, identifier, issue_title, state_value)):
        raise LinearApiError("Linear issueCreate response had invalid issue fields.")
    return {
        "id": issue_id,
        "identifier": identifier,
        "title": issue_title,
        "state": state_value,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--repo", required=True, help="Repo key used in Farm commands.")
    parser.add_argument("--children", type=int, default=2, help="How many child issues to create.")
    parser.add_argument("--prefix", default="Farm Demo", help="Title prefix.")
    parser.add_argument(
        "--backlog-status",
        default="Backlog",
        help="Exact Linear status name for newly created issues.",
    )
    parser.add_argument(
        "--approve-first",
        action="store_true",
        help="Move the first child issue to Approved after creation.",
    )
    args = parser.parse_args()

    config_path = _resolve_config(args.config)
    load_dotenv_file(config_path.parent / ".env")
    cfg = load_config(config_path)
    client = _build_client(cfg)

    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S")
    parent_title = f"{args.prefix}: parent ({stamp})"
    parent_desc = (
        "Sample parent issue for Farm runtime flow validation.\n\n"
        f"Repo: {args.repo}\n"
        "Created by scripts/demo/seed_linear_tasks.py"
    )
    parent = _create_issue(
        client=client,
        title=parent_title,
        description=parent_desc,
        state_name=args.backlog_status,
    )

    children: list[dict[str, str]] = []
    for index in range(args.children):
        child_title = f"{args.prefix}: child {index + 1} ({stamp})"
        child_desc = (
            "Sample child issue for Farm runtime flow validation.\n\n"
            f"Repo: {args.repo}\n"
            "Use with scripts/demo/run_linear_flow.py."
        )
        child = _create_issue(
            client=client,
            title=child_title,
            description=child_desc,
            state_name=args.backlog_status,
            parent_id=parent["id"],
        )
        children.append(child)

    if args.approve_first and children:
        first_child = children[0]
        client.move_issue_to_status(first_child["id"], "Approved")
        first_child["state"] = "Approved"

    output = {
        "parent": parent,
        "children": children,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
