"""API v1 package"""
from fastapi import APIRouter

from .auth import router as auth_router
from .workspaces import router as workspaces_router
from .documents import router as documents_router
from .jobs import router as jobs_router
from .chat import router as chat_router
from .ocr import router as ocr_router
from .health import router as health_router
from .providers import router as providers_router
from .cloudcode import router as cloudcode_router
from .analytics import router as analytics_router
from .models import router as models_router
from .apikeys import router as apikeys_router
from .compare import router as compare_router
from .extraction import router as extraction_router
from .summarize import router as summarize_router
from .categories import router as categories_router
from .images import router as images_router
from .process import router as process_router
from .memori import router as memori_router
from .search import router as search_router  # NEW: Progressive disclosure
from .tools import router as tools_router  # NEW: Direct tools access
from .dashboard import router as dashboard_router  # NEW: Pattern monitoring dashboards
from .feedback import router as feedback_router  # NEW: User feedback collection

api_router = APIRouter()

# Include routers
api_router.include_router(auth_router)
api_router.include_router(workspaces_router)
api_router.include_router(documents_router)
api_router.include_router(jobs_router)
api_router.include_router(chat_router)
api_router.include_router(ocr_router)
api_router.include_router(health_router)
api_router.include_router(providers_router)
api_router.include_router(cloudcode_router)
api_router.include_router(analytics_router)
api_router.include_router(models_router)
api_router.include_router(apikeys_router)
api_router.include_router(compare_router)
api_router.include_router(extraction_router)
api_router.include_router(summarize_router)
api_router.include_router(categories_router)
api_router.include_router(images_router)
api_router.include_router(process_router)
api_router.include_router(memori_router)
api_router.include_router(search_router)  # NEW: Progressive disclosure
api_router.include_router(tools_router)  # NEW: Direct tools access
api_router.include_router(dashboard_router)  # NEW: Pattern monitoring dashboards
api_router.include_router(feedback_router)  # NEW: User feedback collection
