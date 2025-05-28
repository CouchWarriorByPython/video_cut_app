from typing import Dict, List, Any
from celery import Celery, Task
from celery.utils.log import get_task_logger
import os
import tempfile
from datetime import datetime

from db_connector import create_repository
from utils.celery_utils import (
    trim_video_clip, upload_clip_to_azure, create_cvat_task,
    get_blob_service_client, get_blob_container_client,
    get_default_cvat_project_params, format_filename, cleanup_file
)
from configs import Settings

logger = get_task_logger(__name__)

app = Celery('tasks')
app.config_from_object('celery_config')


class VideoProcessingTask(Task):
    """Базовий клас задачі для обробки відео з ініціалізацією необхідних клієнтів"""

    _source_repo = None
    _clips_repo = None
    _azure_client = None
    _container_client = None

    @property
    def source_repo(self):
        if self._source_repo is None:
            self._source_repo = create_repository(collection_name="source_videos")
        return self._source_repo

    @property
    def clips_repo(self):
        if self._clips_repo is None:
            self._clips_repo = create_repository(collection_name="video_clips")
            self._clips_repo.create_indexes()
        return self._clips_repo

    @property
    def azure_client(self):
        if self._azure_client is None:
            self._azure_client = get_blob_service_client()
        return self._azure_client

    @property
    def container_client(self):
        if self._container_client is None:
            self._container_client = get_blob_container_client(self.azure_client)
        return self._container_client


