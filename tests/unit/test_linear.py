from __future__ import annotations

import pytest

from farm.adapters.linear import LinearClient
from farm.support.errors import LinearApiError


def test_from_settings_resolves_api_key_and_team_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINEAR_TOKEN_TEST", "token-from-env")
    monkeypatch.setenv("LINEAR_TEAM_TEST", "team-from-env")

    client = LinearClient.from_settings(
        api_url="https://api.linear.app/graphql",
        api_key=None,
        api_key_env="LINEAR_TOKEN_TEST",
        team_id=None,
        team_id_env="LINEAR_TEAM_TEST",
    )

    assert client.api_key == "token-from-env"
    assert client.team_id == "team-from-env"


def test_get_issue_parses_payload() -> None:
    def fake_request(url, payload, headers):
        _ = url
        _ = headers
        assert "IssueById" in payload["query"]
        return {
            "data": {
                "issue": {
                    "id": "issue-1",
                    "identifier": "FARM-1",
                    "title": "Task",
                    "description": "desc",
                    "parent": {"id": "parent-1"},
                    "state": {"id": "state-1", "name": "Approved"},
                    "project": {"id": "proj-1", "name": "farm"},
                }
            }
        }

    client = LinearClient(
        api_url="https://api.linear.app/graphql",
        api_key="secret",
        team_id="team-abc",
        request_fn=fake_request,
    )

    issue = client.get_issue("issue-1")
    assert issue.id == "issue-1"
    assert issue.identifier == "FARM-1"
    assert issue.state_name == "Approved"
    assert issue.project_name == "farm"


def test_move_issue_to_status_uses_exact_status_and_updates() -> None:
    captured: dict[str, object] = {}

    def fake_request(url, payload, headers):
        _ = url
        _ = headers
        query = payload["query"]
        if "TeamStates" in query:
            return {
                "data": {
                    "team": {
                        "states": {
                            "nodes": [
                                {"id": "state-approved", "name": "Approved"},
                                {"id": "state-done", "name": "Done"},
                            ]
                        }
                    }
                }
            }
        if "IssueUpdate" in query:
            captured["payload"] = payload
            return {"data": {"issueUpdate": {"success": True, "issue": {"id": "issue-10"}}}}
        raise AssertionError(f"Unexpected query: {query}")

    client = LinearClient(
        api_url="https://api.linear.app/graphql",
        api_key="secret",
        team_id="team-abc",
        request_fn=fake_request,
    )

    client.move_issue_to_status("issue-10", "Approved")

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["variables"]["id"] == "issue-10"
    assert payload["variables"]["input"]["stateId"] == "state-approved"


def test_move_issue_to_status_rejects_alias_when_exact_state_missing() -> None:
    def fake_request(url, payload, headers):
        _ = url
        _ = headers
        query = payload["query"]
        if "TeamStates" in query:
            return {
                "data": {
                    "team": {
                        "states": {
                            "nodes": [
                                {"id": "state-todo", "name": "Todo"},
                                {"id": "state-done", "name": "Done"},
                            ]
                        }
                    }
                }
            }
        raise AssertionError(f"Unexpected query: {query}")

    client = LinearClient(
        api_url="https://api.linear.app/graphql",
        api_key="secret",
        team_id="team-abc",
        request_fn=fake_request,
    )

    with pytest.raises(LinearApiError, match="workflow state not found"):
        client.move_issue_to_status("issue-10", "Approved")


def test_graphql_errors_raise_linear_api_error() -> None:
    def fake_request(url, payload, headers):
        _ = url
        _ = payload
        _ = headers
        return {"errors": [{"message": "Invalid input"}]}

    client = LinearClient(
        api_url="https://api.linear.app/graphql",
        api_key="secret",
        team_id="team-abc",
        request_fn=fake_request,
    )

    with pytest.raises(LinearApiError, match="Invalid input"):
        client.get_issue("issue-1")
