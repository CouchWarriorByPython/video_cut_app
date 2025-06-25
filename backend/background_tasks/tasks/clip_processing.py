from typing import Dict, Any
import os
import tempfile
from datetime import datetime, UTC

from backend.background_tasks.app import app
from backend.database import create_repository
from backend.models.database import TaskParams
from backend.utils.azure_path_utils import (
    extract_filename_from_azure_path, azure_path_dict_to_object
)
from backend.utils.video_utils import (
    trim_video_clip, cleanup_file, get_local_video_path, get_video_info
)
from backend.services.azure_service import AzureService
from backend.services.cvat_service import CVATService
from backend.config.settings import get_settings

from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__, "tasks.log")


@app.task(name="process_video_clip", bind=True)
def process_video_clip(self, clip_video_id: str) -> Dict[str, Any]:
    """Process individual video clip from clip_videos collection"""
    logger.debug(f"Starting clip processing: {clip_video_id}")

    temp_clip_path = None

    try:
        clip_repo = create_repository("clip_videos", async_mode=False)
        source_repo = create_repository("source_videos", async_mode=False)

        azure_service = AzureService()
        cvat_service = CVATService()

        clip_data = clip_repo.find_by_id(clip_video_id)
        if not clip_data:
            logger.error(f"Clip not found: {clip_video_id}")
            return {"status": "error", "message": f"Clip not found: {clip_video_id}"}

        source_video = source_repo.find_by_id(clip_data["source_video_id"])
        if not source_video:
            logger.error(f"Source video not found: {clip_data['source_video_id']}")
            return {"status": "error", "message": "Source video not found"}

        source_azure_path = azure_path_dict_to_object(source_video["azure_file_path"])
        clip_azure_path = azure_path_dict_to_object(clip_data["azure_file_path"])

        source_filename = extract_filename_from_azure_path(source_azure_path)
        local_source_path = get_local_video_path(source_filename)

        if not os.path.exists(local_source_path):
            logger.error(f"Local source file not found: {local_source_path}")
            return {"status": "error", "message": f"Local source file not found: {local_source_path}"}

        clip_filename = extract_filename_from_azure_path(clip_azure_path)

        temp_clip_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=f".{clip_data['extension']}",
            dir=settings.temp_folder
        )
        temp_clip_path = temp_clip_file.name
        temp_clip_file.close()

        start_time = seconds_to_time_string(clip_data["start_time_offset_sec"])
        end_time = seconds_to_time_string(clip_data["start_time_offset_sec"] + clip_data["duration_sec"])

        logger.info(f"Creating clip {clip_filename}: {start_time} - {end_time}")

        success = trim_video_clip(
            source_path=local_source_path,
            output_path=temp_clip_path,
            start_time=start_time,
            end_time=end_time
        )

        if not success:
            logger.error(f"Failed to create clip: {clip_filename}")
            clip_repo.update_by_id(clip_video_id, {
                "status": "clip_creation_failed",
                "updated_at_utc": datetime.now(UTC).isoformat(sep=" ", timespec="seconds")
            })
            return {"status": "error", "message": f"Failed to create clip: {clip_filename}"}

        clip_video_info = get_video_info(temp_clip_path)
        if not clip_video_info:
            logger.warning(f"Failed to get video info for clip: {clip_filename}")
            clip_video_info = {}

        logger.info(f"Uploading clip to Azure: {clip_filename}")

        upload_result = azure_service.upload_clip(
            file_path=temp_clip_path,
            azure_path=clip_azure_path,
            metadata={
                "cvat_project_id": str(clip_data["cvat_project_id"]),
                "source_video_id": clip_data["source_video_id"],
                "clip_video_id": clip_video_id
            }
        )

        if not upload_result["success"]:
            logger.error(f"Failed to upload to Azure: {upload_result.get('error')}")
            clip_repo.update_by_id(clip_video_id, {
                "status": "azure_upload_failed",
                "updated_at_utc": datetime.now(UTC).isoformat(sep=" ", timespec="seconds")
            })
            return {"status": "error", "message": f"Failed to upload to Azure: {upload_result.get('error')}"}

        logger.info(f"Creating CVAT task for clip: {clip_filename}")

        cvat_task_params = TaskParams(**clip_data["cvat_task_params"])
        cvat_task_id = None

        try:
            cvat_task_id = cvat_service.create_task(
                filename=os.path.splitext(clip_filename)[0],
                file_path=temp_clip_path,
                project_params=cvat_task_params.model_dump()
            )

            if cvat_task_id:
                logger.info(f"CVAT task created successfully: {cvat_task_id} for clip {clip_filename}")
            else:
                logger.error(f"CVAT task creation returned None for clip: {clip_filename}")

        except Exception as cvat_error:
            logger.error(f"CVAT task creation failed for clip {clip_filename}: {str(cvat_error)}")
            cvat_task_id = None

        update_data = {
            "cvat_task_id": int(cvat_task_id) if cvat_task_id else None,
            "status": "processing" if cvat_task_id else "cvat_failed",
            "fps": clip_video_info.get("fps"),
            "resolution_width": clip_video_info.get("width"),
            "resolution_height": clip_video_info.get("height"),
            "size_MB": round(os.path.getsize(temp_clip_path) / (1024 * 1024), 2) if os.path.exists(
                temp_clip_path) else None,
            "updated_at_utc": datetime.now(UTC).isoformat(sep=" ", timespec="seconds")
        }

        success_update = clip_repo.update_by_id(clip_video_id, update_data)

        if not success_update:
            logger.error(f"Failed to update clip in database: {clip_video_id}")

        logger.info(f"Clip processed: {clip_filename}, CVAT task: {cvat_task_id}, status: {update_data['status']}")

        return {
            "status": "success" if cvat_task_id else "partial_success",
            "message": "Clip successfully processed" if cvat_task_id else "Clip processed but CVAT task creation failed",
            "clip_video_id": clip_video_id,
            "cvat_task_id": cvat_task_id,
            "azure_path": clip_azure_path.model_dump(),
            "filename": clip_filename,
            "fps": clip_video_info.get("fps")
        }

    except Exception as e:
        logger.error(f"Error processing clip {clip_video_id}: {str(e)}")

        # Оновлюємо статус в БД при помилці
        try:
            clip_repo = create_repository("clip_videos", async_mode=False)
            clip_repo.update_by_id(clip_video_id, {
                "status": "processing_failed",
                "updated_at_utc": datetime.now(UTC).isoformat(sep=" ", timespec="seconds")
            })
        except:
            pass

        return {"status": "error", "message": str(e)}
    finally:
        if temp_clip_path:
            cleanup_file(temp_clip_path)


