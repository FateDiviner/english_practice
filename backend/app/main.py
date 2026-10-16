"""FastAPI 应用入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, chat, practice, stats, user, wordbooks
from app.api.admin import audit_router
from app.config import get_settings
from app.db import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动时确保表结构存在。"""
    init_db()
    yield


app = FastAPI(
    title="英语练习平台",
    description="默写记忆 + AI 场景实战的极简英语练习后端",
    version="1.6.0",
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


@app.get("/api/health")
def health() -> dict:
    """健康检查，同时暴露 AI 是否已配置（不含任何密钥内容）。"""
    return {"status": "ok", "ai_enabled": settings.ai_enabled}


app.include_router(auth.router)
app.include_router(wordbooks.router)
app.include_router(practice.router)
app.include_router(stats.router)
app.include_router(user.router)
app.include_router(audit_router)
app.include_router(chat.router)
