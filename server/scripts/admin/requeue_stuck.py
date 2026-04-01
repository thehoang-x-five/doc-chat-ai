"""Requeue stuck documents that are in NEW status"""
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import Document, DocumentVersion
from app.queue.tasks.ocr import process_ocr

async def requeue_stuck_documents():
    async with AsyncSessionLocal() as session:
        # Find all documents with NEW status
        result = await session.execute(
            select(Document).where(Document.status == 'NEW')
        )
        stuck_docs = result.scalars().all()
        
        print(f"Found {len(stuck_docs)} stuck documents in NEW status")
        
        for doc in stuck_docs:
            # Get the latest version
            version_result = await session.execute(
                select(DocumentVersion)
                .where(DocumentVersion.document_id == doc.id)
                .order_by(DocumentVersion.version.desc())
                .limit(1)
            )
            version = version_result.scalar_one_or_none()
            
            if version:
                print(f"  Requeuing: {doc.title} (version: {version.id})")
                
                # Create a new job and queue it
                import uuid
                job_id = str(uuid.uuid4())
                
                # Queue the OCR task (correct signature: job_id, document_version_id, config)
                process_ocr.delay(job_id, str(version.id), {})
                print(f"    -> Queued job: {job_id}")
            else:
                print(f"  Skipping {doc.title} - no version found")

if __name__ == "__main__":
    asyncio.run(requeue_stuck_documents())
