import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import BusinessException
from app.core.responses import error_response

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BusinessException)
    async def handle_business_exception(_: Request, exc: BusinessException):
        return error_response(exc.status_code, exc.code, exc.message, exc.data)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(_: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(map(str, item["loc"])), "message": item["msg"]}
            for item in exc.errors()
        ]
        return error_response(422, 42201, "validation error", {"errors": details})

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_: Request, exc: HTTPException):
        return error_response(exc.status_code, exc.status_code * 100 + 1, str(exc.detail))

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_exception(_: Request, exc: SQLAlchemyError):
        logger.exception("database error", exc_info=exc)
        return error_response(500, 50001, "database operation failed")

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(_: Request, exc: Exception):
        logger.exception("unexpected error", exc_info=exc)
        return error_response(500, 50000, "internal server error")

