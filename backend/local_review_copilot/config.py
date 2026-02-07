from __future__ import annotations

from pathlib import Path
from typing import List, Literal, Optional, Union

import yaml
from pydantic import BaseModel, Field


class WorkspaceConfig(BaseModel):
    root_dir: str = "."
    ignore_patterns: List[str] = Field(
        default_factory=lambda: [
            ".git/*",
            "node_modules/*",
            "__pycache__/*",
            "*.tmp",
            "*.log",
        ]
    )
    max_file_size_mb: int = 10
    max_files_per_run: int = 500


class ParsingConfig(BaseModel):
    pdf_mode: Literal["text_only", "hybrid"] = "text_only"
    image_mode: Literal["send_to_vision", "skip"] = "skip"


class LLMConfig(BaseModel):
    provider: Literal["echo", "openai_compat"] = "echo"
    endpoint: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"
    timeout_seconds: int = 30
    max_context_tokens: int = 12000


class OutputConfig(BaseModel):
    storage_dir: str = "outputs"
    export_markdown: bool = True
    export_json: bool = True


class UIConfig(BaseModel):
    mode: Literal["desktop", "web", "cli"] = "desktop"


class AppConfig(BaseModel):
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    parsing: ParsingConfig = Field(default_factory=ParsingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    ui: UIConfig = Field(default_factory=UIConfig)


def load_config(config_path: Optional[Union[str, Path]] = None) -> AppConfig:
    if config_path is None:
        return AppConfig()
    path = Path(config_path)
    if not path.exists():
        return AppConfig()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AppConfig.parse_obj(raw)
