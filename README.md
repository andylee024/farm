# Farm

Farm is the orchestration entrypoint for coding work across all repositories you manage in Linear.

It provides one consistent control plane for:

- task intake and decomposition (parent/child),
- agent execution orchestration,
- review/verification workflow,
- parent-level integration and handoff.

## Core Model

1. Use Linear as the portfolio board.
2. Use Farm CLI as the lifecycle engine.
3. Keep planning/business logic in skills/docs, not runtime orchestration code.
4. Use one consistent status policy and review pipeline across repos.

Any repository can be orchestrated as long as it exists in `config.yaml` under `repos`.

## CLI Surface

- `farm intake`: create a parent or child issue.
- `farm decide`: approve/cancel child execution.
- `farm run`: launch one queued task.
- `farm status`: board/runtime summary.
- `farm doctor`: environment and config health checks.
- `farm watch`: live worker and board snapshot.
- `farm pulse`: strong-default active monitor.

## Canonical Documentation

- Style guide: [docs/operations/linear_style_guide.md](docs/operations/linear_style_guide.md)
- Quickstart: [docs/operations/quickstart.md](docs/operations/quickstart.md)
- Development workflow: [docs/operations/development_workflow.md](docs/operations/development_workflow.md)
- Review pipeline: [docs/operations/review_pipeline.md](docs/operations/review_pipeline.md)
- Worker status contract: [docs/operations/worker_status_contract.md](docs/operations/worker_status_contract.md)
- Workflow ownership architecture: [docs/architecture/workflow_ownership.md](docs/architecture/workflow_ownership.md)
- Planning skill: [skills/feature-task-decomposition/SKILL.md](skills/feature-task-decomposition/SKILL.md)
- Integration review skill: [skills/farm-integration-review/SKILL.md](skills/farm-integration-review/SKILL.md)
