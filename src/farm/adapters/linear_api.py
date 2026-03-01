"""Linear direct API adapter (GraphQL over HTTPS)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from farm.core.errors import LinearApiError

GraphqlRequestFn = Callable[[str, dict[str, Any], dict[str, str]], dict[str, Any]]

DEFAULT_LINEAR_API_URL = "https://api.linear.app/graphql"

CREATE_ISSUE_MUTATION = """
mutation IssueCreate($input: IssueCreateInput!) {
  issueCreate(input: $input) {
    success
    issue {
      id
      title
      description
    }
  }
}
"""

ISSUE_UPDATE_MUTATION = """
mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
  issueUpdate(id: $id, input: $input) {
    success
    issue {
      id
      state {
        id
        name
      }
    }
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

TEAM_PROJECTS_QUERY = """
query TeamProjects($teamId: String!) {
  team(id: $teamId) {
    id
    projects {
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
      id
      name
    }
    project {
      id
      name
    }
  }
}
"""

TEAM_ISSUES_QUERY = """
query TeamIssues($teamId: String!, $first: Int!) {
  team(id: $teamId) {
    id
    issues(first: $first) {
      nodes {
        id
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


@dataclass(slots=True)
class LinearChildIssue:
    id: str
    title: str
    description: str


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


class LinearApiClient:
    """Minimal client for creating Linear issues via direct API calls."""

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
        self._project_id_by_name: dict[str, str] | None = None

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
    ) -> "LinearApiClient":
        resolved_key = api_key
        if not resolved_key and api_key_env:
            resolved_key = os.getenv(api_key_env)
        if not resolved_key:
            env_hint = f" or env var `{api_key_env}`" if api_key_env else ""
            raise ValueError(f"Linear API key missing. Set `linear.api_key`{env_hint}.")
        resolved_team_id = team_id
        if not resolved_team_id and team_id_env:
            resolved_team_id = os.getenv(team_id_env)
        if not resolved_team_id:
            env_hint = f" or env var `{team_id_env}`" if team_id_env else ""
            raise ValueError(f"Linear team id missing. Set `linear.team_id`{env_hint}.")
        return cls(
            api_url=api_url,
            api_key=resolved_key,
            team_id=resolved_team_id,
            request_fn=request_fn,
        )

    def create_parent_issue(
        self,
        title: str,
        description: str,
        *,
        project_name: str | None = None,
        state_name: str | None = None,
    ) -> str:
        issue = self._create_issue(
            title=title,
            description=description,
            parent_issue_id=None,
            project_name=project_name,
            state_name=state_name,
        )
        return issue.id

    def create_child_issue(
        self,
        *,
        parent_issue_id: str,
        title: str,
        description: str,
        project_name: str | None = None,
        state_name: str | None = None,
    ) -> LinearChildIssue:
        return self._create_issue(
            title=title,
            description=description,
            parent_issue_id=parent_issue_id,
            project_name=project_name,
            state_name=state_name,
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

    def get_issue(self, issue_id: str) -> LinearIssue:
        data = self._execute(ISSUE_QUERY, {"id": issue_id})
        issue_payload = data.get("issue")
        if not isinstance(issue_payload, dict):
            raise LinearApiError("Linear API response missing `issue` payload.")
        issue_id_value = issue_payload.get("id")
        title_value = issue_payload.get("title")
        if not isinstance(issue_id_value, str) or not issue_id_value:
            raise LinearApiError("Linear issue payload missing `id`.")
        if not isinstance(title_value, str):
            raise LinearApiError("Linear issue payload missing `title`.")

        description_value = issue_payload.get("description")
        if description_value is None:
            description_value = ""
        if not isinstance(description_value, str):
            raise LinearApiError("Linear issue payload has invalid `description`.")

        parent_id: str | None = None
        parent = issue_payload.get("parent")
        if isinstance(parent, dict) and isinstance(parent.get("id"), str):
            parent_id = parent["id"]

        state_name: str | None = None
        state = issue_payload.get("state")
        if isinstance(state, dict) and isinstance(state.get("name"), str):
            state_name = state["name"]

        project_name: str | None = None
        project = issue_payload.get("project")
        if isinstance(project, dict) and isinstance(project.get("name"), str):
            project_name = project["name"]

        identifier = issue_payload.get("identifier")
        if identifier is not None and not isinstance(identifier, str):
            raise LinearApiError("Linear issue payload has invalid `identifier`.")

        return LinearIssue(
            id=issue_id_value,
            identifier=identifier,
            title=title_value,
            description=description_value,
            parent_id=parent_id,
            state_name=state_name,
            project_name=project_name,
        )

    def list_child_issue_counts(
        self,
        *,
        project_names: set[str] | None = None,
    ) -> dict[str, int]:
        data = self._execute(TEAM_ISSUES_QUERY, {"teamId": self.team_id, "first": 250})
        team_payload = data.get("team")
        if not isinstance(team_payload, dict):
            raise LinearApiError("Linear API response missing `team` payload for issues.")
        issues_conn = team_payload.get("issues")
        if not isinstance(issues_conn, dict):
            raise LinearApiError("Linear API response missing team issues connection.")
        nodes = issues_conn.get("nodes")
        if not isinstance(nodes, list):
            raise LinearApiError("Linear API issues connection missing nodes list.")

        counts: dict[str, int] = {}
        for node in nodes:
            if not isinstance(node, dict):
                continue
            parent = node.get("parent")
            if not isinstance(parent, dict) or not isinstance(parent.get("id"), str):
                continue

            project_name: str | None = None
            project = node.get("project")
            if isinstance(project, dict) and isinstance(project.get("name"), str):
                project_name = project["name"]
            if project_names and (project_name is None or project_name not in project_names):
                continue

            state = node.get("state")
            state_name: str | None = None
            if isinstance(state, dict) and isinstance(state.get("name"), str):
                state_name = state["name"]
            if state_name is None:
                continue
            canonical_state = self._canonical_status_name(state_name)
            counts[canonical_state] = counts.get(canonical_state, 0) + 1
        return counts

    def get_state_id(self, state_name: str) -> str:
        if self._state_id_by_name is None:
            self._state_id_by_name = self._load_state_id_by_name()
        normalized = state_name.strip().lower()
        state_id = self._state_id_by_name.get(normalized)
        if state_id is None:
            for candidate in self._status_alias_candidates(normalized):
                state_id = self._state_id_by_name.get(candidate)
                if state_id is not None:
                    break
        if state_id is None:
            available = ", ".join(sorted(self._state_id_by_name.keys()))
            raise LinearApiError(
                f"Linear workflow state not found: `{state_name}`. Available: {available}"
            )
        return state_id

    def get_project_id(self, project_name: str) -> str:
        if self._project_id_by_name is None:
            self._project_id_by_name = self._load_project_id_by_name()
        project_id = self._project_id_by_name.get(project_name.lower())
        if project_id is None:
            available = ", ".join(sorted(self._project_id_by_name.keys()))
            raise LinearApiError(
                f"Linear project not found: `{project_name}`. Available: {available}"
            )
        return project_id

    def _create_issue(
        self,
        *,
        title: str,
        description: str,
        parent_issue_id: str | None,
        project_name: str | None,
        state_name: str | None,
    ) -> LinearChildIssue:
        issue_input: dict[str, Any] = {
            "teamId": self.team_id,
            "title": title,
            "description": description,
        }
        if parent_issue_id:
            issue_input["parentId"] = parent_issue_id
        if project_name:
            issue_input["projectId"] = self.get_project_id(project_name)
        if state_name:
            issue_input["stateId"] = self.get_state_id(state_name)

        data = self._execute(CREATE_ISSUE_MUTATION, {"input": issue_input})
        issue_create = data.get("issueCreate")
        if not isinstance(issue_create, dict):
            raise LinearApiError("Linear API response missing `issueCreate` payload.")
        if issue_create.get("success") is not True:
            raise LinearApiError("Linear API issueCreate returned success=false.")

        issue_payload = issue_create.get("issue")
        if not isinstance(issue_payload, dict):
            raise LinearApiError("Linear API response missing created issue object.")

        issue_id = issue_payload.get("id")
        issue_title = issue_payload.get("title")
        issue_description = issue_payload.get("description")
        if not isinstance(issue_id, str) or not issue_id:
            raise LinearApiError("Linear API issue payload missing `id`.")
        if not isinstance(issue_title, str):
            raise LinearApiError("Linear API issue payload missing `title`.")
        if issue_description is None:
            issue_description = ""
        if not isinstance(issue_description, str):
            raise LinearApiError("Linear API issue payload has invalid `description`.")
        return LinearChildIssue(id=issue_id, title=issue_title, description=issue_description)

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
                mapping[state_name.lower()] = state_id
        if not mapping:
            raise LinearApiError("No workflow states found for configured Linear team.")
        return mapping

    def _load_project_id_by_name(self) -> dict[str, str]:
        data = self._execute(TEAM_PROJECTS_QUERY, {"teamId": self.team_id})
        team_payload = data.get("team")
        if not isinstance(team_payload, dict):
            raise LinearApiError("Linear API response missing `team` payload for projects.")
        projects_conn = team_payload.get("projects")
        if not isinstance(projects_conn, dict):
            raise LinearApiError("Linear API response missing team projects connection.")
        nodes = projects_conn.get("nodes")
        if not isinstance(nodes, list):
            raise LinearApiError("Linear API team projects connection missing nodes list.")

        mapping: dict[str, str] = {}
        for node in nodes:
            if not isinstance(node, dict):
                continue
            project_id = node.get("id")
            project_name = node.get("name")
            if isinstance(project_id, str) and isinstance(project_name, str):
                mapping[project_name.lower()] = project_id
        if not mapping:
            raise LinearApiError("No projects found for configured Linear team.")
        return mapping

    @staticmethod
    def _status_alias_candidates(name: str) -> list[str]:
        alias_map: dict[str, list[str]] = {
            "backlog": ["todo"],
            "approved": ["todo"],
            "coding": ["in progress"],
            "completed": ["done"],
            "canceled": ["cancelled"],
            "cancelled": ["canceled"],
        }
        return alias_map.get(name, [])

    @staticmethod
    def _canonical_status_name(name: str) -> str:
        normalized = name.strip().lower()
        if normalized in {"backlog"}:
            return "Backlog"
        if normalized in {"approved", "todo"}:
            return "Approved"
        if normalized in {"coding", "in progress"}:
            return "Coding"
        if normalized in {"completed", "done"}:
            return "Completed"
        if normalized in {"canceled", "cancelled"}:
            return "Canceled"
        return name

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
        messages: list[str] = []
        for entry in errors:
            if isinstance(entry, dict) and isinstance(entry.get("message"), str):
                messages.append(entry["message"])
            else:
                messages.append(str(entry))
        return "; ".join(messages)
