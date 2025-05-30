from typing import Dict, List, Any
from celery import Task, chord
import os
from datetime import datetime

from backend.background_tasks.app import app
from backend.database.repositories.source_video import SyncSourceVideoRepository
from backend.database.repositories.video_clip import SyncVideoClipRepository
from backend.utils.azure_utils import get_blob_service_client, get_blob_container_client
from backend.utils.video_utils import get_local_video_path, cleanup_file
from backend.services.cvat_service import CVATService
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class VideoProcessingTask(Task):
    """Базовий клас задачі для обробки відео з ініціалізацією необхідних клієнтів"""

    _source_repo = None
    _clips_repo = None
    _azure_client = None
    _container_client = None
    _cvat_service = None

    @property
    def source_repo(self):
        if self._source_repo is None:
            self._source_repo = SyncSourceVideoRepository()
        return self._source_repo

    @property
    def clips_repo(self):
        if self._clips_repo is None:
            self._clips_repo = SyncVideoClipRepository()
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

    @property
    def cvat_service(self):
        if self._cvat_service is None:
            self._cvat_service = CVATService()
        return self._cvat_service


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
        if not filename:
            logger.error(f"Назва файлу не знайдена: {azure_link}")
            return {
                "status": "error",
                "message": "Відсутня назва файлу"
            }

        local_path = get_local_video_path(filename)
        if not os.path.exists(local_path):
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

        # Створюємо список задач для обробки кліпів
        from backend.background_tasks.tasks.clip_processing import process_video_clip
        clip_tasks = []
        total_clips = 0

        for project, project_clips in clips.items():
            cvat_params = stored_cvat_params.get(project)
            if not cvat_params:
                cvat_params = self.cvat_service.get_default_project_params(project)
                logger.debug(f"Використовуємо дефолтні CVAT параметри для проєкту {project}")

            for clip in project_clips:
                task = process_video_clip.s(
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
                clip_tasks.append(task)
                total_clips += 1

        # Використовуємо chord для запуску всіх задач та callback після завершення
        callback = finalize_video_processing.s(azure_link)
        job = chord(clip_tasks)(callback)

        logger.info(f"Запущено обробку {total_clips} кліпів для відео: {azure_link}")

        return {
            "status": "success",
            "message": f"Запущено обробку {total_clips} кліпів",
            "chord_id": job.id,
            "total_clips": total_clips
        }

    except Exception as e:
        logger.error(f"Помилка при обробці відео {azure_link}: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }


@app.task(name="finalize_video_processing")
def finalize_video_processing(results: List[Dict], azure_link: str) -> Dict[str, Any]:
    """Завершує обробку відео після завершення всіх кліпів"""
    logger.info(f"Завершення обробки відео: {azure_link}")

    repo = None
    try:
        repo = SyncSourceVideoRepository()
        annotation = repo.get_annotation(azure_link)

        if not annotation:
            logger.error(f"Source відео не знайдено: {azure_link}")
            return {
                "status": "error",
                "message": "Source відео не знайдено"
            }

        # Підраховуємо результати
        successful_clips = len([r for r in results if r and r.get("status") == "success"])
        failed_clips = len([r for r in results if r and r.get("status") == "error"])
        total_clips = len(results)

        logger.info(f"Результати обробки {azure_link}: успішно {successful_clips}/{total_clips}, помилок {failed_clips}")

        # Видаляємо source файл ТІЛЬКИ якщо ВСІ задачі завершились успішно
        if failed_clips == 0 and successful_clips == total_clips:
            filename = annotation.get("filename")
            if filename:
                local_path = get_local_video_path(filename)
                if os.path.exists(local_path):
                    try:
                        cleanup_file(local_path)
                        logger.info(f"Видалено локальний source файл: {local_path}")
                    except Exception as e:
                        logger.error(f"Помилка видалення source файлу {local_path}: {str(e)}")
                        return {
                            "status": "error",
                            "message": f"Помилка видалення source файлу: {str(e)}",
                            "successful_clips": successful_clips,
                            "failed_clips": failed_clips,
                            "total_clips": total_clips
                        }
                else:
                    logger.warning(f"Локальний файл не знайдено або вже видалено: {local_path}")

            # Оновлюємо статус source відео на "annotated"
            annotation["status"] = "annotated"
            annotation["updated_at"] = datetime.now().isoformat(sep=" ", timespec="seconds")
            repo.save_annotation(annotation)

            logger.info(f"Обробку відео {azure_link} повністю завершено")

            return {
                "status": "completed",
                "message": "Обробка відео повністю завершена",
                "successful_clips": successful_clips,
                "failed_clips": failed_clips,
                "total_clips": total_clips
            }
        else:
            # Є помилки - НЕ видаляємо source файл, залишаємо статус як є
            logger.warning(f"Обробка відео {azure_link} завершена з помилками")

            return {
                "status": "partial_success",
                "message": f"Обробка завершена з помилками. Успішно оброблено {successful_clips} з {total_clips} кліпів",
                "successful_clips": successful_clips,
                "failed_clips": failed_clips,
                "total_clips": total_clips
            }

    except Exception as e:
        logger.error(f"Помилка при завершенні обробки відео {azure_link}: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }