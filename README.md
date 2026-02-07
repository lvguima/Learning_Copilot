<<<<<<< HEAD
# Learning_Copilot
=======
# Local Review Copilot (v0.1)

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
uvicorn local_review_copilot.app:app --reload --port 8008
```

## Frontend quick start

```bash
cd frontend
npm install
npm run dev
```

## Desktop quick start

```bash
cd backend
uvicorn local_review_copilot.app:app --reload --port 8008

# new terminal
cd src-tauri
cargo tauri dev
```

## Config

Create `backend/config.yaml` (optional). Defaults are built-in.
Sensitive keys are read from environment variables via `llm.api_key_env`.

## Current v0.1 scope

- Scan a workspace recursively with ignore rules
- Parse `md/txt/pdf(text-layer)/image metadata`
- Run `Chat / Review / Quiz`
- Save session and reports to local `output` directory
- Modern lightweight desktop UI (`Scan`, `Review`, `Quiz/Chat`)
>>>>>>> 3ea5f4d (Initial commit: environment setup and project structure)
