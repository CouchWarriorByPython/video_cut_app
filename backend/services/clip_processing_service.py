from typing import Dict, Any, Optional, List
import os
import tempfile

from backend.database import create_source_video_repository, create_clip_video_repository
from backend.models.shared import AzureFilePath
from backend.utils.azure_path_utils import extract_filename_from_azure_path
from backend.utils.video_utils import (
    trim_video_clip, cleanup_file, get_local_video_path, get_video_info
)
from backend.services.azure_service import AzureService
from backend.services.cvat_service import CVATService
from backend.config.settings import get_settings
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__, "services.log")


class ClipProcessingService:
    """Service for processing video clips"""

    def __init__(self):
        self.clip_repo = create_clip_video_repository()
        self.source_repo = create_source_video_repository()
        self.azure_service = AzureService()
        self.cvat_service = CVATService()

    def process_single_clip(self, clip_video_id: str) -> Dict[str, Any]:
        """Process individual video clip"""
        logger.debug(f"Starting clip processing: {clip_video_id}")
        temp_clip_path = None

        try:
            clip_data = self.clip_repo.get_by_id(clip_video_id)
            if not clip_data:
                logger.error(f"Clip not found: {clip_video_id}")
                return {"status": "error", "message": f"Кліп не знайдено: {clip_video_id}"}

            source_video = self.source_repo.get_by_id(clip_data.source_video_id)
            if not source_video:
                logger.error(f"Source video not found: {clip_data.source_video_id}")
                return {"status": "error", "message": "Відео-джерело не знайдено"}

            temp_clip_path = self._create_clip_file(clip_data, source_video)
            if not temp_clip_path:
                self.clip_repo.update_by_id(clip_video_id, {"status": "clip_creation_failed"})
                return {"status": "error", "message": "Не вдалося створити файл кліпу"}

            clip_video_info = get_video_info(temp_clip_path)
            if not clip_video_info:
                logger.warning(f"Failed to get video info for clip")
                clip_video_info = {}

            upload_success = self._upload_clip_to_azure(clip_data, temp_clip_path, clip_video_id)
            if not upload_success:
                self.clip_repo.update_by_id(clip_video_id, {"status": "azure_upload_failed"})
                return {"status": "error", "message": "Не вдалося завантажити до Azure"}

            cvat_task_id = self._create_cvat_task(clip_data, temp_clip_path)

            update_data = {
                "cvat_task_id": int(cvat_task_id) if cvat_task_id else None,
                "status": "not_annotated" if cvat_task_id else "cvat_failed",
                "fps": clip_video_info.get("fps"),
                "resolution_width": clip_video_info.get("width"),
                "resolution_height": clip_video_info.get("height"),
                "size_MB": round(os.path.getsize(temp_clip_path) / (1024 * 1024), 2) if os.path.exists(
                    temp_clip_path) else None,
            }

            self.clip_repo.update_by_id(clip_video_id, update_data)

            return {
                "status": "success" if cvat_task_id else "partial_success",
                "message": "Кліп успішно оброблено" if cvat_task_id else "Кліп оброблено, але не вдалося створити завдання в CVAT",
                "clip_video_id": clip_video_id,
                "cvat_task_id": cvat_task_id,
                "azure_path": clip_data.azure_file_path,
                "filename": extract_filename_from_azure_path(
                    AzureFilePath(
                        account_name=clip_data.azure_file_path.account_name,
                        container_name=clip_data.azure_file_path.container_name,
                        blob_path=clip_data.azure_file_path.blob_path
                    )
                ),
                "fps": clip_video_info.get("fps")
            }

        except Exception as e:
            logger.error(f"Error processing clip {clip_video_id}: {str(e)}")
            try:
                self.clip_repo.update_by_id(clip_video_id, {"status": "processing_failed"})
            except:
                pass
            return {"status": "error", "message": str(e)}
        finally:
            if temp_clip_path:
                cleanup_file(temp_clip_path)

    def process_all_clips_for_video(self, source_video_id: str) -> Dict[str, Any]:
        """Process all clips for a source video"""
        logger.info(f"Starting processing all clips for source video: {source_video_id}")

        try:
            clips = self.clip_repo.get_all(filter_dict={"source_video_id": source_video_id})

            if not clips:
                logger.warning(f"No clips found for source video: {source_video_id}")
                self.source_repo.update_by_id(source_video_id, {"status": "annotation_error"})
                return {"status": "error", "message": "Не знайдено кліпів для обробки"}

            results = self._process_clips_batch(clips)

            if results["failed_clips"] == 0:
                self._finalize_video_processing(source_video_id, clips)

                return {
                    "status": "completed",
                    "message": "Обробка всіх кліпів завершена",
                    **results
                }
            else:
                self.source_repo.update_by_id(source_video_id, {"status": "annotation_error"})
                return {
                    "status": "partial_success",
                    "message": f"Обробка завершена з помилками. Оброблено {results['successful_clips'] + results['partial_success_clips']} з {results['total_clips']} кліпів",
                    **results
                }

        except Exception as e:
            logger.error(f"Error processing clips for video {source_video_id}: {str(e)}")
            self.source_repo.update_by_id(source_video_id, {"status": "annotation_error"})
            return {"status": "error", "message": str(e)}

    def _create_clip_file(self, clip_data, source_video) -> Optional[str]:
        """Create clip file from source video"""
        try:
            source_azure_path = AzureFilePath(
                account_name=source_video.azure_file_path.account_name,
                container_name=source_video.azure_file_path.container_name,
                blob_path=source_video.azure_file_path.blob_path
            )

            source_filename = extract_filename_from_azure_path(source_azure_path)
            local_source_path = get_local_video_path(source_filename)

            if not os.path.exists(local_source_path):
                logger.error(f"Local source file not found: {local_source_path}")
                return None

            temp_clip_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=f".{clip_data.extension}",
                dir=settings.temp_folder
            )
            temp_clip_path = temp_clip_file.name
            temp_clip_file.close()

            start_time = self._seconds_to_time_string(clip_data.start_time_offset_sec)
            end_time = self._seconds_to_time_string(clip_data.start_time_offset_sec + clip_data.duration_sec)

            clip_filename = extract_filename_from_azure_path(
                AzureFilePath(
                    account_name=clip_data.azure_file_path.account_name,
                    container_name=clip_data.azure_file_path.container_name,
                    blob_path=clip_data.azure_file_path.blob_path
                )
            )
            logger.info(f"Creating clip {clip_filename}: {start_time} - {end_time}")

            success = trim_video_clip(
                source_path=local_source_path,
                output_path=temp_clip_path,
                start_time=start_time,
                end_time=end_time
            )

            return temp_clip_path if success else None

        except Exception as e:
            logger.error(f"Error creating clip file: {str(e)}")
            return None

    def _upload_clip_to_azure(self, clip_data, temp_clip_path: str, clip_video_id: str) -> bool:
        """Upload clip to Azure Storage"""
        try:
            clip_azure_path = AzureFilePath(
                account_name=clip_data.azure_file_path.account_name,
                container_name=clip_data.azure_file_path.container_name,
                blob_path=clip_data.azure_file_path.blob_path
            )

            upload_result = self.azure_service.upload_clip(
                file_path=temp_clip_path,
                azure_path=clip_azure_path,
                metadata={
                    "cvat_project_id": str(clip_data.cvat_project_id),
                    "source_video_id": clip_data.source_video_id,
                    "clip_video_id": clip_video_id
                }
            )

            return upload_result["success"]

        except Exception as e:
            logger.error(f"Error uploading clip to Azure: {str(e)}")
            return False

    def _create_cvat_task(self, clip_data, temp_clip_path: str) -> Optional[str]:
        """Create CVAT task for clip"""
        try:
            clip_filename = extract_filename_from_azure_path(
                AzureFilePath(
                    account_name=clip_data.azure_file_path.account_name,
                    container_name=clip_data.azure_file_path.container_name,
                    blob_path=clip_data.azure_file_path.blob_path
                )
            )

            cvat_task_params = {
                "project_id": clip_data.cvat_project_id,
                "overlap": clip_data.cvat_task_params.overlap,
                "segment_size": clip_data.cvat_task_params.segment_size,
                "image_quality": clip_data.cvat_task_params.image_quality
            }

            cvat_task_id = self.cvat_service.create_task(
                filename=os.path.splitext(clip_filename)[0],
                file_path=temp_clip_path,
                project_params=cvat_task_params
            )

            if cvat_task_id:
                logger.info(f"CVAT task created successfully: {cvat_task_id} for clip {clip_filename}")
            else:
                logger.error(f"CVAT task creation returned None for clip: {clip_filename}")

            return cvat_task_id

        except Exception as e:
            logger.error(f"CVAT task creation failed: {str(e)}")
            return None

    def _process_clips_batch(self, clips: List[Any]) -> Dict[str, int]:
        """Process batch of clips and collect statistics"""
        successful_clips = 0
        failed_clips = 0
        partial_success_clips = 0
        total_clips = len(clips)

        logger.info(f"Processing {total_clips} clips")

        for i, clip in enumerate(clips, 1):
            logger.info(f"Processing clip {i}/{total_clips}: {str(clip.id)}")

            try:
                result = self.process_single_clip(str(clip.id))

                if result.get("status") == "success":
                    successful_clips += 1
                elif result.get("status") == "partial_success":
                    partial_success_clips += 1
                    logger.warning(f"Clip partially processed: {str(clip.id)} - {result.get('message')}")
                else:
                    failed_clips += 1
                    logger.error(f"Clip processing failed: {str(clip.id)} - {result.get('message')}")

            except Exception as e:
                failed_clips += 1
                logger.error(f"Error processing clip {str(clip.id)}: {str(e)}")

        logger.info(f"Clip processing results: "
                    f"successful {successful_clips}/{total_clips}, "
                    f"partial {partial_success_clips}/{total_clips}, "
                    f"failed {failed_clips}/{total_clips}")

        return {
            "successful_clips": successful_clips,
            "partial_success_clips": partial_success_clips,
            "failed_clips": failed_clips,
            "total_clips": total_clips
        }

    def _finalize_video_processing(self, source_video_id: str, clips: List[Any]) -> None:
        """Finalize video processing after all clips are done"""
        try:
            source_video = self.source_repo.get_by_id(source_video_id)
            if source_video:
                source_azure_path = AzureFilePath(
                    account_name=source_video.azure_file_path.account_name,
                    container_name=source_video.azure_file_path.container_name,
                    blob_path=source_video.azure_file_path.blob_path
                )
                source_filename = extract_filename_from_azure_path(source_azure_path)
                local_path = get_local_video_path(source_filename)

                if os.path.exists(local_path):
                    try:
                        cleanup_file(local_path)
                        logger.info(f"Cleaned up local source file: {local_path}")
                    except Exception as e:
                        logger.error(f"Error cleaning up source file {local_path}: {str(e)}")

            clip_ids = [str(clip.id) for clip in clips]
            self.source_repo.update_by_id(source_video_id, {
                "status": "annotated",
                "clips": clip_ids,
            })

            logger.info(f"All clips processing completed for video: {source_video_id}")

        except Exception as e:
            logger.error(f"Error finalizing video processing: {str(e)}")

    @staticmethod
    def _seconds_to_time_string(seconds: int) -> str:
        """Convert seconds to HH:MM:SS format"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"