"""
Indexing task for RAG pipeline.
"""
from uuid import UUID
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


# Module-level engine cache to avoid creating a new engine per task call
_sync_engine = None


def _make_sync_session():
    """Create a synchronous SQLAlchemy session factory, reusing the engine."""
    global _sync_engine
    from sqlalchemy.orm import sessionmaker
    
    if _sync_engine is None:
        from app.core.config import settings
        from sqlalchemy import create_engine
        
        db_url = settings.database_url
        if "asyncpg" in db_url:
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        _sync_engine = create_engine(db_url, echo=False, pool_pre_ping=True)
    
    return sessionmaker(bind=_sync_engine, autocommit=False, autoflush=False)


@shared_task(
    bind=True,
    name="app.queue.tasks.index.process_index",
    queue="index",
    max_retries=3,
    default_retry_delay=60,
)
def process_index(self, job_id: str, document_version_id: str, config: dict = None):
    """
    Index a document version for RAG.
    
    Args:
        job_id: Job UUID string
        document_version_id: DocumentVersion UUID string
        config: Optional configuration dict
    """
    from app.core.config import settings
    from app.services.analytics.job_service import JobService
    from app.services.documents.chunking_service import ChunkingService
    from app.services.core.embedding_service import get_embedding_service
    from app.db.models import DocumentVersion, Chunk, JobStatus
    from app.storage.object_store import ObjectStore
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    import json
    
    SyncSession = _make_sync_session()
    
    logger.info(f"Starting INDEX job {job_id} for document version {document_version_id}")
    config = config or {}
    
    try:
        with SyncSession() as session:
            job_service = JobService(session)
            
            # Update job status to RUNNING
            job_service.update_status_sync(
                UUID(job_id),
                status="RUNNING",
                step="initializing",
                progress=0
            )
            session.commit()
            
            # Get document version WITH its parent document (needed to set READY)
            result = session.execute(
                select(DocumentVersion)
                .options(joinedload(DocumentVersion.document))
                .where(DocumentVersion.id == UUID(document_version_id))
            )
            doc_version = result.unique().scalar_one_or_none()
            
            if not doc_version:
                raise ValueError(f"Document version {document_version_id} not found")
            
            # Load extracted text
            job_service.update_status_sync(
                UUID(job_id),
                step="loading",
                progress=10
            )
            session.commit()
            
            storage = ObjectStore()
            
            # Prefer Markdown text for Semantic Chunking if available
            text_key = doc_version.extracted_md_key or doc_version.extracted_text_key
            
            if not text_key:
                raise ValueError("No extracted text or markdown available. Run OCR first.")
            
            text_content = storage.download(text_key).decode("utf-8")
            structured_json = {}
            if doc_version.structured_json_key:
                try:
                    structured_json = json.loads(
                        storage.download(doc_version.structured_json_key).decode("utf-8")
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to load structured_json for %s: %s",
                        document_version_id,
                        exc,
                    )
            
            # Chunk text
            job_service.update_status_sync(
                UUID(job_id),
                step="chunking",
                progress=25
            )
            session.commit()
            
            chunk_size = config.get("chunk_size", 512)
            chunk_overlap = config.get("chunk_overlap", 50)
            
            chunking_service = ChunkingService(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            
            content_list = structured_json.get("content_list") or []
            use_structure_aware = (
                config.get("chunking_strategy")
                or getattr(chunking_service, "strategy", None)
                or "structure_aware"
            ) == "structure_aware"

            if use_structure_aware and content_list:
                text_chunks = chunking_service.chunk_content_list(
                    content_list,
                    fallback_text=text_content,
                )
                logger.info(
                    "Created %s chunks (structure-aware canonical content_list)",
                    len(text_chunks),
                )
            else:
                text_chunks = chunking_service.chunk_by_sentences(text_content)
                logger.info(
                    "Created %s chunks (LlamaIndex SentenceSplitter)",
                    len(text_chunks),
                )
            
            if not text_chunks:
                logger.warning(f"No chunks generated for {document_version_id}. Document may be empty or unreadable.")
            
            # Generate embeddings
            job_service.update_status_sync(
                UUID(job_id),
                step="embedding",
                progress=50
            )
            session.commit()
            
            embedding_service = get_embedding_service()
            chunk_texts = [c.content for c in text_chunks]
            # embed_batch returns (List[List[float]], EmbeddingModelInfo)
            embeddings, model_info = embedding_service.embed_batch(chunk_texts)
            logger.info(
                "Embedding %s chunks with %s/%s (dim=%s)",
                len(chunk_texts),
                model_info.provider,
                model_info.name,
                model_info.dimension,
            )
            
            # Delete existing chunks for this version
            session.execute(
                Chunk.__table__.delete().where(
                    Chunk.document_version_id == UUID(document_version_id)
                )
            )
            session.commit()
            
            # Store chunks with embeddings
            job_service.update_status_sync(
                UUID(job_id),
                step="storing",
                progress=75
            )
            session.commit()
            
            for i, (text_chunk, embedding) in enumerate(zip(text_chunks, embeddings)):
                chunk = Chunk(
                    document_version_id=UUID(document_version_id),
                    chunk_index=text_chunk.metadata.chunk_index,
                    content=text_chunk.content,
                    token_count=text_chunk.token_count,
                    page_start=text_chunk.metadata.page_start,
                    page_end=text_chunk.metadata.page_end,
                    bbox_json=text_chunk.metadata.bbox_json,
                    section_title=text_chunk.metadata.section_title,
                    hash=text_chunk.hash,
                    chunk_type=text_chunk.metadata.chunk_type,
                )
                
                # Set embedding if pgvector is available
                if hasattr(Chunk, 'embedding'):
                    chunk.embedding = embedding
                
                session.add(chunk)
            
            session.commit()
            
            strict_enrichment_pending = (
                settings.STRICT_NEO4J
                and settings.ENABLE_RAGANYTHING_PARSING
                and bool(text_content.strip())
            )

            # Update document status after indexing.
            if doc_version.document:
                if doc_version.document.status == "READY_ENRICHED":
                    logger.info(
                        "[Index] Document %s is already READY_ENRICHED; keeping enriched status",
                        doc_version.document.id,
                    )
                elif strict_enrichment_pending:
                    doc_version.document.status = "INDEXING"
                    doc_version.document.processing_progress = 95
                    doc_version.document.processing_step = (
                        f"Indexed {len(text_chunks)} chunks, waiting for strict Neo4j enrichment"
                    )
                else:
                    doc_version.document.status = "READY_BASIC"
                    doc_version.document.processing_progress = 100
                    doc_version.document.processing_step = f"Indexed {len(text_chunks)} chunks"
            session.commit()
            
            # Mark job as done
            job_service.update_status_sync(
                UUID(job_id),
                status="DONE",
                step="completed",
                progress=100
            )
            session.commit()
            
            logger.info(f"INDEX job {job_id} completed: {len(text_chunks)} chunks indexed")
            return {"status": "success", "job_id": job_id, "chunks": len(text_chunks)}
            
    except Exception as e:
        logger.error(f"INDEX job {job_id} failed: {e}", exc_info=True)
        
        try:
            from app.services.analytics.job_service import JobService
            from app.db.models import Document, DocumentVersion
            from sqlalchemy import select
            from sqlalchemy.orm import joinedload
            
            ErrSession = _make_sync_session()
            with ErrSession() as session:
                # Mark job as ERROR
                job_service = JobService(session)
                job_service.update_status_sync(
                    UUID(job_id),
                    status="ERROR",
                    error_message=str(e)
                )
                
                # Also set document status to FAILED so UI shows the error
                result = session.execute(
                    select(DocumentVersion)
                    .options(joinedload(DocumentVersion.document))
                    .where(DocumentVersion.id == UUID(document_version_id))
                )
                dv = result.unique().scalar_one_or_none()
                if dv and dv.document:
                    dv.document.status = "FAILED"
                    dv.document.processing_step = f"Index error: {str(e)[:80]}"
                
                session.commit()
        except Exception:
            pass
        
        raise self.retry(exc=e)
