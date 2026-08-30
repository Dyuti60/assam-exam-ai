import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging


setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    logger.info(
        "Application starting | environment=%s",
        settings.environment,
    )

    yield

    logger.info("Application shutting down")


app = FastAPI(
    title=settings.app_name,
    description=(
        "AI-powered exam preparation and content "
        "intelligence platform for Assam competitive examinations."
    ),
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")