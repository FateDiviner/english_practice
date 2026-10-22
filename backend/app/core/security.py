from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings


class TokenDecodeError(Exception):
    """JWT 无法解析、过期或缺少必要字段。"""


def hash_password(password: str) -> str:
    """使用 bcrypt 生成密码哈希，绝不保存明文密码。"""
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError("密码超过 bcrypt 允许的 72 字节上限")

    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与 bcrypt 哈希是否匹配。"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (TypeError, ValueError):
        return False


def create_access_token(user_id: int, role: str) -> str:
    """签发包含 sub、role、exp、iat 的 HS256 JWT。"""
    settings = get_settings()
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expires_at,
        "iat": issued_at,
    }

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """解析 JWT，并由 python-jose 校验签名与 exp。"""
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise TokenDecodeError("JWT 无效或已过期") from exc

    if not payload.get("sub") or not payload.get("role"):
        raise TokenDecodeError("JWT 缺少必要字段")

    return payload
