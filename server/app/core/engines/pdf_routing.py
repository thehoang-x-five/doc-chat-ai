"""
PDF routing helpers for upload OCR.

Classifies PDFs into digital, scanned, mixed, or unknown using the text layer
so the upload pipeline can route scanned PDFs to PaddleOCR and digital PDFs to
Docling without relying on docs-only assumptions.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from app.core.config import settings

logger = logging.getLogger(__name__)


def detect_pdf_content_type(file_path: Path) -> Dict[str, Any]:
    """
    Inspect a PDF's text layer and classify it for OCR routing.

    Returns:
        Dict with keys:
        - content_type: digital | scanned | mixed | unknown
        - sampled_pages
        - pages_with_text
        - avg_chars_per_page
        - char_counts
    """
    result: Dict[str, Any] = {
        "content_type": "unknown",
        "sampled_pages": 0,
        "pages_with_text": 0,
        "avg_chars_per_page": 0,
        "char_counts": [],
    }

    try:
        from pypdf import PdfReader

        reader = PdfReader(str(file_path))
        total_pages = len(reader.pages)
        sample_pages = min(
            total_pages,
            max(1, int(settings.PDF_ROUTING_SAMPLE_PAGES)),
        )
        min_chars = max(1, int(settings.PDF_TEXT_LAYER_MIN_CHARS))
        min_ratio = float(settings.PDF_TEXT_LAYER_MIN_PAGE_RATIO)

        char_counts = []
        pages_with_text = 0
        for idx in range(sample_pages):
            page_text = ""
            try:
                page_text = reader.pages[idx].extract_text() or ""
            except Exception:
                page_text = ""
            char_count = len(page_text.strip())
            char_counts.append(char_count)
            if char_count >= min_chars:
                pages_with_text += 1

        sampled_pages = len(char_counts)
        avg_chars = (
            sum(char_counts) / sampled_pages if sampled_pages else 0
        )
        page_ratio = (
            pages_with_text / sampled_pages if sampled_pages else 0
        )

        if sampled_pages == 0:
            content_type = "unknown"
        elif pages_with_text == 0 and avg_chars < min_chars:
            content_type = "scanned"
        elif page_ratio >= min_ratio:
            content_type = "digital"
        else:
            content_type = "mixed"

        result.update(
            {
                "content_type": content_type,
                "sampled_pages": sampled_pages,
                "pages_with_text": pages_with_text,
                "avg_chars_per_page": round(avg_chars, 2),
                "char_counts": char_counts,
                "page_ratio": round(page_ratio, 3),
            }
        )
        logger.info(
            "[PDFRouting] %s -> %s (sampled=%s, text_pages=%s, avg_chars=%.1f)",
            file_path.name,
            content_type,
            sampled_pages,
            pages_with_text,
            avg_chars,
        )
        return result
    except Exception as exc:
        logger.warning(
            "[PDFRouting] Failed to classify %s: %s",
            file_path.name,
            exc,
        )
        result["error"] = str(exc)
        return result
