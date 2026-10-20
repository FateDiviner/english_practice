"""应用配置：统一从环境变量 / .env 读取，严禁将凭证硬编码于业务代码。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """全局配置对象。"""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 数据库
    database_url: str = "sqlite:///./english_practice.db"

    # 认证
    secret_key: str = "dev-secret-key-please-override"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    # AI 伴学（OpenAI 兼容协议）
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_timeout_seconds: float = 60.0

    # 跨域
    # 跨域
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- RAG ----
    # embedding 走与对话同一个 OpenAI 兼容供应商，不引入本地模型
    embedding_model: str = "text-embedding-v3"
    # 供应商硬上限是 10 条（超了直接 400 batch size is invalid）。
    # 换供应商时先实测上限再改，失败是静默降级的，症状只会表现为「向量路没召回」
    embedding_batch_size: int = 10
    # text-embedding-v3 实测返回 1024 维；换模型必须同步改这里，
    # 否则已有索引与新向量维度不一致，检索会直接崩
    embedding_dimension: int = 1024
    embedding_timeout_seconds: float = 30.0

    # 可插拔：阶段列表全部走环境变量，增删阶段不改代码
    rag_enabled: bool = True
    rag_strategy: str = "naive"
    rag_stages_pre: str = "normalize,lang_detect,intent_gate,keywords,rewrite"
    rag_stages_retrieve: str = "bm25,vector,graph"
    rag_stages_fuse: str = "rrf"
    rag_stages_rerank: str = "lexical"
    rag_stages_post: str = "threshold,dedup,compress,cite"
    # 默认关：开启后每次多一轮 LLM 调用，会吃掉 2 秒首字延迟预算
    rag_llm_rerank: bool = False
    rag_crag_max_rounds: int = 2
    rag_top_k: int = 6
    # 最高分低于此值则不注入上下文，防止不相关内容污染答案。
    # 注意标度：RRF 融合分是 Σ 1/(60+rank)，单路第一名只有 0.0164，
    # 三路同时第一也不过 0.049。默认 0.016 ≈ 「至少在一路里排第一」。
    # 图谱路是人工维护的关系，固定给 1.0，天然能过阈值。
    # 调这个值请用管理端的检索调试页看 trace，别凭感觉改。
    rag_score_threshold: float = 0.016
    rag_max_context_chars: int = 3000
    rag_trace_enabled: bool = False
    rag_index_dir: str = "data/rag_index"

    # ---- 知识库 ----
    kb_max_upload_bytes: int = 10 * 1024 * 1024
    kb_chunk_chars: int = 500
    kb_chunk_overlap: int = 100

    @property
    def cors_origin_list(self) -> list[str]:
        """将逗号分隔的跨域配置解析为列表。"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def ai_enabled(self) -> bool:
        """三项 AI 配置齐全时才走真实模型，否则降级 Mock。"""
        return bool(self.ai_base_url and self.ai_api_key and self.ai_model)


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例。"""
    return Settings()
