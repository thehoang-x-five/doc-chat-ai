"""
OCR processing task — Super RAG Pipeline (Chained Ensemble).

Flow:
  Stage 1 — Structural Extraction
    • Images / Scanned PDFs  → SuryaEngine  (full-page vision OCR)
    • Digital PDFs / DOCX    → DocumentEngine (Docling layout parser)
      └─ If Docling detects embedded images → Surya Sub-OCR on each crop

  Stage 2 — Semantic Enrichment (if ENABLE_RAGANYTHING_PARSING)
    • Pass clean content_list into RAGAnything → Knowledge Graph

  Stage 3 — Standard Vector Indexing
    • Queue JobType.INDEX → ChunkingService → EmbeddingService → pgvector
"""
from uuid import UUID
from pathlib import Path
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
                job.status = JobStatus.RUNNING
                job.step = "initializing"
                job.progress = 0
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

                # ── Route 0: Direct Text (TXT / MD / CSV / HTML / XHTML) ──
                DIRECT_TEXT_EXTENSIONS = {'.txt', '.md', '.csv', '.html', '.xhtml'}
                if tmp_path.suffix.lower() in DIRECT_TEXT_EXTENSIONS:
                    logger.info(f"[Stage1] Route 0: Direct text read for {tmp_path.suffix}")
                    update_doc_progress(
                        session, doc_version.document, 30,
                        "Reading text file directly...",
                    )
                    try:
                        full_text = file_content.decode("utf-8", errors="ignore")
                        markdown_text = full_text
                        structured_json = {}
                        page_count = 1
                        parser_used = "direct"
                        logger.info(
                            f"[Stage1] Direct text OK: {len(full_text)} chars"
                        )
                    except Exception as e:
                        logger.warning(f"[Stage1] Direct text read failed: {e}")

                # ── Route 1: SuryaEngine (images / scanned PDFs) ──────
                try:
                    from app.core.engines.surya_engine import (
                        should_use_surya, SuryaEngine, SURYA_AVAILABLE,
                    )

                    if should_use_surya(tmp_path, config):
                        logger.info(f"[Stage1] Routing to SuryaEngine for {tmp_path.suffix}")
                        update_doc_progress(
                            session, doc_version.document, 25,
                            "Surya OCR (vision AI)...",
                        )

                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                        engine = SuryaEngine()
                        surya_result = loop.run_until_complete(
                            engine.process_document(
                                job_id=job_id,
                                file_path=tmp_path,
                                settings_dict={
                                    "parser": "surya",
                                    "parse_method": "vision_ocr",
                                    "language": language,
                                },
                            )
                        )
                        loop.close()

                        ocr_result = surya_result.get("result", {})
                        full_text = ocr_result.get("fullText", "")
                        markdown_text = ocr_result.get("markdownText", full_text)
                        structured_json = ocr_result.get("structured", {})
                        page_count = ocr_result.get("meta", {}).get("pageCount", 1)
                        language = ocr_result.get("meta", {}).get("language", "auto")
                        parser_used = "surya"

                        logger.info(
                            f"[Stage1] SuryaEngine OK: {len(full_text)} chars, "
                            f"{page_count} pages"
                        )

                except ImportError as e:
                    logger.warning(f"Surya not available: {e}")
                except Exception as e:
                    logger.error(f"SuryaEngine failed: {e}, falling back")
                    # If file is an image, Docling fallback won't help — retry instead
                    if file_ext.lower() in {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif', '.bmp', '.gif'}:
                        raise RuntimeError(f"Surya OCR failed for image {tmp_path.name}: {e}") from e

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
                        enhanced_text = ocr_result.get("enhancedText")

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

                        # ── Nested OCR: Surya sub-image extraction ────
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

                        if embedded_images and SURYA_AVAILABLE:
                            logger.info(
                                f"[Stage1] Nested OCR: {len(embedded_images)} "
                                f"embedded images detected — routing to Surya"
                            )
                            update_doc_progress(
                                session, doc_version.document, 35,
                                f"Surya sub-OCR ({len(embedded_images)} images)...",
                            )

                            # Load page images from file for cropping
                            try:
                                # Force GC to free Docling memory before loading Surya
                                import gc
                                gc.collect()
                                
                                from app.core.engines.surya_engine import SuryaEngine
                                from surya.input.load import load_from_file as surya_load
                                page_images, _ = surya_load(str(tmp_path))

                                surya_engine = SuryaEngine()
                                # Use lightweight mode: only load detection+recognition
                                # (skip layout+table_rec to save ~40% memory)
                                surya_engine._ensure_initialized(lightweight=True)
                                sub_loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(sub_loop)

                                sub_ocr_texts = []
                                # Group crops by page
                                crops_by_page = {}
                                for img_info in embedded_images:
                                    pg = img_info.get("page", 1) - 1  # 0-indexed
                                    bbox = img_info.get("bbox", {})
                                    abs_bbox = None
                                    
                                    if isinstance(bbox, dict):
                                        if "x1" in bbox:
                                            # Absolute pixel bbox from Docling PictureItem
                                            abs_bbox = [
                                                bbox["x1"], bbox["y1"],
                                                bbox["x2"], bbox["y2"],
                                            ]
                                        elif "x" in bbox and "width" in bbox:
                                            # Normalized bbox from layout blocks
                                            pw = img_info.get("page_width", 1)
                                            ph = img_info.get("page_height", 1)
                                            abs_bbox = [
                                                bbox["x"] * pw,
                                                bbox["y"] * ph,
                                                (bbox["x"] + bbox["width"]) * pw,
                                                (bbox["y"] + bbox["height"]) * ph,
                                            ]
                                    elif isinstance(bbox, (list, tuple)):
                                        abs_bbox = list(bbox[:4])
                                    
                                    if not abs_bbox:
                                        continue
                                        
                                    width = abs_bbox[2] - abs_bbox[0]
                                    height = abs_bbox[3] - abs_bbox[1]
                                    
                                    # Heuristic: Skip decorative images (tiny icons, bullets, tiny logos)
                                    if width < 50 or height < 50:
                                        logger.debug(f"Skipping tiny image {width}x{height} on page {pg+1}")
                                        continue
                                        
                                    # Heuristic: Skip highly skewed aspect ratios (likely dividers, separator lines)
                                    if height > 0 and (width / height > 15 or height / width > 15):
                                        logger.debug(f"Skipping skewed image {width}x{height} on page {pg+1}")
                                        continue
                                    
                                    if pg not in crops_by_page:
                                        crops_by_page[pg] = []
                                    crops_by_page[pg].append({"bbox": abs_bbox})

                                for pg_idx, crops in crops_by_page.items():
                                    if pg_idx < len(page_images):
                                        text = sub_loop.run_until_complete(
                                            surya_engine.process_crops(
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

                                parser_used = "docling+surya"

                            except Exception as sub_e:
                                logger.warning(
                                    f"[Stage1] Sub-OCR failed: {sub_e}, "
                                    f"continuing with Docling text only."
                                )
                                
                        elif tmp_path.suffix.lower() == ".docx" and SURYA_AVAILABLE:
                            # ── Position-aware DOCX image OCR ──
                            # Parse the DOCX XML to find images in their correct
                            # paragraph positions and insert OCR text inline.
                            logger.info("[Stage1] DOCX inline image OCR: parsing XML structure...")
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
                                        from app.core.engines.surya_engine import SuryaEngine
                                        from PIL import Image
                                        surya_engine = SuryaEngine()
                                        surya_engine._ensure_initialized(lightweight=True)

                                        media_ocr_cache = {}  # media_path → ocr text
                                        for rid, media_path in rid_to_media.items():
                                            if media_path in media_ocr_cache:
                                                continue
                                            try:
                                                img_data = docx_zip.read(media_path)
                                                pil_img = Image.open(io.BytesIO(img_data)).convert("RGB")
                                                res = surya_engine._recognition_predictor(
                                                    [pil_img],
                                                    det_predictor=surya_engine._detection_predictor,
                                                    highres_images=None
                                                )
                                                texts = []
                                                for r in res:
                                                    for line in getattr(r, "text_lines", []):
                                                        if line.text.strip():
                                                            texts.append(line.text)
                                                media_ocr_cache[media_path] = "\n".join(texts) if texts else ""
                                            except Exception as e:
                                                logger.warning(f"Failed to OCR {media_path}: {e}")
                                                media_ocr_cache[media_path] = ""

                                        # 3. Walk document.xml paragraphs in order,
                                        #    inserting image OCR text at the correct position
                                        doc_xml = docx_zip.read("word/document.xml")
                                        doc_root = ET.fromstring(doc_xml)

                                        # XML namespaces used in OOXML
                                        ns = {
                                            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
                                            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
                                            "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
                                            "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
                                            "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
                                        }

                                        # Find all paragraphs inside <w:body>
                                        body = doc_root.find(".//w:body", ns)
                                        if body is None:
                                            body = doc_root

                                        inline_parts = []  # list of text chunks in reading order
                                        img_count = 0

                                        for elem in body:
                                            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

                                            if tag == "p":
                                                # Extract plain text from this paragraph
                                                para_texts = []
                                                for t_elem in elem.iter(f"{{{ns['w']}}}t"):
                                                    if t_elem.text:
                                                        para_texts.append(t_elem.text)
                                                para_str = "".join(para_texts).strip()

                                                # Check if this paragraph contains any drawings
                                                drawings = list(elem.iter(f"{{{ns['w']}}}drawing"))
                                                img_texts_in_para = []
                                                for drawing in drawings:
                                                    # Find <a:blip r:embed="rIdX">
                                                    for blip in drawing.iter(f"{{{ns['a']}}}blip"):
                                                        embed_rid = blip.get(f"{{{ns['r']}}}embed")
                                                        if embed_rid and embed_rid in rid_to_media:
                                                            media_path = rid_to_media[embed_rid]
                                                            ocr_text = media_ocr_cache.get(media_path, "")
                                                            if ocr_text.strip():
                                                                img_count += 1
                                                                img_texts_in_para.append(ocr_text)

                                                # Build the paragraph output
                                                if para_str:
                                                    inline_parts.append(para_str)
                                                # Insert image OCR text RIGHT AFTER the paragraph text
                                                for it in img_texts_in_para:
                                                    inline_parts.append(f"[Image Text: {it}]")

                                            elif tag == "tbl":
                                                # Tables: extract text from all cells
                                                tbl_texts = []
                                                for t_elem in elem.iter(f"{{{ns['w']}}}t"):
                                                    if t_elem.text:
                                                        tbl_texts.append(t_elem.text)
                                                if tbl_texts:
                                                    inline_parts.append(" | ".join(tbl_texts))

                                        if img_count > 0:
                                            # Rebuild full_text and markdown_text with inline image text
                                            rebuilt = "\n\n".join(inline_parts)
                                            full_text = rebuilt
                                            markdown_text = rebuilt
                                            logger.info(
                                                f"[Stage1] DOCX inline OCR: inserted {img_count} "
                                                f"image(s) text at correct positions, "
                                                f"total {len(full_text)} chars"
                                            )
                                            parser_used = "docling+surya"
                                        else:
                                            logger.info("[Stage1] DOCX images had no extractable text")

                            except Exception as e:
                                logger.warning(f"[Stage1] Failed DOCX inline image OCR: {e}", exc_info=True)
                        else:
                            if embedded_images:
                                logger.info(
                                    f"[Stage1] {len(embedded_images)} images "
                                    f"found but Surya unavailable, skipping sub-OCR"
                                )

                        logger.info(
                            f"[Stage1] Docling OK: {len(full_text)} chars, "
                            f"{page_count} pages"
                        )

                    except ImportError:
                        logger.warning("Docling not available, using plaintext fallback")
                        full_text = file_content.decode("utf-8", errors="ignore")
                        markdown_text = full_text
                        structured_json = {}
                        page_count = 1
                        parser_used = "plaintext"
                    except Exception as e:
                        logger.error(f"Docling parsing failed: {e}")
                        full_text = file_content.decode("utf-8", errors="ignore")
                        markdown_text = full_text
                        structured_json = {}
                        page_count = 1
                        parser_used = "plaintext"

                logger.info(f"[Stage1] Parser used: {parser_used}")

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
