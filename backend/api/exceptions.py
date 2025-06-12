from typing import cast
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.utils.logger import get_logger

logger = get_logger(__name__, "api.log")


def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обробник помилок валідації Pydantic"""
    validation_error = cast(RequestValidationError, exc)

    errors = []
    for error in validation_error.errors():
        field_name = '.'.join(str(x) for x in error['loc'][1:]) if len(error['loc']) > 1 else 'unknown'
        errors.append({
            "field": field_name,
            "error": error['msg'],
            "input": error.get('input')
        })

    logger.warning(f"Помилка валідації для {request.method} {request.url}: {len(errors)} помилок")

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Помилка валідації даних",
            "errors": errors
        }
    )


def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обробник HTTP помилок"""
    http_error = cast(StarletteHTTPException, exc)

    logger.warning(f"HTTP помилка {http_error.status_code} для {request.method} {request.url}")

    return JSONResponse(
        status_code=http_error.status_code,
        content={
            "success": False,
            "message": str(http_error.detail),
            "error": f"HTTP {http_error.status_code}"
        }
    )


def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обробник загальних помилок"""
    logger.error(f"Необроблена помилка для {request.method} {request.url}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Внутрішня помилка сервера",
            "error": str(exc)
        }
    )
