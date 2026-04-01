"""
Enrichment task — Async RAG-Anything Knowledge Graph enrichment.

This task was extracted from ocr.py Stage 2 to run as a separate
Celery task on the 'enrichment' queue, enabling parallel execution
with the Index worker.

Flow:
  1. Load structured.json from MinIO (has content_list)
  2. Initialize RAGAnything pipeline
  3. Call rag_pipeline.insert_content_list(content_list)
  4. Update document status → READY_ENRICHED
"""
from uuid import UUID
from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, joinedload

logger = get_task_logger(__name__)

# Module-level sync engine cache
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
    name="app.queue.tasks.enrichment.process_enrichment",
    queue="enrichment",
    max_retries=2,
    default_retry_delay=120,
)
def process_enrichment(self, job_id: str, document_version_id: str, config: dict = None):
    """
    Enrich a document using RAG-Anything Knowledge Graph.

    Reads the structured.json and content_list stored by the OCR task,
    then calls RAGAnything.insert_content_list() to build the KG.

    Args:
        job_id: Enrichment Job UUID string
        document_version_id: DocumentVersion UUID string
        config: Optional configuration dict
    """
    from app.core.config import settings
    from app.db.models import DocumentVersion, Job, JobStatus, DocumentStatus
    from app.storage.object_store import ObjectStore
    import json

    logger.info(f"[Enrichment] Starting job {job_id} for version {document_version_id}")
    config = config or {}

    try:
        with _get_sync_session() as session:
            # Mark job RUNNING
            job = session.execute(
                select(Job).where(Job.id == UUID(job_id))
            ).scalar_one_or_none()

            if job:
                job.status = JobStatus.RUNNING
                job.step = "initializing"
                job.progress = 0
                session.commit()

            # Load document version
            result = session.execute(
                select(DocumentVersion)
                .options(joinedload(DocumentVersion.document))
                .where(DocumentVersion.id == UUID(document_version_id))
            )
            doc_version = result.unique().scalar_one_or_none()

            if not doc_version:
                raise ValueError(f"Document version {document_version_id} not found")

            # Check if document was canceled/deleted
            if doc_version.document and doc_version.document.status in [
                "CANCELED", "DELETED"
            ]:
                logger.info(f"Document was {doc_version.document.status}. Aborting enrichment.")
                if job:
                    job.status = JobStatus.DONE
                    job.step = "canceled"
                    session.commit()
                return {"status": "canceled"}

            # Update progress
            if job:
                job.step = "loading_content"
                job.progress = 10
                session.commit()

            # Load structured.json from MinIO
            storage = ObjectStore()
            json_key = doc_version.structured_json_key
            if not json_key:
                raise ValueError("No structured_json_key — OCR must run first")

            structured_json = json.loads(
                storage.download(json_key).decode("utf-8")
            )

            # Load markdown text for the main text content
            md_key = doc_version.extracted_md_key or doc_version.extracted_text_key
            markdown_text = ""
            if md_key:
                markdown_text = storage.download(md_key).decode("utf-8")

            if not markdown_text.strip():
                logger.info("[Enrichment] No text content to enrich, marking done.")
                if job:
                    job.status = JobStatus.DONE
                    job.step = "skipped_no_content"
                    job.progress = 100
                    session.commit()
                return {"status": "skipped", "reason": "no_content"}

            # Reuse canonical content_list from normalize.py (stored in structured.json)
            if job:
                job.step = "building_content_list"
                job.progress = 20
                session.commit()

            content_list = structured_json.get("content_list")
            if not content_list:
                # Fallback: build content_list manually if normalize.py didn't store it
                logger.warning("[Enrichment] No content_list in structured.json, rebuilding manually")
                content_list = [{"type": "text", "text": markdown_text, "page_idx": 0}]

                for img in structured_json.get("images", []):
                    content_list.append({
                        "type": "image",
                        "img_path": img.get("image_path") or img.get("path"),
                        "image_caption": img.get("caption", ""),
                        "image_footnote": img.get("footnote", ""),
                        "page_idx": img.get("page_idx", 0),
                    })

                for tbl in structured_json.get("tables", []):
                    content_list.append({
                        "type": "table",
                        "img_path": tbl.get("image_path") or tbl.get("path"),
                        "table_caption": tbl.get("caption", ""),
                        "table_body": tbl.get("markdown") or tbl.get("text", ""),
                        "table_footnote": tbl.get("footnote", ""),
                        "page_idx": tbl.get("page_idx", 0),
                    })

                for eq in structured_json.get("equations", []):
                    content_list.append({
                        "type": "equation",
                        "text": eq.get("latex") or eq.get("text", ""),
                        "text_format": eq.get("format", "latex"),
                        "page_idx": eq.get("page_idx", 0),
                    })
            else:
                logger.info(f"[Enrichment] Reusing canonical content_list ({len(content_list)} items)")

            # Run RAG-Anything enrichment
            enrichment_success = False
            if job:
                job.step = "enriching"
                job.progress = 30
                session.commit()

            try:
                from app.services.core.rag.factory import initialize_raganything
                from app.services.core.embedding_service import get_embedding_service
                from app.services.infrastructure.ai_providers.manager import AIProviderManager
                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                working_dir = settings.STORAGE_DIR / "rag_storage"
                ai_manager = AIProviderManager()

                try:
                    embedding_service = get_embedding_service()
                except Exception:
                    embedding_service = None

                rag_pipeline = loop.run_until_complete(
                    initialize_raganything(
                        working_dir=working_dir,
                        parser="auto",
                        parse_method="auto",
                        ai_manager=ai_manager,
                        embedding_service=embedding_service,
                    )
                )

                if rag_pipeline and hasattr(rag_pipeline, "insert_content_list"):
                    workspace_id_str = (
                        str(doc_version.document.workspace_id)
                        if doc_version.document
                        else "unknown"
                    )
                    file_ref = f"{workspace_id_str}/{doc_version.document_id}"

                    if job:
                        job.step = "inserting_knowledge_graph"
                        job.progress = 50
                        session.commit()

                    enrichment_result = loop.run_until_complete(
                        rag_pipeline.insert_content_list(
                            content_list=content_list,
                            file_path=file_ref,
                            doc_id=None,  # auto-generate
                        )
                    )

                    rag_doc_id = (
                        enrichment_result.doc_id
                        if enrichment_result
                        else None
                    )

                    # Store the RAGAnything doc_id back into structured.json
                    structured_json["raganything_doc_id"] = rag_doc_id
                    storage.upload(
                        json_key,
                        json.dumps(structured_json).encode("utf-8"),
                        content_type="application/json",
                    )

                    logger.info(
                        f"[Enrichment] RAGAnything OK (doc_id={rag_doc_id})"
                    )
                    enrichment_success = True
                else:
                    logger.warning(
                        "[Enrichment] RAGPipeline missing insert_content_list, "
                        "skipping enrichment"
                    )

                loop.close()

            except ImportError as e:
                logger.warning(f"[Enrichment] RAGAnything not available: {e}")
            except Exception as e:
                logger.error(
                    f"[Enrichment] RAGAnything enrichment failed: {e}",
                    exc_info=True,
                )
                # Don't re-raise — enrichment failure shouldn't block the doc
                # Document stays at READY_BASIC which is still searchable

            # Only upgrade to READY_ENRICHED if enrichment actually succeeded
            if enrichment_success and doc_version.document:
                doc_version.document.status = DocumentStatus.READY_ENRICHED
                doc_version.document.processing_progress = 100
                doc_version.document.processing_step = "Enrichment complete"
            elif doc_version.document:
                # Leave at READY_BASIC — still searchable via Vector+BM25
                logger.info(
                    "[Enrichment] Enrichment did not succeed, "
                    "document stays at READY_BASIC"
                )
                doc_version.document.processing_step = "Enrichment skipped/failed"
            session.commit()

            # Mark job done
            if job:
                job.status = JobStatus.DONE
                job.step = "completed"
                job.progress = 100
                session.commit()

            logger.info(f"[Enrichment] Job {job_id} completed successfully")
            return {"status": "success", "job_id": job_id}

    except Exception as e:
        logger.error(f"[Enrichment] Job {job_id} failed: {e}", exc_info=True)

        try:
            with _get_sync_session() as session:
                job = session.execute(
                    select(Job).where(Job.id == UUID(job_id))
                ).scalar_one_or_none()
                if job:
                    job.status = JobStatus.ERROR
                    job.error_message = str(e)
                    session.commit()

                # NOTE: Do NOT set document to FAILED here.
                # Document is already READY_BASIC and searchable.
                # Enrichment failure is non-critical.
        except Exception:
            pass

        raise self.retry(exc=e)
