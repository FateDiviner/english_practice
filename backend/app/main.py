"""FastAPI 应用入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, chat, practice, stats, user, wordbooks
from app.api.admin import audit as admin_audit
from app.api.admin import kb as admin_kb
from app.api.admin import rag as admin_rag
from app.api.admin import relations as admin_relations
from app.api.admin import users as admin_users
from app.api.admin import words as admin_words
from app.config import get_settings
from app.db import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动时确保表结构与词书数据就绪，并后台预热 RAG 索引。"""
    init_db()
    _seed_wordbooks()
    # 预热在后台线程里做，不阻塞启动也不占用户请求：
    # 313 个词条要几十次 embedding 调用，放进第一个用户请求会让那次对话卡十几秒
    if settings.rag_enabled:
        from app.rag import corpus

        corpus.warm_up()
    yield


def _seed_wordbooks() -> None:
    """把内置词书导入数据库。幂等，已存在的词书只补缺失词条。

    放在启动路径上而不是只靠 scripts/init_db：容器里跑的是 main.py，
    不手动执行那条脚本的话 wordbooks 与 words 会一直是空表，
    界面上表现为「没有词书」。本地 python main.py 与容器行为因此保持一致。

    失败只记日志不让启动中断——播种失败不该让整个服务起不来，
    否则连排查问题的接口都访问不到。
    """
    import logging

    logger = logging.getLogger(__name__)
    try:
        from scripts.init_db import seed_wordbooks

        stats = seed_wordbooks()
    except Exception:  # noqa: BLE001 - 播种失败不能阻断启动
        logger.exception("内置词书导入失败，词书中心将为空")
        return
    if stats["books"] or stats["words"]:
        logger.info(
            "内置词书就绪：新增 %s 本 / %s 词，跳过已存在 %s 词",
            stats["books"],
            stats["words"],
            stats["skipped"],
        )


app = FastAPI(
    title="英语练习平台",
    description="默写记忆 + AI 场景实战的极简英语练习后端",
    version="1.5.0",
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
app.include_router(chat.router)

# 管理端路由：与用户端同进程共库，权限由 require_admin 逐路由把关
app.include_router(admin_users.router)
app.include_router(admin_words.router)
app.include_router(admin_relations.router)
app.include_router(admin_kb.router)
app.include_router(admin_rag.router)
app.include_router(admin_audit.router)
