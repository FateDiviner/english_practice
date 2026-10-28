from collections.abc import AsyncIterator, Iterator

import pytest
from app.core.config import get_settings
from app.db.session import async_session_factory
from app.main import app
from app.models.import_job import ImportJob
from app.models.mcp import McpAccessToken, McpAuditLog, McpChangeRequest, McpImportUpload
from app.models.practice_record import PracticeRecord
from app.models.practice_session import PracticeSession
from app.models.session_question import SessionQuestion
from app.models.user import User
from app.models.user_wordbook import UserWordbook
from app.models.word import Word
from app.models.word_progress import WordProgress
from app.models.wordbook import Wordbook
from app.models.wrong_word import WrongWord
from app.services.agent.client import get_llm_client
from app.services.agent.service import get_agent_service
from app.services.profile.service import get_profile_orchestrator
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select


async def clean_answer_data() -> None:
    async with async_session_factory() as session:
        user_ids = select(User.id).where(User.username.like("pytest_answer_%"))
        wordbook_ids = select(Wordbook.id).where(Wordbook.name.like("pytest_answer_wb_%"))
        session_ids = select(PracticeSession.id).where(PracticeSession.user_id.in_(user_ids))
        await session.execute(delete(McpAuditLog).where(McpAuditLog.admin_id.in_(user_ids)))
        await session.execute(
            delete(McpAccessToken).where(McpAccessToken.created_by.in_(user_ids))
        )
        await session.execute(
            delete(McpChangeRequest).where(McpChangeRequest.requested_by.in_(user_ids))
        )
        await session.execute(
            delete(McpImportUpload).where(McpImportUpload.uploaded_by.in_(user_ids))
        )
        await session.execute(delete(ImportJob).where(ImportJob.wordbook_id.in_(wordbook_ids)))
        await session.execute(delete(ImportJob).where(ImportJob.admin_id.in_(user_ids)))
        await session.execute(delete(WrongWord).where(WrongWord.user_id.in_(user_ids)))
        await session.execute(delete(WordProgress).where(WordProgress.user_id.in_(user_ids)))
        await session.execute(delete(UserWordbook).where(UserWordbook.user_id.in_(user_ids)))
        await session.execute(
            delete(PracticeRecord).where(PracticeRecord.session_id.in_(session_ids))
        )
        await session.execute(
            delete(SessionQuestion).where(SessionQuestion.session_id.in_(session_ids))
        )
        await session.execute(delete(PracticeSession).where(PracticeSession.user_id.in_(user_ids)))
        await session.execute(delete(Word).where(Word.wordbook_id.in_(wordbook_ids)))
        await session.execute(delete(Wordbook).where(Wordbook.name.like("pytest_answer_wb_%")))
        await session.execute(delete(User).where(User.username.like("pytest_answer_%")))
        await session.commit()


@pytest.fixture(autouse=True)
async def cleanup_answers() -> AsyncIterator[None]:
    """所有测试模块共用，清理 pytest_answer_* 测试数据。"""
    await clean_answer_data()
    yield
    await clean_answer_data()


@pytest.fixture(autouse=True)
def force_mock_llm(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """测试固定使用 Mock 客户端，避免读取本地 .env 里的真实模型配置。"""
    monkeypatch.setattr(get_settings(), "AI_PROVIDER", "mock")
    for cached in (get_llm_client, get_agent_service, get_profile_orchestrator):
        cached.cache_clear()
    yield
    for cached in (get_llm_client, get_agent_service, get_profile_orchestrator):
        cached.cache_clear()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
