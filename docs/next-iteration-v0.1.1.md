# Next Iteration Task List (v0.1.1)

## Daily Breakdown

### Day 1 — Baseline and docs alignment
- Freeze current runnable baseline.
- Align README/startup/structure docs.
- Define iteration acceptance checklist.

### Day 2 — Sidecar auto-start
- Add backend health check on app startup.
- Auto-start backend if unavailable.
- Prefer venv Python executable, fallback safely.
- Stop spawned backend process on app exit.

### Day 3 — Directory picker and file selection
- Add native directory picker.
- Show scan result list with checkbox selection.
- Support select all / clear all.
- Send `selected_paths` for Chat/Review/Quiz.

### Day 4 — Model settings panel
- Add backend config APIs (`GET /config`, `POST /config`).
- Add frontend settings panel (provider/endpoint/model/timeout/context/api env).
- Apply settings immediately and persist to `config.yaml`.

### Day 5 — Reliability and error UX
- Improve API/network/config error readability.
- Add explicit degraded status hints for parsing issues.
- Remove visible text corruption and mixed wording.

### Day 6 — Tests and regression
- Add/extend backend tests for config APIs.
- Re-run scan/context/API core tests in Python 3.11 env.
- Execute one complete manual smoke regression.

### Day 7 — Wrap-up
- Update docs + troubleshooting.
- Produce iteration summary and known issue list.
- Prepare Windows packaging checklist.

## Definition of Done

- Desktop app works without manual backend startup.
- User can pick directory and choose file subset for context.
- Model settings are editable in UI and persisted.
- Chat/Review/Quiz all run stably with selected files.
- Outputs and sessions remain exportable/replayable.

