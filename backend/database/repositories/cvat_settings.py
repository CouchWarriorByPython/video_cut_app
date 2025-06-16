from typing import Dict, List, Optional

from backend.database.base import AnnotationBase
from backend.database.connection import DatabaseConnection
from backend.models.cvat_settings import CVATProjectSettings
from backend.utils.logger import get_logger

logger = get_logger(__name__, "database.log")


class CVATSettingsRepository(AnnotationBase):
    """Репозиторій для роботи з налаштуваннями CVAT проєктів"""

    def __init__(self) -> None:
        super().__init__("cvat_project_settings")
        self.db = DatabaseConnection.get_sync_database()
        self.collection = self.db[self.collection_name]

    def create_indexes(self) -> None:
        """Створює індекси для колекції"""
        try:
            existing_indexes = self.collection.list_indexes()
            index_names = [idx["name"] for idx in existing_indexes]

            if not any("project_name" in name for name in index_names):
                self.collection.create_index("project_name", unique=True)
                logger.debug("Створено унікальний індекс project_name для cvat_project_settings")

        except Exception as e:
            logger.error(f"Помилка при роботі з індексами: {str(e)}")

    def get_all_settings(self) -> List[Dict]:
        """Отримує всі налаштування проєктів"""
        try:
            docs = list(self.collection.find())
            logger.debug(f"Отримано {len(docs)} налаштувань CVAT проєктів")
            return self._normalize_documents(docs)
        except Exception as e:
            logger.error(f"Помилка отримання налаштувань CVAT: {str(e)}")
            raise

    def get_settings_by_project(self, project_name: str) -> Optional[Dict]:
        """Отримує налаштування конкретного проєкту"""
        try:
            doc = self.collection.find_one({"project_name": project_name})
            return self._normalize_document(doc)
        except Exception as e:
            logger.error(f"Помилка отримання налаштувань проєкту {project_name}: {str(e)}")
            raise

    def save_settings(self, settings: CVATProjectSettings) -> str:
        """Зберігає або оновлює налаштування проєкту"""
        try:
            data = self._prepare_annotation(settings.model_dump())
            data_without_id = {k: v for k, v in data.items() if k != "_id"}

            existing = self.collection.find_one({"project_name": settings.project_name})

            if existing:
                # Перевіряємо унікальність project_id (крім поточного запису)
                conflicting = self.collection.find_one({
                    "project_id": settings.project_id,
                    "project_name": {"$ne": settings.project_name}
                })
                if conflicting:
                    raise ValueError(f"Project ID {settings.project_id} вже використовується проєктом {conflicting['project_name']}")

                data_without_id["created_at"] = existing.get("created_at", data.get("created_at"))
                self.collection.replace_one({"_id": existing["_id"]}, data_without_id)
                logger.info(f"Оновлено налаштування проєкту: {settings.project_name}")
                return str(existing["_id"])
            else:
                # Перевіряємо унікальність project_id для нового запису
                conflicting = self.collection.find_one({"project_id": settings.project_id})
                if conflicting:
                    raise ValueError(f"Project ID {settings.project_id} вже використовується проєктом {conflicting['project_name']}")

                result = self.collection.insert_one(data_without_id)
                logger.info(f"Створено нові налаштування проєкту: {settings.project_name}")
                return str(result.inserted_id)

        except Exception as e:
            logger.error(f"Помилка збереження налаштувань CVAT: {str(e)}")
            raise

    def delete_settings(self, project_name: str) -> bool:
        """Видаляє налаштування проєкту"""
        try:
            result = self.collection.delete_one({"project_name": project_name})
            success = result.deleted_count > 0
            if success:
                logger.info(f"Видалено налаштування проєкту: {project_name}")
            else:
                logger.warning(f"Налаштування проєкту для видалення не знайдено: {project_name}")
            return success
        except Exception as e:
            logger.error(f"Помилка видалення налаштувань CVAT: {str(e)}")
            raise

    def initialize_default_settings(self) -> None:
        """Ініціалізує дефолтні налаштування для всіх проєктів"""
        default_settings = [
            {"project_name": "motion-det", "project_id": 5, "overlap": 5, "segment_size": 400, "image_quality": 100},
            {"project_name": "tracking", "project_id": 6, "overlap": 5, "segment_size": 400, "image_quality": 100},
            {"project_name": "mil-hardware", "project_id": 7, "overlap": 5, "segment_size": 400, "image_quality": 100},
            {"project_name": "re-id", "project_id": 8, "overlap": 5, "segment_size": 400, "image_quality": 100},
        ]

        for settings_data in default_settings:
            existing = self.collection.find_one({"project_name": settings_data["project_name"]})
            if not existing:
                settings = CVATProjectSettings(**settings_data)
                self.save_settings(settings)
                logger.info(f"Ініціалізовано дефолтні налаштування для {settings_data['project_name']}")