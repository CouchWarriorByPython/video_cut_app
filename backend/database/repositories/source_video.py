from typing import Dict, List, Optional, Union
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

from backend.database.base import AnnotationBase
from backend.database.connection import DatabaseConnection
from backend.models.database import SourceVideoAnnotation
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SyncSourceVideoRepository(AnnotationBase):
    """Синхронний репозиторій для роботи з source_videos"""

    def __init__(self) -> None:
        super().__init__("source_videos")
        self.db = DatabaseConnection.get_sync_database()
        self.collection = self.db[self.collection_name]

    def create_indexes(self) -> None:
        """Створює оптимальні індекси для колекції"""
        try:
            existing_indexes = self.collection.list_indexes()
            index_names = [idx["name"] for idx in existing_indexes]

            if not any("azure_link" in name for name in index_names):
                self.collection.create_index("azure_link", unique=True)
                logger.debug("Створено унікальний індекс azure_link для source_videos")

        except Exception as e:
            logger.error(f"Помилка при роботі з індексами: {str(e)}")

    def save_annotation(self, annotation: Union[Dict, SourceVideoAnnotation]) -> str:
        """Зберігає або оновлює анотацію з оптимізованою логікою"""
        try:
            data = self._prepare_annotation(annotation)
            data_without_id = {k: v for k, v in data.items() if k != "_id"}

            azure_link = data.get("azure_link")
            existing = self.collection.find_one({"azure_link": azure_link})

            if existing:
                data_without_id["created_at"] = existing.get("created_at", data.get("created_at"))
                self.collection.replace_one({"_id": existing["_id"]}, data_without_id)
                logger.debug(f"Оновлено соурс відео: {azure_link}")
                return str(existing["_id"])
            else:
                result = self.collection.insert_one(data_without_id)
                logger.info(f"Створено нове соурс відео: {azure_link}")
                return str(result.inserted_id)

        except Exception as e:
            logger.error(f"Помилка збереження анотації: {str(e)}")
            raise

    def get_annotation(self, azure_link: str) -> Optional[Dict]:
        """Отримує анотацію за Azure лінком"""
        try:
            doc = self.collection.find_one({"azure_link": azure_link})
            if not doc:
                logger.debug(f"Соурс відео не знайдено: {azure_link}")
            return self._normalize_document(doc)
        except Exception as e:
            logger.error(f"Помилка отримання анотації: {str(e)}")
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

    def delete_annotation(self, azure_link: str) -> bool:
        """Видаляє анотацію за Azure лінком"""
        try:
            result = self.collection.delete_one({"azure_link": azure_link})
            success = result.deleted_count > 0
            if success:
                logger.info(f"Видалено запис: {azure_link}")
            else:
                logger.warning(f"Запис для видалення не знайдено: {azure_link}")
            return success
        except Exception as e:
            logger.error(f"Помилка видалення анотації: {str(e)}")
            raise


class AsyncSourceVideoRepository(AnnotationBase):
    """Асинхронний репозиторій для роботи з source_videos"""

    def __init__(self) -> None:
        super().__init__("source_videos")
        self.db = DatabaseConnection.get_async_database()
        self.collection = self.db[self.collection_name]

    async def create_indexes(self) -> None:
        """Створює оптимальні індекси для колекції"""
        try:
            existing_indexes = []
            async for idx in self.collection.list_indexes():
                existing_indexes.append(idx)

            index_names = [idx["name"] for idx in existing_indexes]

            if not any("azure_link" in name for name in index_names):
                await self.collection.create_index("azure_link", unique=True)
                logger.debug("Створено асинхронний унікальний індекс azure_link для source_videos")

        except Exception as e:
            logger.error(f"Помилка при асинхронній роботі з індексами: {str(e)}")

    async def save_annotation(self, annotation: Union[Dict, SourceVideoAnnotation]) -> str:
        """Зберігає або оновлює анотацію з оптимізованою логікою"""
        try:
            data = self._prepare_annotation(annotation)
            data_without_id = {k: v for k, v in data.items() if k != "_id"}

            azure_link = data.get("azure_link")
            existing = await self.collection.find_one({"azure_link": azure_link})

            if existing:
                data_without_id["created_at"] = existing.get("created_at", data.get("created_at"))
                await self.collection.replace_one({"_id": existing["_id"]}, data_without_id)
                logger.debug(f"Асинхронно оновлено соурс відео: {azure_link}")
                return str(existing["_id"])
            else:
                result = await self.collection.insert_one(data_without_id)
                logger.info(f"Асинхронно створено нове соурс відео: {azure_link}")
                return str(result.inserted_id)

        except Exception as e:
            logger.error(f"Помилка асинхронного збереження анотації: {str(e)}")
            raise

    async def get_annotation(self, azure_link: str) -> Optional[Dict]:
        """Отримує анотацію за Azure лінком"""
        try:
            doc = await self.collection.find_one({"azure_link": azure_link})
            return self._normalize_document(doc)
        except Exception as e:
            logger.error(f"Помилка асинхронного отримання анотації: {str(e)}")
            raise

    async def get_all_annotations(self, filter_query: Optional[Dict] = None) -> List[Dict]:
        """Отримує всі анотації з можливістю фільтрації"""
        try:
            query = filter_query or {}
            cursor = self.collection.find(query)
            docs = await cursor.to_list(length=None)
            logger.debug(f"Асинхронно отримано {len(docs)} записів з колекції {self.collection_name}")
            return self._normalize_documents(docs)
        except Exception as e:
            logger.error(f"Помилка асинхронного отримання всіх анотацій: {str(e)}")
            raise

    async def delete_annotation(self, azure_link: str) -> bool:
        """Видаляє анотацію за Azure лінком"""
        try:
            result = await self.collection.delete_one({"azure_link": azure_link})
            success = result.deleted_count > 0
            if success:
                logger.info(f"Асинхронно видалено запис: {azure_link}")
            else:
                logger.warning(f"Асинхронно не знайдено запис для видалення: {azure_link}")
            return success
        except Exception as e:
            logger.error(f"Помилка асинхронного видалення анотації: {str(e)}")
            raise