from __future__ import annotations

from typing import Any

from ..models import Citation, ContextChunk, ReviewReport
from ..prompting import SYSTEM_PROMPT, review_prompt


def build_review_messages(
    context: list[ContextChunk],
    topic: str,
    multimodal_parts: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    context_text = "\n\n".join([f"[{chunk.path}]\n{chunk.text}" for chunk in context])
    text_prompt = f"Context files:\n{context_text}\n\n{review_prompt(topic)}"
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


def fallback_review(trace_id: str, context: list[ContextChunk], llm_text: str) -> ReviewReport:
    summary = llm_text[:300] if llm_text else "No valid model output. Generated a baseline review."
    questions = [
        "What is the most important outcome in this round, and where is the evidence?",
        "What was the key bottleneck, and what can we validate next?",
        "What is your first next step and its done criteria?",
    ]
    actions = [
        "Write a summary in under 5 lines and include source file paths.",
        "Design one verifiable check for one risk point (input/expected/failure).",
        "Break the next step into a task that can be completed within 30 minutes.",
    ]
    citations = [
        Citation(doc_id=chunk.doc_id, path=chunk.path, loc_snippet=chunk.text[:80])
        for chunk in context[:3]
    ]
    return ReviewReport(
        trace_id=trace_id,
        summary=summary,
        questions=questions,
        actions=actions,
        citations=citations,
    )
