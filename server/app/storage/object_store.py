"""
Object storage client for MinIO/S3.
Handles file upload, download, and presigned URL generation.
Falls back to local filesystem storage when MinIO is not available.
"""
import io
import hashlib
import logging
from datetime import timedelta
from typing import Optional, BinaryIO, Union
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# Try to import minio, but don't fail if not available
try:
    from minio import Minio
    from minio.error import S3Error
    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False
    S3Error = Exception


class ObjectStoreError(Exception):
    """Base exception for object store errors."""
    pass


class LocalFileStore:
    """
    Local filesystem storage fallback when MinIO is not available.
    """
    
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(settings.STORAGE_DIR) / "objects"
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_path(self, key: str) -> Path:
        """Get full path for a key."""
        path = self.base_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    
    def upload(self, key: str, data: Union[bytes, BinaryIO, Path], content_type: str = None) -> str:
        """Upload file to local storage."""
        path = self._get_path(key)
        
        if isinstance(data, bytes):
            path.write_bytes(data)
        elif isinstance(data, Path):
            import shutil
            shutil.copy(data, path)
        else:
            # File-like object
            data.seek(0)
            path.write_bytes(data.read())
        
        logger.debug(f"Uploaded to local storage: {key}")
        return key
    
    def download(self, key: str) -> bytes:
        """Download file from local storage."""
        path = self._get_path(key)
        if not path.exists():
            raise ObjectStoreError(f"File not found: {key}")
        return path.read_bytes()
    
    def download_to_file(self, key: str, dest_path: Path) -> Path:
        """Download file to local path."""
        import shutil
        src_path = self._get_path(key)
        if not src_path.exists():
            raise ObjectStoreError(f"File not found: {key}")
        shutil.copy(src_path, dest_path)
        return dest_path
    
    def delete(self, key: str) -> bool:
        """Delete file from local storage."""
        path = self._get_path(key)
        if path.exists():
            path.unlink()
            return True
        return False
    
    def exists(self, key: str) -> bool:
        """Check if file exists."""
        return self._get_path(key).exists()


