from typing import Dict, Any

from backend.background_tasks.app import app
from backend.services.video_processing_service import VideoProcessingService
from backend.models.shared import AzureFilePath
from backend.utils.logger import get_logger

logger = get_logger(__name__, "tasks.log")


@app.task(name="download_and_convert_video", bind=True, max_retries=3)
def download_and_convert_video(self, azure_path_dict: Dict[str, str]) -> Dict[str, Any]:
    """Download video from Azure Storage and convert it for web viewing"""
    try:
        service = VideoProcessingService()
        azure_path = AzureFilePath(**azure_path_dict)

        def update_download_progress(downloaded_bytes: int, total_bytes: int) -> None:
            """Update download progress (5-50%)"""
            if total_bytes > 0:
                download_percent = 5 + (downloaded_bytes / total_bytes) * 45
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'progress': min(int(download_percent), 50),
                        'stage': 'downloading',
                        'message': f'Завантажено {downloaded_bytes // (1024 * 1024)} МБ з {total_bytes // (1024 * 1024)} МБ'
                    }
                )

        def update_conversion_progress(progress_percent: float) -> None:
            """Update conversion progress (60-95%)"""
            conversion_progress = 60 + (progress_percent * 0.35)
            self.update_state(
                state='PROGRESS',
                meta={
                    'progress': min(int(conversion_progress), 95),
                    'stage': 'converting',
                    'message': f'Конвертація: {progress_percent:.1f}%'
                }
            )

        self.update_state(
            state='PROGRESS',
            meta={
                'progress': 5,
                'stage': 'downloading',
                'message': 'Початок завантаження з Azure Storage...'
            }
        )

        result = service.download_and_convert_video(
            azure_path=azure_path,
            download_progress_callback=update_download_progress,
            conversion_progress_callback=update_conversion_progress
        )

        if result["status"] == "error":
            raise Exception(result["message"])

        return result

    except Exception as e:
        logger.error(f"Error in download_and_convert_video task: {str(e)}")
        raise self.retry(exc=e, countdown=60)