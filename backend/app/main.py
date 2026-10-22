from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.exception_handlers import register_exception_handlers


def create_app() -> FastAPI:
    application = FastAPI(title="English Practice API", version="0.1.0")
    register_exception_handlers(application)
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
