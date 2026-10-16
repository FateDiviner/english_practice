"""用户注册、登录、游客体验与历史数据迁移。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models.chat import ChatMessage
from core.models.record import UserWordRecord
from core.models.session import PracticeSessionRecord
from core.models.user import User
from core.security import create_access_token, hash_password, verify_password
from app.services import stats_service

GUEST_PREFIX = "guest_"
GUEST_PASSWORD = "guest-session-only"


class AuthError(Exception):
    """业务层认证错误，由 API 层转换为 HTTP 响应。"""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_user_by_username(db: Session, username: str) -> User | None:
    """按用户名查找用户。"""
    return db.scalar(select(User).where(User.username == username))


def create_user(db: Session, username: str, password: str, is_guest: bool = False) -> User:
    """创建用户（密码一律哈希存储）。"""
    user = User(username=username, password_hash=hash_password(password), is_guest=is_guest)
    db.add(user)
    db.flush()
    return user


def register(db: Session, username: str, password: str, guest_id: int | None = None) -> User:
    """注册正式账号，成功后将游客期数据迁移至该账号。"""
    if get_user_by_username(db, username):
        raise AuthError("用户名已被注册", status_code=409)
    if len(username.strip()) < 3:
        raise AuthError("用户名至少 3 个字符")

    user = create_user(db, username.strip(), password)
    migrated = False
    if guest_id is not None:
        migrated = migrate_guest_data(db, guest_id, user)
    db.commit()
    db.refresh(user)
    user.__dict__["migrated"] = migrated
    return user


def login(db: Session, username: str, password: str, guest_id: int | None = None) -> User:
    """校验账号密码，成功后同样迁移游客数据。"""
    user = get_user_by_username(db, username.strip())
    if user is None or user.is_guest or not verify_password(password, user.password_hash):
        raise AuthError("用户名或密码不正确", status_code=401)

    migrated = False
    if guest_id is not None and guest_id != user.id:
        migrated = migrate_guest_data(db, guest_id, user)
    db.commit()
    db.refresh(user)
    user.__dict__["migrated"] = migrated
    return user


def create_guest(db: Session) -> User:
    """一键游客体验：创建临时账号并签发令牌，降低试用门槛。"""
    username = f"{GUEST_PREFIX}{uuid.uuid4().hex[:12]}"
    user = create_user(db, username, GUEST_PASSWORD, is_guest=True)
    db.commit()
    db.refresh(user)
    return user


def migrate_guest_data(db: Session, guest_id: int, target: User) -> bool:
    """把游客账号的练习记录与对话历史合并到正式账号。

    同一单词若双方都有记录则合并计数，取更强的记忆状态，避免进度覆盖丢失。
    """
    guest = db.get(User, guest_id)
    if guest is None or not guest.is_guest or guest.id == target.id:
        return False

    existing = {
        record.word_id: record
        for record in db.scalars(
            select(UserWordRecord).where(UserWordRecord.user_id == target.id)
        ).all()
    }

    moved = 0
    for record in db.scalars(
        select(UserWordRecord).where(UserWordRecord.user_id == guest.id)
    ).all():
        current = existing.get(record.word_id)
        if current is None:
            # 必须通过关系属性指派：只改外键列的话，record 仍留在
            # guest.records 集合里，删除游客时 SQLAlchemy 会把外键置空。
            record.user = target
            existing[record.word_id] = record
        else:
            current.wrong_count += record.wrong_count
            current.right_count += record.right_count
            current.ease_stage = max(current.ease_stage, record.ease_stage)
            if record.status == "wrong":
                current.status = "wrong"
            elif record.status == "mastered" and current.status != "wrong":
                current.status = "mastered"
            db.delete(record)
        moved += 1

    for message in db.scalars(
        select(ChatMessage).where(ChatMessage.user_id == guest.id)
    ).all():
        # 同上：走关系属性，避免与待删除的游客记录冲突
        message.user = target
        moved += 1

    for session_record in db.scalars(
        select(PracticeSessionRecord).where(PracticeSessionRecord.user_id == guest.id)
    ).all():
        session_record.user = target
        moved += 1

    if guest.active_wordbook_id and not target.active_wordbook_id:
        target.active_wordbook_id = guest.active_wordbook_id

    # 连续打卡不能直接取两个计数器的较大值：那样会把其中一方已经断签的
    # 旧天数一起继承下来。练习会话已合并，直接按合并后的日期反推。
    db.flush()
    streak, last_on = stats_service.recompute_streak(db, target.id)
    target.consecutive_days = streak
    target.last_checkin_date = last_on.isoformat() if last_on else None

    db.delete(guest)
    db.flush()
    return moved > 0


def issue_token(user: User) -> str:
    """为用户签发访问令牌。"""
    return create_access_token(subject=str(user.id), extra={"guest": user.is_guest})
