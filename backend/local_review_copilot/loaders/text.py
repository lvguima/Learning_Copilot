from __future__ import annotations

from pathlib import Path

from ..models import DocumentContent, DocumentMeta


def load_text_document(meta: DocumentMeta) -> DocumentContent:
    path = Path(meta.path)
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        status = "ok"
        warnings: list[str] = []
        if not text.strip():
            status = "degraded"
            warnings.append("Document contains no readable text.")
        return DocumentContent(
            doc_id=meta.doc_id,
            path=meta.path,
            file_type=meta.file_type,
            parse_status=status,
            warnings=warnings,
            text=text,
        )
    except Exception as error:
        return DocumentContent(
            doc_id=meta.doc_id,
            path=meta.path,
            file_type=meta.file_type,
            parse_status="failed",
            warnings=[f"Text load failed: {error}"],
            text="",
        )

