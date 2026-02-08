# Handoff Checklist

## Start Commands

### Backend (manual fallback)

```powershell
cd D:\pyproject\LearningCopilot\backend
.\.venv\Scripts\Activate.ps1
uvicorn local_review_copilot.server:app --reload --port 8008
```

### Desktop app

```powershell
cd D:\pyproject\LearningCopilot\src-tauri
cargo tauri dev
```

## Quick Smoke Test

1. Open desktop app.
2. Click **选择目录** and set workspace path.
3. Run **Scan** and confirm file list appears.
4. Select a subset of files.
5. Run **Review** and check report returns.
6. Run **Quiz** generation + evaluation.
7. Open model settings, update values, click **保存设置**, verify API returns success.

## APIs to Verify

- `GET /health`
- `GET /config`
- `POST /config`
- `POST /scan`
- `POST /chat/session`
- `POST /review/run`
- `POST /quiz/generate`
- `POST /quiz/evaluate`
- `GET /session/{trace_id}`

## Important Paths

- Backend: `backend/local_review_copilot/server.py`
- Frontend: `frontend/src/AppV2.jsx`
- Tauri: `src-tauri/src/main.rs`
- Config file: `backend/config.yaml`
- Outputs: `backend/outputs/`

