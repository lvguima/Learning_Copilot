from __future__ import annotations

from typing import Any

from ..models import ChatTurn, Citation, ContextChunk
from ..prompting import SYSTEM_PROMPT


def build_chat_messages(
    context: list[ContextChunk],
    user_message: str,
    multimodal_parts: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    context_text = "\n\n".join([f"[{chunk.path}]\n{chunk.text}" for chunk in context])
    text_prompt = f"Context files:\n{context_text}\n\nUser question:\n{user_message}"
    parts = multimodal_parts or []
    content: Any
    if not parts:
        content = text_prompt
    else:
        content = [{"type": "text", "text": text_prompt}, *parts]
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


def make_chat_turn(answer: str, context: list[ContextChunk]) -> ChatTurn:
    citations = [
        Citation(doc_id=chunk.doc_id, path=chunk.path, loc_snippet=chunk.text[:80])
        for chunk in context[:3]
    ]
    return ChatTurn(role="assistant", content=answer, citations=citations)
