from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import OutputConfig
from .models import SessionRecord


class Storage:
    def __init__(self, output: OutputConfig) -> None:
        self.base_dir = Path(output.storage_dir)
        self.sessions_dir = self.base_dir / "sessions"
        self.exports_dir = self.base_dir / "exports"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.export_markdown = output.export_markdown
        self.export_json = output.export_json

    def save_session(self, session: SessionRecord) -> Path:
        target = self.sessions_dir / f"{session.trace_id}.json"
        target.write_text(
            json.dumps(session.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return target

    def load_session(self, trace_id: str) -> dict[str, Any]:
        target = self.sessions_dir / f"{trace_id}.json"
        if not target.exists():
            raise FileNotFoundError(f"Session not found: {trace_id}")
        return json.loads(target.read_text(encoding="utf-8"))

    def save_export(self, suffix: str, markdown: str, payload: dict[str, Any]) -> dict[str, str]:
        stamp = datetime.utcnow().strftime("%Y-%m-%d")
        saved: dict[str, str] = {}
        if self.export_markdown:
            md_path = self.exports_dir / f"{stamp}_{suffix}.md"
            md_path.write_text(markdown, encoding="utf-8")
            saved["markdown"] = str(md_path)
        if self.export_json:
            json_path = self.exports_dir / f"{stamp}_{suffix}.json"
            json_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            saved["json"] = str(json_path)
        return saved

