from typing import Dict, List, Any
from celery import Celery, Task
from celery.utils.log import get_task_logger
from datetime import datetime
import os
import json
import tempfile
from bson import ObjectId

from db_connector import create_repository
from utils.celery_utils import (
    format_filename, trim_video_clip, upload_clip_to_azure,
    create_cvat_task, get_blob_service_client, get_blob_container_client,
    get_cvat_task_parameters, AZURE_STORAGE_ACCOUNT_NAME,
    AZURE_STORAGE_CONTAINER_NAME, AZURE_OUTPUT_PREFIX
)

logger = get_task_logger(__name__)

# Створюємо екземпляр Celery
app = Celery('tasks')

# Завантажуємо конфігурацію з файлу
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
            self._source_repo = create_repository(collection_name="анотації_соурс_відео")
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
            self._azure_client = get_blob_service_client(AZURE_STORAGE_ACCOUNT_NAME)
        return self._azure_client

    @property
    def container_client(self):
        if self._container_client is None:
            self._container_client = get_blob_container_client(
                self.azure_client, AZURE_STORAGE_CONTAINER_NAME
            )
        return self._container_client


@app.task(name="process_video_annotation", bind=True, base=VideoProcessingTask)
def process_video_annotation(self, azure_link: str) -> Dict[str, Any]:
    """
    Обробляє анотації відео з MongoDB та запускає задачі нарізки кліпів

    Args:
        azure_link: Посилання на вихідне відео

    Returns:
        Dict[str, Any]: Статус операції та список задач
    """
    logger.info(f"Початок обробки відео: {azure_link}")

    try:
        # Отримуємо анотацію з БД
        annotation = self.source_repo.get_annotation(azure_link)

        if not annotation:
            logger.error(f"Анотацію не знайдено: {azure_link}")
            return {
                "status": "error",
                "message": f"Анотацію для відео '{azure_link}' не знайдено"
            }

        # Пропускаємо, якщо відео помічено як "skip"
        if annotation.get("metadata", {}).get("skip", False):
            logger.info(f"Відео пропущено (skip): {azure_link}")
            return {
                "status": "skipped",
                "message": "Відео помічено як 'skip'"
            }

        # Отримуємо шлях до відео
        local_path = annotation.get("local_path")
        if not local_path:
            logger.error(f"Локальний шлях не знайдено: {azure_link}")
            return {
                "status": "error",
                "message": "Відсутній локальний шлях до відео"
            }

        # Перетворюємо шлях /videos/filename.mp4 у повний шлях
        video_filename = os.path.basename(local_path)
        absolute_path = os.path.join("source_videos", video_filename)

        if not os.path.exists(absolute_path):
            logger.error(f"Файл не знайдено: {absolute_path}")
            return {
                "status": "error",
                "message": f"Файл не знайдено: {absolute_path}"
            }

        # Отримуємо метадані та кліпи
        metadata = annotation.get("metadata", {})
        clips = annotation.get("clips", {})
        source_id = annotation.get("id")

        if not clips:
            logger.error(f"Не знайдено інформацію про кліпи: {azure_link}")
            return {
                "status": "error",
                "message": "Не знайдено інформацію про кліпи"
            }

        # Запускаємо задачі обробки кліпів
        task_ids = []
        for project, project_clips in clips.items():
            # Отримуємо параметри CVAT
            cvat_params = annotation.get("cvat_params", {}).get(project, {})
            if not cvat_params and project in get_cvat_task_parameters():
                cvat_params = get_cvat_task_parameters()[project]

            for idx, clip in enumerate(project_clips):
                # Запускаємо задачу обробки кліпу
                task = process_video_clip.delay(
                    source_id=source_id,
                    project=project,
                    clip_id=idx,
                    video_filename=video_filename,
                    absolute_path=absolute_path,
                    start_time=clip["start_time"],
                    end_time=clip["end_time"],
                    metadata=metadata,
                    cvat_params=cvat_params
                )
                task_ids.append(task.id)

        # Оновлюємо статус вихідного відео
        annotation["status"] = "processing"
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
        source_id: str,
        project: str,
        clip_id: int,
        video_filename: str,
        absolute_path: str,
        start_time: str,
        end_time: str,
        metadata: Dict[str, Any],
        cvat_params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Обробляє окремий відео кліп

    Args:
        source_id: ID вихідного відео
        project: Тип проєкту
        clip_id: ID кліпу
        video_filename: Ім'я файлу відео
        absolute_path: Абсолютний шлях до відео
        start_time: Час початку фрагменту
        end_time: Час кінця фрагменту
        metadata: Метадані відео
        cvat_params: Параметри CVAT

    Returns:
        Dict[str, Any]: Результат обробки
    """
    logger.info(f"Початок обробки кліпу {clip_id} проєкту {project} з відео {video_filename}")

    try:
        # Створюємо тимчасову директорію для роботи з файлами
        with tempfile.TemporaryDirectory() as temp_dir:
            # Формуємо ім'я файлу
            filename_base = format_filename(
                metadata=metadata,
                original_filename=video_filename,
                project=project,
                clip_id=clip_id
            )

            filename = f"{filename_base}.mp4"
            clip_path = os.path.join(temp_dir, filename)

            # Нарізаємо відео
            success = trim_video_clip(
                source_path=absolute_path,
                output_path=clip_path,
                start_time=start_time,
                end_time=end_time
            )

            if not success:
                logger.error(f"Не вдалося створити кліп {clip_path}")
                return {
                    "status": "error",
                    "message": f"Не вдалося створити кліп: {clip_path}"
                }

            # Формуємо шлях в Azure
            current_date = datetime.now().strftime("%Y%m%d")
            azure_path = f"{AZURE_OUTPUT_PREFIX}/{project}/{current_date}/{filename}"

            # Завантажуємо на Azure
            upload_result = upload_clip_to_azure(
                container_client=self.container_client,
                file_path=clip_path,
                azure_path=azure_path,
                metadata={
                    "project": project,
                    "source_id": source_id,
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
                filename=filename_base,
                file_path=clip_path,
                project_params=cvat_params
            )

            # Зберігаємо метадані в MongoDB
            clip_data = {
                "source_id": ObjectId(source_id),
                "project": project,
                "clip_id": clip_id,
                "filename": filename_base,
                "extension": ".mp4",
                "cvat_task_id": cvat_task_id,
                "processing_date": datetime.now(),
                "status": "not_annotated",
                "azure_path": f"{AZURE_OUTPUT_PREFIX}/{project}/{current_date}/",
                "fps": 60  # Заглушка
            }

            # Зберігаємо в базу даних
            clip_id_db = self.clips_repo.save_annotation(clip_data)

            logger.info(f"Кліп успішно оброблено: {filename_base}")

            return {
                "status": "success",
                "message": "Кліп успішно оброблено",
                "clip_id": clip_id_db,
                "cvat_task_id": cvat_task_id,
                "azure_path": azure_path
            }

    except Exception as e:
        logger.error(f"Помилка при обробці кліпу {clip_id} проєкту {project}: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }


@app.task(name="monitor_clip_tasks")
def monitor_clip_tasks(task_ids: List[str]) -> Dict[str, Any]:
    """
    Перевіряє статус задач обробки кліпів

    Args:
        task_ids: Список ID задач

    Returns:
        Dict[str, Any]: Загальний статус та результати задач
    """
    results = {}

    for task_id in task_ids:
        task = process_video_clip.AsyncResult(task_id)
        results[task_id] = {
            "status": task.status,
            "result": task.result if task.ready() else None
        }

    overall_status = "completed"
    if any(r["status"] == "PENDING" for r in results.values()):
        overall_status = "pending"
    elif any(r["status"] == "STARTED" for r in results.values()):
        overall_status = "started"
    elif any(r["status"] == "FAILURE" for r in results.values()):
        overall_status = "failed"

    return {
        "status": overall_status,
        "results": results
    }


@app.task(name="process_video_annotation_original_task")
def process_video_annotation_original_task(azure_link: str) -> Dict[str, Any]:
    """
    Обробляє відео анотацію (сумісність з оригінальною реалізацією)

    Args:
        azure_link: Посилання на відео у Azure

    Returns:
        Dict[str, Any]: Результат операції
    """
    repo = None
    try:
        repo = create_repository(collection_name="анотації_соурс_відео", async_mode=False)
        annotation = repo.get_annotation(azure_link)

        if not annotation:
            return {
                "status": "error",
                "message": f"Анотацію для відео '{azure_link}' не знайдено"
            }

        # Запускаємо нову задачу обробки
        task_result = process_video_annotation.delay(azure_link)

        # Конвертуємо документ у плоску структуру для відповіді
        json_str = json.dumps(annotation)
        processed_annotation = json.loads(json_str)

        return {
            "status": "ok",
            "azure_link": azure_link,
            "annotation": processed_annotation,
            "task_id": task_result.id
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }