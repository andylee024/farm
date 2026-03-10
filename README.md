# Farm

Farm is a minimal single-task orchestrator for Linear coding issues.

## Why Farm Exists

Farm is built for one practical workflow:

1. Capture a feature as tasks in Linear quickly.
2. Execute child coding tasks in a consistent way.
3. Review one integration PR at the end for the full feature.

It keeps planning and integration policy in skills, while the runtime stays focused on execution.

Farm is the coding-task lifecycle entrypoint into Linear for this workflow.

## What Problem It Solves

Without Farm, feature delivery tends to sprawl across ad-hoc tickets, inconsistent agent execution, and many small PR reviews.

Farm solves this by:

1. Enforcing a simple child-task lifecycle in Linear (`Backlog -> Approved -> Coding -> Done/Canceled`).
2. Running child tasks through one deterministic runtime path.
3. Creating one clear human decision point at the integration PR.

## Intended Workflow

1. Planner skill creates one parent issue and atomic child issues in Linear.
2. Farm runtime runs approved children (`run/update/finish/status`), either manually or via the daemon.
3. Integrator skill consolidates completed children into one final PR for review.

### Daemon Mode

`farm daemon` is a polling loop that watches Linear for `Approved` issues and auto-launches them. This enables an event-driven split where the planner (e.g. nanoclaw) writes tasks to Linear, and the daemon on the host picks them up and executes them.

Farm treats execution as a pluggable task runtime. Today the default runtime is `TmuxTaskRuntime` (`git worktree + tmux`). The long-term target is to add `DaytonaTaskRuntime` without changing the Linear-driven control plane.

```bash
farm daemon --config config.yaml --interval 30 --max-concurrent 1 --agent codex
```

## Architecture (ASCII)

```text
                    (Skill) Planner
      feature intent / PRD -> parent + child issues
                                 |
                                 v
 +----------------------------------------------------+
 |                      Linear                        |
 |  Backlog -> Approved -> Coding -> Done/Canceled   |
 +--------------------------+-------------------------+
                            ^
                            | read/write issue state
                            |
 +--------------------------+-------------------------+
 |                 Farm Runtime Kernel                |
 |  run / update / finish / status / pulse / watch   |
 |                                                     |
 |  run: TaskService -> TaskRuntime -> agent launch   |
 |  update: append TaskUpdate                          |
 |  finish: write TaskResult + move status            |
 |                                                     |
 |  daemon: poll Linear -> auto-run approved issues   |
 +--------------------------+-------------------------+
                            |
                            v
     <worktree_root>/<repo>/<issue_id>/.farm/
     - task_updates.jsonl
     - task_result.json

                    (Skill) Integrator
     completed children -> integration branch/PR -> human review
```

## User Flow (ASCII)

```text
Manual mode:
  1) Planner skill creates parent + child tasks in Linear
  2) Human sets one child to Approved
  3) farm run --repo <repo> --issue <child-id> --agent <codex|claude>
     -> provision task runtime, launch agent, move Linear to Coding
  4) farm update ... --phase running --summary "..."
  5) farm finish ... --outcome completed|canceled|blocked|failed (optional manual override)
  6) farm status / pulse / watch for observability
  7) Integrator skill consolidates completed children into one final PR

Daemon mode:
  1) Planner skill creates parent + child tasks in Linear
  2) Human sets children to Approved
  3) farm daemon --repo <repo> --agent <codex|claude> --max-concurrent 2
     -> polls Linear every N seconds
     -> auto-launches Approved child issues (up to max-concurrent)
     -> skips already-started issues
  4) farm watch for observability
  5) Integrator skill consolidates completed children into one final PR
```

## What Farm Is Not

1. Not a planning engine in runtime code.
2. Not a replacement for human prioritization or final merge approval.

## Core Design

Farm runs one issue at a time and writes exactly two artifacts per task:

1. `task_updates.jsonl` for periodic progress updates
2. `task_result.json` for final outcome

`farm run` delegates execution to the configured task runtime. The default runtime creates a git worktree, starts a tmux session, and launches Codex or Claude there.

No queue scheduler, local lifecycle state machine, or registry database in the core flow.

## Task Runtime Architecture

Farm separates orchestration from execution:

1. `TaskService` owns lifecycle policy: validate the Linear issue, move statuses, write task artifacts, and assemble observability snapshots.
2. `TaskRuntime` owns execution substrate details: provision a workspace, launch the agent, report liveness, and tail recent output.

Current runtime backends:

- `TmuxTaskRuntime`: local `git worktree + tmux`
- `DaytonaTaskRuntime`: placeholder for a future remote workspace backend

This keeps the Linear control plane stable while allowing the execution substrate to change underneath it.

## CLI Surface

- `farm run` - start one approved issue
- `farm update` - append a task update
- `farm finish` - finalize with outcome
- `farm status` - read Linear + local artifacts summary
- `farm pulse` - lightweight observability snapshot for all started tasks in a repo
- `farm watch` - terminal UI for live status + recent runtime output per task
- `farm daemon` - poll Linear and auto-launch approved issues

The daemon only launches approved child issues. If `--agent` is omitted, it uses `daemon.default_agent` from config.

## Documentation

1. Runtime operations and artifact contract: [docs/operations/operations.md](docs/operations/operations.md)
2. Architecture and scope plan: [features/v0/plan.md](features/v0/plan.md)

## Demo Scripts

Use these from repo root for a live Linear smoke test:

1. Check strict statuses exist in team workflow: `PYTHONPATH=src python scripts/demo/check_linear_statuses.py --config config.yaml`
2. Seed parent + child sample issues in Linear: `PYTHONPATH=src python scripts/demo/seed_linear_tasks.py --config config.yaml --repo farm --children 3 --prefix "Farm Flow Test" --approve-first`
3. Run one child through Farm lifecycle: `PYTHONPATH=src python scripts/demo/run_linear_flow.py --config config.yaml --repo farm --issue <child-issue-id> --outcome completed`
