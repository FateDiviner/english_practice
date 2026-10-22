from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.db.session import async_session_factory
from app.models.user import User
from scripts.create_admin import AdminSeedConfigError, load_admin_credentials, seed_admin
from sqlalchemy import delete, select

OLD_PASSWORD = "OldAdminPass123!"
NEW_PASSWORD = "NewAdminPass123!"


def make_identity(label: str) -> dict[str, str]:
    suffix = uuid4().hex[:12]
    username = f"pytest_seed_{label}_{suffix}"
    return {
        "username": username,
        "email": f"{username}@example.com",
        "password": NEW_PASSWORD,
    }


async def clean_seed_users() -> None:
    async with async_session_factory() as session:
        await session.execute(delete(User).where(User.username.like("pytest_seed_%")))
        await session.commit()


@pytest.fixture(autouse=True)
async def cleanup_seed_users() -> AsyncIterator[None]:
    await clean_seed_users()
    yield
    await clean_seed_users()


async def test_seed_creates_missing_admin() -> None:
    identity = make_identity("missing")
    async with async_session_factory() as session:
        result = await seed_admin(
            session,
            identity["username"],
            identity["email"],
            identity["password"],
        )

    assert result.action == "created"
    async with async_session_factory() as session:
        user = await session.scalar(select(User).where(User.id == result.user_id))
        assert user is not None
        assert user.role == "admin"
        assert user.status == "active"
        assert verify_password(identity["password"], user.password_hash)


async def test_seed_upgrades_existing_user() -> None:
    identity = make_identity("upgrade")
    async with async_session_factory() as session:
        user = User(
            username=identity["username"],
            email=identity["email"],
            password_hash=hash_password(OLD_PASSWORD),
            role="user",
            status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        result = await seed_admin(
            session,
            identity["username"],
            identity["email"],
            identity["password"],
        )

    assert result.action == "upgraded_to_admin"
    assert user.role == "admin"


async def test_seed_admin_password_update_is_idempotent() -> None:
    identity = make_identity("idempotent")
    async with async_session_factory() as session:
        user = User(
            username=identity["username"],
            email=identity["email"],
            password_hash=hash_password(OLD_PASSWORD),
            role="admin",
            status="active",
        )
        session.add(user)
        await session.commit()

        first_result = await seed_admin(
            session,
            identity["username"],
            identity["email"],
            NEW_PASSWORD,
        )
        second_result = await seed_admin(
            session,
            identity["username"],
            identity["email"],
            NEW_PASSWORD,
        )

    assert first_result.action == "password_updated"
    assert second_result.action == "password_updated"
    async with async_session_factory() as session:
        stored_user = await session.scalar(select(User).where(User.id == user.id))
        assert stored_user is not None
        assert verify_password(NEW_PASSWORD, stored_user.password_hash)


def test_seed_requires_all_admin_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_USERNAME", "")
    monkeypatch.setenv("ADMIN_EMAIL", "")
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    get_settings.cache_clear()

    try:
        with pytest.raises(AdminSeedConfigError) as exc_info:
            load_admin_credentials()
        assert "ADMIN_USERNAME" in str(exc_info.value)
        assert "ADMIN_EMAIL" in str(exc_info.value)
        assert "ADMIN_PASSWORD" in str(exc_info.value)
    finally:
        get_settings.cache_clear()
