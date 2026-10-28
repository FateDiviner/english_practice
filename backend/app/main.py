from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.tracing import configure_langsmith
from app.mcp.auth import McpPathRewriteMiddleware
from app.mcp.server import build_mcp_app, create_mcp_server


def _frontend_origins() -> list[str]:
    """读取允许直连后端的前端开发与预览来源。"""
    return [
        origin.strip() for origin in get_settings().FRONTEND_ORIGINS.split(",") if origin.strip()
    ]


def create_app() -> FastAPI:
    configure_langsmith()
    settings = get_settings()
    mcp_server = create_mcp_server() if settings.MCP_ENABLED else None
    mcp_app = build_mcp_app(mcp_server) if mcp_server is not None else None

    @asynccontextmanager
    async def lifespan(_application: FastAPI):
        if mcp_server is None:
            yield
            return
        async with mcp_server.session_manager.run():
            yield

    application = FastAPI(title="English Practice API", version="0.1.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_frontend_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(application)
    application.include_router(api_router, prefix="/api/v1")
    if mcp_app is not None:
        application.add_middleware(McpPathRewriteMiddleware)
        application.mount("/mcp", mcp_app)
    return application


app = create_app()
