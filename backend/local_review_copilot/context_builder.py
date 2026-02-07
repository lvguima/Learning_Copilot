from __future__ import annotations

from .models import ContextChunk, DocumentContent


def build_context_chunks(
    docs: list[DocumentContent], max_chars: int, selected_paths: list[str] | None = None
) -> list[ContextChunk]:
    selected_set = set(selected_paths or [])
    chunks: list[ContextChunk] = []
    consumed = 0
    for doc in docs:
        if selected_set and doc.path not in selected_set:
            continue
        if doc.parse_status in {"failed"}:
            continue
        text = (doc.text or "").strip()
        if not text:
            continue
        if consumed >= max_chars:
            break
        remain = max_chars - consumed
        clipped = text[:remain]
        consumed += len(clipped)
        chunks.append(
            ContextChunk(
                doc_id=doc.doc_id,
                path=doc.path,
                chunk_id=f"{doc.doc_id[:12]}-{len(chunks)}",
                text=clipped,
                score=1.0,
            )
        )
    return chunks


def build_context_text(chunks: list[ContextChunk]) -> str:
    blocks = [f"[{chunk.path}]\n{chunk.text}" for chunk in chunks]
    return "\n\n---\n\n".join(blocks)

