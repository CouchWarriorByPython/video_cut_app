from typing import Dict, List, Optional, Union, Protocol, ClassVar
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from datetime import datetime
from bson import ObjectId

from configs import Settings


# Моделі даних
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    when: Optional[str] = None
    where: Optional[str] = None
    status: str = "not_annotated"
    metadata: Optional[VideoMetadata] = None
    clips: Dict[str, List[ClipInfo]] = Field(default_factory=dict)
    cvat_params: Dict[str, CVATProjectParams] = Field(default_factory=dict)


# Базовий протокол (інтерфейс) для спільного API
class AnnotationRepositoryProtocol(Protocol):
    """Інтерфейс для роботи з анотаціями відео в MongoDB"""

    def create_indexes(self) -> None:
        """Створення необхідних індексів для колекції"""
        ...

    def save_annotation(self, annotation: Union[Dict, VideoAnnotation]) -> str:
        """
        Збереження анотації (створення нової або оновлення існуючої)

        Args:
            annotation: Дані анотації у форматі dict або VideoAnnotation

        Returns:
            str: ID документа або повідомлення про успішне оновлення
        """
        ...

    def get_annotation(self, azure_link: str) -> Optional[Dict]:
        """
        Отримання анотації за посиланням на відео

        Args:
            azure_link: Посилання на відео в Azure

        Returns:
            Optional[Dict]: Документ анотації або None, якщо не знайдено
        """
        ...

    def get_all_annotations(self) -> List[Dict]:
        """
        Отримання всіх анотацій

        Returns:
            List[Dict]: Список документів анотацій
        """
        ...

    def delete_annotation(self, azure_link: str) -> bool:
        """
        Видалення анотації за посиланням на відео

        Args:
            azure_link: Посилання на відео в Azure

        Returns:
            bool: True, якщо видалення виконано успішно
        """
        ...

    def close(self) -> None:
        """Закриття з'єднання з MongoDB"""
        ...


# Синхронна реалізація для Celery та скриптів
class SyncVideoAnnotationRepository:
    """Синхронний репозиторій для збереження відео-анотацій в MongoDB"""

    def __init__(self, collection_name: str = None):
        self.client = MongoClient(Settings.mongo_uri)
        self.db = self.client[Settings.mongo_db_name]
        self.collection = self.db[collection_name]

    def create_indexes(self) -> None:
        self.collection.create_index("azure_link", unique=True)

    def save_annotation(self, annotation: Union[Dict, VideoAnnotation]) -> str:
        # Перетворення Pydantic моделі в словник
        if isinstance(annotation, VideoAnnotation):
            annotation = annotation.model_dump()

        # Встановлюємо або оновлюємо часові мітки
        annotation["updated_at"] = datetime.utcnow()

        azure_link = annotation.get("azure_link")
        if not azure_link:
            raise ValueError("Анотація повинна містити поле 'azure_link'")

        # Перевіряємо, чи існує документ з таким azure_link
        existing = self.collection.find_one({"azure_link": azure_link})

        if existing:
            # Оновлюємо документ
            self.collection.replace_one({"_id": existing["_id"]}, annotation)
            return str(existing["_id"])
        else:
            # Створюємо новий документ
            annotation["created_at"] = datetime.utcnow()
            result = self.collection.insert_one(annotation)
            return str(result.inserted_id)

    def get_annotation(self, azure_link: str) -> Optional[Dict]:
        return self.collection.find_one({"azure_link": azure_link})

    def get_all_annotations(self) -> List[Dict]:
        return list(self.collection.find())

    def delete_annotation(self, azure_link: str) -> bool:
        result = self.collection.delete_one({"azure_link": azure_link})
        return result.deleted_count > 0

    def close(self) -> None:
        self.client.close()


# Асинхронна реалізація для FastAPI
class AsyncVideoAnnotationRepository:
    """Асинхронний репозиторій для збереження відео-анотацій в MongoDB"""

    def __init__(self, collection_name: str):
        self.client = AsyncIOMotorClient(Settings.mongo_uri)
        self.db = self.client[Settings.mongo_db_name]
        self.collection = self.db[collection_name]

    async def create_indexes(self) -> None:
        await self.collection.create_index("azure_link", unique=True)

    async def save_annotation(self, annotation: Union[Dict, VideoAnnotation]) -> str:
        # Перетворення Pydantic моделі в словник
        if isinstance(annotation, VideoAnnotation):
            annotation = annotation.model_dump()

        # Встановлюємо або оновлюємо часові мітки
        annotation["updated_at"] = datetime.utcnow()

        azure_link = annotation.get("azure_link")
        if not azure_link:
            raise ValueError("Анотація повинна містити поле 'azure_link'")

        # Перевіряємо, чи існує документ з таким azure_link
        existing = await self.collection.find_one({"azure_link": azure_link})

        if existing:
            # Оновлюємо документ
            await self.collection.replace_one({"_id": existing["_id"]}, annotation)
            return str(existing["_id"])
        else:
            # Створюємо новий документ
            annotation["created_at"] = datetime.utcnow()
            result = await self.collection.insert_one(annotation)
            return str(result.inserted_id)

    async def get_annotation(self, azure_link: str) -> Optional[Dict]:
        return await self.collection.find_one({"azure_link": azure_link})

    async def get_all_annotations(self) -> List[Dict]:
        cursor = self.collection.find()
        return await cursor.to_list(length=None)

    async def delete_annotation(self, azure_link: str) -> bool:
        result = await self.collection.delete_one({"azure_link": azure_link})
        return result.deleted_count > 0

    def close(self) -> None:
        self.client.close()


# Фабрика для створення потрібної реалізації
def create_repository(collection_name: str, async_mode: bool = False):
    """
    Створення репозиторію для роботи з MongoDB

    Args:
        collection_name: Назва колекції в MongoDB
        async_mode: Використовувати асинхронну реалізацію (True) або синхронну (False)

    Returns:
        Об'єкт репозиторію для роботи з анотаціями відео
    """
    if async_mode:
        return AsyncVideoAnnotationRepository(collection_name=collection_name)
    else:
        return SyncVideoAnnotationRepository(collection_name=collection_name)