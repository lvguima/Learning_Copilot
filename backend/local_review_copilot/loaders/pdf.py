from __future__ import annotations

from ..models import DocumentContent, DocumentMeta


def load_pdf_document(meta: DocumentMeta) -> DocumentContent:
    try:
        from pypdf import PdfReader
    except Exception:
        return DocumentContent(
            doc_id=meta.doc_id,
            path=meta.path,
            file_type=meta.file_type,
            parse_status="failed",
            warnings=["pypdf is not installed."],
            text="",
        )

    try:
        reader = PdfReader(meta.path)
        page_texts = []
        for page in reader.pages:
            page_texts.append((page.extract_text() or "").strip())
        text = "\n\n".join([chunk for chunk in page_texts if chunk])
        if not text.strip():
            return DocumentContent(
                doc_id=meta.doc_id,
                path=meta.path,
                file_type=meta.file_type,
                parse_status="degraded",
                warnings=[
                    "No text layer extracted. PDF might be scanned."
                ],
                text="",
            )
        return DocumentContent(
            doc_id=meta.doc_id,
            path=meta.path,
            file_type=meta.file_type,
            parse_status="ok",
            warnings=[],
            text=text,
        )
    except Exception as error:
        return DocumentContent(
            doc_id=meta.doc_id,
            path=meta.path,
            file_type=meta.file_type,
            parse_status="failed",
            warnings=[f"PDF parse failed: {error}"],
            text="",
        )

