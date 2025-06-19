from typing import Dict, Any
import os
import tempfile
from datetime import datetime

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
from backend.config.settings import Settings
from backend.utils.logger import get_logger

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
            dir=Settings.temp_folder
        )
        temp_clip_path = temp_clip_file.name
        temp_clip_file.close()

        start_time = seconds_to_time_string(clip_data["start_time_offset_sec"])
        end_time = seconds_to_time_string(clip_data["start_time_offset_sec"] + clip_data["duration_sec"])

        success = trim_video_clip(
            source_path=local_source_path,
            output_path=temp_clip_path,
            start_time=start_time,
            end_time=end_time
        )

        if not success:
            logger.error(f"Failed to create clip: {clip_filename}")
            return {"status": "error", "message": f"Failed to create clip: {clip_filename}"}

        clip_video_info = get_video_info(temp_clip_path)
        if not clip_video_info:
            logger.warning(f"Failed to get video info for clip: {clip_filename}")
            clip_video_info = {}

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
            return {"status": "error", "message": f"Failed to upload to Azure: {upload_result.get('error')}"}

        task_params = TaskParams(**clip_data["task_params"])
        cvat_task_id = cvat_service.create_task(
            filename=os.path.splitext(clip_filename)[0],
            file_path=temp_clip_path,
            project_params=task_params.model_dump()
        )

        cvat_task_name = f"{source_video.get('uav_type', 'unknown')}_{source_video.get('where', 'unknown')}_{clip_filename}"

        update_data = {
            "cvat_task_id": int(cvat_task_id) if cvat_task_id else None,
            "cvat_task_name": cvat_task_name,
            "status": "processing" if cvat_task_id else "cvat_failed",
            "fps": clip_video_info.get("fps"),
            "resolution_width": clip_video_info.get("width"),
            "resolution_height": clip_video_info.get("height"),
            "size_MB": os.path.getsize(temp_clip_path) / (1024 * 1024) if os.path.exists(temp_clip_path) else None,
            "updated_at_utc": datetime.now().isoformat()
        }

        clip_repo.update_by_id(clip_video_id, update_data)

        logger.debug(f"Clip processed: {clip_filename}")

        return {
            "status": "success",
            "message": "Clip successfully processed",
            "clip_video_id": clip_video_id,
            "cvat_task_id": cvat_task_id,
            "azure_path": clip_azure_path.model_dump(),
            "filename": clip_filename,
            "fps": clip_video_info.get("fps")
        }

    except Exception as e:
        logger.error(f"Error processing clip {clip_video_id}: {str(e)}")
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
        total_clips = len(clips)

        for clip in clips:
            try:
                result = process_video_clip.apply(args=[clip["_id"]])
                if result.result.get("status") == "success":
                    successful_clips += 1
                else:
                    failed_clips += 1
                    logger.error(f"Clip processing failed: {clip['_id']}")
            except Exception as e:
                failed_clips += 1
                logger.error(f"Error processing clip {clip['_id']}: {str(e)}")

        logger.info(f"Clip processing results for {source_video_id}: "
                    f"successful {successful_clips}/{total_clips}, failed {failed_clips}")

        if failed_clips == 0 and successful_clips == total_clips:
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
                "updated_at_utc": datetime.now().isoformat()
            })

            logger.info(f"All clips processing completed for video: {source_video_id}")

            return {
                "status": "completed",
                "message": "All clips processing completed",
                "successful_clips": successful_clips,
                "failed_clips": failed_clips,
                "total_clips": total_clips
            }
        else:
            logger.warning(f"Clips processing completed with errors for video: {source_video_id}")
            return {
                "status": "partial_success",
                "message": f"Processing completed with errors. {successful_clips} of {total_clips} clips processed successfully",
                "successful_clips": successful_clips,
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