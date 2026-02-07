from __future__ import annotations

from ..models import Citation, ContextChunk, ReviewReport
from ..prompting import SYSTEM_PROMPT, review_prompt


def build_review_messages(context: list[ContextChunk], topic: str) -> list[dict[str, str]]:
    context_text = "\n\n".join([f"[{chunk.path}]\n{chunk.text}" for chunk in context])
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"材料如下：\n{context_text}\n\n{review_prompt(topic)}"},
    ]


def fallback_review(trace_id: str, context: list[ContextChunk], llm_text: str) -> ReviewReport:
    summary = llm_text[:300] if llm_text else "未得到有效模型输出，已生成基础复盘。"
    questions = [
        "你本次最重要的产出是什么？证据在哪个文件？",
        "你卡住的关键瓶颈是什么？可验证原因是什么？",
        "下一轮你要做的第一步是什么？完成标准是什么？",
    ]
    actions = [
        "整理一份 5 行以内的结论摘要，并标注来源文件。",
        "为一个风险点设计可验证检查步骤（输入/预期/失败条件）。",
        "将下一步行动拆成 30 分钟内可完成的任务。",
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

