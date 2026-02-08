# Local Review Copilot (v0.1.1)

Lightweight desktop-first local review assistant using:
- `Tauri` desktop shell
- `Web UI` frontend
- `Python sidecar` for scan/parse/context/LLM

## Structure

- `backend/` Python sidecar (`FastAPI`)
- `frontend/` web app (`React + Vite`)
- `src-tauri/` desktop shell (`Tauri`)

## Backend quick start

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate
pip install -e .[dev]
uvicorn local_review_copilot.server:app --reload --port 8008
```

## Frontend quick start

```bash
cd frontend
npm install
npm run dev
```

## Desktop quick start

```bash
cd src-tauri
cargo tauri dev
```

Notes:
- Desktop now auto-starts backend sidecar in dev mode.
- If auto-start fails, run backend manually with:
  - `cd backend`
  - `uvicorn local_review_copilot.server:app --reload --port 8008`

## Config

- Runtime config API:
  - `GET /config`
  - `POST /config`
- Config persists to `backend/config.yaml`.
- Sensitive keys are still read from env variable names (e.g. `OPENAI_API_KEY`).

## Current v0.1 scope

- Scan a workspace recursively with ignore rules
- Parse `md/txt/pdf(text-layer)/image metadata`
- Run `Chat / Review / Quiz`
- Save session and reports to local `outputs` directory
- Modern lightweight desktop UI (`Scan`, `Review`, `Quiz/Chat`)
- Directory picker + selectable file injection + model config panel

## Iteration docs

- `docs/2026-02-08-dev-log.md`
- `docs/2026-02-09-plan.md`
- `docs/handoff-checklist.md`
- `docs/next-iteration-v0.1.1.md`
