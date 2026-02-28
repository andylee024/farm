from __future__ import annotations

import os
from pathlib import Path

from farm.config import load_dotenv_file


def test_load_dotenv_file_loads_values(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "# comment",
                "LINEAR_API_KEY=abc123",
                "LINEAR_TEAM_ID=team-1",
                "EXPORTED=foo # trailing comment",
                "QUOTED='with spaces'",
                'DOUBLE="also spaced"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    for key in ("LINEAR_API_KEY", "LINEAR_TEAM_ID", "EXPORTED", "QUOTED", "DOUBLE"):
        os.environ.pop(key, None)

    loaded = load_dotenv_file(dotenv_path)

    assert loaded is True
    assert os.environ["LINEAR_API_KEY"] == "abc123"
    assert os.environ["LINEAR_TEAM_ID"] == "team-1"
    assert os.environ["EXPORTED"] == "foo"
    assert os.environ["QUOTED"] == "with spaces"
    assert os.environ["DOUBLE"] == "also spaced"


def test_load_dotenv_file_does_not_override_by_default(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("LINEAR_API_KEY=from-dotenv\n", encoding="utf-8")
    os.environ["LINEAR_API_KEY"] = "already-set"

    _ = load_dotenv_file(dotenv_path, override=False)

    assert os.environ["LINEAR_API_KEY"] == "already-set"


def test_load_dotenv_file_can_override(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("LINEAR_API_KEY=from-dotenv\n", encoding="utf-8")
    os.environ["LINEAR_API_KEY"] = "already-set"

    _ = load_dotenv_file(dotenv_path, override=True)

    assert os.environ["LINEAR_API_KEY"] == "from-dotenv"

