from __future__ import annotations

from ..models import ChatTurn, Citation, ContextChunk
from ..prompting import SYSTEM_PROMPT


def build_chat_messages(context: list[ContextChunk], user_message: str) -> list[dict[str, str]]:
    context_text = "\n\n".join([f"[{chunk.path}]\n{chunk.text}" for chunk in context])
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"材料如下：\n{context_text}\n\n用户问题：{user_message}",
        },
    ]


def make_chat_turn(answer: str, context: list[ContextChunk]) -> ChatTurn:
    citations = [
        Citation(doc_id=chunk.doc_id, path=chunk.path, loc_snippet=chunk.text[:80])
        for chunk in context[:3]
    ]
    return ChatTurn(role="assistant", content=answer, citations=citations)

