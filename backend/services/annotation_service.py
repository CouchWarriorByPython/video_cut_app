from typing import Dict, Any, Optional
from datetime import datetime

from backend.database.repositories.source_video import SyncSourceVideoRepository
from backend.services.cvat_service import CVATService
from backend.utils.logger import get_logger

logger = get_logger(__name__, "services.log")


class AnnotationService:
    """Сервіс для роботи з анотаціями"""

    def __init__(self):
        self.source_repo = SyncSourceVideoRepository()
        self.cvat_service = CVATService()

    def save_fragments_and_metadata(self, azure_link: str, annotation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Зберігає фрагменти відео та метадані"""
        try:
            skip_processing = annotation_data.get("metadata", {}).get("skip", False)

            self.source_repo.create_indexes()

            existing = self.source_repo.get_annotation(azure_link)
            if not existing:
                return {
                    "success": False,
                    "error": f"Відео з посиланням {azure_link} не знайдено"
                }

            # Валідація мінімальної тривалості кліпів
            clips = annotation_data.get("clips", {})
            validation_error = self._validate_clips_duration(clips)
            if validation_error:
                return {
                    "success": False,
                    "error": validation_error
                }

            # Оновлення анотації
            existing.update({
                "metadata": annotation_data.get("metadata"),
                "clips": annotation_data.get("clips"),
                "status": "annotated",
                "updated_at": datetime.now().isoformat(sep=" ", timespec="seconds")
            })

            # Додавання CVAT параметрів якщо відсутні
            if "cvat_params" not in existing or not existing["cvat_params"]:
                cvat_params = {}
                for clip_type in annotation_data.get("clips", {}).keys():
                    cvat_params[clip_type] = self.cvat_service.get_default_project_params(clip_type)
                existing["cvat_params"] = cvat_params

            record_id = self.source_repo.save_annotation(existing)

            if skip_processing:
                success_message = "Дані успішно збережено. Обробку пропущено (skip)."
                logger.info(f"Відео пропущено (skip): {azure_link}")
                task_id = None
            else:
                success_message = "Дані успішно збережено. Готово до запуску обробки."
                task_id = None  # Task ID буде встановлено в API layer

            return {
                "success": True,
                "_id": record_id,
                "task_id": task_id,
                "message": success_message,
                "skip_processing": skip_processing
            }

        except Exception as e:
            logger.error(f"Помилка при збереженні анотації: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _validate_clips_duration(self, clips: Dict[str, Any]) -> Optional[str]:
        """Валідує мінімальну тривалість кліпів"""
        for project_type, project_clips in clips.items():
            for clip in project_clips:
                start_parts = clip["start_time"].split(":")
                end_parts = clip["end_time"].split(":")

                start_seconds = int(start_parts[0]) * 3600 + int(start_parts[1]) * 60 + int(start_parts[2])
                end_seconds = int(end_parts[0]) * 3600 + int(end_parts[1]) * 60 + int(end_parts[2])

                if end_seconds - start_seconds < 1:
                    return f"Мінімальна тривалість кліпу - 1 секунда. Кліп {clip['id']} в проєкті {project_type} занадто короткий."

        return None