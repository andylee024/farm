from __future__ import annotations

import pytest

from farm.cli.commands import resolve_agent_or_raise
from farm.runtime.models import Agent


def test_resolve_agent_uses_config_default_when_flag_omitted() -> None:
    assert resolve_agent_or_raise(None, default="claude") == Agent.CLAUDE


def test_resolve_agent_rejects_unknown_agent() -> None:
    with pytest.raises(ValueError, match="Unsupported agent"):
        resolve_agent_or_raise("nope", default="codex")
