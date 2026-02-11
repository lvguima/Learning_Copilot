from __future__ import annotations

from pathlib import Path

import local_review_copilot.multimodal as multimodal
from local_review_copilot.models import DocumentMeta
from local_review_copilot.multimodal import build_multimodal_parts, resolve_supported_modalities


def _meta(path: Path, file_type: str, index: int) -> DocumentMeta:
    stat = path.stat()
    return DocumentMeta(
        doc_id=f"doc-{index}",
        path=str(path),
        mtime=stat.st_mtime,
        size=stat.st_size,
        file_hash=f"hash-{index}",
        file_type=file_type,
    )


def test_build_multimodal_parts_includes_supported_types(local_tmp_dir: Path) -> None:
    image_path = local_tmp_dir / "a.png"
    text_path = local_tmp_dir / "c.md"
    image_path.write_bytes(b"\x89PNG\r\n")
    text_path.write_text("# note", encoding="utf-8")

    docs = [
        _meta(image_path, "image", 1),
        _meta(text_path, "md", 2),
    ]
    parts, warnings = build_multimodal_parts(
        docs,
        [str(image_path), str(text_path)],
        model="Qwen/Qwen3-VL",
    )

    assert len(parts) == 1
    assert parts[0]["type"] == "image_url"
    assert warnings == []


def test_build_multimodal_parts_reports_missing_and_limit(local_tmp_dir: Path) -> None:
    p1 = local_tmp_dir / "1.png"
    p2 = local_tmp_dir / "2.png"
    p3 = local_tmp_dir / "3.png"
    for item in [p1, p2, p3]:
        item.write_bytes(b"\x89PNG\r\n")
    docs = [
        _meta(p1, "image", 1),
        _meta(p2, "image", 2),
        _meta(p3, "image", 3),
    ]
    missing = local_tmp_dir / "missing.png"
    parts, warnings = build_multimodal_parts(
        docs,
        [str(missing), str(p1), str(p2), str(p3)],
        max_parts=2,
    )

    assert len(parts) == 2
    assert any("Selected file not found" in item for item in warnings)
    assert any("Too many multimodal files selected" in item for item in warnings)


def test_build_multimodal_parts_converts_pdf_to_image_parts(local_tmp_dir: Path, monkeypatch) -> None:
    pdf_path = local_tmp_dir / "doc.pdf"
    image_path = local_tmp_dir / "a.png"
    pdf_path.write_bytes(b"%PDF-1.4")
    image_path.write_bytes(b"\x89PNG\r\n")
    docs = [
        _meta(pdf_path, "pdf", 1),
        _meta(image_path, "image", 2),
    ]

    monkeypatch.setattr(
        multimodal,
        "_extract_pdf_images_for_vision",
        lambda _path, max_pages=6, max_images_per_page=2: (
            [
                (
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,AAA", "detail": "auto"},
                    },
                    3,
                )
            ],
            [],
        ),
    )

    parts, warnings = build_multimodal_parts(
        docs,
        [str(pdf_path), str(image_path)],
        model="Qwen/Qwen2-VL-72B-Instruct",
    )

    assert len(parts) == 2
    assert parts[0]["type"] == "image_url"
    assert warnings == []


def test_build_multimodal_parts_skips_for_text_only_model(local_tmp_dir: Path) -> None:
    image_path = local_tmp_dir / "a.png"
    image_path.write_bytes(b"\x89PNG\r\n")
    docs = [_meta(image_path, "image", 1)]

    parts, warnings = build_multimodal_parts(
        docs,
        [str(image_path)],
        model="deepseek-ai/DeepSeek-V3.2",
    )

    assert parts == []
    assert any("Skipped unsupported modality" in item for item in warnings)


def test_resolve_supported_modalities() -> None:
    assert resolve_supported_modalities("deepseek-ai/DeepSeek-OCR") == {"image"}
    assert resolve_supported_modalities("Qwen/Qwen3-Omni") == {"image"}
    assert resolve_supported_modalities("Qwen/Qwen3-VL") == {"image"}
    assert resolve_supported_modalities("deepseek-ai/DeepSeek-V3.2") == set()
