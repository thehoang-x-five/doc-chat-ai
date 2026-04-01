"""
OCR extraction API routes
"""
import asyncio
import json
import logging
from typing import Optional
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.jobs import job_store, JobStatus
from app.core.engines.ocr import rag_engine
from app.models.schemas import OcrSettings, JobResponse, AsyncJobResponse
from app.utils.files import (
    validate_file_extension, validate_file_size, 
    save_uploaded_file, get_file_info
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/extract", response_model=JobResponse)
async def extract_ocr(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    settings_json: Optional[str] = Form(None),
    sync: bool = Query(False, description="Process synchronously for small files")
):
    """
    Extract text from uploaded file using OCR
    
    - **file**: File to process (PDF, image, Office doc, etc.)
    - **settings**: JSON string with OCR settings
    - **sync**: If true, process synchronously and return result immediately
    """
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
        
    if not validate_file_extension(file.filename):
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    
    # Read file content
    try:
        content = await file.read()
    except Exception as e:
        logger.error(f"Error reading uploaded file: {e}")
        raise HTTPException(status_code=400, detail="Error reading file")
    
    # Validate file size
    if not validate_file_size(len(content)):
        max_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
        raise HTTPException(
            status_code=413, 
            detail=f"File too large. Maximum size: {max_mb:.1f}MB"
        )
    
    # Parse settings
    ocr_settings = OcrSettings()
    if settings_json:
        try:
            settings_dict = json.loads(settings_json)
            ocr_settings = OcrSettings(**settings_dict)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing settings: {e}")
            raise HTTPException(status_code=400, detail="Invalid settings JSON")
    
    # Create job
    job_id = job_store.create_job()
    
    try:
        # Save uploaded file
        file_path = save_uploaded_file(job_id, file.filename, content)
        
        # Log file info
        file_info = get_file_info(file_path)
        logger.info(f"Processing file for job {job_id}: {file_info}")
        
        # Convert settings to dict
        settings_dict = ocr_settings.model_dump()
        
        if sync:
            # Process synchronously (for small files)
            try:
                result = await rag_engine.process_document(job_id, file_path, settings_dict)
                return JobResponse(**result)
            except Exception as e:
                logger.error(f"Sync processing failed for job {job_id}: {e}")
                raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
        else:
            # Process asynchronously
            background_tasks.add_task(
                rag_engine.process_document,
                job_id, file_path, settings_dict
            )
            
            return JSONResponse(
                status_code=202,
                content=AsyncJobResponse(jobId=job_id, status="running").model_dump()
            )
            
    except HTTPException:
        # Clean up job on HTTP errors
        job_store.delete_job(job_id)
        raise
    except Exception as e:
        # Clean up job on unexpected errors
        job_store.delete_job(job_id)
        logger.error(f"Unexpected error in extract_ocr: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/status")
async def get_ocr_status():
    """Get OCR service status and capabilities"""
    return {
        "service": "OCR Extraction",
        "version": "1.0.0",
        "parsers": ["docling", "mineru"],
        "defaultParser": settings.DEFAULT_PARSER,
        "supportedFormats": settings.ALLOWED_EXTENSIONS,
        "maxFileSize": f"{settings.MAX_FILE_SIZE / (1024 * 1024):.1f}MB",
        "features": {
            "asyncProcessing": True,
            "syncProcessing": True,
            "layoutPreservation": True,
            "multipleFormats": True,
            "batchProcessing": False  # Not implemented yet
        }
    }