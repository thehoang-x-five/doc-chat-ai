"""
OCR processing task — Super RAG Pipeline (Chained Ensemble).

Flow:
  Stage 1 — Structural Extraction
    • Images / Scanned PDFs  → PaddleOCREngine (PPStructureV3 layout → Markdown)
    • Digital PDFs / DOCX    → DocumentEngine (Docling layout parser)
      └─ If Docling detects embedded images → PaddleOCR Sub-OCR on each crop
    • NO fallback — PaddleOCR is required. If unavailable, task fails immediately.

  Stage 2 — Semantic Enrichment (if ENABLE_RAGANYTHING_PARSING)
    • Pass clean content_list into RAGAnything → Knowledge Graph

  Stage 3 — Standard Vector Indexing
    • Queue JobType.INDEX → ChunkingService → EmbeddingService → pgvector
"""
import asyncio
from uuid import UUID
from pathlib import Path
from typing import Any, Dict, List
from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, joinedload

logger = get_task_logger(__name__)


# ---------------------------------------------------------------------------
# Module-level sync engine cache (prevents max_connections leak)
# ---------------------------------------------------------------------------
_sync_engine = None
_SyncSession = None

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".bmp", ".gif"}


def _safe_enhanced_text(original_text: str, enhanced_text: str | None) -> str | None:
    """Use AI-enhanced text only when it did not drop a meaningful amount."""
    if not enhanced_text:
        return None

    original_len = len(original_text.strip())
    enhanced_len = len(enhanced_text.strip())
    if original_len == 0:
        return enhanced_text

    min_len = int(original_len * 0.95)
    if enhanced_len < min_len:
        logger.warning(
            "[Stage1] Ignoring AI-enhanced text because it is shorter than source "
            "(original=%s chars, enhanced=%s chars)",
            original_len,
            enhanced_len,
        )
        return None

    return enhanced_text


def _get_sync_session():
    """Get or create module-level cached sync session factory."""
    global _sync_engine, _SyncSession
    if _SyncSession is None:
        from app.core.config import settings
        db_url = settings.database_url
        if "asyncpg" in db_url:
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        _sync_engine = create_engine(db_url, echo=False, pool_pre_ping=True)
        _SyncSession = sessionmaker(bind=_sync_engine, autocommit=False, autoflush=False)
    return _SyncSession()


def _load_pdf_page_images(file_path: Path) -> List[Any]:
    """Render PDF pages to images for targeted mixed-page OCR."""
    try:
        from pdf2image import convert_from_path

        return convert_from_path(str(file_path), dpi=200)
    except Exception as exc:
        logger.warning(
            "[Stage1] pdf2image page rendering unavailable for %s: %s",
            file_path.name,
            exc,
        )

    try:
        import fitz
        from PIL import Image as PILImage

        images: List[Any] = []
        with fitz.open(str(file_path)) as pdf_doc:
            for page in pdf_doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                images.append(
                    PILImage.frombytes(
                        "RGB",
                        [pix.width, pix.height],
                        pix.samples,
                    )
                )
        return images
    except Exception as exc:
        logger.warning(
            "[Stage1] PyMuPDF page rendering unavailable for %s: %s",
            file_path.name,
            exc,
        )
        return []


def _decode_text_bytes(file_content: bytes) -> str:
    """Decode text-like uploads with a conservative encoding fallback."""
    try:
        return file_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return file_content.decode("latin-1", errors="ignore")


