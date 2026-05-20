"""
PaddleOCR Engine — CPU-optimized OCR for images and scanned documents.

Uses PaddleOCR PP-OCRv5 for text detection/recognition and PPStructureV3
for full layout analysis with Markdown output.

Two modes:
  1. OCR Mode   (PaddleOCR)      → Fast text-only OCR (~1-2s/page CPU)
  2. Structure Mode (PPStructureV3) → Layout + Table + Formula → Markdown (~5-10s/page CPU)
"""
import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Availability check (mirrors surya_engine.py pattern)
# ---------------------------------------------------------------------------
PADDLEOCR_AVAILABLE = False
try:
    import paddleocr  # noqa: F401
    PADDLEOCR_AVAILABLE = True
except ImportError:
    logger.info("paddleocr not installed — PaddleOCR engine unavailable")

# Extensions that should be routed to PaddleOCR for vision OCR
PADDLEOCR_IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".bmp",
}


def should_use_paddleocr(file_path: Path, config: dict = None) -> bool:
    """
    Determine whether PaddleOCREngine should handle this file.

    Rules:
    1. Image files (.jpg, .png, .webp, .tiff, .bmp) → Always PaddleOCR
    2. If config explicitly sets parser="paddleocr" → PaddleOCR
    3. If config marks PDF as scanned → PaddleOCR
    4. If USE_PADDLEOCR_FOR_PDF env is set and file is PDF → PaddleOCR
    5. Otherwise → False (let Docling handle)

    Args:
        file_path: Path to the input file
        config: Optional processing config dict

    Returns:
        True if PaddleOCREngine should handle this file
    """
    if not PADDLEOCR_AVAILABLE:
        return False

    ext = file_path.suffix.lower()
    config = config or {}

    # Rule 1: Image files always use PaddleOCR
    if ext in PADDLEOCR_IMAGE_EXTENSIONS:
        return True

    # Rule 2: Explicit parser request
    if config.get("parser") == "paddleocr":
        return True

    # Rule 3: Routed scanned PDF
    if ext == ".pdf" and config.get("pdf_content_type") == "scanned":
        return True

    # Rule 4: Environment variable for PDF
    import os
    if ext == ".pdf" and os.environ.get(
        "USE_PADDLEOCR_FOR_PDF", ""
    ).lower() in ("true", "1", "yes"):
        return True

    return False


