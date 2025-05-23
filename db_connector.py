from typing import Dict, List, Optional, Union
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from datetime import datetime

from configs import Settings
from utils.logger import get_logger

logger = get_logger(__name__)


class ClipInfo(BaseModel):
    """Інформація про відрізок відео"""
    id: int
    start_time: str
    end_time: str


class VideoMetadata(BaseModel):
    """Метадані відео"""
    skip: bool = False
    uav_type: str = ""
    video_content: str = ""
    is_urban: bool = False
    has_osd: bool = False
    is_analog: bool = False
    night_video: bool = False
    multiple_streams: bool = False
    has_infantry: bool = False
    has_explosions: bool = False


class CVATProjectParams(BaseModel):
    """Параметри проєкту CVAT"""
    project_id: int
    overlap: int
    segment_size: int
    image_quality: int


class VideoAnnotation(BaseModel):
    """Повна модель анотації відео"""
    azure_link: str
    extension: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    when: Optional[str] = None
    where: Optional[str] = None
    status: str = "not_annotated"
    metadata: Optional[VideoMetadata] = None
    clips: Dict[str, List[ClipInfo]] = Field(default_factory=dict)
    cvat_params: Dict[str, CVATProjectParams] = Field(default_factory=dict)


class AnnotationBase:
    """Базовий клас для роботи з анотаціями відео"""

    def __init__(self, collection_name: str):
        """Ініціалізує клас з вказаною колекцією"""
        self.collection_name = collection_name
        logger.info(f"Ініціалізація репозиторію для колекції: {collection_name}")

    def _prepare_annotation(self, annotation: Union[Dict, BaseModel]) -> Dict:
        """Підготовка даних анотації до збереження"""
        if isinstance(annotation, BaseModel):
            annotation = annotation.model_dump()

        annotation["updated_at"] = datetime.now().isoformat(sep=" ", timespec="seconds")

        # Змінюємо логіку перевірки - для колекції video_clips не вимагаємо azure_link
        if self.collection_name != "video_clips" and "azure_link" not in annotation:
            raise ValueError("Анотація повинна містити поле 'azure_link'")

        return annotation

    @staticmethod
    def _normalize_document(doc: Optional[Dict]) -> Optional[Dict]:
        """Перетворює MongoDB документ у звичайний словник з плоскою структурою"""
        if not doc:
            return None

        # Перетворення ObjectId в рядок
        if "_id" in doc:
            doc["id"] = str(doc["_id"])
            del doc["_id"]

        # Перетворення дат у рядки ISO формату
        for field in ["created_at", "updated_at"]:
            if field in doc and isinstance(doc[field], datetime):
                doc[field] = doc[field].isoformat()

        return doc

    def _normalize_documents(self, docs: List[Dict]) -> List[Dict]:
        """Нормалізує список документів"""
        return [self._normalize_document(doc) for doc in docs]


class SyncVideoAnnotationRepository(AnnotationBase):
    """Синхронний репозиторій для збереження відеоанотацій в MongoDB"""

    def __init__(self, collection_name: str = None):
        """Ініціалізує репозиторій з вказаною колекцією"""
        super().__init__(collection_name or "анотації")
        try:
            self.client = MongoClient(Settings.mongo_uri)
            self.db = self.client[Settings.mongo_db_name]
            self.collection = self.db[self.collection_name]
            logger.info(f"Успішне підключення до MongoDB: {Settings.mongo_db_name}.{self.collection_name}")
        except Exception as e:
            logger.error(f"Помилка підключення до MongoDB: {str(e)}")
            raise

    def create_indexes(self) -> None:
        """Створює унікальний індекс для azure_link"""
        try:
            if self.collection_name != "video_clips":
                self.collection.create_index("azure_link", unique=True)
                logger.info(f"Створено індекс для колекції {self.collection_name}")
        except Exception as e:
            logger.error(f"Помилка створення індексу: {str(e)}")

    def save_annotation(self, annotation: Union[Dict, VideoAnnotation]) -> str:
        """Зберігає або оновлює анотацію"""
        try:
            data = self._prepare_annotation(annotation)

            if self.collection_name == "video_clips":
                # Для кліпів просто вставляємо новий запис
                data["created_at"] = datetime.now().isoformat(sep=" ", timespec="seconds")
                result = self.collection.insert_one(data)
                logger.info(f"Збережено новий кліп з ID: {result.inserted_id}")
                return str(result.inserted_id)
            else:
                # Для основних анотацій використовуємо upsert по azure_link
                azure_link = data.get("azure_link")
                existing = self.collection.find_one({"azure_link": azure_link})

                if existing:
                    self.collection.replace_one({"_id": existing["_id"]}, data)
                    logger.info(f"Оновлено анотацію для: {azure_link}")
                    return str(existing["_id"])
                else:
                    data["created_at"] = datetime.now().isoformat(sep=" ", timespec="seconds")
                    result = self.collection.insert_one(data)
                    logger.info(f"Створено нову анотацію для: {azure_link}")
                    return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Помилка збереження анотації: {str(e)}")
            raise

    def get_annotation(self, azure_link: str) -> Optional[Dict]:
        """Отримує анотацію за URL"""
        try:
            doc = self.collection.find_one({"azure_link": azure_link})
            if doc:
                logger.info(f"Знайдено анотацію для: {azure_link}")
            else:
                logger.warning(f"Анотацію не знайдено для: {azure_link}")
            return self._normalize_document(doc)
        except Exception as e:
            logger.error(f"Помилка отримання анотації: {str(e)}")
            raise

    def get_all_annotations(self) -> List[Dict]:
        """Отримує всі анотації"""
        try:
            docs = list(self.collection.find())
            logger.info(f"Отримано {len(docs)} анотацій з колекції {self.collection_name}")
            return self._normalize_documents(docs)
        except Exception as e:
            logger.error(f"Помилка отримання всіх анотацій: {str(e)}")
            raise

    def delete_annotation(self, azure_link: str) -> bool:
        """Видаляє анотацію за URL"""
        try:
            result = self.collection.delete_one({"azure_link": azure_link})
            success = result.deleted_count > 0
            if success:
                logger.info(f"Видалено анотацію для: {azure_link}")
            else:
                logger.warning(f"Анотацію для видалення не знайдено: {azure_link}")
            return success
        except Exception as e:
            logger.error(f"Помилка видалення анотації: {str(e)}")
            raise

    def close(self) -> None:
        """Закриває з'єднання з MongoDB"""
        try:
            self.client.close()
            logger.info("З'єднання з MongoDB закрито")
        except Exception as e:
            logger.error(f"Помилка закриття з'єднання: {str(e)}")


