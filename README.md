# Farm

Farm is a local orchestration control plane for autonomous coding workflows.

This repository currently contains the V0 rewrite skeleton:
- typed task/state contracts
- JSON-backed task registry
- state transition guards
- minimal CLI operations (`intake`, `decide`, `run`, `status`)
- unit tests for state machine and JSON storage

Planning and task decomposition guidance lives in:
- `skills/farm-linear-planning/SKILL.md`
