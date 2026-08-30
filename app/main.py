from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description="AI-powered exam preparation and content intelligence platform.",
    version=settings.app_version,
    debug=settings.debug
)

app.include_router(api_router, prefix="/api/v1")