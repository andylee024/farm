# Farm V0 Plan: Minimal Execution Kernel

Status: Draft  
Last updated: 2026-03-02

## Goal

Farm should only enable three workflows:

1. Planning (skill-owned)
2. Single task execution (runtime-owned)
3. Integration/hygiene/review (skill-owned)

Runtime code stays minimal and deterministic.

## Ownership Boundaries

### Planner (Skill, not runtime code)

The planner consumes a feature PRD and creates:

1. One parent Linear issue
2. Multiple child Linear issues

It also explains intent and provides guidance for runtime commands.

### Runtime (Farm code)

The runtime executes one approved child task and emits:

1. Periodic task updates
2. One final task result

### Integrator (Skill, not runtime code)

When children are complete, integrator skill:

1. Reviews and cleans implementation
2. Applies software hygiene improvements
3. Prepares a consolidated PR for review

## Architecture (ASCII)

```text
                 (Skill) Planner
      PRD -> parent/child issues in Linear
                        |
                        v
+------------------------------------------------+
|                    Linear                      |
| Backlog -> Approved -> Coding -> Done/...      |
+---------------------------+--------------------+
                            ^
                            | read/write issue state
                            |
+---------------------------+--------------------+
|             Farm Runtime Kernel                |
| run / update / finish / status                 |
| - create worktree                              |
| - start tmux session                           |
| - append TaskUpdate                            |
| - write TaskResult                             |
+---------------------------+--------------------+
                            |
                            v
   <worktree_root>/<repo>/<issue_id>/.farm/
   - task_updates.jsonl
   - task_result.json

               (Skill) Integrator
       all children Done -> review/cleanup/PR
```

## Runtime Contracts

Farm runtime supports only six operations:

1. `run(issue_id, repo, agent)`
2. `update(issue_id, repo, phase, summary)`
3. `finish(issue_id, repo, outcome, summary, pr_url=None)`
4. `status(issue_id, repo)`
5. `pulse(repo)`
6. `watch(repo)`

No scheduler, no queue manager, no local state machine, no registry DB.

## Runtime Dataclasses

```python
@dataclass
class TaskUpdate:
    issue_id: str
    repo: str
    phase: str      # starting|running|blocked|completed|canceled
    summary: str
    ts: str

@dataclass
class TaskResult:
    issue_id: str
    repo: str
    outcome: str    # completed|canceled|blocked|failed
    summary: str
    started_at: str
    ended_at: str
    pr_url: str | None
```

## Runtime Artifact Contract

For each task:

1. `task_updates.jsonl` for periodic updates
2. `task_result.json` for final result

Path:

`<worktree_root>/<repo>/<issue_id>/.farm/`

## CLI Surface

```bash
farm run --issue <id> --repo <repo-key> [--agent codex|claude]
farm update --issue <id> --repo <repo-key> --phase running --summary "..."
farm finish --issue <id> --repo <repo-key> --outcome completed --summary "..." [--pr-url <url>]
farm status --issue <id> --repo <repo-key>
```

## Linear Calls Runtime Needs

Execution runtime only needs:

1. `get_issue`
2. `move_issue_to_status`

Planning/integration skill workflows may use richer Linear operations, but those remain outside runtime orchestration code.

## Code Organization

```text
src/farm/
  cli/
    app.py               # typer entrypoint
    commands.py          # command handlers
  runtime/
    models.py            # TaskUpdate, TaskResult
    runner.py            # run/update/finish/status orchestration
    paths.py             # deterministic worktree/branch/session naming
  adapters/
    linear.py            # get_issue + move_issue_to_status
    git.py               # shell boundary
    tmux.py              # shell boundary
  support/
    config.py            # typed config loading
    errors.py            # minimal shared errors
```

## Non-Goals (V0)

1. Automatic task decomposition in runtime code
2. Automatic integration orchestration in runtime code
3. Multi-task queue scheduling
4. Runtime-owned planning logic
5. Runtime-owned review policy logic

## Definition of Simplicity

Farm V0 is considered simple when:

1. A new contributor can understand the runtime flow in under 10 minutes.
2. Runtime code is focused only on execution and artifact emission.
3. Skills own intention, planning, and integration guidance.
4. Linear remains the state authority for issue lifecycle.
