from typing import Dict, Any

from backend.background_tasks.app import app
from backend.services.clip_processing_service import ClipProcessingService
from backend.utils.logger import get_logger
from backend.database.connection import DatabaseConnection

logger = get_logger(__name__, "tasks.log")


@app.task(name="process_video_clip", bind=True)
def process_video_clip(self, clip_video_id: str) -> Dict[str, Any]:
    """Process individual video clip from clip_videos collection"""
    try:
        # Ensure database connection
        if not DatabaseConnection.is_connected():
            DatabaseConnection.connect()

        service = ClipProcessingService()
        return service.process_single_clip(clip_video_id)
    except Exception as e:
        logger.error(f"Error processing clip {clip_video_id}: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.task(name="process_all_video_clips", bind=True)
def process_all_video_clips(self, source_video_id: str) -> Dict[str, Any]:
    """Process all clips for a source video"""
    try:
        # Ensure database connection
        if not DatabaseConnection.is_connected():
            DatabaseConnection.connect()

        service = ClipProcessingService()
        return service.process_all_clips_for_video(source_video_id)
    except Exception as e:
        logger.error(f"Error processing clips for video {source_video_id}: {str(e)}")
        return {"status": "error", "message": str(e)}