from __future__ import annotations

from typing import Any

from ..models import Citation, ContextChunk, QuizItem
from ..prompting import SYSTEM_PROMPT, quiz_prompt


def build_quiz_messages(
    context: list[ContextChunk],
    count: int,
    multimodal_parts: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    context_text = "\n\n".join([f"[{chunk.path}]\n{chunk.text}" for chunk in context])
    text_prompt = f"Context files:\n{context_text}\n\n{quiz_prompt(count)}"
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


def fallback_quiz(context: list[ContextChunk], count: int) -> list[QuizItem]:
    quizzes: list[QuizItem] = []
    for index in range(max(3, count)):
        sample = context[index % len(context)] if context else None
        path = sample.path if sample else "unknown"
        snippet = sample.text[:120] if sample else "no context"
        quizzes.append(
            QuizItem(
                question=f"Q{index + 1}: summarize key points from {path}.",
                expected_points=[
                    "define the core issue",
                    "explain method or conclusion",
                    "provide verifiable evidence",
                ],
                citations=[
                    Citation(
                        doc_id=(sample.doc_id if sample else "n/a"),
                        path=path,
                        loc_snippet=snippet,
                    )
                ],
            )
        )
    return quizzes


def evaluate_quiz_items(items: list[QuizItem], answers: list[str]) -> list[QuizItem]:
    for index, item in enumerate(items):
        answer = answers[index] if index < len(answers) else ""
        item.user_answer = answer
        if not answer.strip():
            item.score = 0
            item.feedback = "No answer. Start with concise bullet points."
            continue
        score = 0.3
        for point in item.expected_points:
            if any(token in answer.lower() for token in point[:8].split()):
                score += 0.2
        item.score = min(1.0, round(score, 2))
        item.feedback = (
            "Partially covered. Add evidence and counterexamples."
            if item.score < 0.8
            else "Good coverage."
        )
    return items
