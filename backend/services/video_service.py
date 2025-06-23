import os
from typing import Dict, Any, Optional
from datetime import datetime, UTC
import math

from backend.database import create_repository
from backend.services.azure_service import AzureService
from backend.services.video_lock_service import VideoLockService
from backend.models.database import SourceVideo, AzureFilePath, VideoStatus
from backend.utils.azure_path_utils import extract_filename_from_azure_path
from backend.utils.video_utils import get_local_video_path
from backend.utils.logger import get_logger

logger = get_logger(__name__, "services.log")


class VideoService:
    """Service for working with videos using new data structure"""

    def __init__(self):
        self.source_repo = create_repository("source_videos", async_mode=False)
        self.azure_service = AzureService()
        self.lock_service = VideoLockService()

    def validate_and_register_video(self, video_url: str) -> Dict[str, Any]:
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
                status=VideoStatus.DOWNLOADING,
                size_MB=round(size_bytes / (1024 * 1024), 2) if size_bytes else None,
                created_at_utc=datetime.now(UTC).isoformat(sep=" ", timespec="seconds"),
                updated_at_utc=datetime.now(UTC).isoformat(sep=" ", timespec="seconds")
            )

            self.source_repo.create_indexes()
            video_data = source_video.model_dump()
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

    def get_videos_list_paginated(self, page: int = 1, per_page: int = 20, user_id: Optional[str] = None) -> Dict[
        str, Any]:
        """Get paginated list of videos with lock status"""
        try:
            offset = (page - 1) * per_page
            valid_statuses = [VideoStatus.NOT_ANNOTATED, VideoStatus.IN_PROGRESS, VideoStatus.ANNOTATED]
            total_filter = {"status": {"$in": valid_statuses}}
            all_videos = self.source_repo.find_all(filter_query=total_filter)
            total_count = len(all_videos)
            total_pages = math.ceil(total_count / per_page)
            videos_for_page = all_videos[offset:offset + per_page]
            video_ids = [video["_id"] for video in videos_for_page]
            lock_statuses = self.lock_service.get_all_video_locks(video_ids)

            clip_repo = create_repository("clip_videos", async_mode=False)

            processed_videos = []
            for video in videos_for_page:
                video_id = video["_id"]
                lock_status = lock_statuses.get(video_id, {"locked": False})
                can_start_work = self._can_user_start_work(video, lock_status, user_id)

                # Отримуємо метадані з першого кліпу
                first_clip = clip_repo.find_all(filter_query={"source_video_id": video_id}, limit=1)
                metadata = first_clip[0] if first_clip else {}

                processed_video = {
                    "id": video_id,
                    "azure_file_path": video.get("azure_file_path"),
                    "filename": self._get_display_filename(video),
                    "status": video.get("status", VideoStatus.NOT_ANNOTATED),
                    "created_at_utc": video.get("created_at_utc", ""),
                    "where": metadata.get("where"),
                    "when": metadata.get("when"),
                    "uav_type": metadata.get("uav_type"),
                    "duration_sec": video.get("duration_sec"),
                    "lock_status": lock_status,
                    "can_start_work": can_start_work
                }
                processed_videos.append(processed_video)

            return {
                "success": True,
                "videos": processed_videos,
                "pagination": {
                    "current_page": page,
                    "per_page": per_page,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                }
            }

        except Exception as e:
            logger.error(f"Error getting paginated videos list: {str(e)}")
            return {"success": False, "error": str(e)}

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
                    "message": str(task.info.get('error', task.result)) if hasattr(task, 'info') and task.info else str(
                        task.result)
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
                "ready_for_annotation": status == VideoStatus.NOT_ANNOTATED
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
            if status not in [VideoStatus.NOT_ANNOTATED, VideoStatus.IN_PROGRESS]:
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

    def lock_video_for_annotation(self, video_id: str, user_id: str, user_email: str) -> Dict[str, Any]:
        """Lock video for annotation by user"""
        try:
            video = self.source_repo.find_by_id(video_id)
            if not video:
                return {
                    "success": False,
                    "error": "Відео не знайдено"
                }

            if video.get("status") not in [VideoStatus.NOT_ANNOTATED, VideoStatus.IN_PROGRESS]:
                return {
                    "success": False,
                    "error": f"Відео не готове для анотування. Поточний статус: {video.get('status')}"
                }

            lock_result = self.lock_service.lock_video(video_id, user_id, user_email)

            if lock_result["success"]:
                self.source_repo.update_by_id(video_id, {
                    "status": VideoStatus.IN_PROGRESS
                })

                logger.info(f"Відео {video_id} заблоковано для анотування користувачем {user_email}")

            return lock_result

        except Exception as e:
            logger.error(f"Error locking video {video_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def unlock_video_for_annotation(self, video_id: str, user_id: str) -> Dict[str, Any]:
        """Unlock video for annotation"""
        try:
            unlock_result = self.lock_service.unlock_video(video_id, user_id)

            if unlock_result["success"]:
                video = self.source_repo.find_by_id(video_id)
                if video and video.get("status") == VideoStatus.IN_PROGRESS:
                    self.source_repo.update_by_id(video_id, {
                        "status": VideoStatus.NOT_ANNOTATED
                    })

            return unlock_result

        except Exception as e:
            logger.error(f"Error unlocking video {video_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _can_user_start_work(self, video: Dict[str, Any], lock_status: Dict[str, Any], user_id: Optional[str]) -> bool:
        """Determine if user can start work on video"""
        video_status = video.get("status")

        if video_status == VideoStatus.ANNOTATED:
            return False

        if video_status == VideoStatus.NOT_ANNOTATED:
            return not lock_status.get("locked") or (user_id and lock_status.get("user_id") == user_id)

        if video_status == VideoStatus.IN_PROGRESS:
            return user_id and lock_status.get("user_id") == user_id

        return False

    def get_video_lock_status(self, video_id: str) -> Dict[str, Any]:
        """Get video lock status"""
        try:
            return self.lock_service.get_video_lock_status(video_id)

        except Exception as e:
            logger.error(f"Error getting video lock status {video_id}: {str(e)}")
            return {
                "locked": False,
                "error": str(e)
            }

    def cleanup_expired_locks(self) -> int:
        """Clean up expired video locks"""
        try:
            return self.lock_service.cleanup_expired_locks()

        except Exception as e:
            logger.error(f"Error cleaning up expired locks: {str(e)}")
            return 0

    def update_video_status(self, video_id: str, status: str, additional_data: Optional[Dict[str, Any]] = None) -> bool:
        """Update video status and additional data"""
        try:
            update_data = {
                "status": status,
                "updated_at_utc": datetime.now(UTC).isoformat(sep=" ", timespec="seconds")
            }

            if additional_data:
                update_data.update(additional_data)

            success = self.source_repo.update_by_id(video_id, update_data)

            if success:
                logger.info(f"Video status updated: {video_id} -> {status}")

            return success

        except Exception as e:
            logger.error(f"Error updating video status {video_id}: {str(e)}")
            return False

    def get_video_by_azure_path(self, azure_file_path: AzureFilePath) -> Optional[Dict[str, Any]]:
        """Get video by Azure file path"""
        try:
            return self.source_repo.find_by_field("azure_file_path.blob_path", azure_file_path.blob_path)

        except Exception as e:
            logger.error(f"Error getting video by Azure path: {str(e)}")
            return None

    def get_video_by_id(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video by ID"""
        try:
            return self.source_repo.find_by_id(video_id)

        except Exception as e:
            logger.error(f"Error getting video by ID {video_id}: {str(e)}")
            return None

    def delete_video(self, video_id: str) -> bool:
        """Delete video record"""
        try:
            video = self.source_repo.find_by_id(video_id)
            if not video:
                return False

            success = self.source_repo.delete_by_id(video_id)

            if success:
                logger.info(f"Video deleted: {video_id}")

                azure_path_dict = video.get("azure_file_path", {})
                if azure_path_dict:
                    try:
                        from backend.utils.azure_path_utils import azure_path_dict_to_object
                        azure_path = azure_path_dict_to_object(azure_path_dict)
                        filename = extract_filename_from_azure_path(azure_path)
                        local_path = get_local_video_path(filename)

                        if os.path.exists(local_path):
                            os.remove(local_path)
                            logger.info(f"Local file deleted: {local_path}")

                    except Exception as cleanup_error:
                        logger.warning(f"Error cleaning up local file for video {video_id}: {str(cleanup_error)}")

            return success

        except Exception as e:
            logger.error(f"Error deleting video {video_id}: {str(e)}")
            return False

    def get_videos_statistics(self) -> Dict[str, Any]:
        """Get videos statistics"""
        try:
            all_videos = self.source_repo.find_all()

            total_videos = len(all_videos)
            not_annotated_videos = len([v for v in all_videos if v.get("status") == VideoStatus.NOT_ANNOTATED])
            in_progress_videos = len([v for v in all_videos if v.get("status") == VideoStatus.IN_PROGRESS])
            annotated_videos = len([v for v in all_videos if v.get("status") == VideoStatus.ANNOTATED])
            downloading_videos = len([v for v in all_videos if v.get("status") == VideoStatus.DOWNLOADING])
            download_error_videos = len([v for v in all_videos if v.get("status") == VideoStatus.DOWNLOAD_ERROR])
            annotation_error_videos = len([v for v in all_videos if v.get("status") == VideoStatus.ANNOTATION_ERROR])

            total_size_mb = sum(v.get("size_MB", 0) for v in all_videos if v.get("size_MB"))
            total_duration_sec = sum(v.get("duration_sec", 0) for v in all_videos if v.get("duration_sec"))

            return {
                "success": True,
                "statistics": {
                    "total_videos": total_videos,
                    "not_annotated_videos": not_annotated_videos,
                    "in_progress_videos": in_progress_videos,
                    "annotated_videos": annotated_videos,
                    "downloading_videos": downloading_videos,
                    "download_error_videos": download_error_videos,
                    "annotation_error_videos": annotation_error_videos,
                    "total_size_mb": round(total_size_mb, 2),
                    "total_duration_sec": total_duration_sec,
                    "total_duration_hours": round(total_duration_sec / 3600, 2) if total_duration_sec else 0
                }
            }

        except Exception as e:
            logger.error(f"Error getting videos statistics: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _get_display_filename(self, video: Dict[str, Any]) -> str:
        """Get display filename for video"""
        azure_path = video.get("azure_file_path")
        if azure_path and azure_path.get("blob_path"):
            return azure_path["blob_path"].split("/")[-1]
        return f"Video #{video.get('_id', 'unknown')}"

    def _calculate_file_size_mb(self, size_bytes: Optional[int]) -> Optional[float]:
        """Calculate file size in MB"""
        if not size_bytes:
            return None
        return round(size_bytes / (1024 * 1024), 2)

    def _format_duration(self, duration_sec: Optional[int]) -> str:
        """Format duration in human readable format"""
        if not duration_sec:
            return "Unknown"

        hours = duration_sec // 3600
        minutes = (duration_sec % 3600) // 60
        seconds = duration_sec % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"

    def _validate_video_data(self, video_data: Dict[str, Any]) -> Optional[str]:
        """Validate video data before saving"""
        required_fields = ["azure_file_path", "extension"]

        for field in required_fields:
            if field not in video_data or not video_data[field]:
                return f"Required field '{field}' is missing or empty"

        azure_path = video_data.get("azure_file_path")
        if not isinstance(azure_path, dict):
            return "azure_file_path must be a dictionary"

        required_path_fields = ["account_name", "container_name", "blob_path"]
        for field in required_path_fields:
            if field not in azure_path or not azure_path[field]:
                return f"Required azure_file_path field '{field}' is missing or empty"

        return None