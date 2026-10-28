from fastapi import APIRouter

from app.api.v1.admin_import import router as admin_import_router
from app.api.v1.admin_mcp import router as admin_mcp_router
from app.api.v1.admin_profile import router as admin_profile_router
from app.api.v1.admin_stats import router as admin_stats_router
from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.admin_wordbooks import router as admin_wordbooks_router
from app.api.v1.admin_words import router as admin_words_router
from app.api.v1.agent import router as agent_router
from app.api.v1.ai import router as ai_router
from app.api.v1.audio import router as audio_router
from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.practice import router as practice_router
from app.api.v1.stats import router as stats_router
from app.api.v1.wordbooks import router as wordbooks_router
from app.api.v1.wrong_words import router as wrong_words_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(agent_router)
api_router.include_router(ai_router)
api_router.include_router(audio_router)
api_router.include_router(health_router)
api_router.include_router(admin_stats_router)
api_router.include_router(admin_import_router)
api_router.include_router(admin_mcp_router)
api_router.include_router(admin_users_router)
api_router.include_router(admin_profile_router)
api_router.include_router(admin_wordbooks_router)
api_router.include_router(admin_words_router)
api_router.include_router(wordbooks_router)
api_router.include_router(practice_router)
api_router.include_router(wrong_words_router)
api_router.include_router(stats_router)
