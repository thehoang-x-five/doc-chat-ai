"""
File handling utilities
"""
import os
import shutil
from pathlib import Path
from typing import Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def validate_file_extension(filename: str) -> bool:
    """Validate file extension against allowed list"""
    if not filename:
        return False
        
    extension = Path(filename).suffix.lower().lstrip('.')
    return extension in settings.ALLOWED_EXTENSIONS


def validate_file_size(file_size: int) -> bool:
    """Validate file size against maximum allowed"""
    return file_size <= settings.MAX_FILE_SIZE


def get_job_storage_path(job_id: str) -> Path:
    """Get storage path for a job"""
    documents_dir = settings.STORAGE_DIR / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    return documents_dir / job_id


def get_job_input_path(job_id: str) -> Path:
    """Get input storage path for a job"""
    path = get_job_storage_path(job_id) / "input"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_job_output_path(job_id: str) -> Path:
    """Get output storage path for a job"""
    path = get_job_storage_path(job_id) / "output"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_uploaded_file(job_id: str, filename: str, content: bytes) -> Path:
    """Save uploaded file to job input directory"""
    input_path = get_job_input_path(job_id)
    file_path = input_path / filename
    
    with open(file_path, "wb") as f:
        f.write(content)
        
    logger.info(f"Saved uploaded file: {file_path}")
    return file_path


def cleanup_job_files(job_id: str) -> bool:
    """Clean up all files for a job"""
    try:
        job_path = get_job_storage_path(job_id)
        if job_path.exists():
            shutil.rmtree(job_path)
            logger.info(f"Cleaned up files for job {job_id}")
            return True
    except Exception as e:
        logger.error(f"Error cleaning up job {job_id}: {e}")
    return False


def get_file_info(file_path: Path) -> dict:
    """Get file information"""
    if not file_path.exists():
        return {}
        
    stat = file_path.stat()
    return {
        "name": file_path.name,
        "size": stat.st_size,
        "extension": file_path.suffix.lower().lstrip('.'),
        "created": stat.st_ctime,
        "modified": stat.st_mtime
    }