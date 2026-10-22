from fastapi import APIRouter

from app.schemas.health import HealthData, HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(code=0, message="ok", data=HealthData(status="up"))
