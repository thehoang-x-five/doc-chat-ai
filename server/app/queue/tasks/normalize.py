"""
Normalize module — Canonical schema converter + Quality gate.

Converts PaddleOCR/Docling/plaintext parser output into a unified format
that can be used by both the Index worker and the Enrichment worker.

The canonical content_list format matches RAG-Anything's insert_content_list() API:
  [{"type": "text", "text": "...", "page_idx": 0},
   {"type": "image", "img_path": "...", "page_idx": 1}, ...]
"""
import logging
from typing import Tuple, List, Dict, Any

logger = logging.getLogger(__name__)


def _split_markdown_sections(markdown_text: str) -> List[Dict[str, Any]]:
    """
    Split markdown into structure-aware text blocks using headings.

    If no headings are found, return a single block.
    """
    text = (markdown_text or "").strip()
    if not text:
        return []

    lines = text.splitlines()
    sections: List[Dict[str, Any]] = []
    current_title = None
    current_lines: List[str] = []

    def flush_section() -> None:
        block_text = "\n".join(current_lines).strip()
        if not block_text:
            return
        sections.append(
            {
                "type": "text",
                "text": block_text,
                "page_idx": 0,
                "section_title": current_title,
            }
        )

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            flush_section()
            current_lines = [line]
            current_title = stripped.lstrip("#").strip() or None
            continue
        current_lines.append(line)

    flush_section()

    if sections:
        return sections

    return [{"type": "text", "text": text, "page_idx": 0}]


def _detect_language(text: str) -> str:
    """Simple language detection based on character analysis."""
    if not text:
        return "unknown"
    sample = text[:2000]
    vietnamese_chars = set('àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ')
    vi_count = sum(1 for c in sample.lower() if c in vietnamese_chars)
    if vi_count > len(sample) * 0.01:
        return "vi"
    return "en"


def normalize_parser_output(
    parser_used: str,
    full_text: str,
    markdown_text: str,
    structured_json: dict,
    page_count: int,
    language: str,
) -> dict:
    """
    Normalize all parser outputs into a canonical schema.

    Args:
        parser_used: "paddleocr", "docling", "docling+paddleocr", "plaintext", "direct"
        full_text: Raw extracted text
        markdown_text: Markdown-formatted text
        structured_json: Parser-specific structured output
        page_count: Number of pages
        language: Detected language (or "auto")

    Returns:
        Canonical dict with: content_list, full_text, markdown_text, stats, parser_used, language
    """
    # Build content_list (RAG-Anything compatible format)
    content_list: List[Dict[str, Any]] = []

    # 1. Add main text block(s), preserving markdown headings when possible
    content_list.extend(_split_markdown_sections(markdown_text))

    # 2. Extract images from structured_json
    images = structured_json.get("images", [])
    for img in images:
        img_path = img.get("image_path") or img.get("path")
        if img_path:
            content_list.append({
                "type": "image",
                "img_path": img_path,
                "image_caption": img.get("caption", ""),
                "image_footnote": img.get("footnote", ""),
                "page_idx": img.get("page_idx", 0),
            })

    # 3. Extract tables from structured_json
    tables = structured_json.get("tables", [])
    for tbl in tables:
        content_list.append({
            "type": "table",
            "img_path": tbl.get("image_path") or tbl.get("path"),
            "table_caption": tbl.get("caption", ""),
            "table_body": tbl.get("markdown") or tbl.get("text", ""),
            "table_footnote": tbl.get("footnote", ""),
            "page_idx": tbl.get("page_idx", 0),
        })

    # 4. Extract equations from structured_json
    equations = structured_json.get("equations", [])
    for eq in equations:
        content_list.append({
            "type": "equation",
            "text": eq.get("latex") or eq.get("text", ""),
            "text_format": eq.get("format", "latex"),
            "page_idx": eq.get("page_idx", 0),
        })

    # 5. Extract mixed-PDF page OCR blocks produced by PaddleOCR recovery
    mixed_page_ocr = structured_json.get("mixed_page_ocr", [])
    for page_ocr in mixed_page_ocr:
        text = (page_ocr.get("text") or "").strip()
        if not text:
            continue
        content_list.append({
            "type": "text",
            "text": text,
            "page_idx": page_ocr.get("page_idx", 0),
            "section_title": page_ocr.get("section_title"),
        })

    # Compute stats
    char_count = len(full_text) if full_text else 0
    word_count = len(full_text.split()) if full_text else 0

    # Language detection (auto mode)
    detected_language = language
    if language == "auto" or not language:
        detected_language = _detect_language(full_text)

    return {
        "content_list": content_list,
        "full_text": full_text or "",
        "markdown_text": markdown_text or "",
        "stats": {
            "char_count": char_count,
            "word_count": word_count,
            "page_count": page_count,
            "image_count": len(images),
            "table_count": len(tables),
            "equation_count": len(equations),
            "mixed_page_ocr_count": len(mixed_page_ocr),
            "parser_used": parser_used,
        },
        "parser_used": parser_used,
        "language": detected_language,
    }


def quality_check(normalized: dict, min_chars: int = 50) -> Tuple[bool, str]:
    """
    Check if parser output quality is acceptable.

    Args:
        normalized: Output from normalize_parser_output()
        min_chars: Minimum character count to pass

    Returns:
        (ok, reason) — ok=True if quality passes, reason explains failure
    """
    stats = normalized.get("stats", {})
    char_count = stats.get("char_count", 0)

    # Rule 1: Must have minimum text (unless there are images/tables)
    has_multimodal = (
        stats.get("image_count", 0) > 0
        or stats.get("table_count", 0) > 0
        or stats.get("equation_count", 0) > 0
    )

    if char_count < min_chars and not has_multimodal:
        return False, (
            f"Extracted text too short: {char_count} chars "
            f"(minimum {min_chars}). No images/tables found either."
        )

    # Rule 2: Check for empty pages (if page_count > 0 but no text)
    page_count = stats.get("page_count", 1)
    if page_count > 0 and char_count == 0 and not has_multimodal:
        return False, f"Document has {page_count} pages but no extractable content."

    return True, "OK"