def _extract_rtf_text(file_content: bytes) -> str:
    """Best-effort plain text extraction from RTF without external deps."""
    import re

    text = _decode_text_bytes(file_content)
    text = re.sub(r"\\par[d]?", "\n", text)
    text = re.sub(r"\\tab", "\t", text)
    text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", text)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
    text = re.sub(r"[{}]", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _extract_odt_text(file_content: bytes) -> str:
    """Extract visible text from an OpenDocument Text file."""
    import io
    import zipfile
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(io.BytesIO(file_content)) as archive:
        xml_data = archive.read("content.xml")

    root = ET.fromstring(xml_data)
    paragraphs: List[str] = []
    for elem in root.iter():
        if elem.tag.endswith("}p") or elem.tag.endswith("}h"):
            text = "".join(elem.itertext()).strip()
            if text:
                paragraphs.append(text)
    return "\n\n".join(paragraphs).strip()


def _extract_direct_text(file_content: bytes, file_ext: str) -> str:
    """Extract text for formats handled without OCR/Docling."""
    if file_ext == ".rtf":
        return _extract_rtf_text(file_content)
    if file_ext == ".odt":
        return _extract_odt_text(file_content)

    text = _decode_text_bytes(file_content)
    if file_ext == ".json":
        try:
            import json

            return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
        except Exception:
            return text
    return text


def _extract_image_text_tesseract(file_path: Path) -> str:
    """Extract image text with the system Tesseract binary as a lightweight fallback."""
    import subprocess

    result = subprocess.run(
        [
            "tesseract",
            str(file_path),
            "stdout",
            "-l",
            "vie+eng",
            "--psm",
            "6",
        ],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(
            f"Tesseract failed with code {result.returncode}: {stderr[:500]}"
        )
    return (result.stdout or "").strip()


def _extract_mixed_pdf_page_ocr(
    file_path: Path,
    docling_pages: List[Dict[str, Any]],
    paddle_engine: Any,
) -> List[Dict[str, Any]]:
    """OCR only the low-text pages of a mixed PDF using PaddleOCR."""
    from app.core.config import settings

    min_chars = max(
        int(settings.PDF_TEXT_LAYER_MIN_CHARS),
        int(settings.PDF_MIXED_PAGE_MIN_TEXT_CHARS),
    )
    candidate_pages: List[int] = []
    for page in docling_pages or []:
        page_number = page.get("page")
        if not isinstance(page_number, int) or page_number < 1:
            continue
        page_text = (page.get("text") or "").strip()
        if len(page_text) < min_chars:
            candidate_pages.append(page_number)

    if not candidate_pages:
        return []

    page_images = _load_pdf_page_images(file_path)
    if not page_images:
        raise RuntimeError(
            f"Mixed PDF page OCR required for {file_path.name} but page rendering failed"
        )

    page_results: List[Dict[str, Any]] = []
    page_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(page_loop)
    try:
        for page_number in candidate_pages:
            page_idx = page_number - 1
            if page_idx >= len(page_images):
                continue
            ocr_text = page_loop.run_until_complete(
                paddle_engine.ocr_image(page_images[page_idx])
            )
            ocr_text = (ocr_text or "").strip()
            if not ocr_text:
                continue
            page_results.append(
                {
                    "type": "text",
                    "page_idx": page_idx,
                    "page_number": page_number,
                    "section_title": f"Scanned Page {page_number}",
                    "text": ocr_text,
                }
            )
    finally:
        page_loop.close()
        asyncio.set_event_loop(None)

    return page_results


@shared_task(
    bind=True,
    name="app.queue.tasks.ocr.process_ocr",
    queue="ocr",
    max_retries=3,
    default_retry_delay=60,
)
def process_ocr(self, job_id: str, document_version_id: str, config: dict = None):
    """
    Process OCR for a document version using the Super RAG Pipeline.

    Args:
        job_id: Job UUID string
        document_version_id: DocumentVersion UUID string
        config: Optional configuration dict
    """
    from app.core.config import settings
    from app.db.models import DocumentVersion, Job, JobStatus, Document, JobType
    from app.storage.object_store import ObjectStore

    logger.info(f"[SuperRAG] Starting OCR job {job_id} for version {document_version_id}")
    config = config or {}

    def update_doc_progress(session, doc, progress: int, step: str):
        """Helper to update document processing progress."""
        if doc:
            doc.processing_progress = progress
            doc.processing_step = step
            session.commit()

    try:
        with _get_sync_session() as session:
            # ── Mark job RUNNING ──────────────────────────────────────
            job = session.execute(
                select(Job).where(Job.id == UUID(job_id))
            ).scalar_one_or_none()

            if job:
                config = {**(job.config_json or {}), **config}
                job.status = JobStatus.RUNNING
                job.step = "initializing"
                job.progress = 0
                job.error_message = None
                session.commit()

            # ── Load document version ─────────────────────────────────
            result = session.execute(
                select(DocumentVersion)
                .options(joinedload(DocumentVersion.document))
                .where(DocumentVersion.id == UUID(document_version_id))
            )
            doc_version = result.unique().scalar_one_or_none()

            if not doc_version:
                raise ValueError(f"Document version {document_version_id} not found")

            if doc_version.document:
                if doc_version.document.status in ["CANCELED", "DELETED"]:
                    logger.info(f"Document {document_version_id} was {doc_version.document.status}. Aborting OCR job.")
                    if job:
                        job.status = JobStatus.DONE
                        job.step = "canceled"
                        session.commit()
                    return {"status": "canceled"}
                    
                doc_version.document.status = "INDEXING"
                doc_version.document.processing_progress = 5
                doc_version.document.processing_step = "Initializing..."
                session.commit()

            # ── Download file ─────────────────────────────────────────
            if job:
                job.step = "downloading"
                job.progress = 10
                session.commit()
            update_doc_progress(session, doc_version.document, 10, "Downloading file...")

            storage = ObjectStore()
            file_key = doc_version.original_file_key

            if file_key.startswith("http"):
                import httpx
                response = httpx.get(file_key, follow_redirects=True)
                file_content = response.content
                file_ext = Path(file_key).suffix or ".html"
            else:
                file_content = storage.download(file_key)
                file_ext = Path(file_key).suffix

            # Save to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
                tmp.write(file_content)
                tmp_path = Path(tmp.name)

            try:
                # ==========================================================
                #  STAGE 1 — Structural Extraction
                # ==========================================================
                if job:
                    job.step = "parsing"
                    job.progress = 20
                    session.commit()
                update_doc_progress(session, doc_version.document, 20, "Analyzing document type...")

                parser_used = None
                full_text = ""
                markdown_text = ""
                structured_json = {}
                page_count = 1
                language = config.get("language", "auto")
                mixed_page_markdown_appendix = ""
                routing_metadata = {
                    "input_extension": tmp_path.suffix.lower(),
                    "parser_override": config.get("parser"),
                    "pdf_content_type": None,
                    "routing_decision": None,
                    "sub_ocr_used": False,
                    "mixed_page_ocr_used": False,
                    "mixed_page_ocr_pages": [],
                }

                if tmp_path.suffix.lower() == ".pdf":
                    from app.core.engines.pdf_routing import detect_pdf_content_type

                    if config.get("parser") == "paddleocr":
                        routing_metadata["pdf_content_type"] = "forced_paddleocr"
                        routing_metadata["routing_decision"] = "forced_paddleocr"
                    elif config.get("parser") == "docling":
                        routing_metadata["pdf_content_type"] = "forced_docling"
                        routing_metadata["routing_decision"] = "forced_docling"
                    else:
                        pdf_routing = detect_pdf_content_type(tmp_path)
                        routing_metadata.update(pdf_routing)
                        config["pdf_content_type"] = pdf_routing.get("content_type")
                        routing_metadata["routing_decision"] = (
                            "scanned_pdf_paddleocr"
                            if pdf_routing.get("content_type") == "scanned"
                            else "digital_pdf_docling"
                            if pdf_routing.get("content_type") == "digital"
                            else "mixed_pdf_docling_plus_paddle_page_ocr"
                        )
                        logger.info(
                            "[Stage1] PDF routing decided: %s",
                            routing_metadata["routing_decision"],
                        )

                # ── Route 0: Direct Text (TXT / MD / CSV / JSON / RTF / ODT / HTML / XHTML) ──
                DIRECT_TEXT_EXTENSIONS = {
                    '.txt', '.md', '.csv', '.json', '.rtf', '.odt', '.html', '.xhtml'
                }
                if tmp_path.suffix.lower() in DIRECT_TEXT_EXTENSIONS:
                    logger.info(f"[Stage1] Route 0: Direct text read for {tmp_path.suffix}")
                    update_doc_progress(
                        session, doc_version.document, 30,
                        "Reading text file directly...",
                    )
                    try:
                        full_text = _extract_direct_text(file_content, tmp_path.suffix.lower())
                        markdown_text = full_text
                        structured_json = {
                            "source_format": tmp_path.suffix.lower().lstrip("."),
                        }
                        page_count = 1
                        parser_used = "direct"
                        logger.info(
                            f"[Stage1] Direct text OK: {len(full_text)} chars"
                        )
                    except Exception as e:
                        logger.warning(f"[Stage1] Direct text read failed: {e}")

                # ── Route 1: PaddleOCREngine (images / scanned PDFs) ──────
                try:
                    from app.core.engines.paddleocr_engine import (
                        should_use_paddleocr, PaddleOCREngine, PADDLEOCR_AVAILABLE,
                    )

                    if should_use_paddleocr(tmp_path, config):
                        routing_metadata["routing_decision"] = (
                            routing_metadata["routing_decision"]
                            or ("image_paddleocr" if tmp_path.suffix.lower() != ".pdf" else "pdf_paddleocr")
                        )
                        logger.info(f"[Stage1] Routing to PaddleOCREngine for {tmp_path.suffix}")
                        update_doc_progress(
                            session, doc_version.document, 25,
                            "PaddleOCR (PPStructureV3 layout)...",
                        )

                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                        engine = PaddleOCREngine()
                        paddle_result = loop.run_until_complete(
                            engine.process_document(
                                job_id=job_id,
                                file_path=tmp_path,
                                settings_dict={
                                    "parser": "paddleocr",
                                    "parse_method": "pp_structurev3",
                                    "language": language,
                                },
                            )
                        )
                        loop.close()

                        ocr_result = paddle_result.get("result", {})
                        full_text = ocr_result.get("fullText", "")
                        markdown_text = ocr_result.get("markdownText", full_text)
                        structured_json = ocr_result.get("structured", {})
                        page_count = ocr_result.get("meta", {}).get("pageCount", 1)
                        language = ocr_result.get("meta", {}).get("language", "auto")
                        parser_used = "paddleocr"

                        logger.info(
                            f"[Stage1] PaddleOCREngine OK: {len(full_text)} chars, "
                            f"{page_count} pages"
                        )

                except ImportError as e:
                    logger.error(f"PaddleOCR not available: {e}")
                    raise RuntimeError(
                        f"PaddleOCR is REQUIRED but not installed: {e}. "
                        f"Please add paddlepaddle and paddleocr to requirements-extra.txt and rebuild."
                    ) from e
                except Exception as e:
                    logger.error(f"PaddleOCREngine failed: {e}")
                    if tmp_path.suffix.lower() in IMAGE_EXTENSIONS:
                        logger.warning(
                            "[Stage1] Falling back to Tesseract for image %s after PaddleOCR failure",
                            tmp_path.name,
                        )
                        update_doc_progress(
                            session,
                            doc_version.document,
                            30,
                            "Tesseract image OCR fallback...",
                        )
                        try:
                            full_text = _extract_image_text_tesseract(tmp_path)
                            markdown_text = full_text
                            structured_json = {
                                "source_format": tmp_path.suffix.lower().lstrip("."),
                                "parser": "tesseract",
                                "fallback_from": "paddleocr",
                                "paddleocr_error": str(e),
                            }
                            page_count = 1
                            parser_used = "tesseract"
                            routing_metadata["routing_decision"] = "image_tesseract_fallback"
                            logger.info(
                                "[Stage1] Tesseract fallback OK: %s chars",
                                len(full_text),
                            )
                        except Exception as fallback_error:
                            logger.error(
                                "Tesseract fallback failed for %s: %s",
                                tmp_path.name,
                                fallback_error,
                            )
                            raise RuntimeError(
                                f"PaddleOCR failed for {tmp_path.name}: {e}; "
                                f"Tesseract fallback also failed: {fallback_error}"
                            ) from fallback_error
                    else:
                        raise RuntimeError(f"PaddleOCR failed for {tmp_path.name}: {e}") from e

                # ── Route 2: Docling (digital PDFs / DOCX / XLSX …) ──
                if parser_used is None:
                    logger.info(f"[Stage1] Routing to Docling for {tmp_path.suffix}")
                    update_doc_progress(
                        session, doc_version.document, 25,
                        "Docling parsing (layout analysis)...",
                    )
                    try:
                        from app.core.engines.ocr import DocumentEngine

                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                        engine = DocumentEngine()
                        docling_result = loop.run_until_complete(
                            engine.process_document(
                                job_id=job_id,
                                file_path=tmp_path,
                                settings_dict={
                                    "parser": config.get("parser", "docling"),
                                    "parse_method": config.get("parse_method", "auto"),
                                    "language": language,
                                },
                            )
                        )
                        loop.close()

                        ocr_result = docling_result.get("result", {})
                        original_text = ocr_result.get("fullText", "")
                        enhanced_text = _safe_enhanced_text(
                            original_text,
                            ocr_result.get("enhancedText"),
                        )

                        full_text = enhanced_text if enhanced_text else original_text
                        markdown_text = (
                            enhanced_text
                            if enhanced_text
                            else ocr_result.get("markdownText", original_text)
                        )
                        structured_json = ocr_result.get("structured", {})
                        page_count = ocr_result.get("meta", {}).get("pageCount", 1)
                        language = ocr_result.get("meta", {}).get("language", "auto")
                        parser_used = "docling"

                        # ── Nested OCR: PaddleOCR sub-image extraction ────
                        embedded_images = structured_json.get("images", [])
                        if not embedded_images:
                            # Also check layout blocks for image-type regions
                            layout_pages = ocr_result.get("layout", {}).get("pages", [])
                            for lp in layout_pages:
                                for blk in lp.get("blocks", []):
                                    if blk.get("type") == "image":
                                        embedded_images.append({
                                            **blk,
                                            "page": lp.get("page", 1),
                                            "page_width": lp.get("width", 1),
                                            "page_height": lp.get("height", 1),
                                        })

                        _sub_ocr_available = False
                        _sub_ocr_engine = None
                        _sub_ocr_label = "paddleocr"
                        try:
                            from app.core.engines.paddleocr_engine import PaddleOCREngine as _SubEngine, PADDLEOCR_AVAILABLE as _SUB_AVAIL
                            if _SUB_AVAIL:
                                _sub_ocr_available = True
                                _sub_ocr_engine = _SubEngine()
                                _sub_ocr_label = "paddleocr"
                        except ImportError:
                            pass
                        if not _sub_ocr_available:
                            logger.warning(
                                "[Stage1] PaddleOCR sub-OCR engine not available. "
                                "Embedded images will be skipped."
                            )

                        mixed_page_ocr_results = []
                        if (
                            tmp_path.suffix.lower() == ".pdf"
                            and config.get("pdf_content_type") == "mixed"
                            and settings.PDF_MIXED_PAGE_OCR
                        ):
                            if not _sub_ocr_available or _sub_ocr_engine is None:
                                raise RuntimeError(
                                    "Mixed PDF requires PaddleOCR page OCR but PaddleOCR is unavailable"
                                )

                            docling_pages = ocr_result.get("pages", [])
                            mixed_page_ocr_results = _extract_mixed_pdf_page_ocr(
                                tmp_path,
                                docling_pages,
                                _sub_ocr_engine,
                            )
                            if mixed_page_ocr_results:
                                routing_metadata["sub_ocr_used"] = True
                                routing_metadata["mixed_page_ocr_used"] = True
                                routing_metadata["mixed_page_ocr_pages"] = [
                                    item["page_number"] for item in mixed_page_ocr_results
                                ]
                                structured_json["mixed_page_ocr"] = mixed_page_ocr_results

                                mixed_page_text = "\n\n".join(
                                    item["text"] for item in mixed_page_ocr_results if item.get("text")
                                )
                                if mixed_page_text:
                                    full_text += (
                                        "\n\n--- Mixed PDF Page OCR ---\n"
                                        f"{mixed_page_text}"
                                    )
                                    mixed_page_markdown_appendix = "\n\n".join(
                                        (
                                            f"### Scanned Page {item['page_number']}\n\n{item['text']}"
                                        )
                                        for item in mixed_page_ocr_results
                                        if item.get("text")
                                    )
                                    parser_used = "docling+paddleocr"
                                    logger.info(
                                        "[Stage1] Mixed PDF page OCR recovered %s chars across pages %s",
                                        len(mixed_page_text),
                                        routing_metadata["mixed_page_ocr_pages"],
                                    )
                            else:
                                logger.info(
                                    "[Stage1] Mixed PDF route selected, but no low-text pages required PaddleOCR"
                                )

                        if embedded_images and _sub_ocr_available and _sub_ocr_label == "paddleocr":
                            routing_metadata["sub_ocr_used"] = True
                            logger.info(
                                f"[Stage1] Nested OCR: {len(embedded_images)} "
                                f"embedded images detected — routing to PaddleOCR"
                            )
                            update_doc_progress(
                                session, doc_version.document, 35,
                                f"PaddleOCR sub-OCR ({len(embedded_images)} images)...",
                            )

                            # Load page images from file for cropping
                            try:
                                import gc
                                gc.collect()

                                from PIL import Image as PILImage
                                page_images = []
                                if tmp_path.suffix.lower() == '.pdf':
                                    page_images = _load_pdf_page_images(tmp_path)
                                else:
                                    page_images = [PILImage.open(str(tmp_path)).convert("RGB")]

                                paddle_engine = _sub_ocr_engine
                                sub_loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(sub_loop)

                                sub_ocr_texts = []
                                crops_by_page = {}
                                for img_info in embedded_images:
                                    pg = img_info.get("page", 1) - 1
                                    bbox = img_info.get("bbox", {})
                                    abs_bbox = None
                                    
                                    if isinstance(bbox, dict):
                                        if "x1" in bbox:
                                            abs_bbox = [bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]]
                                        elif "x" in bbox and "width" in bbox:
                                            pw = img_info.get("page_width", 1)
                                            ph = img_info.get("page_height", 1)
                                            abs_bbox = [
                                                bbox["x"] * pw, bbox["y"] * ph,
                                                (bbox["x"] + bbox["width"]) * pw,
                                                (bbox["y"] + bbox["height"]) * ph,
                                            ]
                                    elif isinstance(bbox, (list, tuple)):
                                        abs_bbox = list(bbox[:4])
                                    
                                    if not abs_bbox:
                                        continue
                                    width = abs_bbox[2] - abs_bbox[0]
                                    height = abs_bbox[3] - abs_bbox[1]
                                    if width < 50 or height < 50:
                                        continue
                                    if height > 0 and (width / height > 15 or height / width > 15):
                                        continue
                                    
                                    if pg not in crops_by_page:
                                        crops_by_page[pg] = []
                                    crops_by_page[pg].append({"bbox": abs_bbox})

                                for pg_idx, crops in crops_by_page.items():
                                    if pg_idx < len(page_images):
                                        text = sub_loop.run_until_complete(
                                            paddle_engine.process_crops(
                                                crops, page_images[pg_idx]
                                            )
                                        )
                                        if text.strip():
                                            sub_ocr_texts.append(text)

                                sub_loop.close()

                                if sub_ocr_texts:
                                    sub_text = "\n\n".join(sub_ocr_texts)
                                    full_text += f"\n\n--- Embedded Image Text ---\n{sub_text}"
                                    markdown_text += (
                                        f"\n\n---\n\n"
                                        f"### Embedded Image Text\n\n{sub_text}"
                                    )
                                    logger.info(
                                        f"[Stage1] Sub-OCR extracted "
                                        f"{len(sub_text)} chars from "
                                        f"{len(embedded_images)} images"
                                    )

                                parser_used = "docling+paddleocr"

                            except Exception as sub_e:
                                logger.warning(
                                    f"[Stage1] PaddleOCR Sub-OCR failed: {sub_e}, "
                                    f"continuing with Docling text only."
                                )

                        elif embedded_images and not _sub_ocr_available:
                            logger.warning(
                                f"[Stage1] {len(embedded_images)} embedded images detected "
                                f"but PaddleOCR sub-OCR is not available. Skipping image OCR."
                            )

                        elif tmp_path.suffix.lower() == ".docx" and _sub_ocr_available:
                            # ── Position-aware DOCX image OCR ──
                            # Parse the DOCX XML to find images in their correct
                            # paragraph positions and insert OCR text inline.
                            logger.info(f"[Stage1] DOCX inline image OCR (via {_sub_ocr_label}): parsing XML structure...")
                            import zipfile
                            import io
                            import xml.etree.ElementTree as ET
                            try:
                                with zipfile.ZipFile(tmp_path, "r") as docx_zip:
                                    # 1. Build rId → media filename map from relationships
                                    rid_to_media = {}
                                    try:
                                        rels_xml = docx_zip.read("word/_rels/document.xml.rels")
                                        rels_root = ET.fromstring(rels_xml)
                                        for rel in rels_root:
                                            target = rel.get("Target", "")
                                            if target.startswith("media/"):
                                                rid_to_media[rel.get("Id")] = f"word/{target}"
                                    except Exception:
                                        pass

                                    if not rid_to_media:
                                        logger.info("[Stage1] No image relationships found in DOCX")
                                    else:
                                        logger.info(f"[Stage1] Found {len(rid_to_media)} image refs in DOCX rels")

                                        # 2. Pre-OCR all unique media files
                                        from PIL import Image

                                        if _sub_ocr_label == "paddleocr":
                                            paddle_eng = _sub_ocr_engine
                                            docx_loop = asyncio.new_event_loop()
                                            asyncio.set_event_loop(docx_loop)

                                        media_ocr_cache = {}
                                        for rid, media_path in rid_to_media.items():
                                            if media_path in media_ocr_cache:
                                                continue
                                            try:
                                                img_data = docx_zip.read(media_path)
                                                pil_img = Image.open(io.BytesIO(img_data)).convert("RGB")

                                                if _sub_ocr_label == "paddleocr":
                                                    ocr_text = docx_loop.run_until_complete(
                                                        paddle_eng.ocr_image(pil_img)
                                                    )
                                                    media_ocr_cache[media_path] = ocr_text
                                                else:
                                                    logger.warning(
                                                        f"PaddleOCR not available for DOCX inline image OCR. "
                                                        f"Skipping image: {media_path}"
                                                    )
                                                    media_ocr_cache[media_path] = ""
                                            except Exception as e:
                                                logger.warning(f"Failed to OCR {media_path}: {e}")
                                                media_ocr_cache[media_path] = ""

                                        if _sub_ocr_label == "paddleocr":
                                            docx_loop.close()

                                        # 3. Walk document.xml paragraphs in order
                                        doc_xml = docx_zip.read("word/document.xml")
                                        doc_root = ET.fromstring(doc_xml)

                                        ns = {
                                            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
                                            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
                                            "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
                                            "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
                                            "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
                                        }

                                        body = doc_root.find(".//w:body", ns)
                                        if body is None:
                                            body = doc_root

                                        inline_parts = []
                                        img_count = 0

                                        for elem in body:
                                            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

                                            if tag == "p":
                                                para_texts = []
                                                for t_elem in elem.iter(f"{{{ns['w']}}}t"):
                                                    if t_elem.text:
                                                        para_texts.append(t_elem.text)
                                                para_str = "".join(para_texts).strip()

                                                drawings = list(elem.iter(f"{{{ns['w']}}}drawing"))
                                                img_texts_in_para = []
                                                for drawing in drawings:
                                                    for blip in drawing.iter(f"{{{ns['a']}}}blip"):
                                                        embed_rid = blip.get(f"{{{ns['r']}}}embed")
                                                        if embed_rid and embed_rid in rid_to_media:
                                                            media_path = rid_to_media[embed_rid]
                                                            ocr_text = media_ocr_cache.get(media_path, "")
                                                            if ocr_text.strip():
                                                                img_count += 1
                                                                img_texts_in_para.append(ocr_text)

                                                if para_str:
                                                    inline_parts.append(para_str)
                                                for it in img_texts_in_para:
                                                    inline_parts.append(f"[Image Text: {it}]")

                                            elif tag == "tbl":
                                                tbl_texts = []
                                                for t_elem in elem.iter(f"{{{ns['w']}}}t"):
                                                    if t_elem.text:
                                                        tbl_texts.append(t_elem.text)
                                                if tbl_texts:
                                                    inline_parts.append(" | ".join(tbl_texts))

                                        if img_count > 0:
                                            rebuilt = "\n\n".join(inline_parts)
                                            full_text = rebuilt
                                            markdown_text = rebuilt
                                            logger.info(
                                                f"[Stage1] DOCX inline OCR ({_sub_ocr_label}): inserted {img_count} "
                                                f"image(s), total {len(full_text)} chars"
                                            )
                                            parser_used = f"docling+{_sub_ocr_label}"
                                            routing_metadata["sub_ocr_used"] = True
                                        else:
                                            logger.info("[Stage1] DOCX images had no extractable text")

                            except Exception as e:
                                logger.warning(f"[Stage1] Failed DOCX inline image OCR: {e}", exc_info=True)
                        else:
                            if embedded_images and not _sub_ocr_available:
                                logger.info(
                                    f"[Stage1] {len(embedded_images)} images "
                                    f"found but no OCR engine available, skipping sub-OCR"
                                )

                        logger.info(
                            f"[Stage1] Docling OK: {len(full_text)} chars, "
                            f"{page_count} pages"
                        )

                    except ImportError as e:
                        logger.error("Docling not available: %s", e)
                        raise RuntimeError(
                            f"Docling is REQUIRED for {tmp_path.suffix.lower()} files but is not installed: {e}"
                        ) from e
                    except Exception as e:
                        logger.error(f"Docling parsing failed: {e}")
                        raise RuntimeError(
                            f"Docling failed for {tmp_path.name}: {e}"
                        ) from e

                logger.info(f"[Stage1] Parser used: {parser_used}")
                if parser_used and not routing_metadata["routing_decision"]:
                    routing_metadata["routing_decision"] = f"{parser_used}_default"

                # ==========================================================
                #  STAGE 1.5 — Normalize + Quality Gate
                # ==========================================================
                from app.queue.tasks.normalize import (
                    normalize_parser_output, quality_check,
                )

                normalized = normalize_parser_output(
                    parser_used=parser_used or "unknown",
                    full_text=full_text,
                    markdown_text=markdown_text,
                    structured_json=structured_json,
                    page_count=page_count,
                    language=language,
                )
                logger.info(
                    f"[Stage1.5] Normalized: {normalized['stats']}"
                )

                quality_ok, quality_reason = quality_check(normalized)
                if not quality_ok:
                    logger.warning(
                        f"[Stage1.5] Quality gate FAILED: {quality_reason}"
                    )
                    if doc_version.document:
                        doc_version.document.status = "FAILED"
                        doc_version.document.processing_step = (
                            f"Quality check failed: {quality_reason[:200]}"
                        )
                    if job:
                        job.status = JobStatus.ERROR
                        job.error_message = quality_reason
                    session.commit()
                    return {
                        "status": "failed",
                        "reason": quality_reason,
                    }

                logger.info("[Stage1.5] Quality gate PASSED")

                if mixed_page_markdown_appendix:
                    markdown_text += (
                        "\n\n---\n\n## Mixed PDF PaddleOCR Recovery\n\n"
                        f"{mixed_page_markdown_appendix}"
                    )

                if settings.STRICT_NEO4J and not settings.ENABLE_RAGANYTHING_PARSING:
                    raise RuntimeError(
                        "STRICT_NEO4J requires ENABLE_RAGANYTHING_PARSING=true"
                    )

                # ==========================================================
                #  STAGE 3 — Store outputs & queue Vector Indexing
                # ==========================================================
                
                logger.info(f"[Stage3] Final parsed text length: {len(full_text)} chars (Document layout: {parser_used})")
                if len(full_text) < 100:
                    logger.warning(f"[Stage3] Extremely short or empty extracted text: {full_text!r}")
                    
                if job:
                    job.step = "storing"
                    job.progress = 70
                    session.commit()
                update_doc_progress(
                    session, doc_version.document, 70, "Storing outputs..."
                )

                workspace_id = (
                    str(doc_version.document.workspace_id)
                    if doc_version.document
                    else "unknown"
                )
                doc_id = str(doc_version.document_id)
                version = doc_version.version

                # Store extracted text
                text_key = f"outputs/{workspace_id}/{doc_id}/v{version}/text.txt"
                storage.upload(
                    text_key,
                    full_text.encode("utf-8"),
                    content_type="text/plain",
                )

                update_doc_progress(
                    session, doc_version.document, 80, "Saving markdown..."
                )

                # Store markdown
                md_key = f"outputs/{workspace_id}/{doc_id}/v{version}/content.md"
                storage.upload(
                    md_key,
                    markdown_text.encode("utf-8"),
                    content_type="text/markdown",
                )

                # Store structured JSON (with canonical content_list for enrichment)
                import json

                json_key = f"outputs/{workspace_id}/{doc_id}/v{version}/structured.json"
                structured_json["parser_used"] = parser_used
                structured_json["routing"] = routing_metadata
                structured_json["content_list"] = normalized.get("content_list", [])
                structured_json["detected_language"] = normalized.get("language", language)
                structured_json["normalize_stats"] = normalized.get("stats", {})

                def _json_default(obj):
                    """Handle non-serializable types from DoclingDocument."""
                    import datetime
                    if isinstance(obj, (datetime.datetime, datetime.date)):
                        return obj.isoformat()
                    if hasattr(obj, '__str__'):
                        return str(obj)
                    return None

                storage.upload(
                    json_key,
                    json.dumps(structured_json, default=_json_default, ensure_ascii=False).encode("utf-8"),
                    content_type="application/json",
                )

                update_doc_progress(
                    session, doc_version.document, 90, "Finalizing..."
                )

                # Update document version
                doc_version.extracted_text_key = text_key
                doc_version.extracted_md_key = md_key
                doc_version.structured_json_key = json_key
                doc_version.page_count = page_count
                doc_version.language_detected = normalized.get("language", language)
                doc_version.parser = parser_used or doc_version.parser
                doc_version.parse_method = (
                    "pp_structurev3"
                    if parser_used == "paddleocr"
                    else config.get("parse_method", "auto")
                )

                # Queue INDEX job (Stage 3 — Vector Indexing)
                index_job = Job(
                    workspace_id=(
                        doc_version.document.workspace_id
                        if doc_version.document
                        else None
                    ),
                    document_version_id=doc_version.id,
                    type=JobType.INDEX,
                    status=JobStatus.QUEUED,
                    config_json=config,
                )
                session.add(index_job)

                # Queue ENRICHMENT job (async, parallel with INDEX)
                enrichment_job = None
                if settings.ENABLE_RAGANYTHING_PARSING and full_text.strip():
                    enrichment_job = Job(
                        workspace_id=(
                            doc_version.document.workspace_id
                            if doc_version.document
                            else None
                        ),
                        document_version_id=doc_version.id,
                        type=JobType.ENRICHMENT,
                        status=JobStatus.QUEUED,
                        config_json=config,
                    )
                    session.add(enrichment_job)

                if doc_version.document:
                    doc_version.document.processing_progress = 95
                    doc_version.document.processing_step = "Queueing for Indexing..."

                session.commit()

                # Dispatch the Index task
                try:
                    from app.queue.tasks.index import process_index

                    process_index.delay(
                        str(index_job.id),
                        str(doc_version.id),
                        config,
                    )
                    logger.info(f"[Stage3] Queued INDEX job {index_job.id}")
                except Exception as e:
                    logger.error(f"[Stage3] Failed to queue INDEX job: {e}")

                # Dispatch the Enrichment task (async, separate worker)
                if enrichment_job:
                    try:
                        from app.queue.tasks.enrichment import process_enrichment

                        process_enrichment.delay(
                            str(enrichment_job.id),
                            str(doc_version.id),
                            config,
                        )
                        logger.info(
                            f"[Stage3] Queued ENRICHMENT job {enrichment_job.id}"
                        )
                    except Exception as e:
                        logger.error(
                            f"[Stage3] Failed to queue ENRICHMENT job: {e}"
                        )
                else:
                    if not settings.ENABLE_RAGANYTHING_PARSING:
                        logger.info(
                            "[Stage3] Enrichment skipped "
                            "(ENABLE_RAGANYTHING_PARSING=false)"
                        )

                # Mark OCR job as done
                if job:
                    job.status = JobStatus.DONE
                    job.step = "completed"
                    job.progress = 100
                    job.error_message = None
                    session.commit()

                logger.info(
                    f"[SuperRAG] OCR job {job_id} completed — "
                    f"parser={parser_used}, "
                    f"enrichment={'queued' if enrichment_job else 'skipped'}"
                )
                return {"status": "success", "job_id": job_id, "parser": parser_used}

            finally:
                # Cleanup temp file
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    except Exception as e:
        logger.error(f"[SuperRAG] OCR job {job_id} failed: {e}", exc_info=True)

        # Update job status to ERROR
        try:
            with _get_sync_session() as session:
                job = session.execute(
                    select(Job).where(Job.id == UUID(job_id))
                ).scalar_one_or_none()
                if job:
                    job.status = JobStatus.ERROR
                    job.error_message = str(e)
                    session.commit()

                # Also mark document as FAILED
                dv = session.execute(
                    select(DocumentVersion)
                    .options(joinedload(DocumentVersion.document))
                    .where(DocumentVersion.id == UUID(document_version_id))
                ).unique().scalar_one_or_none()
                if dv and dv.document:
                    dv.document.status = "FAILED"
                    dv.document.processing_step = f"Error: {str(e)[:200]}"
                    session.commit()
        except Exception:
            pass

        # Retry if possible
        raise self.retry(exc=e)