class PaddleOCREngine:
    """
    OCR engine wrapping PaddleOCR PP-OCRv5 and PPStructureV3.

    Supports two modes:
    - OCR mode:       Quick text detection + recognition (for inline images)
    - Structure mode: Full layout analysis → Markdown output (for full pages)

    Both modes are lazy-initialized to avoid loading models until needed.
    """

    def __init__(self):
        self._ocr = None          # PaddleOCR instance (lightweight text-only)
        self._structure = None     # PPStructureV3 instance (full layout)
        self._initialized_mode: Optional[str] = None

    def _ensure_initialized(self, mode: str = "structure") -> None:
        """
        Lazy-initialize the requested PaddleOCR pipeline.

        Args:
            mode: "ocr" for text-only, "structure" for full layout analysis
        """
        if mode == "ocr" and self._ocr is not None:
            return
        if mode == "structure" and self._structure is not None:
            return

        if not PADDLEOCR_AVAILABLE:
            raise RuntimeError(
                "paddleocr is not installed. "
                "Add 'paddleocr>=3.0.0' to requirements-extra.txt"
            )

        t0 = time.time()

        if mode == "ocr":
            from paddleocr import PaddleOCR
            logger.info("[PaddleOCR] Initializing OCR mode (PP-OCRv5)...")
            self._ocr = PaddleOCR(
                lang="vi",
                ocr_version="PP-OCRv5",
            )
            logger.info(
                f"[PaddleOCR] OCR mode ready in {time.time() - t0:.1f}s"
            )

        elif mode == "structure":
            from paddleocr import PPStructureV3
            logger.info(
                "[PaddleOCR] Initializing Structure mode (PPStructureV3)..."
            )
            self._structure = PPStructureV3(
                lang="vi",
                ocr_version="PP-OCRv5",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=True,
                use_seal_recognition=False,
                use_table_recognition=True,
                use_formula_recognition=True,
                use_chart_recognition=False,
                use_region_detection=False,
            )
            logger.info(
                f"[PaddleOCR] Structure mode ready in {time.time() - t0:.1f}s"
            )

        self._initialized_mode = mode

    # ------------------------------------------------------------------
    # Public API: Full document processing (Structure mode)
    # ------------------------------------------------------------------
    async def process_document(
        self,
        job_id: str,
        file_path: Path,
        settings_dict: dict = None,
    ) -> Dict[str, Any]:
        """
        Process a full document using PPStructureV3 (layout analysis → Markdown).

        Returns a dict matching the SuryaEngine output format:
        {
            "result": {
                "fullText": "...",
                "markdownText": "...",
                "structured": {...},
                "meta": {"pageCount": N, "language": "vi", "parser": "paddleocr"}
            }
        }

        Args:
            job_id: Job UUID string for logging
            file_path: Path to the input file (image or PDF)
            settings_dict: Optional settings (language, etc.)
        """
        settings_dict = settings_dict or {}
        loop = asyncio.get_event_loop()

        # Initialize in thread pool to avoid blocking the event loop
        await loop.run_in_executor(
            None, self._ensure_initialized, "structure"
        )

        t0 = time.time()
        logger.info(f"[PaddleOCR] Processing {file_path.name} (structure mode)")

        # Run PPStructureV3 prediction in thread pool
        results = await loop.run_in_executor(
            None, self._predict_structure, str(file_path)
        )

        # Extract markdown from results
        markdown_pages = []
        full_text_pages = []
        structured_data = {"pages": [], "images": []}

        for page_idx, result in enumerate(results):
            # PPStructureV3 result has .markdown attribute with .text
            page_md = ""
            if hasattr(result, "markdown") and result.markdown:
                page_md = getattr(result.markdown, "text", "")

            # Fallback: extract from text_contents if markdown is empty
            if not page_md and hasattr(result, "text_contents"):
                page_md = "\n".join(
                    getattr(tc, "text", str(tc))
                    for tc in result.text_contents
                    if tc
                )

            markdown_pages.append(page_md)

            # Plain text version (strip markdown syntax)
            plain = page_md
            for ch in ("#", "*", "_", "`", "~", "|", "-"):
                plain = plain.replace(ch, "")
            full_text_pages.append(plain.strip())

            # Collect structured layout info
            page_data = {
                "page": page_idx + 1,
                "blocks": [],
            }
            if hasattr(result, "layout") and result.layout:
                for block in result.layout:
                    block_info = {
                        "type": getattr(block, "label", "unknown"),
                        "bbox": getattr(block, "bbox", None),
                    }
                    page_data["blocks"].append(block_info)

                    # Track image blocks for potential sub-OCR
                    if block_info["type"] == "image":
                        structured_data["images"].append({
                            "page": page_idx + 1,
                            "bbox": block_info["bbox"],
                        })

            structured_data["pages"].append(page_data)

        # Concatenate pages
        full_text = "\n\n".join(full_text_pages)
        markdown_text = "\n\n---\n\n".join(markdown_pages)

        # Try using the official concatenation method if available
        if self._structure and markdown_pages:
            try:
                markdown_text = self._structure.concatenate_markdown_pages(
                    markdown_pages
                )
            except Exception:
                pass  # Fall back to manual join above

        elapsed = time.time() - t0
        page_count = len(results) or 1
        logger.info(
            f"[PaddleOCR] Done: {len(full_text)} chars, "
            f"{page_count} pages in {elapsed:.1f}s "
            f"({elapsed / page_count:.1f}s/page)"
        )

        return {
            "result": {
                "fullText": full_text,
                "markdownText": markdown_text,
                "structured": structured_data,
                "meta": {
                    "pageCount": page_count,
                    "language": settings_dict.get("language", "vi"),
                    "parser": "paddleocr",
                    "elapsed_seconds": round(elapsed, 2),
                },
            }
        }

    def _predict_structure(self, file_path: str) -> list:
        """Run PPStructureV3 prediction (synchronous, called in executor)."""
        return self._structure.predict(file_path)

    # ------------------------------------------------------------------
    # Public API: Quick OCR for a single image (OCR mode)
    # ------------------------------------------------------------------
    async def ocr_image(self, image) -> str:
        """
        Run quick text-only OCR on a single PIL Image.

        Args:
            image: PIL.Image.Image or file path string

        Returns:
            Extracted text as a single string
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, self._ensure_initialized, "ocr"
        )

        result = await loop.run_in_executor(
            None, self._predict_ocr, image
        )
        return result

    def _predict_ocr(self, image) -> str:
        """Run PaddleOCR text-only prediction (synchronous)."""
        import numpy as np
        from PIL import Image as PILImage

        # Convert PIL Image to numpy array if needed
        if isinstance(image, PILImage.Image):
            img_array = np.array(image)
        elif isinstance(image, str):
            img_array = image  # PaddleOCR can accept file paths
        elif isinstance(image, np.ndarray):
            img_array = image
        else:
            logger.warning(f"[PaddleOCR] Unsupported image type: {type(image)}")
            return ""

        try:
            results = self._ocr.predict(img_array)
            all_text = []
            for result in results:
                if hasattr(result, "rec_texts"):
                    all_text.extend(result.rec_texts)
                elif hasattr(result, "text"):
                    all_text.append(result.text)
            return "\n".join(all_text)
        except Exception as e:
            logger.error(f"[PaddleOCR] OCR prediction failed: {e}")
            return ""

    # ------------------------------------------------------------------
    # Public API: Process image crops (replaces Surya's process_crops)
    # ------------------------------------------------------------------
    async def process_crops(
        self,
        crops: List[Dict[str, Any]],
        page_image,
    ) -> str:
        """
        OCR cropped regions from a page image.
        Drop-in replacement for SuryaEngine.process_crops().

        Args:
            crops: List of dicts with "bbox" key [x1, y1, x2, y2]
            page_image: PIL Image of the full page

        Returns:
            Concatenated OCR text from all crops
        """
        if not crops:
            return ""

        all_text = []
        for crop_info in crops:
            bbox = crop_info.get("bbox", [])
            if len(bbox) < 4:
                continue

            try:
                x1, y1, x2, y2 = [int(v) for v in bbox[:4]]
                cropped = page_image.crop((x1, y1, x2, y2))

                if cropped.size[0] < 10 or cropped.size[1] < 10:
                    continue

                text = await self.ocr_image(cropped.convert("RGB"))
                if text.strip():
                    all_text.append(text)

            except Exception as e:
                logger.warning(f"[PaddleOCR] Failed to process crop: {e}")
                continue

        return "\n".join(all_text)