@app.task(name="process_all_video_clips", bind=True)
def process_all_video_clips(self, source_video_id: str) -> Dict[str, Any]:
    """Process all clips for a source video"""
    logger.info(f"Starting processing all clips for source video: {source_video_id}")

    try:
        clip_repo = create_repository("clip_videos", async_mode=False)
        source_repo = create_repository("source_videos", async_mode=False)

        clips = clip_repo.find_all(filter_query={"source_video_id": source_video_id})

        if not clips:
            logger.warning(f"No clips found for source video: {source_video_id}")
            return {"status": "error", "message": "No clips found for processing"}

        successful_clips = 0
        failed_clips = 0
        partial_success_clips = 0
        total_clips = len(clips)

        logger.info(f"Processing {total_clips} clips for source video: {source_video_id}")

        for i, clip in enumerate(clips, 1):
            logger.info(f"Processing clip {i}/{total_clips}: {clip['_id']}")

            try:
                result = process_video_clip.apply(args=[clip["_id"]])

                if result.result.get("status") == "success":
                    successful_clips += 1
                elif result.result.get("status") == "partial_success":
                    partial_success_clips += 1
                    logger.warning(f"Clip partially processed: {clip['_id']} - {result.result.get('message')}")
                else:
                    failed_clips += 1
                    logger.error(f"Clip processing failed: {clip['_id']} - {result.result.get('message')}")

            except Exception as e:
                failed_clips += 1
                logger.error(f"Error processing clip {clip['_id']}: {str(e)}")

        logger.info(f"Clip processing results for {source_video_id}: "
                    f"successful {successful_clips}/{total_clips}, "
                    f"partial {partial_success_clips}/{total_clips}, "
                    f"failed {failed_clips}/{total_clips}")

        # Видаляємо source файл тільки якщо всі кліпи оброблені (включаючи partial success)
        if failed_clips == 0:
            source_video = source_repo.find_by_id(source_video_id)
            if source_video:
                source_azure_path = azure_path_dict_to_object(source_video["azure_file_path"])
                source_filename = extract_filename_from_azure_path(source_azure_path)
                local_path = get_local_video_path(source_filename)

                if os.path.exists(local_path):
                    try:
                        cleanup_file(local_path)
                        logger.info(f"Cleaned up local source file: {local_path}")
                    except Exception as e:
                        logger.error(f"Error cleaning up source file {local_path}: {str(e)}")

            clip_ids = [clip["_id"] for clip in clips]
            source_repo.update_by_id(source_video_id, {
                "status": "annotated",
                "clips": clip_ids,
                "updated_at_utc": datetime.now(UTC).isoformat(sep=" ", timespec="seconds")
            })

            logger.info(f"All clips processing completed for video: {source_video_id}")

            return {
                "status": "completed",
                "message": "All clips processing completed",
                "successful_clips": successful_clips,
                "partial_success_clips": partial_success_clips,
                "failed_clips": failed_clips,
                "total_clips": total_clips
            }
        else:
            logger.warning(f"Clips processing completed with errors for video: {source_video_id}")
            return {
                "status": "partial_success",
                "message": f"Processing completed with errors. {successful_clips + partial_success_clips} of {total_clips} clips processed",
                "successful_clips": successful_clips,
                "partial_success_clips": partial_success_clips,
                "failed_clips": failed_clips,
                "total_clips": total_clips
            }

    except Exception as e:
        logger.error(f"Error processing clips for video {source_video_id}: {str(e)}")
        return {"status": "error", "message": str(e)}


def seconds_to_time_string(seconds: int) -> str:
    """Convert seconds to HH:MM:SS format"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
