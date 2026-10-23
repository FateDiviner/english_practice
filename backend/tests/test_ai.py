from httpx import AsyncClient

from tests.practice_answer_helpers import create_user


async def test_ai_placeholder_requires_login(client: AsyncClient) -> None:
    for method, path in (
        ("post", "/api/v1/ai/chat"),
        ("get", "/api/v1/ai/sessions"),
        ("post", "/api/v1/ai/sessions"),
    ):
        response = await getattr(client, method)(path)
        assert response.status_code == 401
        assert response.json()["code"] == 40101


async def test_ai_placeholder_returns_50101(client: AsyncClient) -> None:
    user, _ = await create_user(client, "ai_placeholder")
    for method, path in (
        ("post", "/api/v1/ai/chat"),
        ("get", "/api/v1/ai/sessions"),
        ("post", "/api/v1/ai/sessions"),
    ):
        response = await getattr(client, method)(path, headers=user)
        assert response.status_code == 501
        assert response.json() == {
            "code": 50101,
            "message": "not implemented",
            "data": None,
        }