class AsyncVideoAnnotationRepository(AnnotationBase):
    """Асинхронний репозиторій для збереження відеоанотацій в MongoDB"""

    def __init__(self, collection_name: str):
        """Ініціалізує репозиторій з вказаною колекцією"""
        super().__init__(collection_name)
        try:
            self.client = AsyncIOMotorClient(Settings.mongo_uri)
            self.db = self.client[Settings.mongo_db_name]
            self.collection = self.db[self.collection_name]
            logger.info(
                f"Ініціалізовано асинхронне підключення до MongoDB: {Settings.mongo_db_name}.{self.collection_name}")
        except Exception as e:
            logger.error(f"Помилка ініціалізації асинхронного підключення: {str(e)}")
            raise

    async def create_indexes(self) -> None:
        """Створює унікальний індекс для azure_link"""
        try:
            if self.collection_name != "video_clips":
                await self.collection.create_index("azure_link", unique=True)
                logger.info(f"Створено асинхронний індекс для колекції {self.collection_name}")
        except Exception as e:
            logger.error(f"Помилка створення асинхронного індексу: {str(e)}")

    async def save_annotation(self, annotation: Union[Dict, VideoAnnotation]) -> str:
        """Зберігає або оновлює анотацію"""
        try:
            data = self._prepare_annotation(annotation)

            if self.collection_name == "video_clips":
                data["created_at"] = datetime.now().isoformat(sep=" ", timespec="seconds")
                result = await self.collection.insert_one(data)
                logger.info(f"Асинхронно збережено новий кліп з ID: {result.inserted_id}")
                return str(result.inserted_id)
            else:
                azure_link = data.get("azure_link")
                existing = await self.collection.find_one({"azure_link": azure_link})

                if existing:
                    await self.collection.replace_one({"_id": existing["_id"]}, data)
                    logger.info(f"Асинхронно оновлено анотацію для: {azure_link}")
                    return str(existing["_id"])
                else:
                    data["created_at"] = datetime.now().isoformat(sep=" ", timespec="seconds")
                    result = await self.collection.insert_one(data)
                    logger.info(f"Асинхронно створено нову анотацію для: {azure_link}")
                    return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Помилка асинхронного збереження анотації: {str(e)}")
            raise

    async def get_annotation(self, azure_link: str) -> Optional[Dict]:
        """Отримує анотацію за URL"""
        try:
            doc = await self.collection.find_one({"azure_link": azure_link})
            if doc:
                logger.info(f"Асинхронно знайдено анотацію для: {azure_link}")
            else:
                logger.warning(f"Асинхронно не знайдено анотацію для: {azure_link}")
            return self._normalize_document(doc)
        except Exception as e:
            logger.error(f"Помилка асинхронного отримання анотації: {str(e)}")
            raise

    async def get_all_annotations(self) -> List[Dict]:
        """Отримує всі анотації"""
        try:
            cursor = self.collection.find()
            docs = await cursor.to_list(length=None)
            logger.info(f"Асинхронно отримано {len(docs)} анотацій з колекції {self.collection_name}")
            return self._normalize_documents(docs)
        except Exception as e:
            logger.error(f"Помилка асинхронного отримання всіх анотацій: {str(e)}")
            raise

    async def delete_annotation(self, azure_link: str) -> bool:
        """Видаляє анотацію за URL"""
        try:
            result = await self.collection.delete_one({"azure_link": azure_link})
            success = result.deleted_count > 0
            if success:
                logger.info(f"Асинхронно видалено анотацію для: {azure_link}")
            else:
                logger.warning(f"Асинхронно не знайдено анотацію для видалення: {azure_link}")
            return success
        except Exception as e:
            logger.error(f"Помилка асинхронного видалення анотації: {str(e)}")
            raise

    def close(self) -> None:
        """Закриває з'єднання з MongoDB"""
        try:
            self.client.close()
            logger.info("Асинхронне з'єднання з MongoDB закрито")
        except Exception as e:
            logger.error(f"Помилка закриття асинхронного з'єднання: {str(e)}")


def create_repository(collection_name: str, async_mode: bool = False):
    """
    Створює репозиторій для роботи з MongoDB

    Args:
        collection_name: Назва колекції
        async_mode: Використовувати асинхронну реалізацію

    Returns:
        Репозиторій для роботи з анотаціями відео
    """
    logger.info(f"Створення репозиторію: колекція={collection_name}, асинхронний={async_mode}")

    if async_mode:
        return AsyncVideoAnnotationRepository(collection_name=collection_name)
    else:
        return SyncVideoAnnotationRepository(collection_name=collection_name)
