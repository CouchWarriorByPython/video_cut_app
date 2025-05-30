from typing import Dict, List, Optional, Union
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

from backend.database.base import AnnotationBase
from backend.database.connection import DatabaseConnection
from backend.models.database import VideoClipRecord
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SyncVideoClipRepository(AnnotationBase):
    """Синхронний репозиторій для роботи з video_clips"""

    def __init__(self) -> None:
        super().__init__("video_clips")
        self.db = DatabaseConnection.get_sync_database()
        self.collection = self.db[self.collection_name]

    def create_indexes(self) -> None:
        """Створює оптимальні індекси для колекції"""
        try:
            existing_indexes = self.collection.list_indexes()
            index_names = [idx["name"] for idx in existing_indexes]

            compound_exists = any("source_id_1_project_1_clip_id_1" in name for name in index_names)
            if not compound_exists:
                self.collection.create_index([
                    ("source_id", 1),
                    ("project", 1),
                    ("clip_id", 1)
                ], unique=True)
                logger.debug("Створено унікальний складний індекс для video_clips")

            if not any("azure_link" in name for name in index_names):
                self.collection.create_index("azure_link", unique=False)
                logger.debug("Створено індекс azure_link для швидкого пошуку")

        except Exception as e:
            logger.error(f"Помилка при роботі з індексами: {str(e)}")

    def save_annotation(self, annotation: Union[Dict, VideoClipRecord]) -> str:
        """Зберігає або оновлює анотацію з оптимізованою логікою"""
        try:
            data = self._prepare_annotation(annotation)
            data_without_id = {k: v for k, v in data.items() if k != "_id"}

            source_id = data.get("source_id")
            project = data.get("project")
            clip_id = data.get("clip_id")

            source_id_obj = ObjectId(source_id) if isinstance(source_id, str) else source_id
            data_without_id["source_id"] = source_id_obj

            existing = self.collection.find_one({
                "source_id": source_id_obj,
                "project": project,
                "clip_id": clip_id
            })

            if existing:
                data_without_id["created_at"] = existing.get("created_at", data.get("created_at"))
                self.collection.replace_one({"_id": existing["_id"]}, data_without_id)
                logger.debug(f"Оновлено кліп: {project} clip_id={clip_id}")
                return str(existing["_id"])
            else:
                result = self.collection.insert_one(data_without_id)
                logger.debug(f"Створено новий кліп: {project} clip_id={clip_id}")
                return str(result.inserted_id)

        except Exception as e:
            logger.error(f"Помилка збереження анотації: {str(e)}")
            raise

    def get_annotation(self, annotation_id: str) -> Optional[Dict]:
        """Отримує анотацію за ID"""
        try:
            doc = self.collection.find_one({"_id": ObjectId(annotation_id)})
            if not doc:
                logger.debug(f"Кліп не знайдено: {annotation_id}")
            return self._normalize_document(doc)
        except Exception as e:
            logger.error(f"Помилка отримання анотації: {str(e)}")
            raise

    def get_clips_by_source_id(self, source_id: str) -> List[Dict]:
        """Отримує всі кліпи для вказаного соурс відео"""
        try:
            source_id_obj = ObjectId(source_id)
            docs = list(self.collection.find({"source_id": source_id_obj}))
            logger.debug(f"Знайдено {len(docs)} кліпів для source_id: {source_id}")
            return self._normalize_documents(docs)
        except Exception as e:
            logger.error(f"Помилка отримання кліпів: {str(e)}")
            raise

    def get_all_annotations(self, filter_query: Optional[Dict] = None) -> List[Dict]:
        """Отримує всі анотації з можливістю фільтрації"""
        try:
            query = filter_query or {}
            docs = list(self.collection.find(query))
            logger.debug(f"Отримано {len(docs)} записів з колекції {self.collection_name}")
            return self._normalize_documents(docs)
        except Exception as e:
            logger.error(f"Помилка отримання всіх анотацій: {str(e)}")
            raise

    def delete_annotation(self, annotation_id: str) -> bool:
        """Видаляє анотацію за ID"""
        try:
            result = self.collection.delete_one({"_id": ObjectId(annotation_id)})
            success = result.deleted_count > 0
            if success:
                logger.info(f"Видалено запис: {annotation_id}")
            else:
                logger.warning(f"Запис для видалення не знайдено: {annotation_id}")
            return success
        except Exception as e:
            logger.error(f"Помилка видалення анотації: {str(e)}")
            raise


class AsyncVideoClipRepository(AnnotationBase):
    """Асинхронний репозиторій для роботи з video_clips"""

    def __init__(self) -> None:
        super().__init__("video_clips")
        self.db = DatabaseConnection.get_async_database()
        self.collection = self.db[self.collection_name]

    async def create_indexes(self) -> None:
        """Створює оптимальні індекси для колекції"""
        try:
            existing_indexes = []
            async for idx in self.collection.list_indexes():
                existing_indexes.append(idx)

            index_names = [idx["name"] for idx in existing_indexes]

            compound_exists = any("source_id_1_project_1_clip_id_1" in name for name in index_names)
            if not compound_exists:
                await self.collection.create_index([
                    ("source_id", 1),
                    ("project", 1),
                    ("clip_id", 1)
                ], unique=True)
                logger.debug("Створено асинхронний унікальний складний індекс для video_clips")

            if not any("azure_link" in name for name in index_names):
                await self.collection.create_index("azure_link", unique=False)
                logger.debug("Створено асинхронний індекс azure_link для швидкого пошуку")

        except Exception as e:
            logger.error(f"Помилка при асинхронній роботі з індексами: {str(e)}")

    async def save_annotation(self, annotation: Union[Dict, VideoClipRecord]) -> str:
        """Зберігає або оновлює анотацію з оптимізованою логікою"""
        try:
            data = self._prepare_annotation(annotation)
            data_without_id = {k: v for k, v in data.items() if k != "_id"}

            source_id = data.get("source_id")
            project = data.get("project")
            clip_id = data.get("clip_id")

            source_id_obj = ObjectId(source_id) if isinstance(source_id, str) else source_id
            data_without_id["source_id"] = source_id_obj

            existing = await self.collection.find_one({
                "source_id": source_id_obj,
                "project": project,
                "clip_id": clip_id
            })

            if existing:
                data_without_id["created_at"] = existing.get("created_at", data.get("created_at"))
                await self.collection.replace_one({"_id": existing["_id"]}, data_without_id)
                logger.debug(f"Асинхронно оновлено кліп: {project} clip_id={clip_id}")
                return str(existing["_id"])
            else:
                result = await self.collection.insert_one(data_without_id)
                logger.debug(f"Асинхронно створено новий кліп: {project} clip_id={clip_id}")
                return str(result.inserted_id)

        except Exception as e:
            logger.error(f"Помилка асинхронного збереження анотації: {str(e)}")
            raise

    async def get_clips_by_source_id(self, source_id: str) -> List[Dict]:
        """Отримує всі кліпи для вказаного соурс відео"""
        try:
            source_id_obj = ObjectId(source_id)
            cursor = self.collection.find({"source_id": source_id_obj})
            docs = await cursor.to_list(length=None)
            logger.debug(f"Асинхронно знайдено {len(docs)} кліпів для source_id: {source_id}")
            return self._normalize_documents(docs)
        except Exception as e:
            logger.error(f"Помилка асинхронного отримання кліпів: {str(e)}")
            raise