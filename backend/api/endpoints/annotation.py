from fastapi import APIRouter, HTTPException, Depends

from backend.models.api import (
    SaveFragmentsRequest, SaveFragmentsResponse, ErrorResponse,
    GetAnnotationResponse
)
from backend.services.annotation_service import AnnotationService
from backend.services.video_service import VideoService
from backend.api.dependencies import convert_db_annotation_to_response, require_any_role
from backend.background_tasks.tasks.video_processing import process_video_annotation
from backend.utils.logger import get_logger

logger = get_logger(__name__, "api.log")

router = APIRouter(tags=["annotation"])


@router.get("/get_annotation",
            response_model=GetAnnotationResponse,
            dependencies=[Depends(require_any_role())],
            responses={
                404: {"model": ErrorResponse},
                500: {"model": ErrorResponse}
            })
async def get_annotation(azure_link: str) -> GetAnnotationResponse:
    """Отримання існуючої анотації для відео"""
    video_service = VideoService()

    result = video_service.get_annotation(azure_link)

    if not result["success"]:
        if "не знайдено" in result["error"]:
            raise HTTPException(status_code=404, detail=result["error"])
        else:
            raise HTTPException(status_code=500, detail=result["error"])

    annotation = convert_db_annotation_to_response(result["annotation"])
    return GetAnnotationResponse(annotation=annotation)


@router.post("/save_fragments",
             response_model=SaveFragmentsResponse,
             dependencies=[Depends(require_any_role())],
             responses={
                 400: {"model": ErrorResponse},
                 404: {"model": ErrorResponse},
                 500: {"model": ErrorResponse}
             })
async def save_fragments(data: SaveFragmentsRequest) -> SaveFragmentsResponse:
    """Збереження фрагментів відео та метаданих"""
    annotation_service = AnnotationService()

    result = annotation_service.save_fragments_and_metadata(
        data.azure_link, data.data
    )

    if not result["success"]:
        if "не знайдено" in result["error"]:
            raise HTTPException(status_code=404, detail=result["error"])
        elif "занадто короткий" in result["error"]:
            raise HTTPException(status_code=400, detail=result["error"])
        else:
            raise HTTPException(status_code=500, detail=result["error"])

    # Запускаємо Celery задачу якщо не skip
    task_id = None
    if not result.get("skip_processing", False):
        task_result = process_video_annotation.delay(data.azure_link)
        task_id = task_result.id
        logger.info(f"Запущено обробку для відео: {data.azure_link}, task_id: {task_id}")

    return SaveFragmentsResponse(
        id=result["_id"],  # Маппінг _id -> id
        task_id=task_id,
        message=result["message"]
    )