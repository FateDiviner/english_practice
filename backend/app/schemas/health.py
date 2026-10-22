from typing import Literal

from pydantic import BaseModel

from app.schemas.common import ApiResponse


class HealthData(BaseModel):
    status: Literal["up"]


class HealthResponse(ApiResponse[HealthData]):
    pass
