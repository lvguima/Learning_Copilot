from __future__ import annotations

import fnmatch
import hashlib
from pathlib import Path
from typing import List, Optional

from .config import WorkspaceConfig
from .models import DocumentMeta


SUPPORTED_TYPES = {
    ".md": "md",
    ".txt": "txt",
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".gif": "image",
    ".bmp": "image",
    ".tif": "image",
    ".tiff": "image",
}


def _is_ignored(path: Path, root: Path, patterns: List[str]) -> bool:
    relative = str(path.relative_to(root)).replace("\\", "/")
    return any(fnmatch.fnmatch(relative, pattern) for pattern in patterns)


def _file_hash(path: Path) -> str:
    stat = path.stat()
    payload = f"{path}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def scan_workspace(workspace: WorkspaceConfig, root_override: Optional[str] = None) -> List[DocumentMeta]:
    root = Path(root_override or workspace.root_dir).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Workspace root not found: {root}")

    max_size = workspace.max_file_size_mb * 1024 * 1024
    docs: List[DocumentMeta] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _is_ignored(path, root, workspace.ignore_patterns):
            continue
        stat = path.stat()
        if stat.st_size > max_size:
            continue
        file_type = SUPPORTED_TYPES.get(path.suffix.lower(), "other")
        if file_type == "other":
            continue
        docs.append(
            DocumentMeta(
                doc_id=_file_hash(path),
                path=str(path),
                mtime=stat.st_mtime,
                size=stat.st_size,
                file_hash=_file_hash(path),
                file_type=file_type,
            )
        )
        if len(docs) >= workspace.max_files_per_run:
            break
    return docs
