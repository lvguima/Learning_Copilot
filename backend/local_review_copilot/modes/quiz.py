from __future__ import annotations

from ..models import Citation, ContextChunk, QuizItem
from ..prompting import SYSTEM_PROMPT, quiz_prompt


def build_quiz_messages(context: list[ContextChunk], count: int) -> list[dict[str, str]]:
    context_text = "\n\n".join([f"[{chunk.path}]\n{chunk.text}" for chunk in context])
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"材料如下：\n{context_text}\n\n{quiz_prompt(count)}"},
    ]


def fallback_quiz(context: list[ContextChunk], count: int) -> list[QuizItem]:
    quizzes: list[QuizItem] = []
    for index in range(max(3, count)):
        sample = context[index % len(context)] if context else None
        path = sample.path if sample else "unknown"
        snippet = sample.text[:120] if sample else "无材料"
        quizzes.append(
            QuizItem(
                question=f"第{index + 1}题：总结材料 {path} 的关键观点。",
                expected_points=["定义核心问题", "说明方法或结论", "给出可验证证据"],
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
            item.feedback = "未作答。建议先给出要点式回答。"
            continue
        score = 0.3
        for point in item.expected_points:
            if any(token in answer for token in point[:4]):
                score += 0.2
        item.score = min(1.0, round(score, 2))
        item.feedback = "回答覆盖部分要点，可补充证据与反例。" if item.score < 0.8 else "回答较完整。"
    return items

