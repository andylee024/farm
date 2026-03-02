"""Minimal Linear API adapter for runtime execution."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from farm.support.errors import LinearApiError

GraphqlRequestFn = Callable[[str, dict[str, Any], dict[str, str]], dict[str, Any]]

DEFAULT_LINEAR_API_URL = "https://api.linear.app/graphql"

ISSUE_UPDATE_MUTATION = """
mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
  issueUpdate(id: $id, input: $input) {
    success
  }
}
"""

TEAM_STATES_QUERY = """
query TeamStates($teamId: String!) {
  team(id: $teamId) {
    id
    states {
      nodes {
        id
        name
      }
    }
  }
}
"""

ISSUE_QUERY = """
query IssueById($id: String!) {
  issue(id: $id) {
    id
    identifier
    title
    description
    parent {
      id
    }
    state {
      name
    }
    project {
      name
    }
  }
}
"""


@dataclass(slots=True)
class LinearIssue:
    id: str
    identifier: str | None
    title: str
    description: str
    parent_id: str | None
    state_name: str | None
    project_name: str | None



def normalize_state_name(state_name: str | None) -> str:
    if state_name is None:
        return ""
    return " ".join(state_name.strip().lower().split())


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise LinearApiError(f"Linear issue payload missing `{key}`.")
    return value


def _optional_nested_str(payload: dict[str, Any], parent_key: str, child_key: str) -> str | None:
    parent = payload.get(parent_key)
    if not isinstance(parent, dict):
        return None
    value = parent.get(child_key)
    return value if isinstance(value, str) else None


def _resolve_setting(value: str | None, env_name: str | None, key: str) -> str:
    resolved = value
    if not resolved and env_name:
        resolved = os.getenv(env_name)
    if not resolved:
        env_hint = f" or env var `{env_name}`" if env_name else ""
        raise ValueError(f"Linear {key} missing. Set `linear.{key}`{env_hint}.")
    return resolved


def _default_graphql_request(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise LinearApiError(f"Linear API HTTP error {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise LinearApiError(f"Linear API request failed: {exc.reason}") from exc

    try:
        decoded = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise LinearApiError("Linear API returned invalid JSON payload.") from exc

    if not isinstance(decoded, dict):
        raise LinearApiError("Linear API response must be a JSON object.")
    return decoded


class LinearClient:
    """Minimal client for runtime issue reads and status updates."""

    def __init__(
        self,
        *,
        api_url: str,
        api_key: str,
        team_id: str,
        request_fn: GraphqlRequestFn | None = None,
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.team_id = team_id
        self.request_fn = request_fn or _default_graphql_request
        self._state_id_by_name: dict[str, str] | None = None

    @classmethod
    def from_settings(
        cls,
        *,
        api_url: str = DEFAULT_LINEAR_API_URL,
        api_key: str | None,
        api_key_env: str | None,
        team_id: str | None,
        team_id_env: str | None,
        request_fn: GraphqlRequestFn | None = None,
    ) -> "LinearClient":
        return cls(
            api_url=api_url,
            api_key=_resolve_setting(api_key, api_key_env, "api_key"),
            team_id=_resolve_setting(team_id, team_id_env, "team_id"),
            request_fn=request_fn,
        )

    def get_issue(self, issue_id: str) -> LinearIssue:
        data = self._execute(ISSUE_QUERY, {"id": issue_id})
        issue_payload = data.get("issue")
        if not isinstance(issue_payload, dict):
            raise LinearApiError("Linear API response missing `issue` payload.")

        description_value = issue_payload.get("description")
        if description_value is None:
            description_value = ""
        if not isinstance(description_value, str):
            raise LinearApiError("Linear issue payload has invalid `description`.")

        identifier = issue_payload.get("identifier")
        if identifier is not None and not isinstance(identifier, str):
            raise LinearApiError("Linear issue payload has invalid `identifier`.")

        return LinearIssue(
            id=_required_str(issue_payload, "id"),
            identifier=identifier,
            title=_required_str(issue_payload, "title"),
            description=description_value,
            parent_id=_optional_nested_str(issue_payload, "parent", "id"),
            state_name=_optional_nested_str(issue_payload, "state", "name"),
            project_name=_optional_nested_str(issue_payload, "project", "name"),
        )

    def move_issue_to_status(self, issue_id: str, status_name: str) -> None:
        state_id = self.get_state_id(status_name)
        data = self._execute(
            ISSUE_UPDATE_MUTATION,
            {
                "id": issue_id,
                "input": {"stateId": state_id},
            },
        )
        issue_update = data.get("issueUpdate")
        if not isinstance(issue_update, dict):
            raise LinearApiError("Linear API response missing `issueUpdate` payload.")
        if issue_update.get("success") is not True:
            raise LinearApiError("Linear API issueUpdate returned success=false.")

    def get_state_id(self, state_name: str) -> str:
        if self._state_id_by_name is None:
            self._state_id_by_name = self._load_state_id_by_name()
        normalized = normalize_state_name(state_name)
        state_id = self._state_id_by_name.get(normalized)
        if state_id is None:
            available = ", ".join(sorted(self._state_id_by_name.keys()))
            raise LinearApiError(
                f"Linear workflow state not found: `{state_name}`. Available: {available}"
            )
        return state_id

    def _load_state_id_by_name(self) -> dict[str, str]:
        data = self._execute(TEAM_STATES_QUERY, {"teamId": self.team_id})
        team_payload = data.get("team")
        if not isinstance(team_payload, dict):
            raise LinearApiError("Linear API response missing `team` payload for states.")
        states_conn = team_payload.get("states")
        if not isinstance(states_conn, dict):
            raise LinearApiError("Linear API response missing team states connection.")
        nodes = states_conn.get("nodes")
        if not isinstance(nodes, list):
            raise LinearApiError("Linear API team states connection missing nodes list.")

        mapping: dict[str, str] = {}
        for node in nodes:
            if not isinstance(node, dict):
                continue
            state_id = node.get("id")
            state_name = node.get("name")
            if isinstance(state_id, str) and isinstance(state_name, str):
                mapping.setdefault(normalize_state_name(state_name), state_id)
        if not mapping:
            raise LinearApiError("No workflow states found for configured Linear team.")
        return mapping

    def _execute(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        response = self.request_fn(
            self.api_url,
            {"query": query, "variables": variables},
            {"Authorization": self.api_key},
        )
        errors = response.get("errors")
        if errors:
            raise LinearApiError(f"Linear API GraphQL errors: {self._format_errors(errors)}")
        data = response.get("data")
        if not isinstance(data, dict):
            raise LinearApiError("Linear API response missing `data` object.")
        return data

    @staticmethod
    def _format_errors(errors: Any) -> str:
        if not isinstance(errors, list):
            return str(errors)
        return "; ".join(
            entry["message"]
            if isinstance(entry, dict) and isinstance(entry.get("message"), str)
            else str(entry)
            for entry in errors
        )
