from __future__ import annotations

from ..models import DocumentContent, DocumentMeta
from .image import load_image_document
from .pdf import load_pdf_document
from .text import load_text_document


def load_document(meta: DocumentMeta) -> DocumentContent:
    if meta.file_type in {"md", "txt"}:
        return load_text_document(meta)
    if meta.file_type == "pdf":
        return load_pdf_document(meta)
    if meta.file_type == "image":
        return load_image_document(meta)
    return DocumentContent(
        doc_id=meta.doc_id,
        path=meta.path,
        file_type=meta.file_type,
        parse_status="failed",
        warnings=[f"Unsupported file type: {meta.file_type}"],
        text="",
    )


def load_documents(metas: list[DocumentMeta]) -> list[DocumentContent]:
    return [load_document(meta) for meta in metas]

