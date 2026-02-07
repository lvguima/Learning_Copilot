from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class DocumentMeta(BaseModel):
    doc_id: str
    path: str
    mtime: float
    size: int
    file_hash: str
    file_type: Literal["md", "txt", "pdf", "image", "other"]


class DocumentContent(BaseModel):
    doc_id: str
    path: str
    file_type: str
    parse_status: Literal["ok", "degraded", "failed", "image_only"] = "ok"
    warnings: List[str] = Field(default_factory=list)
    text: str = ""


class ContextChunk(BaseModel):
    doc_id: str
    path: str
    chunk_id: str
    text: str
    score: float = 0.0


class Citation(BaseModel):
    doc_id: str
    path: str
    loc_snippet: str


class ChatTurn(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str
    citations: List[Citation] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionRecord(BaseModel):
    trace_id: str
    mode: Literal["chat", "review", "quiz", "scan"]
    root_dir: str
    turns: List[ChatTurn] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewReport(BaseModel):
    trace_id: str
    summary: str
    questions: List[str]
    actions: List[str]
    citations: List[Citation] = Field(default_factory=list)


class QuizItem(BaseModel):
    question: str
    expected_points: List[str]
    user_answer: str = ""
    feedback: str = ""
    score: float = 0.0
    citations: List[Citation] = Field(default_factory=list)


class ScanRequest(BaseModel):
    root_dir: Optional[str] = None


class ChatRequest(BaseModel):
    root_dir: Optional[str] = None
    message: str
    selected_paths: List[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    root_dir: Optional[str] = None
    topic: str = ""
    selected_paths: List[str] = Field(default_factory=list)


class QuizGenerateRequest(BaseModel):
    root_dir: Optional[str] = None
    count: int = 3
    selected_paths: List[str] = Field(default_factory=list)


class QuizEvaluateRequest(BaseModel):
    trace_id: str
    answers: List[str]
