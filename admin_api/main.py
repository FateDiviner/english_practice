"""管理端 FastAPI 应用入口。

与用户端 backend 分进程：可单独重启、单独部署到内网、单独限制访问来源。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from admin_api.api import audit, auth, users, words
from core.config import get_settings
from core.db import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动时确保表结构与缺列就位（与用户端共用同一套幂等建表逻辑）。"""
    init_db()
    yield


app = FastAPI(
    title="英语练习平台 · 管理端",
    description="用户管理、词库管理与审计留痕；与用户端分进程部署",
    version="1.8.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """统一兜底错误响应，避免向前端泄露堆栈。"""
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误，请稍后重试"})


@app.get("/api/admin/health")
def health() -> dict:
    """健康检查：不暴露任何密钥内容。"""
    return {
        "status": "ok",
        "database": settings.database_url.split("://", 1)[0],
        "invite_code_required": bool(settings.admin_invite_code),
    }


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(words.router)
app.include_router(audit.router)
