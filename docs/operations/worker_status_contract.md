# Farm Worker Status Contract

Status: Active  
Last updated: 2026-03-01

## Purpose

Provide a structured heartbeat/status contract so `farm watch` and `farm pulse` can make deterministic decisions without relying on freeform logs.

## Status File

Each worker writes:

- `<worktree>/.farm_worker_status.json`

Schema (v1):

```json
{
  "schema_version": 1,
  "task_id": "LINEAR_TASK_ID",
  "phase": "starting|running|blocked|ready_for_review|failed",
  "summary": "short progress summary",
  "ready_for_review": false,
  "blocked": false,
  "blocked_reason": null,
  "updated_at": "2026-03-01T18:35:42.123456+00:00"
}
```

## CLI Helper

Use `farm heartbeat` to write status updates:

```bash
farm heartbeat \
  --config "$FARM_CONFIG" \
  --registry "$FARM_REGISTRY" \
  --task "<child-issue-id>" \
  --phase running \
  --summary "Implementing API endpoint and unit tests"
```

Mark ready:

```bash
farm heartbeat \
  --config "$FARM_CONFIG" \
  --registry "$FARM_REGISTRY" \
  --task "<child-issue-id>" \
  --phase ready_for_review \
  --ready-for-review \
  --summary "Code complete, tests passing, ready for PR review"
```

Mark blocked:

```bash
farm heartbeat \
  --config "$FARM_CONFIG" \
  --registry "$FARM_REGISTRY" \
  --task "<child-issue-id>" \
  --phase blocked \
  --blocked \
  --blocked-reason "Waiting on schema decision"
```

## Monitor Semantics

`farm watch` and `farm pulse` now use structured status first:

1. `ready_for_review` or `phase=ready_for_review` -> `ready`
2. `blocked` or `phase in {blocked, failed}` -> `stuck`
3. Otherwise use heartbeat freshness + session status to classify `running|stuck|idle`

If status file is missing, Farm falls back to log markers for backward compatibility.

## Auto-Complete Semantics

When `--auto-complete-ready` is enabled:

1. Structured ready signal is checked first.
2. Legacy log marker fallback is checked second.
3. Farm updates local state and moves Linear child issue to `Completed`.

