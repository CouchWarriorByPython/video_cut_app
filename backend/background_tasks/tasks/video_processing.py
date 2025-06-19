from typing import Dict, Any
import os
from datetime import datetime, UTC

from backend.background_tasks.app import app
from backend.database import create_repository
from backend.utils.azure_path_utils import (
    parse_azure_blob_url_to_path, extract_filename_from_azure_path,
    azure_path_dict_to_object
)
from backend.utils.video_utils import get_local_video_path, cleanup_file
from backend.utils.logger import get_logger

logger = get_logger(__name__, "tasks.log")


@app.task(name="process_video_annotation", bind=True)
def process_video_annotation(self, azure_link: str) -> Dict[str, Any]:
    """Process video annotations using new clip_videos structure"""
    logger.info(f"Starting video annotation processing: {azure_link}")

    try:
        # Parse legacy azure_link to new structure
        azure_path = parse_azure_blob_url_to_path(azure_link)

        source_repo = create_repository("source_videos", async_mode=False)
        clip_repo = create_repository("clip_videos", async_mode=False)

        # Find source video
        source_video = source_repo.find_by_field("azure_file_path.blob_path", azure_path.blob_path)
        if not source_video:
            logger.error(f"Source video not found: {azure_path.blob_path}")
            return {"status": "error", "message": f"Source video not found: {azure_path.blob_path}"}

        if source_video.get("skip_annotation", False):
            logger.info(f"Video skipped (skip_annotation): {azure_path.blob_path}")
            return {"status": "skipped", "message": "Video marked as skip_annotation"}

        source_video_id = source_video["_id"]

        # Get filename and check local file exists
        source_azure_path = azure_path_dict_to_object(source_video["azure_file_path"])
        filename = extract_filename_from_azure_path(source_azure_path)
        local_path = get_local_video_path(filename)

        if not os.path.exists(local_path):
            logger.error(f"Local file not found: {local_path}")
            return {"status": "error", "message": "Local file not found"}

        # Find all clips for this source video
        clips = clip_repo.find_all(filter_query={"source_video_id": source_video_id})

        if not clips:
            logger.error(f"No clips found for source video: {source_video_id}")
            return {"status": "error", "message": "No clips found for processing"}

        total_clips = len(clips)
        logger.info(f"Found {total_clips} clips for processing")

        # Start processing all clips
        from backend.background_tasks.tasks.clip_processing import process_all_video_clips
        task = process_all_video_clips.delay(source_video_id)

        logger.info(f"Started clips processing for video: {azure_link}, task_id: {task.id}")

        return {
            "status": "success",
            "message": f"Started processing {total_clips} clips",
            "task_id": task.id,
            "total_clips": total_clips,
            "source_video_id": source_video_id
        }

    except Exception as e:
        logger.error(f"Error processing video {azure_link}: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.task(name="cleanup_source_video_files")
def cleanup_source_video_files(source_video_ids: list) -> Dict[str, Any]:
    """Clean up local source video files after processing"""
    logger.info(f"Starting cleanup for {len(source_video_ids)} source videos")

    try:
        source_repo = create_repository("source_videos", async_mode=False)
        cleaned_files = 0
        failed_cleanups = 0

        for source_video_id in source_video_ids:
            try:
                source_video = source_repo.find_by_id(source_video_id)
                if not source_video:
                    logger.warning(f"Source video not found for cleanup: {source_video_id}")
                    continue

                source_azure_path = azure_path_dict_to_object(source_video["azure_file_path"])
                filename = extract_filename_from_azure_path(source_azure_path)
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


@app.task(name="update_video_statistics")
def update_video_statistics(source_video_id: str) -> Dict[str, Any]:
    """Update video statistics based on processed clips"""
    logger.info(f"Updating statistics for source video: {source_video_id}")

    try:
        source_repo = create_repository("source_videos", async_mode=False)
        clip_repo = create_repository("clip_videos", async_mode=False)

        clips = clip_repo.find_all(filter_query={"source_video_id": source_video_id})

        if not clips:
            logger.warning(f"No clips found for statistics update: {source_video_id}")
            return {"status": "error", "message": "No clips found"}

        total_clips = len(clips)
        processed_clips = len([c for c in clips if c.get("cvat_task_id")])
        failed_clips = len([c for c in clips if c.get("status") == "cvat_failed"])

        total_duration = sum(c.get("duration_sec", 0) for c in clips)

        update_data = {
            "clips": [c["_id"] for c in clips],
            "updated_at_utc": datetime.now(UTC).isoformat(sep=" ", timespec="seconds")
        }

        success = source_repo.update_by_id(source_video_id, update_data)

        if success:
            logger.info(f"Statistics updated for video: {source_video_id}")
            return {
                "status": "success",
                "message": "Statistics updated successfully",
                "statistics": {
                    "total_clips": total_clips,
                    "processed_clips": processed_clips,
                    "failed_clips": failed_clips,
                    "total_duration_sec": total_duration
                }
            }
        else:
            return {"status": "error", "message": "Failed to update statistics"}

    except Exception as e:
        logger.error(f"Error updating statistics for video {source_video_id}: {str(e)}")
        return {"status": "error", "message": str(e)}