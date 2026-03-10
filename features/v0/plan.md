# Farm V0 Plan: Minimal Execution Kernel

Status: Draft  
Last updated: 2026-03-02

## Goal

Farm should only enable four workflows:

1. Planning (skill-owned)
2. Single task execution (runtime-owned)
3. Daemon-driven auto-execution (runtime-owned)
4. Integration/hygiene/review (skill-owned)

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

Farm runtime supports seven operations:

1. `run(issue_id, repo, agent)`
2. `update(issue_id, repo, phase, summary)`
3. `finish(issue_id, repo, outcome, summary, pr_url=None)`
4. `status(issue_id, repo)`
5. `pulse(repo)`
6. `watch(repo)`
7. `daemon(repos, poll_interval, max_concurrent, agent)` — polling loop

No local state machine or registry DB. The daemon uses Linear as the queue and worktree existence as the dedup mechanism.

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
farm pulse --repo <repo-key>
farm watch --repo <repo-key>
farm daemon [--repo <repo-key>] --interval 30 --max-concurrent 1 --agent codex
```

## Linear Calls Runtime Needs

Execution runtime needs:

1. `get_issue`
2. `move_issue_to_status`
3. `list_issues_by_state` (daemon only — queries Approved issues by project)

Planning/integration skill workflows may use richer Linear operations, but those remain outside runtime orchestration code.

## Code Organization

```text
src/farm/
  cli/
    commands.py          # typer entrypoint + command handlers
  runtime/
    models.py            # TaskUpdate, TaskResult, Agent
    runner.py            # run/update/finish/status orchestration
    daemon.py            # polling loop for auto-launching approved issues
    paths.py             # deterministic worktree/branch/session naming
  adapters/
    linear.py            # get_issue + move_issue_to_status + list_issues_by_state
    git.py               # shell boundary
    tmux.py              # shell boundary
  support/
    config.py            # typed config loading (includes DaemonConfig)
    errors.py            # minimal shared errors
```

## Non-Goals (V0)

1. Automatic task decomposition in runtime code
2. Automatic integration orchestration in runtime code
3. Runtime-owned planning logic
4. Runtime-owned review policy logic

## Definition of Simplicity

Farm V0 is considered simple when:

1. A new contributor can understand the runtime flow in under 10 minutes.
2. Runtime code is focused only on execution and artifact emission.
3. Skills own intention, planning, and integration guidance.
4. Linear remains the state authority for issue lifecycle.
