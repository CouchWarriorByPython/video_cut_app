from fastapi import APIRouter, HTTPException, Query

from backend.models.api import (
    SaveFragmentsRequest, SaveFragmentsResponse, ErrorResponse,
    GetAnnotationResponse
)
from backend.services.annotation_service import AnnotationService
from backend.api.dependencies import convert_db_annotation_to_response
from backend.background_tasks.tasks.video_processing import process_video_annotation
from backend.utils.logger import get_logger
from backend.utils.azure_path_utils import azure_path_to_url
from backend.models.database import AzureFilePath

logger = get_logger(__name__, "api.log")

router = APIRouter(tags=["annotation"])


@router.get("/get_annotation",
            response_model=GetAnnotationResponse,
            responses={
                404: {"model": ErrorResponse},
                500: {"model": ErrorResponse}
            })
async def get_annotation(
    account_name: str = Query(...),
    container_name: str = Query(...),
    blob_path: str = Query(...)
) -> GetAnnotationResponse:
    """Отримання існуючої анотації для відео"""
    annotation_service = AnnotationService()

    azure_path = AzureFilePath(
        account_name=account_name,
        container_name=container_name,
        blob_path=blob_path
    )

    result = annotation_service.get_annotation(azure_path)

    if not result["success"]:
        if "не знайдено" in result["error"]:
            raise HTTPException(status_code=404, detail=result["error"])
        else:
            raise HTTPException(status_code=500, detail=result["error"])

    annotation = convert_db_annotation_to_response(result["annotation"])
    return GetAnnotationResponse(annotation=annotation)


@router.post("/save_fragments",
             response_model=SaveFragmentsResponse,
             responses={
                 400: {"model": ErrorResponse},
                 404: {"model": ErrorResponse},
                 500: {"model": ErrorResponse}
             })
async def save_fragments(data: SaveFragmentsRequest) -> SaveFragmentsResponse:
    """Збереження фрагментів відео та метаданих"""
    annotation_service = AnnotationService()

    result = annotation_service.save_fragments_and_metadata(
        data.azure_file_path, data.data
    )

    if not result["success"]:
        if "не знайдено" in result["error"]:
            raise HTTPException(status_code=404, detail=result["error"])
        elif "занадто короткий" in result["error"]:
            raise HTTPException(status_code=400, detail=result["error"])
        else:
            raise HTTPException(status_code=500, detail=result["error"])

    task_id = None
    if not result.get("skip_processing", False):
        azure_link = azure_path_to_url(data.azure_file_path)
        task_result = process_video_annotation.delay(azure_link)
        task_id = task_result.id
        logger.info(f"Запущено обробку для відео: {azure_link}, task_id: {task_id}")

    return SaveFragmentsResponse(
        id=result["_id"],
        task_id=task_id,
        message=result["message"]
    )