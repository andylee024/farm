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
2. Farm runtime runs one approved child at a time (`run/update/finish/status`).
3. Integrator skill consolidates completed children into one final PR for review.

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
 |                  run / update / finish / status    |
 |                                                     |
 |  run: git worktree -> tmux session -> agent launch |
 |  update: append TaskUpdate                          |
 |  finish: write TaskResult + move status            |
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
1) Planner skill creates parent + child tasks in Linear
2) Human sets one child to Approved
3) farm run --repo <repo> --issue <child-id> --agent <codex|claude>
   -> create worktree
   -> start tmux + launch agent
   -> move Linear: Approved -> Coding
   -> write TaskUpdate(starting)
4) farm update ... --phase running --summary "..."
   -> append heartbeat TaskUpdate(s)
5) farm finish ... --outcome completed|canceled|blocked|failed
   -> move Linear: completed -> Done (else -> Canceled)
   -> append terminal TaskUpdate
   -> write task_result.json
6) farm status ... shows Linear state + latest update + result summary
7) Integrator skill consolidates completed children into one final PR
```

## What Farm Is Not

1. Not a planning engine in runtime code.
2. Not a multi-task scheduler or queue manager.
3. Not a replacement for human prioritization or final merge approval.

## Core Design

Farm runs one issue at a time and writes exactly two artifacts per task:

1. `task_updates.jsonl` for periodic progress updates
2. `task_result.json` for final outcome

`farm run` creates a git worktree, starts a tmux session, and launches Codex or Claude in that session.

No queue scheduler, local lifecycle state machine, or registry database in the core flow.

## CLI Surface

- `farm run` - start one approved issue
- `farm update` - append a task update
- `farm finish` - finalize with outcome
- `farm status` - read Linear + local artifacts summary

## Documentation

1. Runtime operations and artifact contract: [docs/operations/operations.md](docs/operations/operations.md)
2. Architecture and scope plan: [features/v0/plan.md](features/v0/plan.md)

## Demo Scripts

Use these from repo root for a live Linear smoke test:

1. Check strict statuses exist in team workflow: `PYTHONPATH=src python scripts/demo/check_linear_statuses.py --config config.yaml`
2. Seed parent + child sample issues in Linear: `PYTHONPATH=src python scripts/demo/seed_linear_tasks.py --config config.yaml --repo farm --children 3 --prefix "Farm Flow Test" --approve-first`
3. Run one child through Farm lifecycle: `PYTHONPATH=src python scripts/demo/run_linear_flow.py --config config.yaml --repo farm --issue <child-issue-id> --outcome completed`
