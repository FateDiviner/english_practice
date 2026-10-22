from fastapi import APIRouter

from app.api.v1.admin_wordbooks import router as admin_wordbooks_router
from app.api.v1.admin_words import router as admin_words_router
from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.wordbooks import router as wordbooks_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(admin_wordbooks_router)
api_router.include_router(admin_words_router)
api_router.include_router(wordbooks_router)
