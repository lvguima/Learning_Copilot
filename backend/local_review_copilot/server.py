from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import LLMConfig, load_config, save_config
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
    UpdateConfigRequest,
)
from .scanner import scan_workspace
from .storage import Storage

setup_logging()
logger = logging.getLogger("local_review_copilot")
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"
config = load_config(CONFIG_PATH)
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


def _dump_model(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return value


def _validate_model(model: Any, payload: Any) -> Any:
    if hasattr(model, "model_validate"):
        return model.model_validate(payload)
    return model.parse_obj(payload)


def _scan_documents(root_dir: str | None) -> list[Any]:
    try:
        return scan_workspace(config.workspace, root_dir)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Scan failed: {error}") from error


def _dedupe_messages(messages: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in messages:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _build_context_warnings(contents: list[Any], selected_paths: list[str], chunk_count: int) -> list[str]:
    selected_set = set(selected_paths)
    targeted_count = 0
    warnings: list[str] = []

    for content in contents:
        if selected_set and content.path not in selected_set:
            continue
        targeted_count += 1
        if content.parse_status == "ok":
            continue
        detail = "；".join(content.warnings) if content.warnings else "无额外说明"
        if content.parse_status == "degraded":
            warnings.append(f"降级解析：{content.path} -> {detail}")
        elif content.parse_status == "image_only":
            warnings.append(f"图片文件未提取正文：{content.path} -> {detail}")
        else:
            warnings.append(f"解析失败：{content.path} -> {detail}")

    if selected_set and targeted_count == 0:
        warnings.append("已勾选文件未出现在扫描结果中，请先重新扫描。")
    if targeted_count > 0 and chunk_count == 0:
        warnings.append("未提取到可用文本上下文，结果可能不完整。")

    return _dedupe_messages(warnings)


def _prepare_context(
    root_dir: str | None, selected_paths: list[str]
) -> tuple[list[Any], list[Any], list[str]]:
    docs = _scan_documents(root_dir)
    contents = load_documents(docs)
    chunks = build_context_chunks(
        contents,
        max_chars=config.llm.max_context_tokens * 3,
        selected_paths=selected_paths,
    )
    warnings = _build_context_warnings(contents, selected_paths, len(chunks))
    return docs, chunks, warnings


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config")
def get_runtime_config() -> dict[str, Any]:
    return {
        "workspace_root_dir": config.workspace.root_dir,
        "llm": _dump_model(config.llm),
    }


@app.post("/config")
def update_runtime_config(request: UpdateConfigRequest) -> dict[str, Any]:
    global llm_client

    next_workspace_root = config.workspace.root_dir
    if request.workspace_root_dir is not None:
        candidate_root = Path(request.workspace_root_dir).expanduser()
        if not candidate_root.exists() or not candidate_root.is_dir():
            raise HTTPException(status_code=400, detail=f"Workspace root not found: {candidate_root}")
        next_workspace_root = str(candidate_root.resolve())

    try:
        next_llm = LLMConfig(**_dump_model(request.llm)) if request.llm is not None else config.llm
        next_llm_client = LLMClient(next_llm)
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Invalid llm config: {error}") from error

    previous_workspace_root = config.workspace.root_dir
    previous_llm = config.llm
    previous_llm_client = llm_client
    config.workspace.root_dir = next_workspace_root
    config.llm = next_llm
    llm_client = next_llm_client

    try:
        save_path = save_config(config, CONFIG_PATH)
    except Exception as error:
        config.workspace.root_dir = previous_workspace_root
        config.llm = previous_llm
        llm_client = previous_llm_client
        raise HTTPException(status_code=500, detail=f"Save config failed: {error}") from error

    return {
        "saved_to": str(Path(save_path).resolve()),
        "workspace_root_dir": config.workspace.root_dir,
        "llm": _dump_model(config.llm),
    }


@app.post("/scan")
def scan(request: ScanRequest) -> dict[str, Any]:
    trace_id = _trace_id()
    docs = _scan_documents(request.root_dir)
    session = SessionRecord(
        trace_id=trace_id,
        mode="scan",
        root_dir=request.root_dir or config.workspace.root_dir,
    )
    storage.save_session(session)
    return {
        "trace_id": trace_id,
        "count": len(docs),
        "documents": [_dump_model(doc) for doc in docs],
    }


@app.post("/chat/session")
async def chat(request: ChatRequest) -> dict[str, Any]:
    trace_id = _trace_id()
    _, chunks, warnings = _prepare_context(request.root_dir, request.selected_paths)
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
        errors=warnings,
    )
    storage.save_session(session)
    return {
        "trace_id": trace_id,
        "answer": assistant_turn.content,
        "citations": [_dump_model(citation) for citation in assistant_turn.citations],
        "warnings": warnings,
    }


@app.post("/review/run")
async def review(request: ReviewRequest) -> dict[str, Any]:
    trace_id = _trace_id()
    _, chunks, warnings = _prepare_context(request.root_dir, request.selected_paths)
    messages = build_review_messages(chunks, request.topic)
    llm_text = ""
    try:
        llm_text = await llm_client.generate(messages)
    except Exception as error:
        logger.warning("Review LLM failed: %s", error)
    report = fallback_review(trace_id, chunks, llm_text)

    markdown = (
        f"# 复盘报告\n\n"
        f"Trace ID: `{trace_id}`\n\n"
        f"## 总结\n{report.summary}\n\n"
        f"## 问题\n" + "\n".join([f"- {item}" for item in report.questions]) + "\n\n"
        f"## 行动\n" + "\n".join([f"- {item}" for item in report.actions]) + "\n"
    )
    exports = storage.save_export("review", markdown, _dump_model(report))
    session = SessionRecord(
        trace_id=trace_id,
        mode="review",
        root_dir=request.root_dir or config.workspace.root_dir,
        turns=[ChatTurn(role="assistant", content=report.summary, citations=report.citations)],
        errors=warnings,
    )
    storage.save_session(session)
    return {
        "trace_id": trace_id,
        "report": _dump_model(report),
        "exports": exports,
        "warnings": warnings,
    }


@app.post("/quiz/generate")
async def quiz_generate(request: QuizGenerateRequest) -> dict[str, Any]:
    trace_id = _trace_id()
    _, chunks, warnings = _prepare_context(request.root_dir, request.selected_paths)
    messages = build_quiz_messages(chunks, request.count)
    try:
        _ = await llm_client.generate(messages)
    except Exception as error:
        logger.warning("Quiz LLM failed: %s", error)
    quiz_items = fallback_quiz(chunks, request.count)
    QUIZ_CACHE[trace_id] = [_dump_model(item) for item in quiz_items]
    session = SessionRecord(
        trace_id=trace_id,
        mode="quiz",
        root_dir=request.root_dir or config.workspace.root_dir,
        turns=[ChatTurn(role="assistant", content=f"Generated {len(quiz_items)} quiz questions.")],
        errors=warnings,
    )
    storage.save_session(session)
    return {
        "trace_id": trace_id,
        "items": [_dump_model(item) for item in quiz_items],
        "warnings": warnings,
    }


@app.post("/quiz/evaluate")
def quiz_evaluate(request: QuizEvaluateRequest) -> dict[str, Any]:
    if request.trace_id not in QUIZ_CACHE:
        raise HTTPException(status_code=404, detail="Quiz trace_id not found")

    from .models import QuizItem

    items = [_validate_model(QuizItem, item) for item in QUIZ_CACHE[request.trace_id]]
    scored = evaluate_quiz_items(items, request.answers)
    payload = {"trace_id": request.trace_id, "items": [_dump_model(item) for item in scored]}
    markdown = "# 测验结果\n\n" + "\n\n".join(
        [
            f"## Q{index + 1}\n- 题目：{item.question}\n- 得分：{item.score}\n- 点评：{item.feedback}"
            for index, item in enumerate(scored)
        ]
    )
    exports = storage.save_export("quiz", markdown, payload)
    return {"trace_id": request.trace_id, "items": payload["items"], "exports": exports}


@app.get("/session/{trace_id}")
def session(trace_id: str) -> dict[str, Any]:
    try:
        return storage.load_session(trace_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
