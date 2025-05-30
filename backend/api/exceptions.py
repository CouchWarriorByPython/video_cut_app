from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Обробник помилок валідації Pydantic"""
    errors = []
    for error in exc.errors():
        field_name = '.'.join(str(x) for x in error['loc'][1:]) if len(error['loc']) > 1 else 'unknown'
        errors.append({
            "field": field_name,
            "error": error['msg'],
            "input": error.get('input')
        })

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Помилка валідації даних",
            "errors": errors
        }
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Обробник HTTP помилок"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": str(exc.detail),
            "error": f"HTTP {exc.status_code}"
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обробник загальних помилок"""
    logger.error(f"Необроблена помилка: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Внутрішня помилка сервера",
            "error": str(exc)
        }
    )