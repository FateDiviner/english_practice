"""LangSmith 追踪配置：把 Settings 中的值桥接为 SDK 读取的环境变量。"""

import logging
import os
from typing import Any

from langsmith import get_current_run_tree

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def configure_langsmith() -> None:
    """在应用启动时把 .env 配置同步到 LangSmith SDK 依赖的环境变量。"""
    settings = get_settings()
    enabled = bool(settings.LANGSMITH_TRACING and settings.LANGSMITH_API_KEY)
    os.environ["LANGSMITH_TRACING"] = "true" if enabled else "false"
    if not enabled:
        if settings.LANGSMITH_TRACING:
            logger.warning("LANGSMITH_TRACING 已开启但缺少 LANGSMITH_API_KEY，追踪未启用")
        return

    os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
    os.environ["LANGSMITH_TRACING_SAMPLING_RATE"] = str(settings.LANGSMITH_SAMPLING_RATE)
    os.environ["LANGSMITH_HIDE_INPUTS"] = str(settings.LANGSMITH_HIDE_INPUTS).lower()
    os.environ["LANGSMITH_HIDE_OUTPUTS"] = str(settings.LANGSMITH_HIDE_OUTPUTS).lower()
    if settings.LANGSMITH_ENDPOINT:
        os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT


def annotate_trace(**metadata: Any) -> None:
    """给当前 span 补充运行时才知道的元数据；未启用追踪时静默跳过。"""
    run_tree = get_current_run_tree()
    if run_tree is not None:
        run_tree.add_metadata(metadata)
