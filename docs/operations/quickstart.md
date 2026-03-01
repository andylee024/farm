# Farm Quickstart

Status: Active  
Last updated: 2026-03-01

## Purpose

Fast copy/paste onboarding to run coding task orchestration through Farm for any repo.

## Prerequisites

1. Repo is configured in `/Users/andylee/Projects/farm/config.yaml` under `repos.<repo-key>`.
2. Linear API credentials are available via Farm config + `.env`.
3. Farm CLI is installed and available as `farm`.

## Set Once Per Session

```bash
export FARM_CONFIG="/Users/andylee/Projects/farm/config.yaml"
export FARM_REGISTRY="/Users/andylee/Projects/farm/data/registry.json"
export REPO_KEY="<repo-key>"
```

## Validate Environment (Recommended)

```bash
farm doctor \
  --config "$FARM_CONFIG" \
  --registry "$FARM_REGISTRY"
```

## 1) Create Parent Issue

```bash
farm intake \
  --config "$FARM_CONFIG" \
  --registry "$FARM_REGISTRY" \
  --repo "$REPO_KEY" \
  --title "<parent outcome>" \
  --description "<goal + constraints>" \
  --status backlog
```

Capture the returned parent issue id.

## 2) Create Child Issues

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

Repeat once per child.

Note: Farm automatically appends an `Agent Startup Instructions` block to each child issue so the agent reads the repository context before coding.

## 3) Approve Child Task

```bash
farm decide \
  --config "$FARM_CONFIG" \
  --registry "$FARM_REGISTRY" \
  --issue "<child-issue-id>" \
  --approve \
  --repo "$REPO_KEY"
```

## 4) Launch Execution

```bash
farm run \
  --config "$FARM_CONFIG" \
  --registry "$FARM_REGISTRY" \
  --repo "$REPO_KEY"
```

Run repeatedly to launch queued tasks.

## 5) Monitor Progress

```bash
farm pulse \
  --config "$FARM_CONFIG" \
  --registry "$FARM_REGISTRY"
```

Optional detailed view:

```bash
farm watch \
  --config "$FARM_CONFIG" \
  --registry "$FARM_REGISTRY" \
  --only-active
```

Optional structured heartbeat updates from agents:

```bash
farm heartbeat \
  --config "$FARM_CONFIG" \
  --registry "$FARM_REGISTRY" \
  --task "<child-issue-id>" \
  --phase running \
  --summary "Current work and progress"
```

## 6) Integration Review and Parent Handoff

When child tasks are complete, follow:

- [review_pipeline.md](./review_pipeline.md)
- `/Users/andylee/Projects/farm/skills/farm-integration-review/references/review_playbook.md`

Move parent to `In Review` only after review/verify pipeline pass.

## Common Commands

```bash
farm status --config "$FARM_CONFIG" --registry "$FARM_REGISTRY"
farm pulse --config "$FARM_CONFIG" --registry "$FARM_REGISTRY" --once
farm decide --config "$FARM_CONFIG" --registry "$FARM_REGISTRY" --issue "<id>" --cancel
```

## Policy

Farm is the coding-task lifecycle entrypoint.

- Use Farm CLI for coding task orchestration.
- Keep planning/review policy aligned with:
  - [linear_style_guide.md](./linear_style_guide.md)
  - [development_workflow.md](./development_workflow.md)
