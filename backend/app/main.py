from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exception_handlers import register_exception_handlers


def _frontend_origins() -> list[str]:
    """读取允许直连后端的前端开发与预览来源。"""
    return [
        origin.strip() for origin in get_settings().FRONTEND_ORIGINS.split(",") if origin.strip()
    ]


def create_app() -> FastAPI:
    application = FastAPI(title="English Practice API", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_frontend_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(application)
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
