import os

from typing import Dict, Any

from backend.background_tasks.app import app
from backend.background_tasks.tasks.clip_processing import process_all_video_clips
from backend.services.clip_processing_service import ClipProcessingService
from backend.services.video_service import VideoService
from backend.utils.azure_path_utils import parse_azure_blob_url_to_path
from backend.utils.logger import get_logger
from backend.database.connection import DatabaseConnection

logger = get_logger(__name__, "tasks.log")


@app.task(name="process_video_annotation", bind=True)
def process_video_annotation(self, azure_link: str) -> Dict[str, Any]:
    """Process video annotations using new clip_videos structure"""
    logger.info(f"Starting video annotation processing: {azure_link}")

    try:
        # Ensure database connection
        if not DatabaseConnection.is_connected():
            DatabaseConnection.connect()

        azure_path = parse_azure_blob_url_to_path(azure_link)
        video_service = VideoService()

        # Перевіряємо статус відео
        video_status = video_service.get_video_status(azure_path)
        if not video_status.ready_for_annotation:
            return {
                "status": "error",
                "message": f"Video not ready for annotation: {video_status.status}"
            }

        # Запускаємо обробку всіх кліпів через іншу задачу
        clip_service = ClipProcessingService()
        result = clip_service.process_all_clips_for_video(str(video_status.id))

        if result["status"] == "error":
            return result

        # Запускаємо асинхронну задачу для обробки кліпів
        task = process_all_video_clips.delay(str(video_status.id))

        logger.info(f"Started clips processing for video: {azure_link}, task_id: {task.id}")

        return {
            "status": "success",
            "message": f"Started processing {result.get('total_clips', 0)} clips",
            "task_id": task.id,
            "total_clips": result.get('total_clips', 0),
            "source_video_id": str(video_status.id)
        }

    except Exception as e:
        logger.error(f"Error processing video {azure_link}: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.task(name="cleanup_source_video_files")
def cleanup_source_video_files(source_video_ids: list) -> Dict[str, Any]:
    """Clean up local source video files after processing"""
    from backend.utils.video_utils import get_local_video_path, cleanup_file
    from backend.database import create_source_video_repository
    from backend.utils.azure_path_utils import extract_filename_from_azure_path
    from backend.models.shared import AzureFilePath

    logger.info(f"Starting cleanup for {len(source_video_ids)} source videos")

    try:
        # Ensure database connection
        if not DatabaseConnection.is_connected():
            DatabaseConnection.connect()

        source_repo = create_source_video_repository()
        cleaned_files = 0
        failed_cleanups = 0

        for source_video_id in source_video_ids:
            try:
                source_video = source_repo.get_by_id(source_video_id)
                if not source_video:
                    logger.warning(f"Source video not found for cleanup: {source_video_id}")
                    continue

                azure_path = AzureFilePath(
                    account_name=source_video.azure_file_path.account_name,
                    container_name=source_video.azure_file_path.container_name,
                    blob_path=source_video.azure_file_path.blob_path
                )
                filename = extract_filename_from_azure_path(azure_path)
                local_path = get_local_video_path(filename)

                if os.path.exists(local_path):
                    cleanup_file(local_path)
                    logger.info(f"Cleaned up local file: {local_path}")
                    cleaned_files += 1

            except Exception as e:
                logger.error(f"Error cleaning up source video {source_video_id}: {str(e)}")
                failed_cleanups += 1

        return {
            "status": "completed",
            "message": f"Cleanup completed: {cleaned_files} files cleaned, {failed_cleanups} failed",
            "cleaned_files": cleaned_files,
            "failed_cleanups": failed_cleanups
        }

    except Exception as e:
        logger.error(f"Error in cleanup task: {str(e)}")
        return {"status": "error", "message": str(e)}