class ObjectStore:
    """
    MinIO/S3 object storage client.
    Falls back to local filesystem when MinIO is not available.
    """
    
    def __init__(
        self,
        endpoint: str = None,
        access_key: str = None,
        secret_key: str = None,
        bucket: str = None,
        secure: bool = None,
    ):
        self.endpoint = endpoint or settings.minio_endpoint
        self.access_key = access_key or settings.minio_access_key
        self.secret_key = secret_key or settings.minio_secret_key
        self.bucket = bucket or settings.minio_bucket
        self.secure = secure if secure is not None else settings.minio_secure
        
        self._client = None
        self._presign_client = None  # Separate client for presigned URLs (uses external endpoint)
        self._local_store = None
        self._use_local = False
        
        # External endpoint for browser-accessible presigned URLs
        self._external_endpoint = getattr(settings, 'minio_external_endpoint', '') or ''
        
        # Check if MinIO is available
        self._init_storage()
    
    def _init_storage(self):
        """Initialize storage backend."""
        if not MINIO_AVAILABLE:
            logger.warning("MinIO library not installed, using local storage")
            self._use_local = True
            self._local_store = LocalFileStore()
            return
        
        # Quick port check before trying to connect
        import socket
        try:
            host, port = self.endpoint.split(':')
            port = int(port)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result != 0:
                logger.warning(f"MinIO port {port} not reachable, using local storage")
                self._use_local = True
                self._local_store = LocalFileStore()
                return
        except Exception as e:
            logger.warning(f"MinIO endpoint check failed ({e}), using local storage")
            self._use_local = True
            self._local_store = LocalFileStore()
            return
        
        try:
            client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
            # Auto-create bucket if needed
            if not client.bucket_exists(self.bucket):
                client.make_bucket(self.bucket)
                logger.info(f"Created MinIO bucket: {self.bucket}")
            
            self._client = client
            self._use_local = False
            logger.info(f"Connected to MinIO at {self.endpoint} (bucket: {self.bucket})")
            
            # Create presigned URL client using external endpoint
            # Presigned URLs must be signed with the hostname the browser will use
            if self._external_endpoint and self._external_endpoint != self.endpoint:
                self._presign_client = Minio(
                    self._external_endpoint,
                    access_key=self.access_key,
                    secret_key=self.secret_key,
                    secure=self.secure,
                    region="us-east-1",  # Prevent SDK from hitting the external endpoint to verify region
                )
                logger.info(f"Presigned URL client configured for external endpoint: {self._external_endpoint}")
            else:
                self._presign_client = client
                
        except Exception as e:
            logger.warning(f"MinIO not available ({e}), using local storage")
            self._use_local = True
            self._local_store = LocalFileStore()
    
    @property
    def client(self) -> Optional["Minio"]:
        """Lazy initialization of Minio client."""
        if self._use_local:
            return None
        if self._client is None:
            self._init_storage()
        return self._client
    
    def ensure_bucket(self) -> None:
        """Create bucket if it doesn't exist."""
        if self._use_local:
            return
        
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except S3Error as e:
            raise ObjectStoreError(f"Failed to create bucket: {e}")

    def upload(
        self,
        key: str,
        data: Union[bytes, BinaryIO, Path],
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload file to object storage.
        
        Args:
            key: Object key (path in bucket)
            data: File data (bytes, file-like object, or Path)
            content_type: MIME type
            
        Returns:
            Object key
        """
        if self._use_local:
            return self._local_store.upload(key, data, content_type)
        
        self.ensure_bucket()
        
        try:
            if isinstance(data, bytes):
                data_stream = io.BytesIO(data)
                length = len(data)
            elif isinstance(data, Path):
                data_stream = open(data, "rb")
                length = data.stat().st_size
            else:
                # File-like object
                data.seek(0, 2)  # Seek to end
                length = data.tell()
                data.seek(0)  # Seek back to start
                data_stream = data
            
            self.client.put_object(
                self.bucket,
                key,
                data_stream,
                length,
                content_type=content_type,
            )
            
            return key
        except S3Error as e:
            raise ObjectStoreError(f"Failed to upload: {e}")
        finally:
            if isinstance(data, Path):
                data_stream.close()
    
    def download(self, key: str) -> bytes:
        """
        Download file from object storage.
        
        Args:
            key: Object key
            
        Returns:
            File content as bytes
        """
        if self._use_local:
            return self._local_store.download(key)
        
        try:
            response = self.client.get_object(self.bucket, key)
            return response.read()
        except S3Error as e:
            raise ObjectStoreError(f"Failed to download: {e}")
        finally:
            response.close()
            response.release_conn()
    
    def download_to_file(self, key: str, path: Path) -> Path:
        """
        Download file to local path.
        
        Args:
            key: Object key
            path: Local file path
            
        Returns:
            Local file path
        """
        if self._use_local:
            return self._local_store.download_to_file(key, path)
        
        try:
            self.client.fget_object(self.bucket, key, str(path))
            return path
        except S3Error as e:
            raise ObjectStoreError(f"Failed to download: {e}")

    def delete(self, key: str) -> bool:
        """
        Delete file from object storage.
        
        Args:
            key: Object key
            
        Returns:
            True if deleted
        """
        if self._use_local:
            return self._local_store.delete(key)
        
        try:
            self.client.remove_object(self.bucket, key)
            return True
        except S3Error as e:
            raise ObjectStoreError(f"Failed to delete: {e}")
    
    def exists(self, key: str) -> bool:
        """
        Check if object exists.
        
        Args:
            key: Object key
            
        Returns:
            True if exists
        """
        if self._use_local:
            return self._local_store.exists(key)
        
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except S3Error:
            return False
    
    def get_presigned_url(
        self,
        key: str,
        expires: timedelta = timedelta(hours=1),
        response_headers: dict = None,
    ) -> str:
        """
        Generate presigned URL for download.
        
        Args:
            key: Object key
            expires: URL expiration time
            response_headers: Optional dict of response headers to override
            
        Returns:
            Presigned URL
        """
        if self._use_local:
            # Return a local file path for local storage
            return f"file://{self._local_store._get_path(key)}"
        
        try:
            return self._presign_client.presigned_get_object(
                self.bucket,
                key,
                expires=expires,
                response_headers=response_headers,
            )
        except S3Error as e:
            raise ObjectStoreError(f"Failed to generate URL: {e}")
    
    def get_presigned_upload_url(
        self,
        key: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """
        Generate presigned URL for upload.
        
        Args:
            key: Object key
            expires: URL expiration time
            
        Returns:
            Presigned URL
        """
        if self._use_local:
            return f"file://{self._local_store._get_path(key)}"
        
        try:
            return self._presign_client.presigned_put_object(
                self.bucket,
                key,
                expires=expires,
            )
        except S3Error as e:
            raise ObjectStoreError(f"Failed to generate URL: {e}")
    
    @staticmethod
    def generate_key(
        workspace_id: str,
        document_id: str,
        filename: str,
        prefix: str = "documents",
    ) -> str:
        """
        Generate object key for a file.
        
        Args:
            workspace_id: Workspace UUID
            document_id: Document UUID
            filename: Original filename
            prefix: Key prefix (documents, outputs, etc.)
            
        Returns:
            Object key
        """
        return f"{prefix}/{workspace_id}/{document_id}/{filename}"
    
    @staticmethod
    def compute_checksum(data: bytes) -> str:
        """Compute SHA256 checksum of data."""
        return hashlib.sha256(data).hexdigest()
