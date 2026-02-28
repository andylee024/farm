"""CI adapter placeholders for test status polling."""

from __future__ import annotations

from enum import Enum


class CiStatus(str, Enum):
    UNKNOWN = "unknown"
    PASS = "pass"
    FAIL = "fail"


def normalize_ci_status(raw: str) -> CiStatus:
    value = raw.strip().lower()
    if value in {"pass", "passed", "success"}:
        return CiStatus.PASS
    if value in {"fail", "failed", "error"}:
        return CiStatus.FAIL
    return CiStatus.UNKNOWN

