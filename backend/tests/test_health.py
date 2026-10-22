from httpx import AsyncClient


async def test_health_returns_unified_response(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "ok",
        "data": {"status": "up"},
    }


async def test_not_found_returns_unified_error_response(client: AsyncClient) -> None:
    response = await client.get("/api/v1/not-found")

    assert response.status_code == 404
    assert response.json() == {
        "code": 404,
        "message": "Not Found",
        "data": None,
    }
