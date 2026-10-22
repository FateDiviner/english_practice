import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import ApiResponse

logger = logging.getLogger(__name__)

ERROR_CODE_UNAUTHENTICATED = 40101
ERROR_CODE_FORBIDDEN = 40301
ERROR_CODE_CONFLICT = 40901
ERROR_CODE_VALIDATION = 42201
ERROR_CODE_UNKNOWN = 50000

_HTTP_STATUS_TO_BUSINESS_CODE = {
    401: ERROR_CODE_UNAUTHENTICATED,
    403: ERROR_CODE_FORBIDDEN,
    409: ERROR_CODE_CONFLICT,
    422: ERROR_CODE_VALIDATION,
    500: ERROR_CODE_UNKNOWN,
}


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: int,
        message: str,
        data: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.data = data


def build_error_response(
    status_code: int,
    code: int,
    message: str,
    data: Any | None = None,
) -> JSONResponse:
    payload = ApiResponse[Any](code=code, message=message, data=data)
    return JSONResponse(status_code=status_code, content=jsonable_encoder(payload))


async def _handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    return build_error_response(exc.status_code, exc.code, exc.message, exc.data)


async def _handle_validation_error(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return build_error_response(
        status_code=422,
        code=ERROR_CODE_VALIDATION,
        message="validation error",
        data=exc.errors(),
    )


async def _handle_http_exception(
    _request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    code = _HTTP_STATUS_TO_BUSINESS_CODE.get(exc.status_code, exc.status_code)
    message = exc.detail if isinstance(exc.detail, str) else "request failed"
    return build_error_response(exc.status_code, code, message)


async def _handle_unexpected_exception(
    request: Request,
    _exc: Exception,
) -> JSONResponse:
    logger.exception("Unhandled exception for %s %s", request.method, request.url.path)
    return build_error_response(500, ERROR_CODE_UNKNOWN, "internal server error")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected_exception)
