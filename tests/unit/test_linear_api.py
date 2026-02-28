from __future__ import annotations

import pytest

from farm.adapters.linear_api import LinearApiClient
from farm.core.errors import LinearApiError


def test_from_settings_resolves_api_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINEAR_TOKEN_TEST", "token-from-env")
    client = LinearApiClient.from_settings(
        api_url="https://api.linear.app/graphql",
        api_key=None,
        api_key_env="LINEAR_TOKEN_TEST",
        team_id="team-1",
        team_id_env=None,
    )

    assert client.api_key == "token-from-env"
    assert client.team_id == "team-1"


def test_create_parent_issue_sends_expected_payload() -> None:
    captured: dict[str, object] = {}

    def fake_request(url: str, payload: dict[str, object], headers: dict[str, str]) -> dict[str, object]:
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        return {
            "data": {
                "issueCreate": {
                    "success": True,
                    "issue": {"id": "issue-1", "title": "Parent", "description": "desc"},
                }
            }
        }

    client = LinearApiClient(
        api_url="https://api.linear.app/graphql",
        api_key="secret",
        team_id="team-abc",
        request_fn=fake_request,
    )
    issue_id = client.create_parent_issue("Parent", "desc")

    assert issue_id == "issue-1"
    assert captured["url"] == "https://api.linear.app/graphql"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    variables = payload["variables"]
    assert isinstance(variables, dict)
    issue_input = variables["input"]
    assert isinstance(issue_input, dict)
    assert issue_input["teamId"] == "team-abc"
    assert issue_input["title"] == "Parent"
    assert issue_input["description"] == "desc"
    assert "parentId" not in issue_input

    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer secret"


def test_create_child_issue_sets_parent_id() -> None:
    captured: dict[str, object] = {}

    def fake_request(url: str, payload: dict[str, object], headers: dict[str, str]) -> dict[str, object]:
        _ = url
        _ = headers
        captured["payload"] = payload
        return {
            "data": {
                "issueCreate": {
                    "success": True,
                    "issue": {"id": "issue-2", "title": "Child", "description": "child desc"},
                }
            }
        }

    client = LinearApiClient(
        api_url="https://api.linear.app/graphql",
        api_key="secret",
        team_id="team-abc",
        request_fn=fake_request,
    )
    child = client.create_child_issue(
        parent_issue_id="parent-1",
        title="Child",
        description="child desc",
    )

    assert child.id == "issue-2"
    assert child.title == "Child"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    variables = payload["variables"]
    assert isinstance(variables, dict)
    issue_input = variables["input"]
    assert isinstance(issue_input, dict)
    assert issue_input["parentId"] == "parent-1"


def test_graphql_errors_raise_linear_api_error() -> None:
    def fake_request(url: str, payload: dict[str, object], headers: dict[str, str]) -> dict[str, object]:
        _ = url
        _ = payload
        _ = headers
        return {"errors": [{"message": "Invalid input"}]}

    client = LinearApiClient(
        api_url="https://api.linear.app/graphql",
        api_key="secret",
        team_id="team-abc",
        request_fn=fake_request,
    )

    with pytest.raises(LinearApiError, match="Invalid input"):
        client.create_parent_issue("Parent", "desc")


def test_from_settings_requires_team_id_and_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LINEAR_TOKEN_MISSING", raising=False)

    with pytest.raises(ValueError, match="Linear API key missing"):
        LinearApiClient.from_settings(
            api_url="https://api.linear.app/graphql",
            api_key=None,
            api_key_env="LINEAR_TOKEN_MISSING",
            team_id="team-1",
            team_id_env=None,
        )

    with pytest.raises(ValueError, match="Linear team id missing"):
        LinearApiClient.from_settings(
            api_url="https://api.linear.app/graphql",
            api_key="secret",
            api_key_env=None,
            team_id=None,
            team_id_env=None,
        )


def test_from_settings_resolves_team_id_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINEAR_TEAM_TEST", "team-from-env")
    client = LinearApiClient.from_settings(
        api_url="https://api.linear.app/graphql",
        api_key="secret",
        api_key_env=None,
        team_id=None,
        team_id_env="LINEAR_TEAM_TEST",
    )

    assert client.team_id == "team-from-env"


def test_create_child_issue_resolves_project_and_state_ids() -> None:
    captured: dict[str, object] = {}

    def fake_request(url: str, payload: dict[str, object], headers: dict[str, str]) -> dict[str, object]:
        _ = url
        _ = headers
        query = payload["query"]
        if "TeamProjects" in query:
            return {"data": {"team": {"projects": {"nodes": [{"id": "proj-1", "name": "scout"}]}}}}
        if "TeamStates" in query:
            return {"data": {"team": {"states": {"nodes": [{"id": "state-1", "name": "Backlog"}]}}}}
        if "IssueCreate" in query:
            captured["payload"] = payload
            return {
                "data": {
                    "issueCreate": {
                        "success": True,
                        "issue": {"id": "issue-3", "title": "Child", "description": "desc"},
                    }
                }
            }
        raise AssertionError(f"Unexpected query: {query}")

    client = LinearApiClient(
        api_url="https://api.linear.app/graphql",
        api_key="secret",
        team_id="team-abc",
        request_fn=fake_request,
    )
    child = client.create_child_issue(
        parent_issue_id="parent-2",
        title="Child",
        description="desc",
        project_name="scout",
        state_name="Backlog",
    )

    assert child.id == "issue-3"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    issue_input = payload["variables"]["input"]
    assert issue_input["projectId"] == "proj-1"
    assert issue_input["stateId"] == "state-1"


def test_move_issue_to_status_uses_issue_update() -> None:
    captured: dict[str, object] = {}

    def fake_request(url: str, payload: dict[str, object], headers: dict[str, str]) -> dict[str, object]:
        _ = url
        _ = headers
        query = payload["query"]
        if "TeamStates" in query:
            return {"data": {"team": {"states": {"nodes": [{"id": "state-2", "name": "Coding"}]}}}}
        if "IssueUpdate" in query:
            captured["payload"] = payload
            return {"data": {"issueUpdate": {"success": True, "issue": {"id": "issue-10"}}}}
        raise AssertionError(f"Unexpected query: {query}")

    client = LinearApiClient(
        api_url="https://api.linear.app/graphql",
        api_key="secret",
        team_id="team-abc",
        request_fn=fake_request,
    )
    client.move_issue_to_status("issue-10", "Coding")

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["variables"]["id"] == "issue-10"
    assert payload["variables"]["input"]["stateId"] == "state-2"
