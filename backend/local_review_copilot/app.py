from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import load_config
from .context_builder import build_context_chunks
from .llm.client import LLMClient
from .loaders import load_documents
from .logging import setup_logging
from .modes.chat import build_chat_messages, make_chat_turn
from .modes.quiz import build_quiz_messages, evaluate_quiz_items, fallback_quiz
from .modes.review import build_review_messages, fallback_review
from .models import (
    ChatRequest,
    ChatTurn,
    QuizEvaluateRequest,
    QuizGenerateRequest,
    ReviewRequest,
    ScanRequest,
    SessionRecord,
)
from .scanner import scan_workspace
from .storage import Storage

setup_logging()
logger = logging.getLogger("local_review_copilot")
config = load_config("config.yaml")
storage = Storage(config.output)
llm_client = LLMClient(config.llm)
app = FastAPI(title="Local Review Copilot Sidecar", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
QUIZ_CACHE: dict[str, list[dict[str, Any]]] = {}


def _trace_id() -> str:
    return uuid.uuid4().hex[:12]


def _prepare_context(root_dir: str | None, selected_paths: list[str]) -> tuple[list[Any], list[Any]]:
    docs = scan_workspace(config.workspace, root_dir)
    contents = load_documents(docs)
    chunks = build_context_chunks(
        contents,
        max_chars=config.llm.max_context_tokens * 3,
        selected_paths=selected_paths,
    )
    return docs, chunks


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/scan")
def scan(request: ScanRequest) -> dict[str, Any]:
    trace_id = _trace_id()
    docs = scan_workspace(config.workspace, request.root_dir)
    session = SessionRecord(
        trace_id=trace_id,
        mode="scan",
        root_dir=request.root_dir or config.workspace.root_dir,
    )
    storage.save_session(session)
    return {
        "trace_id": trace_id,
        "count": len(docs),
        "documents": [doc.model_dump() for doc in docs],
    }


@app.post("/chat/session")
async def chat(request: ChatRequest) -> dict[str, Any]:
    trace_id = _trace_id()
    _, chunks = _prepare_context(request.root_dir, request.selected_paths)
    messages = build_chat_messages(chunks, request.message)
    try:
        answer = await llm_client.generate(messages)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {error}") from error

    assistant_turn = make_chat_turn(answer, chunks)
    session = SessionRecord(
        trace_id=trace_id,
        mode="chat",
        root_dir=request.root_dir or config.workspace.root_dir,
        turns=[
            ChatTurn(role="user", content=request.message),
            assistant_turn,
        ],
    )
    storage.save_session(session)
    return {
        "trace_id": trace_id,
        "answer": assistant_turn.content,
        "citations": [citation.model_dump() for citation in assistant_turn.citations],
    }


@app.post("/review/run")
async def review(request: ReviewRequest) -> dict[str, Any]:
    trace_id = _trace_id()
    _, chunks = _prepare_context(request.root_dir, request.selected_paths)
    messages = build_review_messages(chunks, request.topic)
    llm_text = ""
    try:
        llm_text = await llm_client.generate(messages)
    except Exception as error:
        logger.warning("Review LLM failed: %s", error)
    report = fallback_review(trace_id, chunks, llm_text)

    markdown = (
        f"# Review Report\n\n"
        f"Trace ID: `{trace_id}`\n\n"
        f"## Summary\n{report.summary}\n\n"
        f"## Questions\n" + "\n".join([f"- {item}" for item in report.questions]) + "\n\n"
        f"## Actions\n" + "\n".join([f"- {item}" for item in report.actions]) + "\n"
    )
    exports = storage.save_export("review", markdown, report.model_dump(mode="json"))
    session = SessionRecord(
        trace_id=trace_id,
        mode="review",
        root_dir=request.root_dir or config.workspace.root_dir,
        turns=[ChatTurn(role="assistant", content=report.summary, citations=report.citations)],
    )
    storage.save_session(session)
    return {"trace_id": trace_id, "report": report.model_dump(mode="json"), "exports": exports}


@app.post("/quiz/generate")
async def quiz_generate(request: QuizGenerateRequest) -> dict[str, Any]:
    trace_id = _trace_id()
    _, chunks = _prepare_context(request.root_dir, request.selected_paths)
    messages = build_quiz_messages(chunks, request.count)
    try:
        _ = await llm_client.generate(messages)
    except Exception as error:
        logger.warning("Quiz LLM failed: %s", error)
    quiz_items = fallback_quiz(chunks, request.count)
    QUIZ_CACHE[trace_id] = [item.model_dump(mode="json") for item in quiz_items]
    session = SessionRecord(
        trace_id=trace_id,
        mode="quiz",
        root_dir=request.root_dir or config.workspace.root_dir,
        turns=[ChatTurn(role="assistant", content=f"Generated {len(quiz_items)} quiz questions.")],
    )
    storage.save_session(session)
    return {"trace_id": trace_id, "items": [item.model_dump(mode="json") for item in quiz_items]}


@app.post("/quiz/evaluate")
def quiz_evaluate(request: QuizEvaluateRequest) -> dict[str, Any]:
    if request.trace_id not in QUIZ_CACHE:
        raise HTTPException(status_code=404, detail="Quiz trace_id not found")

    from .models import QuizItem

    items = [QuizItem.model_validate(item) for item in QUIZ_CACHE[request.trace_id]]
    scored = evaluate_quiz_items(items, request.answers)
    payload = {"trace_id": request.trace_id, "items": [item.model_dump(mode="json") for item in scored]}
    markdown = "# Quiz Result\n\n" + "\n\n".join(
        [f"## Q{index + 1}\n- 题目：{item.question}\n- 得分：{item.score}\n- 点评：{item.feedback}" for index, item in enumerate(scored)]
    )
    exports = storage.save_export("quiz", markdown, payload)
    return {"trace_id": request.trace_id, "items": payload["items"], "exports": exports}


@app.get("/session/{trace_id}")
def session(trace_id: str) -> dict[str, Any]:
    try:
        return storage.load_session(trace_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
