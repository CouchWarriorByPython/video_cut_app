from typing import Dict, Any
import os
import tempfile
from datetime import datetime

from backend.background_tasks.app import app
from backend.background_tasks.tasks.video_processing import VideoProcessingTask
from backend.utils.video_utils import (
    trim_video_clip, format_filename, cleanup_file,
    get_local_video_path, get_video_fps
)
from backend.services.azure_service import AzureService
from backend.config.settings import Settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@app.task(name="process_video_clip", bind=True, base=VideoProcessingTask)
def process_video_clip(
        self,
        azure_link: str,
        project: str,
        clip_id: int,
        filename: str,
        start_time: str,
        end_time: str,
        metadata: Dict[str, Any],
        cvat_params: Dict[str, Any],
        where: str = "",
        when: str = ""
) -> Dict[str, Any]:
    """Обробляє окремий відео кліп з локального файлу"""
    logger.debug(f"Початок обробки кліпу {clip_id} проєкту {project} з відео {filename}")

    temp_clip_path = None
    azure_service = None

    try:
        source_annotation = self.source_repo.get_annotation(azure_link)
        if not source_annotation:
            logger.error(f"Не вдалося знайти соурс відео за azure_link: {azure_link}")
            return {
                "status": "error",
                "message": f"Не вдалося знайти соурс відео за azure_link: {azure_link}"
            }

        source_id = source_annotation.get("_id")
        local_source_path = get_local_video_path(filename)

        if not os.path.exists(local_source_path):
            logger.error(f"Локальний файл не знайдено: {local_source_path}")
            return {
                "status": "error",
                "message": f"Локальний файл не знайдено: {local_source_path}"
            }

        # Створюємо тимчасовий файл для кліпу
        clip_filename = format_filename(metadata, filename, project, clip_id, where, when)

        temp_clip_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".mp4",
            dir=Settings.temp_folder
        )
        temp_clip_path = temp_clip_file.name
        temp_clip_file.close()

        # Нарізаємо кліп з локального файлу
        success = trim_video_clip(
            source_path=local_source_path,
            output_path=temp_clip_path,
            start_time=start_time,
            end_time=end_time
        )

        if not success:
            logger.error(f"Не вдалося створити кліп {temp_clip_path}")
            return {
                "status": "error",
                "message": f"Не вдалося створити кліп: {clip_filename}"
            }

        # Визначаємо FPS після створення кліпу
        fps = get_video_fps(temp_clip_path)
        if fps is None:
            logger.warning(f"Не вдалося визначити FPS для кліпу {clip_filename}")

        # Формуємо Azure шлях для кліпу
        video_base_name = os.path.splitext(filename)[0]
        azure_clip_path = f"{Settings.azure_output_folder_path}{video_base_name}/{clip_filename}"

        # Завантажуємо кліп на Azure
        azure_service = AzureService()
        upload_result = azure_service.upload_clip(
            file_path=temp_clip_path,
            azure_path=azure_clip_path,
            metadata={
                "project": project,
                "source_id": str(source_id),
                "clip_id": str(clip_id)
            }
        )

        if not upload_result["success"]:
            logger.error(f"Помилка при завантаженні на Azure: {upload_result.get('error')}")
            return {
                "status": "error",
                "message": f"Помилка при завантаженні на Azure: {upload_result.get('error')}"
            }

        # Створюємо CVAT задачу
        cvat_task_id = self.cvat_service.create_task(
            filename=os.path.splitext(clip_filename)[0],
            file_path=temp_clip_path,
            project_params=cvat_params
        )

        # Підготовка даних для збереження в video_clips
        clip_data = {
            "source_id": source_id,
            "project": project,
            "clip_id": clip_id,
            "extension": "mp4",
            "cvat_task_id": cvat_task_id,
            "status": "not_annotated",
            "azure_link": upload_result["azure_url"],
            "fps": fps,
            "created_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
            "updated_at": datetime.now().isoformat(sep=" ", timespec="seconds")
        }

        clip_id_db = self.clips_repo.save_annotation(clip_data)

        logger.debug(f"Кліп оброблено: {clip_filename} (FPS: {fps})")

        return {
            "status": "success",
            "message": "Кліп успішно оброблено",
            "clip_id_db": clip_id_db,
            "cvat_task_id": cvat_task_id,
            "azure_link": upload_result["azure_url"],
            "filename": clip_filename,
            "fps": fps
        }

    except Exception as e:
        logger.error(f"Помилка при обробці кліпу {clip_id} проєкту {project}: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }
    finally:
        # Очищаємо тимчасовий кліп
        if temp_clip_path:
            cleanup_file(temp_clip_path)