from __future__ import annotations

from pathlib import Path

from ..models import DocumentContent, DocumentMeta


def load_image_document(meta: DocumentMeta) -> DocumentContent:
    path = Path(meta.path)
    size_kb = round(path.stat().st_size / 1024, 2)
    return DocumentContent(
        doc_id=meta.doc_id,
        path=meta.path,
        file_type=meta.file_type,
        parse_status="image_only",
        warnings=[f"Image metadata only ({size_kb} KB)."],
        text=f"[IMAGE] {path.name}",
    )

