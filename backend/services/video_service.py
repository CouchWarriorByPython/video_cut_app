import os
from typing import Dict, Any, Optional
from datetime import datetime

from backend.database.repositories.source_video import SyncSourceVideoRepository
from backend.services.azure_service import AzureService
from backend.utils.video_utils import get_local_video_path
from backend.utils.logger import get_logger

logger = get_logger(__name__, "services.log")


class VideoService:
    """Сервіс для роботи з відео"""

    def __init__(self):
        self.source_repo = SyncSourceVideoRepository()
        self.azure_service = AzureService()

    def validate_and_register_video(self, video_url: str, where: Optional[str], when: Optional[str]) -> Dict[str, Any]:
        """Валідує Azure URL та реєструє відео для асинхронної обробки"""
        try:
            validation_result = self.azure_service.validate_azure_url(video_url)

            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": f"Невірний Azure URL: {validation_result['error']}"
                }

            filename = validation_result["filename"]

            video_record = {
                "azure_link": video_url,
                "filename": filename,
                "created_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
                "updated_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
                "when": when,
                "where": where,
                "status": "queued"
            }

            self.source_repo.create_indexes()
            record_id = self.source_repo.save_annotation(video_record)

            # Запускаємо асинхронну задачу завантаження та конвертації
            from backend.background_tasks.tasks.video_download_conversion import download_and_convert_video
            task = download_and_convert_video.delay(video_url)

            logger.info(f"Відео зареєстровано та поставлено в чергу: {filename}, task_id: {task.id}")

            return {
                "success": True,
                "_id": record_id,
                "azure_link": video_url,
                "filename": filename,
                "task_id": task.id,
                "message": "Відео зареєстровано та поставлено в чергу обробки"
            }

        except Exception as e:
            logger.error(f"Помилка при реєстрації відео: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Отримує статус виконання задачі Celery"""
        try:
            from backend.background_tasks.app import app
            task = app.AsyncResult(task_id)

            if task.state == 'PENDING':
                response = {
                    "status": "pending",
                    "progress": 0,
                    "stage": "queued",
                    "message": "Задача в черзі на виконання"
                }
            elif task.state == 'PROGRESS':
                response = {
                    "status": "processing",
                    "progress": task.info.get('progress', 0),
                    "stage": task.info.get('stage', 'unknown'),
                    "message": task.info.get('message', 'Обробка...')
                }
            elif task.state == 'SUCCESS':
                response = {
                    "status": "completed",
                    "progress": 100,
                    "stage": "completed",
                    "message": "Відео готове до анотування",
                    "result": task.result
                }
            elif task.state == 'FAILURE':
                response = {
                    "status": "failed",
                    "progress": task.info.get('progress', 0) if hasattr(task, 'info') and task.info else 0,
                    "stage": "failed",
                    "message": str(task.info.get('error', task.result)) if hasattr(task, 'info') and task.info else str(
                        task.result)
                }
            else:
                response = {
                    "status": task.state.lower(),
                    "progress": 0,
                    "stage": "unknown",
                    "message": f"Невідомий стан: {task.state}"
                }

            return {
                "success": True,
                **response
            }

        except Exception as e:
            logger.error(f"Помилка при отриманні статусу задачі {task_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_video_status(self, azure_link: str) -> Dict[str, Any]:
        """Отримує статус обробки відео за Azure посиланням"""
        try:
            annotation = self.source_repo.get_annotation(azure_link)

            if not annotation:
                return {
                    "success": False,
                    "error": "Відео не знайдено"
                }

            status = annotation.get("status", "unknown")

            return {
                "success": True,
                "status": status,
                "filename": annotation.get("filename"),
                "ready_for_annotation": status in ["ready", "not_annotated"]
            }

        except Exception as e:
            logger.error(f"Помилка при отриманні статусу відео: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_video_for_streaming(self, azure_link: str) -> Optional[str]:
        """Отримує локальний шлях до відео для стрімінгу"""
        try:
            annotation = self.source_repo.get_annotation(azure_link)

            if not annotation:
                logger.error(f"Відео не знайдено: {azure_link}")
                return None

            # Перевіряємо, чи відео готове для перегляду
            status = annotation.get("status")
            if status not in ["ready", "not_annotated"]:
                logger.warning(f"Відео ще не готове для перегляду, статус: {status}")
                return None

            filename = annotation.get("filename")
            if not filename:
                logger.error(f"Назва файлу не знайдена для: {azure_link}")
                return None

            local_path = get_local_video_path(filename)

            if not os.path.exists(local_path):
                logger.error(f"Локальний файл не знайдено: {local_path}")
                return None

            return local_path

        except Exception as e:
            logger.error(f"Помилка при отриманні відео для стрімінгу: {str(e)}")
            return None

    def get_videos_list(self) -> Dict[str, Any]:
        """Отримує список відео які готові до анотування або ще обробляються"""
        try:
            videos_data = self.source_repo.get_all_annotations(
                filter_query={"status": {"$ne": "annotated"}}
            )

            return {
                "success": True,
                "videos": videos_data
            }
        except Exception as e:
            logger.error(f"Помилка при отриманні списку відео: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_annotation(self, azure_link: str) -> Dict[str, Any]:
        """Отримує існуючу анотацію для відео"""
        try:
            annotation_data = self.source_repo.get_annotation(azure_link)

            if not annotation_data:
                return {
                    "success": False,
                    "error": f"Анотацію для відео '{azure_link}' не знайдено"
                }

            return {
                "success": True,
                "annotation": annotation_data
            }

        except Exception as e:
            logger.error(f"Помилка при отриманні анотації: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }