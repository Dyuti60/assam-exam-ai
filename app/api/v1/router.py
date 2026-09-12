from fastapi import APIRouter

from app.api.v1.routes import ai, claim_extraction, health, knowledge

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(ai.router, tags=["AI audit"])
api_router.include_router(claim_extraction.router, tags=["Grounded claim extraction"])
api_router.include_router(knowledge.router, tags=["Knowledge"])
