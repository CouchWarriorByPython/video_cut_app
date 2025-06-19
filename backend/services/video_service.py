import os
from typing import Dict, Any, Optional
from datetime import datetime, UTC

from backend.database import create_repository
from backend.services.azure_service import AzureService
from backend.models.database import SourceVideo, AzureFilePath
from backend.utils.azure_path_utils import extract_filename_from_azure_path, get_file_extension_from_azure_path
from backend.utils.video_utils import get_local_video_path
from backend.utils.logger import get_logger

logger = get_logger(__name__, "services.log")


class VideoService:
    """Service for working with videos using new data structure"""

    def __init__(self):
        self.source_repo = create_repository("source_videos", async_mode=False)
        self.azure_service = AzureService()

    def validate_and_register_video(self, video_url: str, where: Optional[str], when: Optional[str]) -> Dict[str, Any]:
        """Validate Azure URL and register video for async processing"""
        try:
            validation_result = self.azure_service.validate_azure_url(video_url)

            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": f"Invalid Azure URL: {validation_result['error']}"
                }

            azure_path = validation_result["azure_path"]
            filename = validation_result["filename"]
            size_bytes = validation_result["size_bytes"]

            source_video = SourceVideo(
                azure_file_path=azure_path,
                extension=get_file_extension_from_azure_path(azure_path),
                uav_type=None,
                where=where,
                when=when,
                size_MB=round(size_bytes / (1024 * 1024), 2) if size_bytes else None,
                created_at_utc=datetime.now(UTC).isoformat(sep=" ", timespec="seconds"),
                updated_at_utc=datetime.now(UTC).isoformat(sep=" ", timespec="seconds")
            )

            self.source_repo.create_indexes()

            video_data = source_video.model_dump()
            video_data["status"] = "queued"

            record_id = self.source_repo.save_document(video_data)

            from backend.background_tasks.tasks.video_download_conversion import download_and_convert_video
            task = download_and_convert_video.delay(azure_path.model_dump())

            logger.info(f"Video registered and queued: {filename}, task_id: {task.id}")

            return {
                "success": True,
                "_id": record_id,
                "azure_file_path": azure_path,
                "filename": filename,
                "task_id": task.id,
                "message": "Video registered and queued for processing"
            }

        except Exception as e:
            logger.error(f"Error registering video: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get Celery task execution status"""
        try:
            from backend.background_tasks.app import app
            task = app.AsyncResult(task_id)

            if task.state == 'PENDING':
                response = {
                    "status": "pending",
                    "progress": 0,
                    "stage": "queued",
                    "message": "Task queued for execution"
                }
            elif task.state == 'PROGRESS':
                response = {
                    "status": "processing",
                    "progress": task.info.get('progress', 0),
                    "stage": task.info.get('stage', 'unknown'),
                    "message": task.info.get('message', 'Processing...')
                }
            elif task.state == 'SUCCESS':
                response = {
                    "status": "completed",
                    "progress": 100,
                    "stage": "completed",
                    "message": "Video ready for annotation",
                    "result": task.result
                }
            elif task.state == 'FAILURE':
                response = {
                    "status": "failed",
                    "progress": task.info.get('progress', 0) if hasattr(task, 'info') and task.info else 0,
                    "stage": "failed",
                    "message": str(task.info.get('error', task.result)) if hasattr(task, 'info') and task.info else str(task.result)
                }
            else:
                response = {
                    "status": task.state.lower(),
                    "progress": 0,
                    "stage": "unknown",
                    "message": f"Unknown state: {task.state}"
                }

            return {
                "success": True,
                **response
            }

        except Exception as e:
            logger.error(f"Error getting task status {task_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_video_status(self, azure_file_path: AzureFilePath) -> Dict[str, Any]:
        """Get video processing status by Azure file path"""
        try:
            video = self.source_repo.find_by_field("azure_file_path.blob_path", azure_file_path.blob_path)

            if not video:
                return {
                    "success": False,
                    "error": "Video not found"
                }

            status = video.get("status", "unknown")
            filename = extract_filename_from_azure_path(azure_file_path)

            return {
                "success": True,
                "status": status,
                "filename": filename,
                "ready_for_annotation": status in ["ready", "not_annotated"]
            }

        except Exception as e:
            logger.error(f"Error getting video status: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_video_for_streaming(self, azure_file_path: AzureFilePath) -> Optional[str]:
        """Get local video path for streaming"""
        try:
            video = self.source_repo.find_by_field("azure_file_path.blob_path", azure_file_path.blob_path)

            if not video:
                logger.error(f"Video not found: {azure_file_path.blob_path}")
                return None

            status = video.get("status")
            if status not in ["ready", "not_annotated"]:
                logger.warning(f"Video not ready for viewing, status: {status}")
                return None

            filename = extract_filename_from_azure_path(azure_file_path)
            if not filename:
                logger.error(f"Filename not found for: {azure_file_path.blob_path}")
                return None

            local_path = get_local_video_path(filename)

            if not os.path.exists(local_path):
                logger.error(f"Local file not found: {local_path}")
                return None

            return local_path

        except Exception as e:
            logger.error(f"Error getting video for streaming: {str(e)}")
            return None

    def get_videos_list(self) -> Dict[str, Any]:
        """Get list of videos ready for annotation or still processing"""
        try:
            videos_data = self.source_repo.find_all(
                filter_query={"status": {"$ne": "annotated"}}
            )

            return {
                "success": True,
                "videos": videos_data
            }
        except Exception as e:
            logger.error(f"Error getting videos list: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_annotation(self, azure_file_path: AzureFilePath) -> Dict[str, Any]:
        """Get existing annotation for video"""
        try:
            annotation = self.source_repo.find_by_field("azure_file_path.blob_path", azure_file_path.blob_path)

            if not annotation:
                return {
                    "success": False,
                    "error": f"Annotation for video '{azure_file_path.blob_path}' not found"
                }

            return {
                "success": True,
                "annotation": annotation
            }

        except Exception as e:
            logger.error(f"Error getting annotation: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }