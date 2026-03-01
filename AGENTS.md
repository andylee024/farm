# AGENTS.md

## Purpose

This is the canonical operating contract for any agent doing coding work in repositories managed by Farm.

If a project-level `AGENTS.md` exists, this file is still the source of truth for orchestration policy.

## Required Reading Order

Before starting coding work, read in this order:

1. `/Users/andylee/Projects/farm/AGENTS.md` (this file)
2. `/Users/andylee/Projects/farm/docs/operations/quickstart.md`
3. `/Users/andylee/Projects/farm/docs/operations/linear_style_guide.md`
4. `/Users/andylee/Projects/farm/docs/operations/review_pipeline.md`
5. `/Users/andylee/Projects/farm/docs/operations/worker_status_contract.md`

## Non-Negotiable Rules

1. Farm is the entrypoint for coding task orchestration into Linear.
2. Use Farm CLI for coding lifecycle operations.
3. Do not use Linear MCP tools to create/move coding tasks.
4. Keep planning/business logic in skills/docs, not runtime orchestration code.
5. Parent issues move to `In Review` only after review/verification pipeline pass.

## Scope

This applies to all repo keys configured in:

- `/Users/andylee/Projects/farm/config.yaml` under `repos.<repo-key>`

## Standard Environment

Use these defaults unless the user specifies otherwise:

```bash
export FARM_CONFIG="/Users/andylee/Projects/farm/config.yaml"
export FARM_REGISTRY="/Users/andylee/Projects/farm/data/registry.json"
export REPO_KEY="<repo-key>"
```

## Standard Coding Lifecycle

1. Create parent:

```bash
farm intake \
  --config "$FARM_CONFIG" \
  --registry "$FARM_REGISTRY" \
  --repo "$REPO_KEY" \
  --title "<parent outcome>" \
  --description "<goal + constraints>" \
  --status backlog
```

2. Create child:

```bash
farm intake \
  --config "$FARM_CONFIG" \
  --registry "$FARM_REGISTRY" \
  --repo "$REPO_KEY" \
  --parent-id "<parent-issue-id>" \
  --title "<child task title>" \
  --description "<scope + deterministic checks + evidence>" \
  --status backlog
```

3. Approve child:

```bash
farm decide \
  --config "$FARM_CONFIG" \
  --registry "$FARM_REGISTRY" \
  --issue "<child-issue-id>" \
  --approve \
  --repo "$REPO_KEY"
```

4. Execute:

```bash
farm run \
  --config "$FARM_CONFIG" \
  --registry "$FARM_REGISTRY" \
  --repo "$REPO_KEY"
```

5. Monitor:

```bash
farm pulse \
  --config "$FARM_CONFIG" \
  --registry "$FARM_REGISTRY"
```

Optional heartbeat update from worker/agent:

```bash
farm heartbeat \
  --config "$FARM_CONFIG" \
  --registry "$FARM_REGISTRY" \
  --task "<child-issue-id>" \
  --phase running \
  --summary "Current step in progress"
```

## Review + Parent Handoff

Use the integration review process to consolidate child work, run review/verification, and hand off:

- `/Users/andylee/Projects/farm/skills/farm-integration-review/SKILL.md`
- `/Users/andylee/Projects/farm/skills/farm-integration-review/references/review_playbook.md`

Required review summary format (PM + CTO) is defined in:

- `/Users/andylee/Projects/farm/docs/operations/review_pipeline.md`

## Definition Of Done

Child issue is `Completed` only when required evidence and review/verification criteria are satisfied (PR opened alone is not done).

Parent issue moves to `In Review` only when:

1. Integration PR is open and linked.
2. Verify gates pass.
3. Review output is published in required summary format.

## How To Apply In Other Repos

Project-level `AGENTS.md` files should include:

1. A Farm-first orchestration note.
2. A link to this file: `/Users/andylee/Projects/farm/AGENTS.md`
3. Any project-specific constraints (schema, test commands, deployment policies).

Reference snippet:

```md
## Farm-Orchestrated Coding (Required)

For any coding task in this repository:
1. Read `/Users/andylee/Projects/farm/AGENTS.md` before starting.
2. Use Farm CLI as the control plane for Linear coding task lifecycle.
3. Do not create or move coding tasks via Linear MCP tools or ad-hoc scripts.
4. Keep planning/business logic in Farm skills/docs, not in repository orchestration scripts.
```
