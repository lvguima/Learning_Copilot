from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from .models import DocumentMeta


_MIME_OVERRIDES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}

_VISION_IMAGE_TYPES = {"image"}
_SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def resolve_supported_modalities(model: str) -> set[str]:
    name = (model or "").strip().lower()
    if not name:
        return {"image"}

    if "deepseek-ocr" in name:
        return {"image"}
    if "qwen3-omni" in name:
        return {"image"}
    if "qwen3-vl" in name:
        return {"image"}
    if "qwen2-vl" in name or "deepseek-vl" in name or "step3" in name or "glm-4v" in name:
        return {"image"}
    if "deepseek-v3" in name or "deepseek-r1" in name:
        return set()
    if "vl" in name or "vision" in name:
        return {"image"}
    return {"image"}


def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _MIME_OVERRIDES:
        return _MIME_OVERRIDES[ext]
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _as_data_url(path: Path) -> str:
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{_guess_mime(path)};base64,{payload}"


def _as_data_url_bytes(payload: bytes, mime: str) -> str:
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _to_image_content_part(url: str) -> dict[str, Any]:
    return {
        "type": "image_url",
        "image_url": {
            "url": url,
            "detail": "auto",
        },
    }


def _extract_pdf_images_for_vision(
    path: Path,
    max_pages: int = 6,
    max_images_per_page: int = 2,
) -> tuple[list[tuple[dict[str, Any], int]], list[str]]:
    warnings: list[str] = []
    parts: list[tuple[dict[str, Any], int]] = []
    try:
        from pypdf import PdfReader
    except Exception:
        return [], ["PDF image extraction unavailable: install `pypdf`."]

    try:
        reader = PdfReader(path)
    except Exception as error:
        return [], [f"PDF open failed for vision extraction: {error}"]

    page_count = min(len(reader.pages), max_pages)
    for page_index in range(page_count):
        page = reader.pages[page_index]
        try:
            images = list(page.images)
        except Exception as error:
            warnings.append(f"PDF page image extraction failed (page {page_index + 1}): {error}")
            continue
        for image_index, image in enumerate(images[:max_images_per_page]):
            name = getattr(image, "name", f"page-{page_index + 1}-img-{image_index + 1}.png")
            ext = Path(name).suffix.lower()
            if ext not in _SUPPORTED_IMAGE_EXTS:
                warnings.append(
                    f"Skipped unsupported image in PDF (page {page_index + 1}): {name}"
                )
                continue
            mime = _MIME_OVERRIDES.get(ext, "image/png")
            payload = image.data
            url = _as_data_url_bytes(payload, mime)
            parts.append((_to_image_content_part(url), len(payload)))
    return parts, warnings


def build_multimodal_parts(
    docs: list[DocumentMeta],
    selected_paths: list[str],
    model: str = "",
    max_parts: int = 500,
    max_total_bytes: int = 50 * 1024 * 1024,
) -> tuple[list[dict[str, Any]], list[str]]:
    docs_by_path = {doc.path: doc for doc in docs}
    candidate_paths = selected_paths or [doc.path for doc in docs]
    warnings: list[str] = []
    parts: list[dict[str, Any]] = []
    total_bytes = 0
    allowed_types = resolve_supported_modalities(model)
    allowed_label = ", ".join(sorted(allowed_types)) if allowed_types else "none"

    for path_value in candidate_paths:
        meta = docs_by_path.get(path_value)
        if meta is None:
            warnings.append(f"Selected file not found in scan results: {path_value}")
            continue
        if meta.file_type not in {"image", "pdf"}:
            continue
        if "image" not in allowed_types:
            warnings.append(
                f"Skipped unsupported modality for current model ({allowed_label}): "
                f"{meta.path} [{meta.file_type}]"
            )
            continue

        if meta.file_type == "pdf":
            pdf_path = Path(meta.path)
            if not pdf_path.exists() or not pdf_path.is_file():
                warnings.append(f"Multimodal file missing: {meta.path}")
                continue
            pdf_parts, pdf_warnings = _extract_pdf_images_for_vision(pdf_path)
            warnings.extend(pdf_warnings)
            if not pdf_parts:
                warnings.append(f"No extractable PDF page images for vision: {meta.path}")
                continue
            for part, part_bytes in pdf_parts:
                if len(parts) >= max_parts:
                    warnings.append(f"Too many multimodal files selected. Only first {max_parts} were attached.")
                    return parts, warnings
                if total_bytes + part_bytes > max_total_bytes:
                    warnings.append(
                        f"Multimodal payload exceeded size limit ({max_total_bytes} bytes). "
                        f"Skipped: {meta.path}"
                    )
                    break
                parts.append(part)
                total_bytes += part_bytes
            continue

        if len(parts) >= max_parts:
            warnings.append(f"Too many multimodal files selected. Only first {max_parts} were attached.")
            break
        path = Path(meta.path)
        if not path.exists() or not path.is_file():
            warnings.append(f"Multimodal file missing: {meta.path}")
            continue
        if path.suffix.lower() not in _SUPPORTED_IMAGE_EXTS:
            warnings.append(
                "Skipped unsupported image format for vision API "
                f"(.png/.jpg/.jpeg/.webp/.gif only): {meta.path}"
            )
            continue
        file_bytes = path.stat().st_size
        if total_bytes + file_bytes > max_total_bytes:
            warnings.append(
                f"Multimodal payload exceeded size limit ({max_total_bytes} bytes). "
                f"Skipped: {meta.path}"
            )
            continue
        try:
            parts.append(_to_image_content_part(_as_data_url(path)))
            total_bytes += file_bytes
        except Exception as error:
            warnings.append(f"Failed to attach multimodal file {meta.path}: {error}")

    return parts, warnings