@app.task(name="process_video_annotation", bind=True, base=VideoProcessingTask)
def process_video_annotation(self, azure_link: str) -> Dict[str, Any]:
    """Обробляє анотації відео з MongoDB та запускає задачі нарізки кліпів"""
    logger.info(f"Початок обробки відео: {azure_link}")

    try:
        annotation = self.source_repo.get_annotation(azure_link)

        if not annotation:
            logger.error(f"Анотацію не знайдено: {azure_link}")
            return {
                "status": "error",
                "message": f"Анотацію для відео '{azure_link}' не знайдено"
            }

        if annotation.get("metadata", {}).get("skip", False):
            logger.info(f"Відео пропущено (skip): {azure_link}")
            return {
                "status": "skipped",
                "message": "Відео помічено як 'skip'"
            }

        filename = annotation.get("filename")
        local_path = annotation.get("local_path")

        if not filename:
            logger.error(f"Назва файлу не знайдена: {azure_link}")
            return {
                "status": "error",
                "message": "Відсутня назва файлу"
            }

        if not local_path or not os.path.exists(local_path):
            logger.error(f"Локальний файл не знайдено: {local_path}")
            return {
                "status": "error",
                "message": "Локальний файл не знайдено"
            }

        metadata = annotation.get("metadata", {})
        clips = annotation.get("clips", {})
        where = annotation.get("where", "")
        when = annotation.get("when", "")

        if not clips:
            logger.error(f"Не знайдено інформацію про кліпи: {azure_link}")
            return {
                "status": "error",
                "message": "Не знайдено інформацію про кліпи"
            }

        stored_cvat_params = annotation.get("cvat_params", {})
        task_ids = []

        for project, project_clips in clips.items():
            cvat_params = stored_cvat_params.get(project)
            if not cvat_params:
                cvat_params = get_default_cvat_project_params(project)
                logger.info(f"Використовуємо дефолтні CVAT параметри для проєкту {project}")

            for clip in project_clips:
                task = process_video_clip.delay(
                    azure_link=azure_link,
                    project=project,
                    clip_id=clip["id"],
                    filename=filename,
                    start_time=clip["start_time"],
                    end_time=clip["end_time"],
                    metadata=metadata,
                    cvat_params=cvat_params,
                    where=where,
                    when=when
                )
                task_ids.append(task.id)

        # Оновлюємо статус соурс відео
        annotation["status"] = "processing"
        annotation["updated_at"] = datetime.now().isoformat(sep=" ", timespec="seconds")
        self.source_repo.save_annotation(annotation)

        logger.info(f"Запущено обробку {len(task_ids)} кліпів для відео: {azure_link}")

        return {
            "status": "success",
            "message": f"Запущено обробку {len(task_ids)} кліпів",
            "task_ids": task_ids
        }

    except Exception as e:
        logger.error(f"Помилка при обробці відео {azure_link}: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }


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
    logger.info(f"Початок обробки кліпу {clip_id} проєкту {project} з відео {filename}")

    temp_clip_path = None

    try:
        source_annotation = self.source_repo.get_annotation(azure_link)
        if not source_annotation:
            logger.error(f"Не вдалося знайти соурс відео за azure_link: {azure_link}")
            return {
                "status": "error",
                "message": f"Не вдалося знайти соурс відео за azure_link: {azure_link}"
            }

        source_id = source_annotation.get("_id")
        local_source_path = source_annotation.get("local_path")

        if not local_source_path or not os.path.exists(local_source_path):
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

        # Формуємо Azure шлях для кліпу
        video_base_name = os.path.splitext(filename)[0]
        azure_clip_path = f"{Settings.azure_output_folder_path}{video_base_name}/{clip_filename}"

        # Завантажуємо кліп на Azure
        upload_result = upload_clip_to_azure(
            container_client=self.container_client,
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
        cvat_task_id = create_cvat_task(
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
            "status": "processing",
            "azure_link": upload_result["azure_path"],
            "blob_url": upload_result["blob_url"],
            "fps": Settings.default_fps,
            "created_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
            "updated_at": datetime.now().isoformat(sep=" ", timespec="seconds")
        }

        clip_id_db = self.clips_repo.save_annotation(clip_data)

        logger.info(f"Кліп успішно оброблено: {clip_filename}")

        return {
            "status": "success",
            "message": "Кліп успішно оброблено",
            "clip_id_db": clip_id_db,
            "cvat_task_id": cvat_task_id,
            "azure_path": upload_result["azure_path"],
            "blob_url": upload_result["blob_url"],
            "filename": clip_filename
        }

    except Exception as e:
        logger.error(f"Помилка при обробці кліпу {clip_id} проєкту {project}: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }
    finally:
        # Очищаємо тільки тимчасовий кліп
        if temp_clip_path:
            cleanup_file(temp_clip_path)


@app.task(name="cleanup_processed_video")
def cleanup_processed_video(azure_link: str) -> Dict[str, Any]:
    """Видаляє source відео після завершення обробки всіх кліпів"""
    logger.info(f"Перевірка статусу обробки для відео: {azure_link}")

    repo = None
    clips_repo = None
    try:
        repo = create_repository(collection_name="source_videos")
        annotation = repo.get_annotation(azure_link)

        if not annotation:
            return {
                "status": "error",
                "message": "Відео не знайдено"
            }

        source_id = annotation.get("_id")
        clips_repo = create_repository(collection_name="video_clips")
        clips = clips_repo.get_clips_by_source_id(source_id)

        # Перевіряємо чи всі кліпи оброблено
        pending_clips = [clip for clip in clips if clip.get("status") == "processing"]

        if not pending_clips:
            # Всі кліпи оброблено, можна видаляти source
            local_path = annotation.get("local_path")
            if local_path and os.path.exists(local_path):
                cleanup_file(local_path)
                logger.info(f"Видалено локальний файл: {local_path}")

            annotation["status"] = "completed"
            annotation["updated_at"] = datetime.now().isoformat(sep=" ", timespec="seconds")
            repo.save_annotation(annotation)

            logger.info(f"Обробку відео {azure_link} завершено. Source файл видалено з локального сховища.")

            return {
                "status": "completed",
                "message": "Обробка завершена, source файл очищено"
            }
        else:
            return {
                "status": "pending",
                "message": f"Очікує завершення {len(pending_clips)} кліпів"
            }

    except Exception as e:
        logger.error(f"Помилка при очищенні відео {azure_link}: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }
    finally:
        if repo:
            repo.close()
        if clips_repo:
            clips_repo.close()