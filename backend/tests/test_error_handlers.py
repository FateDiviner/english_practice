from app.core.exception_handlers import register_exception_handlers
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel


class ValidationPayload(BaseModel):
    value: int


def build_error_test_app() -> FastAPI:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.post("/validation")
    async def validate(payload: ValidationPayload) -> dict[str, int]:
        return {"value": payload.value}

    @test_app.get("/unauthorized")
    async def unauthorized() -> None:
        raise HTTPException(status_code=401, detail="not authenticated")

    @test_app.get("/forbidden")
    async def forbidden() -> None:
        raise HTTPException(status_code=403, detail="forbidden")

    @test_app.get("/unexpected")
    async def unexpected() -> None:
        raise RuntimeError("unexpected test error")

    return test_app


async def test_error_handlers_use_business_codes() -> None:
    transport = ASGITransport(app=build_error_test_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        validation_response = await client.post("/validation", json={"value": "invalid"})
        unauthorized_response = await client.get("/unauthorized")
        forbidden_response = await client.get("/forbidden")
        unexpected_response = await client.get("/unexpected")

    assert validation_response.status_code == 422
    assert validation_response.json()["code"] == 42201
    assert unauthorized_response.status_code == 401
    assert unauthorized_response.json()["code"] == 40101
    assert forbidden_response.status_code == 403
    assert forbidden_response.json()["code"] == 40301
    assert unexpected_response.status_code == 500
    assert unexpected_response.json()["code"] == 50000
