from typing import Dict, Any, Optional

from backend.database import create_source_video_repository, create_clip_video_repository, create_cvat_settings_repository
from backend.services.cvat_service import CVATService
from backend.models.documents import AzureFilePathDocument
from backend.models.shared import AzureFilePath, CVATSettings
from backend.models.api import (
    VideoAnnotationResponse, VideoMetadataResponse,
    ClipInfoResponse
)
from backend.utils.azure_path_utils import generate_clip_azure_path
from backend.utils.logger import get_logger

logger = get_logger(__name__, "services.log")


class AnnotationService:
    """Service for video annotation operations and metadata management"""

    def __init__(self):
        self.source_repo = create_source_video_repository()
        self.clip_repo = create_clip_video_repository()
        self.cvat_settings_repo = create_cvat_settings_repository()  # Додаємо цей рядок
        self.cvat_service = CVATService()

    def save_fragments_and_metadata(self, azure_file_path: AzureFilePath, annotation_data: Dict[str, Any]) -> Dict[
        str, Any]:
        """Save fragments and metadata with comprehensive validation"""
        existing = None
        try:
            metadata = annotation_data.get("metadata", {})
            skip_annotation = metadata.get("skip", False)

            existing = self.source_repo.get_by_field("azure_file_path.blob_path", azure_file_path.blob_path)
            if not existing:
                return {
                    "success": False,
                    "error": f"Video with path {azure_file_path.blob_path} not found"
                }

            clips = annotation_data.get("clips", {})
            validation_error = self._validate_clips_duration(clips)
            if validation_error:
                return {
                    "success": False,
                    "error": validation_error
                }

            update_data = {
                "skip_annotation": skip_annotation,
                "status": "annotated"
            }

            success = self.source_repo.update_by_id(str(existing.id), update_data)
            if not success:
                self.source_repo.update_by_id(str(existing.id), {"status": "annotation_error"})
                return {
                    "success": False,
                    "error": "Failed to update document"
                }

            record_id = str(existing.id)

            if skip_annotation:
                success_message = "Data successfully saved. Processing skipped (skip_annotation)."
                logger.info(f"Video skipped (skip_annotation): {azure_file_path.blob_path}")
                task_id = None
            else:
                self._prepare_clips_for_processing(str(existing.id), azure_file_path, clips, metadata)
                success_message = "Data successfully saved. Processing started."
                task_id = None

            return {
                "success": True,
                "_id": record_id,
                "task_id": task_id,
                "message": success_message,
                "skip_processing": skip_annotation
            }

        except Exception as e:
            logger.error(f"Error saving annotation: {str(e)}")

            if existing:
                self.source_repo.update_by_id(str(existing.id), {"status": "annotation_error"})

            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def _seconds_to_time_string(seconds: int) -> str:
        """Convert seconds to HH:MM:SS format"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def get_annotation(self, azure_file_path: AzureFilePath) -> Dict[str, Any]:
        """Get video annotation in API format"""
        try:
            annotation = self.source_repo.get_by_field("azure_file_path.blob_path", azure_file_path.blob_path)

            if not annotation:
                return {
                    "success": False,
                    "error": f"Annotation for video '{azure_file_path.blob_path}' not found"
                }

            converted_annotation = self._convert_to_api_response(annotation)

            return {
                "success": True,
                "annotation": converted_annotation
            }

        except Exception as e:
            logger.error(f"Error getting annotation: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_annotation_by_id(self, video_id: str) -> Dict[str, Any]:
        """Get annotation by video ID"""
        try:
            annotation = self.source_repo.get_by_id(video_id)

            if not annotation:
                return {
                    "success": False,
                    "error": f"Video with ID {video_id} not found"
                }

            converted_annotation = self._convert_to_api_response(annotation)

            return {
                "success": True,
                "annotation": converted_annotation
            }

        except Exception as e:
            logger.error(f"Error getting annotation by ID: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def update_annotation_status(self, video_id: str, status: str) -> Dict[str, Any]:
        """Update annotation status"""
        try:
            success = self.source_repo.update_by_id(video_id, {"status": status})

            if not success:
                return {
                    "success": False,
                    "error": f"Failed to update status for video {video_id}"
                }

            logger.info(f"Annotation status updated: {video_id} -> {status}")

            return {
                "success": True,
                "message": f"Status updated to {status}"
            }

        except Exception as e:
            logger.error(f"Error updating annotation status: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def delete_annotation(self, video_id: str) -> Dict[str, Any]:
        """Delete annotation and associated clips"""
        try:
            clips = self.clip_repo.get_all({"source_video_id": video_id})
            for clip in clips:
                clip.delete()

            success = self.source_repo.delete_by_id(video_id)

            if not success:
                return {
                    "success": False,
                    "error": f"Failed to delete annotation {video_id}"
                }

            logger.info(f"Annotation deleted: {video_id} with {len(clips)} clips")

            return {
                "success": True,
                "message": f"Annotation and {len(clips)} clips deleted"
            }

        except Exception as e:
            logger.error(f"Error deleting annotation: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _prepare_clips_for_processing(self, source_video_id: str, azure_path: AzureFilePath,
                                      clips: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """Create clip documents with unified metadata structure"""
        try:
            existing_clips = self.clip_repo.get_all({"source_video_id": source_video_id})
            for clip in existing_clips:
                clip.delete()

            for project_name, project_clips in clips.items():
                cvat_settings_doc = self.cvat_service.get_cvat_settings_document(project_name)

                if not cvat_settings_doc:
                    logger.warning(f"CVAT settings not found for project {project_name}, creating defaults")
                    cvat_params = self.cvat_service.get_default_project_params(project_name)

                    cvat_settings_doc = self.cvat_settings_repo.create(
                        project_name=project_name,
                        project_id=cvat_params["project_id"],
                        overlap=cvat_params["overlap"],
                        segment_size=cvat_params["segment_size"],
                        image_quality=cvat_params["image_quality"]
                    )

                for clip_idx, clip in enumerate(project_clips):
                    start_seconds = self._time_to_seconds(clip["start_time"])
                    end_seconds = self._time_to_seconds(clip["end_time"])

                    original_filename = azure_path.blob_path.split('/')[-1]
                    name_without_ext = original_filename.rsplit('.', 1)[0]
                    extension = original_filename.rsplit('.', 1)[1] if '.' in original_filename else 'mp4'

                    clip_filename = f"{name_without_ext}_{project_name}_{clip_idx}.{extension}"
                    clip_azure_path = generate_clip_azure_path(azure_path, clip_filename)

                    azure_file_path_doc = AzureFilePathDocument(
                        account_name=clip_azure_path.account_name,
                        container_name=clip_azure_path.container_name,
                        blob_path=clip_azure_path.blob_path
                    )

                    self.clip_repo.create(
                        source_video_id=source_video_id,
                        azure_file_path=azure_file_path_doc,
                        cvat_task_params=cvat_settings_doc,  # Тепер це reference
                        cvat_project_id=cvat_settings_doc.project_id,
                        status="not_annotated",
                        extension=extension,
                        duration_sec=end_seconds - start_seconds,
                        start_time_offset_sec=start_seconds,
                        where=metadata.get("where", ""),
                        when=metadata.get("when", ""),
                        uav_type=metadata.get("uav_type", ""),
                        video_content=metadata.get("video_content", ""),
                        is_urban=metadata.get("is_urban", False),
                        has_osd=metadata.get("has_osd", False),
                        is_analog=metadata.get("is_analog", False),
                        night_video=metadata.get("night_video", False),
                        multiple_streams=metadata.get("multiple_streams", False),
                        has_infantry=metadata.get("has_infantry", False),
                        has_explosions=metadata.get("has_explosions", False),
                        ml_project=project_name
                    )

            logger.info(f"Prepared clips for processing: {source_video_id}")

        except Exception as e:
            logger.error(f"Error preparing clips: {str(e)}")
            raise

    # backend/services/annotation_service.py (оновлені методи)
    def _convert_to_api_response(self, annotation) -> VideoAnnotationResponse:
        """Convert database document to API response format"""
        azure_file_path_api = AzureFilePath(
            account_name=annotation.azure_file_path.account_name,
            container_name=annotation.azure_file_path.container_name,
            blob_path=annotation.azure_file_path.blob_path
        )

        filename = azure_file_path_api.blob_path.split("/")[-1]
        clips_data = self.clip_repo.get_all({"source_video_id": str(annotation.id)})

        clips = {}
        cvat_settings = {}
        metadata = None

        if clips_data:
            first_clip = clips_data[0]

            metadata = VideoMetadataResponse(
                skip=annotation.skip_annotation,
                where=first_clip.where,
                when=first_clip.when,
                uav_type=first_clip.uav_type or "",
                video_content=first_clip.video_content or "",
                is_urban=first_clip.is_urban,
                has_osd=first_clip.has_osd,
                is_analog=first_clip.is_analog,
                night_video=first_clip.night_video,
                multiple_streams=first_clip.multiple_streams,
                has_infantry=first_clip.has_infantry,
                has_explosions=first_clip.has_explosions
            )

            for clip_data in clips_data:
                project_name = clip_data.ml_project
                if project_name not in clips:
                    clips[project_name] = []
                    cvat_settings[project_name] = CVATSettings(
                        project_name=project_name,
                        project_id=clip_data.cvat_project_id,
                        overlap=clip_data.cvat_task_params.overlap,
                        segment_size=clip_data.cvat_task_params.segment_size,
                        image_quality=clip_data.cvat_task_params.image_quality
                    )

                start_time = self._seconds_to_time_string(clip_data.start_time_offset_sec)
                end_time = self._seconds_to_time_string(
                    clip_data.start_time_offset_sec + clip_data.duration_sec
                )

                clips[project_name].append(ClipInfoResponse(
                    id=len(clips[project_name]),
                    start_time=start_time,
                    end_time=end_time
                ))
        else:
            if annotation.skip_annotation:
                metadata = VideoMetadataResponse(
                    skip=True,
                    where=None,
                    when=None,
                    uav_type="",
                    video_content="",
                    is_urban=False,
                    has_osd=False,
                    is_analog=False,
                    night_video=False,
                    multiple_streams=False,
                    has_infantry=False,
                    has_explosions=False
                )

        return VideoAnnotationResponse(
            id=str(annotation.id),
            azure_file_path=azure_file_path_api,
            filename=filename,
            created_at_utc=annotation.created_at_utc.isoformat(sep=" ", timespec="seconds"),
            updated_at_utc=annotation.updated_at_utc.isoformat(sep=" ", timespec="seconds"),
            status=annotation.status,
            metadata=metadata,
            clips=clips,
            cvat_settings=cvat_settings
        )

    def _validate_clips_duration(self, clips: Dict[str, Any]) -> Optional[str]:
        """Validate clips duration meets minimum requirements"""
        for project_type, project_clips in clips.items():
            for clip in project_clips:
                start_seconds = self._time_to_seconds(clip["start_time"])
                end_seconds = self._time_to_seconds(clip["end_time"])

                if end_seconds - start_seconds < 1:
                    return f"Minimum clip duration is 1 second. Clip {clip['id']} in project {project_type} is too short."

        return None

    @staticmethod
    def _time_to_seconds(time_str: str) -> int:
        """Convert HH:MM:SS to seconds"""
        parts = time_str.split(":")
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

    def get_clips_by_video_id(self, video_id: str) -> Dict[str, Any]:
        """Get all clips for a specific video"""
        try:
            clips = self.clip_repo.get_all({"source_video_id": video_id})

            clip_list = [
                {
                    "id": str(clip.id),
                    "ml_project": clip.ml_project,
                    "start_time_offset_sec": clip.start_time_offset_sec,
                    "duration_sec": clip.duration_sec,
                    "cvat_task_id": clip.cvat_task_id,
                    "status": clip.status,
                    "azure_path": {
                        "account_name": clip.azure_file_path.account_name,
                        "container_name": clip.azure_file_path.container_name,
                        "blob_path": clip.azure_file_path.blob_path
                    }
                }
                for clip in clips
            ]

            return {
                "success": True,
                "clips": clip_list,
                "total_count": len(clip_list)
            }

        except Exception as e:
            logger.error(f"Error getting clips for video {video_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_annotation_statistics(self) -> Dict[str, Any]:
        """Get comprehensive annotation statistics"""
        try:
            all_annotations = self.source_repo.get_all()
            all_clips = self.clip_repo.get_all()

            stats = {
                "total_annotations": len(all_annotations),
                "completed_annotations": len([a for a in all_annotations if a.status == "annotated"]),
                "in_progress_annotations": len([a for a in all_annotations if a.status == "in_progress"]),
                "skipped_annotations": len([a for a in all_annotations if a.skip_annotation]),
                "total_clips": len(all_clips),
                "clips_by_project": {},
                "clips_with_cvat_tasks": len([c for c in all_clips if c.cvat_task_id])
            }

            for clip in all_clips:
                project = clip.ml_project
                if project not in stats["clips_by_project"]:
                    stats["clips_by_project"][project] = 0
                stats["clips_by_project"][project] += 1

            return {
                "success": True,
                "statistics": stats
            }

        except Exception as e:
            logger.error(f"Error getting annotation statistics: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }