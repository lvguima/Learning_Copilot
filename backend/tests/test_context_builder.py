from local_review_copilot.context_builder import build_context_chunks
from local_review_copilot.models import DocumentContent


def test_build_context_chunks_respects_budget() -> None:
    docs = [
        DocumentContent(doc_id="1", path="a.md", file_type="md", text="a" * 100, parse_status="ok"),
        DocumentContent(doc_id="2", path="b.md", file_type="md", text="b" * 100, parse_status="ok"),
    ]
    chunks = build_context_chunks(docs, max_chars=120)
    assert len(chunks) >= 1
    assert sum(len(item.text) for item in chunks) <= 120

