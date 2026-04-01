"""
Document processing API - sync processing without Celery.
"""
import logging
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Document, DocumentVersion, Job, Chunk, DocumentStatus, JobStatus
from app.api.deps import get_current_user
from app.storage.object_store import ObjectStore
from app.db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/process", tags=["Processing"])


class DocumentCanceledError(Exception):
    """Raised when a document has been deleted/canceled during processing."""
    pass


async def _check_canceled(document_id: UUID, db: AsyncSession, stage: str) -> None:
    """Checkpoint: re-read document status from DB. Raise if deleted/canceled."""
    await db.expire_all()
    result = await db.execute(
        select(Document.status).where(Document.id == document_id)
    )
    row = result.scalar_one_or_none()
    if row is None or row in (DocumentStatus.DELETED, DocumentStatus.CANCELED):
        logger.info(f"Document {document_id} was canceled/deleted at stage '{stage}' — aborting.")
        raise DocumentCanceledError(f"Document {document_id} canceled at {stage}")


async def process_document_sync(
    document_id: UUID,
    db: AsyncSession,
):
    """Process document synchronously - OCR and create chunks."""
    # Get document with versions
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise ValueError(f"Document {document_id} not found")
    
    # Get latest version
    version_result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.created_at.desc())
        .limit(1)
    )
    doc_version = version_result.scalar_one_or_none()
    
    if not doc_version:
        raise ValueError(f"No version found for document {document_id}")
    
    # Download file from storage
    storage = ObjectStore()
    file_key = doc_version.original_file_key
    
    try:
        if file_key.startswith("http"):
            import httpx
            response = httpx.get(file_key, follow_redirects=True)
            file_content = response.content
            file_ext = Path(file_key).suffix or ".html"
        else:
            file_content = storage.download(file_key)
            file_ext = Path(file_key).suffix
    except Exception as e:
        logger.error(f"Failed to download file: {e}")
        document.status = DocumentStatus.FAILED
        await db.commit()
        raise
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
        tmp.write(file_content)
        tmp_path = Path(tmp.name)
    
    try:
        # === CHECKPOINT 1: Before OCR ===
        await _check_canceled(document_id, db, "pre-ocr")

        # Try to process with DocumentEngine
        full_text = ""
        markdown_text = ""
        
        try:
            from app.core.engines.ocr import DocumentEngine
            import asyncio
            
            engine = DocumentEngine()
            result = await engine.process_document(
                job_id=str(document_id),
                file_path=tmp_path,
                settings_dict={
                    "parser": "docling",
                    "parse_method": "auto",
                    "language": "auto",
                }
            )
            
            ocr_result = result.get("result", {})
            full_text = ocr_result.get("fullText", "")
            markdown_text = ocr_result.get("markdownText", full_text)
            page_count = ocr_result.get("meta", {}).get("pageCount", 1)
            language = ocr_result.get("meta", {}).get("language", "auto")
            
        except ImportError:
            logger.warning("DocumentEngine not available, using simple text extraction")
            # Fallback: simple text extraction
            try:
                full_text = file_content.decode("utf-8", errors="ignore")
            except:
                full_text = str(file_content)[:10000]
            markdown_text = full_text
            page_count = 1
            language = "auto"
        
        # === CHECKPOINT 2: Before storing outputs & chunking ===
        await _check_canceled(document_id, db, "pre-chunking")

        # Store outputs
        workspace_id = str(document.workspace_id)
        doc_id = str(document.id)
        version = doc_version.version
        
        text_key = f"outputs/{workspace_id}/{doc_id}/v{version}/text.txt"
        storage.upload(text_key, full_text.encode("utf-8"), content_type="text/plain")
        
        md_key = f"outputs/{workspace_id}/{doc_id}/v{version}/content.md"
        storage.upload(md_key, markdown_text.encode("utf-8"), content_type="text/markdown")
        
        # Update document version
        doc_version.extracted_text_key = text_key
        doc_version.extracted_md_key = md_key
        doc_version.page_count = page_count
        doc_version.language_detected = language
        
        # Create chunks from text using proper ChunkingService (same as Celery index pipeline)
        from app.services.documents.chunking_service import ChunkingService
        
        chunking_svc = ChunkingService(chunk_size=512, chunk_overlap=50)
        text_chunks = chunking_svc.chunk_text(markdown_text or full_text)
        
        # === CHECKPOINT 3: Before writing chunks to DB ===
        await _check_canceled(document_id, db, "pre-db-write")

        for text_chunk in text_chunks:
            if text_chunk.content.strip():
                chunk = Chunk(
                    document_version_id=doc_version.id,
                    chunk_index=text_chunk.metadata.chunk_index,
                    content=text_chunk.content,
                    token_count=text_chunk.token_count,
                    page_start=text_chunk.metadata.page_start,
                    page_end=text_chunk.metadata.page_end,
                    section_title=text_chunk.metadata.section_title,
                    hash=text_chunk.hash,
                )
                db.add(chunk)
        
        # Update document status
        document.status = DocumentStatus.READY_BASIC
        await db.commit()
        
        logger.info(f"Document {document_id} processed: {len(text_chunks)} chunks created")
        return {"status": "success", "chunks": len(text_chunks)}

    except DocumentCanceledError:
        logger.info(f"Document {document_id} processing aborted due to cancellation.")
        return {"status": "canceled", "chunks": 0}
        
    finally:
        try:
            tmp_path.unlink()
        except:
            pass


# NOTE: Static routes must be defined BEFORE dynamic routes
@router.post("/batch")
async def process_all_pending(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Process all pending documents."""
    # Get all NEW or INDEXING documents
    result = await db.execute(
        select(Document).where(
            Document.status.in_([DocumentStatus.NEW, DocumentStatus.INDEXING])
        )
    )
    documents = result.scalars().all()
    
    processed = []
    failed = []
    
    for doc in documents:
        try:
            await process_document_sync(doc.id, db)
            processed.append(str(doc.id))
        except Exception as e:
            logger.error(f"Failed to process {doc.id}: {e}")
            failed.append({"id": str(doc.id), "error": str(e)})
    
    return {
        "processed": len(processed),
        "failed": len(failed),
        "processed_ids": processed,
        "failed_details": failed,
    }


@router.post("/document/{document_id}")
async def process_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Process a document (OCR + chunking) synchronously.
    Use this when Celery worker is not running.
    """
    # Get document
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check if already processed
    if document.status in (DocumentStatus.READY, DocumentStatus.READY_BASIC, DocumentStatus.READY_ENRICHED):
        return {"status": "already_processed", "message": "Document already processed"}
    
    try:
        # Update status to processing
        document.status = DocumentStatus.INDEXING
        await db.commit()
        
        # Process synchronously
        result = await process_document_sync(document_id, db)
        return result
        
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        document.status = DocumentStatus.FAILED
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))
