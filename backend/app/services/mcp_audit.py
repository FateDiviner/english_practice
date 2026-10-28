import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp import McpAuditLog

logger = logging.getLogger(__name__)

_SENSITIVE_KEYWORDS = ("password", "token", "secret", "authorization", "content", "base64")
_MAX_TEXT_LENGTH = 500


def _redact(value: Any, key: str | None = None) -> Any:
    if key and any(keyword in key.lower() for keyword in _SENSITIVE_KEYWORDS):
        return "***"
    if isinstance(value, dict):
        return {item_key: _redact(item_value, item_key) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value[:20]]
    if isinstance(value, str) and len(value) > _MAX_TEXT_LENGTH:
        return f"{value[:_MAX_TEXT_LENGTH]}..."
    return value


def summarize_params(params: dict[str, Any] | None) -> dict[str, Any] | None:
    """脱敏工具参数，避免密码、令牌和导入文件内容进入审计表。"""
    if params is None:
        return None
    return _redact(params)


async def log_mcp_event(
    session: AsyncSession,
    *,
    admin_id: int,
    tool_name: str,
    outcome: str,
    action_type: str | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    params: dict[str, Any] | None = None,
    error_code: int | None = None,
    client_name: str | None = None,
    client_ip: str | None = None,
) -> None:
    """记录 MCP 调用；审计失败不阻断主流程。"""
    entry = McpAuditLog(
        admin_id=admin_id,
        tool_name=tool_name,
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        params_summary=summarize_params(params),
        outcome=outcome,
        error_code=error_code,
        client_name=(client_name or None) and client_name[:100],
        client_ip=(client_ip or None) and client_ip[:45],
    )
    session.add(entry)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("Failed to write MCP audit log for tool %s", tool_name)
