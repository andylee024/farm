# Farm Operations (Canonical)

Status: Active  
Last updated: 2026-03-02

## Purpose

This is the single source of truth for Farm runtime operations.

Farm exists to make feature delivery simple:

1. Write and track work as Linear tasks.
2. Execute child coding tasks with a predictable runtime.
3. Finish with one integration PR review for the feature.

Farm runs one approved Linear child issue at a time and writes exactly two local artifacts:

1. `task_updates.jsonl`
2. `task_result.json`

This is designed to produce one clear human decision point: the final integration PR review.

## Scope And Ownership

1. Human owns priority, approval, and final PR merge decisions.
2. Planner skill owns decomposition from feature intent to parent/child tasks.
3. Farm runtime owns deterministic child execution (`run`, `update`, `finish`, `status`).
4. Integrator skill owns final consolidation and parent review handoff.

Operational rule:

1. Farm is the entrypoint for coding-task lifecycle orchestration into Linear.

## Prerequisites

1. Repo key exists in `/Users/andylee/Projects/farm/config.yaml` under `repos.<repo-key>`.
2. Linear credentials are available via config and environment.
3. Team workflow includes required statuses: `Backlog`, `Approved`, `Coding`, `Done`, `Canceled`.

## Environment

```bash
export FARM_CONFIG="/Users/andylee/Projects/farm/config.yaml"
export REPO_KEY="<repo-key>"
```

## Command Surface

```bash
farm run --config "$FARM_CONFIG" --repo "$REPO_KEY" --issue "<child-issue-id>"
farm update --config "$FARM_CONFIG" --repo "$REPO_KEY" --issue "<child-issue-id>" --phase running --summary "Current step"
farm finish --config "$FARM_CONFIG" --repo "$REPO_KEY" --issue "<child-issue-id>" --outcome completed --summary "Complete" --pr-url "<optional-pr-url>"
farm finish --config "$FARM_CONFIG" --repo "$REPO_KEY" --issue "<child-issue-id>" --outcome canceled --summary "Stop reason"
farm status --config "$FARM_CONFIG" --repo "$REPO_KEY" --issue "<child-issue-id>"
farm pulse --config "$FARM_CONFIG" --repo "$REPO_KEY"
farm watch --config "$FARM_CONFIG" --repo "$REPO_KEY" --interval 1.5 --lines 3
```

## Lifecycle

1. Human sets child issue to `Approved` in Linear.
2. `farm run` starts work and moves issue to `Coding`.
3. Agent session exit auto-runs `farm finish`:
   - exit code `0` -> `Done` (`outcome=completed`)
   - non-zero exit -> `Canceled` (`outcome=failed`)
4. Optional `farm update` adds progress checkpoints.
5. `farm finish --outcome completed` can be used as a manual override and moves issue to `Done`.
6. `farm finish --outcome canceled` can be used as a manual override and moves issue to `Canceled`.

## Linear Status Policy

Use exactly these child statuses:

1. `Backlog`
2. `Approved`
3. `Coding`
4. `Done`
5. `Canceled`

## Task Quality Bar

Before moving a child issue to `Approved`, it should be:

1. Atomic: one clear outcome, one main change thread.
2. Testable: acceptance checks are explicit and deterministic.
3. Reviewable: expected evidence is clear (tests, notes, optional PR link).

## Non-Goals

1. Runtime-owned task decomposition/planning.
2. Runtime-owned integration/review policy logic.
3. Multi-task queue scheduling in runtime.

## Artifact Contract

Paths for issue `<ISSUE_ID>` in repo `<repo-key>`:

1. `<worktree_root>/<repo-key>/<ISSUE_ID>/.farm/task_updates.jsonl`
2. `<worktree_root>/<repo-key>/<ISSUE_ID>/.farm/task_result.json`

`worktree_root` comes from `config.yaml`.

### `task_updates.jsonl`

Append-only JSON lines:

```json
{
  "schema_version": 1,
  "ts": "2026-03-02T19:22:11Z",
  "issue_id": "FARM-123",
  "repo": "farm",
  "phase": "running",
  "summary": "Implementing command parser"
}
```

Recommended phases:

1. `starting`
2. `running`
3. `blocked`
4. `completed`
5. `canceled`

### `task_result.json`

Final task outcome:

```json
{
  "schema_version": 1,
  "issue_id": "FARM-123",
  "repo": "farm",
  "started_at": "2026-03-02T19:10:00Z",
  "ended_at": "2026-03-02T19:42:31Z",
  "outcome": "completed",
  "summary": "Implementation complete",
  "pr_url": "https://github.com/org/repo/pull/123"
}
```

## Definition Of Done

A child issue is done when:

1. Linear state is `Done`
2. `task_result.json` exists with `outcome="completed"`
3. Summary/evidence is sufficient for human review

## Lightweight Observability

Use two commands:

1. `farm status` for one task
2. `farm pulse` for all started tasks in one repo
3. `farm watch` for live terminal snapshot + recent output lines

`farm pulse` shows per-task:

1. Issue id
2. Linear state
3. Latest update phase
4. Final outcome (if available)
5. tmux session liveness

`farm watch` continuously refreshes and shows:

1. Human-friendly task label (`identifier` when available)
2. Current state/phase/outcome
3. Age since last update
4. Last N tmux pane lines per live session

## Review Handoff

Reviewer checks:

1. Scope matches issue intent
2. Evidence in `task_result.json.summary` and optional `pr_url`
3. Diff/tests are acceptable

Integration handoff gates:

1. Consolidated integration PR exists for the parent feature.
2. Required verification checks pass.
3. Review summary is published.
4. Parent moves to `In Review` only after gates pass.

## Agent Launch Permissions

`farm run` starts a tmux session and launches the selected agent CLI directly:

1. Codex: `codex exec --model <model> --dangerously-bypass-approvals-and-sandbox "<prompt>"`
2. Claude: `claude --model <model> --print --dangerously-skip-permissions "<prompt>"`

After agent exit, Farm automatically calls `finish`:

1. Success -> `outcome=completed` -> `Done`
2. Failure -> `outcome=failed` -> `Canceled`

Default behavior uses bypass flags. To disable both, set:

```yaml
agent_defaults:
  dangerous_bypass_permissions: false
```

Minimal review summary template:

```md
## Review Summary
- Issue:
- Result outcome:
- Evidence checked:
- Risks:
- Decision: pass | needs_fix | blocked
```
