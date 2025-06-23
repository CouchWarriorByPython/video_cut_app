from typing import Dict, Any, Optional
from datetime import datetime, UTC

from backend.database import create_repository
from backend.services.cvat_service import CVATService
from backend.models.database import AzureFilePath, VideoStatus
from backend.utils.logger import get_logger

logger = get_logger(__name__, "services.log")


class AnnotationService:
    """Service for working with annotations using new data structure"""

    def __init__(self):
        self.source_repo = create_repository("source_videos", async_mode=False)
        self.clip_repo = create_repository("clip_videos", async_mode=False)
        self.cvat_service = CVATService()

    def save_fragments_and_metadata(self, azure_file_path: AzureFilePath, annotation_data: Dict[str, Any]) -> Dict[
        str, Any]:
        """Save video fragments and metadata"""
        try:
            skip_annotation = annotation_data.get("metadata", {}).get("skip", False)
            self.source_repo.create_indexes()

            existing = self.source_repo.find_by_field("azure_file_path.blob_path", azure_file_path.blob_path)
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

            # Оновлюємо ТІЛЬКИ skip_annotation та status в source_videos
            update_data = {
                "skip_annotation": skip_annotation,
                "status": VideoStatus.ANNOTATED,
                "updated_at_utc": datetime.now(UTC).isoformat(sep=" ", timespec="seconds")
            }

            success = self.source_repo.update_by_id(existing["_id"], update_data)

            if not success:
                self.source_repo.update_by_id(existing["_id"], {"status": VideoStatus.ANNOTATION_ERROR})
                return {
                    "success": False,
                    "error": "Failed to update document"
                }

            record_id = existing["_id"]

            if skip_annotation:
                success_message = "Дані успішно збережено. Обробку пропущено (skip_annotation)."
                logger.info(f"Video skipped (skip_annotation): {azure_file_path.blob_path}")
                task_id = None
            else:
                # Передаємо where/when в metadata
                metadata = annotation_data.get("metadata", {})
                self._prepare_clips_for_processing(existing["_id"], azure_file_path, clips, metadata)
                success_message = "Дані успішно збережено. Обробку розпочато."
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

            if 'existing' in locals() and existing:
                self.source_repo.update_by_id(existing["_id"], {"status": VideoStatus.ANNOTATION_ERROR})

            return {
                "success": False,
                "error": str(e)
            }

    def _prepare_clips_for_processing(
            self, source_video_id: str, azure_path: AzureFilePath, clips: Dict[str, Any], metadata: Dict[str, Any]
    ) -> None:
        """Prepare clip records for processing"""
        try:
            from backend.utils.azure_path_utils import generate_clip_azure_path

            self.clip_repo.create_indexes()
            self.clip_repo.collection.delete_many({"source_video_id": source_video_id})

            where = metadata.get("where")
            when = metadata.get("when")

            for project_name, project_clips in clips.items():
                cvat_params = self.cvat_service.get_default_project_params(project_name)
                project_id = cvat_params.pop("project_id")

                for clip_idx, clip in enumerate(project_clips):
                    start_seconds = self._time_to_seconds(clip["start_time"])
                    end_seconds = self._time_to_seconds(clip["end_time"])

                    clip_filename = f"{azure_path.blob_path.split('/')[-1].split('.')[0]}_{project_name}_{clip_idx}.{azure_path.blob_path.split('.')[-1]}"
                    clip_azure_path = generate_clip_azure_path(azure_path, clip_filename)

                    clip_data = {
                        "source_video_id": source_video_id,
                        "azure_file_path": clip_azure_path.model_dump(),
                        "cvat_task_id": None,
                        "cvat_task_params": cvat_params,
                        "status": "not_annotated",
                        "extension": azure_path.blob_path.split(".")[-1].lower(),
                        "duration_sec": end_seconds - start_seconds,
                        "start_time_offset_sec": start_seconds,
                        # ВСІ метадані зберігаємо в clips
                        "where": where,
                        "when": when,
                        "uav_type": metadata.get("uav_type"),
                        "video_content": metadata.get("video_content"),
                        "is_urban": metadata.get("is_urban", False),
                        "has_osd": metadata.get("has_osd", False),
                        "is_analog": metadata.get("is_analog", False),
                        "night_video": metadata.get("night_video", False),
                        "multiple_streams": metadata.get("multiple_streams", False),
                        "has_infantry": metadata.get("has_infantry", False),
                        "has_explosions": metadata.get("has_explosions", False),
                        "ml_project": project_name,
                        "cvat_project_id": project_id,
                        "created_at_utc": datetime.now(UTC).isoformat(sep=" ", timespec="seconds"),
                        "updated_at_utc": datetime.now(UTC).isoformat(sep=" ", timespec="seconds")
                    }

                    self.clip_repo.save_document(clip_data)

            logger.info(f"Prepared clips for processing: {source_video_id}")

        except Exception as e:
            logger.error(f"Error preparing clips: {str(e)}")
            raise

    def _validate_clips_duration(self, clips: Dict[str, Any]) -> Optional[str]:
        """Validate minimum clips duration"""
        for project_type, project_clips in clips.items():
            for clip in project_clips:
                start_seconds = self._time_to_seconds(clip["start_time"])
                end_seconds = self._time_to_seconds(clip["end_time"])

                if end_seconds - start_seconds < 1:
                    return f"Minimum clip duration is 1 second. Clip {clip['id']} in project {project_type} is too short."

        return None

    def _time_to_seconds(self, time_str: str) -> int:
        """Convert time string (HH:MM:SS) to seconds"""
        parts = time_str.split(":")
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

    def get_annotation(self, azure_file_path: AzureFilePath) -> Dict[str, Any]:
        """Get annotation by azure_file_path"""
        try:
            annotation = self.source_repo.find_by_field("azure_file_path.blob_path", azure_file_path.blob_path)

            if not annotation:
                return {
                    "success": False,
                    "error": f"Annotation for video '{azure_file_path.blob_path}' not found"
                }

            converted_annotation = self._convert_to_api_format(annotation)

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

    def _convert_to_api_format(self, annotation: Dict[str, Any]) -> Dict[str, Any]:
        """Convert new format annotation to API format"""
        azure_path_dict = annotation.get("azure_file_path", {})
        clips_data = self.clip_repo.find_all(filter_query={"source_video_id": annotation["_id"]})

        clips = {}
        cvat_params = {}
        metadata = None
        where = None
        when = None

        # Отримуємо метадані з першого кліпу
        if clips_data:
            first_clip = clips_data[0]
            where = first_clip.get("where")
            when = first_clip.get("when")

            metadata = {
                "skip": annotation.get("skip_annotation", False),
                "uav_type": first_clip.get("uav_type", ""),
                "video_content": first_clip.get("video_content", ""),
                "is_urban": first_clip.get("is_urban", False),
                "has_osd": first_clip.get("has_osd", False),
                "is_analog": first_clip.get("is_analog", False),
                "night_video": first_clip.get("night_video", False),
                "multiple_streams": first_clip.get("multiple_streams", False),
                "has_infantry": first_clip.get("has_infantry", False),
                "has_explosions": first_clip.get("has_explosions", False)
            }

            for clip_data in clips_data:
                project_name = clip_data.get("ml_project", "unknown")
                if project_name not in clips:
                    clips[project_name] = []
                    cvat_params[project_name] = clip_data.get("cvat_task_params", {})

                start_time = self._seconds_to_time_string(clip_data.get("start_time_offset_sec", 0))
                end_time = self._seconds_to_time_string(
                    clip_data.get("start_time_offset_sec", 0) + clip_data.get("duration_sec", 0)
                )

                clips[project_name].append({
                    "id": len(clips[project_name]),
                    "start_time": start_time,
                    "end_time": end_time
                })
        else:
            if annotation.get("skip_annotation"):
                metadata = {"skip": True}

        return {
            "_id": annotation["_id"],
            "azure_file_path": azure_path_dict,
            "filename": azure_path_dict.get("blob_path", "").split("/")[-1],
            "created_at_utc": annotation.get("created_at_utc", ""),
            "updated_at_utc": annotation.get("updated_at_utc", ""),
            "when": when,
            "where": where,
            "status": annotation.get("status", VideoStatus.NOT_ANNOTATED),
            "metadata": metadata,
            "clips": clips,
            "cvat_params": cvat_params
        }

    def _get_project_name_by_id(self, project_id: int) -> str:
        """Get project name by CVAT project ID"""
        project_mapping = {
            5: "motion-det",
            6: "tracking",
            7: "mil-hardware",
            8: "re-id"
        }
        return project_mapping.get(project_id, "unknown")

    def _seconds_to_time_string(self, seconds: int) -> str:
        """Convert seconds to HH:MM:SS format"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"