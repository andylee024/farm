# Farm Integration Review Playbook

## 0) Set Variables

```bash
PARENT_ID="<linear-parent-issue-id>"
REPO="<repo-key>"                  # must exist in farm config
BASE="main"
READY_STATUS="In Review"           # parent review stage
REPO_ROOT="<absolute-repo-path>"   # should match repos.<repo-key>.path
INTEGRATION_BRANCH="farm/${REPO}/parent-${PARENT_ID:0:8}-integration-$(date +%Y%m%d-%H%M)"
```

## 1) List Candidate Child Tasks

```bash
python3 - <<'PY'
from pathlib import Path
from farm.config import load_config, load_dotenv_file
from farm.adapters.storage_json import JsonRegistryStore
from farm.adapters.linear_api import LinearApiClient

PARENT_ID = "<linear-parent-issue-id>"
CFG_PATH = Path("config.yaml")
REGISTRY_PATH = Path("data/registry.json")

load_dotenv_file()
cfg = load_config(CFG_PATH)
client = LinearApiClient.from_settings(
    api_url=cfg.linear.api_url,
    api_key=cfg.linear.api_key,
    api_key_env=cfg.linear.api_key_env,
    team_id=cfg.linear.team_id,
    team_id_env=cfg.linear.team_id_env,
)
store = JsonRegistryStore(REGISTRY_PATH)

for task in store.list_tasks():
    issue = client.get_issue(task.task_id)
    if issue.parent_id != PARENT_ID:
        continue
    ident = issue.identifier or task.task_id
    state = issue.state_name or "unknown"
    print(f"{ident}\t{task.task_id}\t{state}\t{task.branch or '-'}\t{task.worktree_path or '-'}")
PY
```

Select child branches that are done and intended for integration.

## 2) Quick Review Per Child Branch

```bash
git -C "$REPO_ROOT" fetch origin
# Repeat per child branch
BRANCH="farm/<child-task-id>-attempt-0"
git -C "$REPO_ROOT" log --oneline --no-merges "origin/$BASE..$BRANCH"
git -C "$REPO_ROOT" diff --stat "origin/$BASE...$BRANCH"
```

## 3) Build Integration Branch

```bash
git -C "$REPO_ROOT" switch -c "$INTEGRATION_BRANCH" "origin/$BASE"

# Repeat per selected child branch
BRANCH="farm/<child-task-id>-attempt-0"
git -C "$REPO_ROOT" merge --no-ff --no-edit "$BRANCH"
```

If there are conflicts: resolve files, `git add`, then `git commit`.

## 4) Validate + Code Review

```bash
# Full repo checks (use repo default test command if different)
cd "$REPO_ROOT"
pytest -q

# Integrated-diff review
codex review --base "origin/$BASE" \
  "Review for regressions, contract drift, missing tests, and integration risks."
```

If blockers are found, fix directly on the integration branch, commit, push, and rerun this step.

## 5) Push and Open Single PR

```bash
git -C "$REPO_ROOT" push -u origin "$INTEGRATION_BRANCH"
```

If GitHub CLI is unavailable in this environment, open PR manually using compare URL:

```bash
REPO_URL="$(gh repo view --json url -q .url)"
echo "${REPO_URL}/compare/${BASE}...${INTEGRATION_BRANCH}?expand=1"
```

## 6) Link Parent + Move Parent Status

```bash
python3 skills/farm-integration-review/scripts/update_parent_issue.py \
  --config config.yaml \
  --issue "$PARENT_ID" \
  --pr-url "<opened-pr-url>" \
  --note "Integrated child branches into one parent review PR" \
  --status "$READY_STATUS"
```

This appends a review block to parent description and moves the parent issue to `In Review` (or your chosen review stage).

## 7) Publish Human Review Summary (Required)

Post one summary comment on the parent PR and mirror key points on the parent Linear issue using this template:

```md
## 1) Feature Purpose (PM Context)
- Problem this solves:
- Who it’s for:
- Intended outcome:
- Business reason / priority now:

## 2) Scope and Boundaries
- In scope:
- Out of scope:
- Non-goals:

## 3) Technical Implementation Overview (CTO Context)
- Architecture touchpoints:
- End-to-end flow:
- Key design decisions:
- Alternatives considered:
- Operational considerations:
- Failure modes + mitigations:
- Compatibility/migration:

## 4) What Was Implemented
- Concrete behavior changes (before -> after):
- Major files/components touched:
- Linked child tasks/issues:

## 5) Validation and Evidence
- CI/checks status:
- Tests run + outcomes:
- Manual verification:
- UI artifacts/screenshots (if relevant):

## 6) Risks and Follow-ups
- Remaining risks:
- Deferred items:
- Recommended next steps:

## 7) Decision Request
- Recommendation: Ready for Review | Needs Fix
- Human reviewer focus areas (top 3):
```
