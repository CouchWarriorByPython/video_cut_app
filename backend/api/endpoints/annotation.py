from fastapi import APIRouter, HTTPException, Depends
from typing import Annotated

from backend.models.api import (
    SaveFragmentsRequest, SaveFragmentsResponse, ErrorResponse,
    GetAnnotationResponse, SaveAnnotationRequest, SaveAnnotationResponse
)
from backend.services.annotation_service import AnnotationService
from backend.models.shared import AzureFilePath
from backend.api.dependencies import get_current_user, get_azure_path_from_query
from backend.utils.logger import get_logger

logger = get_logger(__name__, "api.log")
router = APIRouter(tags=["annotation"])


@router.get(
    "/get_annotation",
    response_model=GetAnnotationResponse,
    summary="Отримати анотацію відео",
    description="Повертає існуючу анотацію для відео за його Azure шляхом",
    responses={
        404: {"model": ErrorResponse, "description": "Анотація не знайдена"},
        422: {"model": ErrorResponse, "description": "Невалідні параметри Azure path"}
    }
)
async def get_annotation(
    _current_user: Annotated[dict, Depends(get_current_user)],
    azure_path: Annotated[AzureFilePath, Depends(get_azure_path_from_query)]
) -> GetAnnotationResponse:
    """Отримати існуючу анотацію для відео"""
    annotation_service = AnnotationService()
    result = annotation_service.get_annotation(azure_path)

    if not result["success"]:
        status_code = 404 if "не знайдено" in result["error"] else 500
        raise HTTPException(status_code=status_code, detail=result["error"])

    return GetAnnotationResponse(annotation=result["annotation"])


@router.post(
    "/save_fragments",
    response_model=SaveFragmentsResponse,
    summary="Зберегти фрагменти відео",
    description="Зберігає розмічені фрагменти відео та метадані для подальшої обробки Celery",
    responses={
        400: {"model": ErrorResponse, "description": "Невалідні дані або кліп занадто короткий"},
        404: {"model": ErrorResponse, "description": "Відео не знайдено"},
        422: {"model": ErrorResponse, "description": "Помилка валідації даних"}
    }
)
async def save_fragments(
    data: SaveFragmentsRequest,
    _current_user: Annotated[dict, Depends(get_current_user)]
) -> SaveFragmentsResponse:
    """Зберегти фрагменти відео та метадані"""
    annotation_service = AnnotationService()

    result = await annotation_service.save_fragments_and_metadata(
        data.azure_file_path, data.data
    )

    if not result["success"]:
        status_code = 404 if "не знайдено" in result["error"] else 400 if "короткий" in result["error"] else 500
        raise HTTPException(status_code=status_code, detail=result["error"])

    return SaveFragmentsResponse(
        id=result["_id"],
        task_id=result.get("task_id"),
        message=result["message"]
    )


@router.post(
    "/save_annotation",
    response_model=SaveAnnotationResponse,
    summary="Зберегти анотацію без обробки",
    description="Зберігає поточний стан анотації в базу без запуску обробки кліпів",
    responses={
        400: {"model": ErrorResponse, "description": "Невалідні дані"},
        404: {"model": ErrorResponse, "description": "Відео не знайдено"},
        422: {"model": ErrorResponse, "description": "Помилка валідації даних"}
    }
)
async def save_annotation(
    data: SaveAnnotationRequest,
    _current_user: Annotated[dict, Depends(get_current_user)]
) -> SaveAnnotationResponse:
    """Зберегти анотацію без обробки"""
    annotation_service = AnnotationService()

    result = await annotation_service.save_annotation_only(
        data.azure_file_path, data.data
    )

    if not result["success"]:
        status_code = 404 if "не знайдено" in result["error"] else 400
        raise HTTPException(status_code=status_code, detail=result["error"])

    return SaveAnnotationResponse(
        id=result["_id"],
        message=result["message"]
    )