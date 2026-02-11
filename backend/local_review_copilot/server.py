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
from .loaders.pdf import load_pdf_document
from .loaders.text import load_text_document
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
from .multimodal import build_multimodal_parts
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


def _resolve_selected_docs(docs: list[Any], selected_paths: list[str]) -> tuple[list[Any], list[str]]:
    if not selected_paths:
        return docs, []

    docs_by_path = {doc.path: doc for doc in docs}
    selected_docs: list[Any] = []
    missing: list[str] = []
    for path in selected_paths:
        doc = docs_by_path.get(path)
        if doc is None:
            missing.append(path)
            continue
        selected_docs.append(doc)
    return selected_docs, missing


def _build_text_context(selected_docs: list[Any]) -> tuple[list[Any], list[str]]:
    warnings: list[str] = []
    text_contents: list[Any] = []
    for doc in selected_docs:
        if doc.file_type not in {"md", "txt", "pdf"}:
            continue
        content = load_pdf_document(doc) if doc.file_type == "pdf" else load_text_document(doc)
        if content.parse_status != "ok":
            detail = "; ".join(content.warnings) if content.warnings else "no detail"
            warnings.append(f"Text parse {content.parse_status}: {content.path} -> {detail}")
        text_contents.append(content)

    chunks = build_context_chunks(
        text_contents,
        max_chars=config.llm.max_context_tokens * 3,
        selected_paths=[doc.path for doc in selected_docs],
    )
    if text_contents and not chunks:
        warnings.append("Selected text files produced no usable context chunks.")
    return chunks, warnings


def _prepare_prompt_assets(
    root_dir: str | None,
    selected_paths: list[str],
) -> tuple[list[Any], list[Any], list[dict[str, Any]], list[str]]:
    docs = _scan_documents(root_dir)
    selected_docs, missing_paths = _resolve_selected_docs(docs, selected_paths)

    warnings = [f"Selected file not found in scan results: {path}" for path in missing_paths]
    chunks, text_warnings = _build_text_context(selected_docs)
    multimodal_parts, multimodal_warnings = build_multimodal_parts(
        docs,
        selected_paths,
        model=config.llm.model,
    )

    warnings.extend(text_warnings)
    warnings.extend(multimodal_warnings)

    if not chunks and not multimodal_parts:
        warnings.append("No usable text context or multimodal attachments were prepared.")

    return docs, chunks, multimodal_parts, _dedupe_messages(warnings)


def _is_multimodal_not_supported_error(error: Exception) -> bool:
    message = str(error).lower()
    markers = [
        "http 400",
        "invalid_request_error",
        "unsupported",
        "image_url",
        "audio_url",
        "video_url",
    ]
    return any(item in message for item in markers)


def _error_text(error: Exception) -> str:
    text = str(error).strip()
    return text if text else repr(error)


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
    _, chunks, multimodal_parts, warnings = _prepare_prompt_assets(request.root_dir, request.selected_paths)
    messages = build_chat_messages(chunks, request.message, multimodal_parts)
    try:
        answer = await llm_client.generate(messages)
    except Exception as error:
        logger.warning("Chat LLM failed (first attempt): %s", _error_text(error))
        if multimodal_parts and _is_multimodal_not_supported_error(error):
            warnings.append(
                "Current model may not support multimodal parts. Retried with text-only context."
            )
            try:
                answer = await llm_client.generate(build_chat_messages(chunks, request.message, []))
            except Exception as retry_error:
                logger.warning("Chat LLM failed after text-only retry: %s", _error_text(retry_error))
                raise HTTPException(status_code=502, detail=f"LLM call failed: {_error_text(retry_error)}") from retry_error
        else:
            raise HTTPException(status_code=502, detail=f"LLM call failed: {_error_text(error)}") from error

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
    _, chunks, multimodal_parts, warnings = _prepare_prompt_assets(request.root_dir, request.selected_paths)
    messages = build_review_messages(chunks, request.topic, multimodal_parts)
    llm_text = ""
    try:
        llm_text = await llm_client.generate(messages)
    except Exception as error:
        if multimodal_parts and _is_multimodal_not_supported_error(error):
            warnings.append(
                "Current model may not support multimodal parts. Retried with text-only context."
            )
            try:
                llm_text = await llm_client.generate(build_review_messages(chunks, request.topic, []))
            except Exception as retry_error:
                logger.warning("Review LLM failed after text-only retry: %s", _error_text(retry_error))
                warnings.append(f"Review model call failed after retry: {_error_text(retry_error)}")
        else:
            logger.warning("Review LLM failed: %s", _error_text(error))
            warnings.append(f"Review model call failed: {_error_text(error)}")
    if not llm_text.strip():
        warnings.append("Review model output is empty. Used fallback template.")
    report = fallback_review(trace_id, chunks, llm_text)

    markdown = (
        f"# Review Report\n\n"
        f"Trace ID: `{trace_id}`\n\n"
        f"## Summary\n{report.summary}\n\n"
        f"## Questions\n" + "\n".join([f"- {item}" for item in report.questions]) + "\n\n"
        f"## Actions\n" + "\n".join([f"- {item}" for item in report.actions]) + "\n"
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
    _, chunks, multimodal_parts, warnings = _prepare_prompt_assets(request.root_dir, request.selected_paths)
    messages = build_quiz_messages(chunks, request.count, multimodal_parts)
    try:
        _ = await llm_client.generate(messages)
    except Exception as error:
        if multimodal_parts and _is_multimodal_not_supported_error(error):
            warnings.append(
                "Current model may not support multimodal parts. Retried with text-only context."
            )
            try:
                _ = await llm_client.generate(build_quiz_messages(chunks, request.count, []))
            except Exception as retry_error:
                logger.warning("Quiz LLM failed after text-only retry: %s", _error_text(retry_error))
                warnings.append(f"Quiz model call failed after retry: {_error_text(retry_error)}")
        else:
            logger.warning("Quiz LLM failed: %s", _error_text(error))
            warnings.append(f"Quiz model call failed: {_error_text(error)}")
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
    markdown = "# Quiz Result\n\n" + "\n\n".join(
        [
            f"## Q{index + 1}\n- Question: {item.question}\n- Score: {item.score}\n- Feedback: {item.feedback}"
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
