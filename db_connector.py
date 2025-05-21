from typing import Dict, List, Optional, Union
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from datetime import datetime

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

    def _prepare_annotation(self, annotation: Union[Dict, BaseModel]) -> Dict:
        """Підготовка даних анотації до збереження"""
        if isinstance(annotation, BaseModel):
            annotation = annotation.model_dump()

        annotation["updated_at"] = datetime.utcnow()

        if "azure_link" not in annotation:
            raise ValueError("Анотація повинна містити поле 'azure_link'")

        return annotation

    def _normalize_document(self, doc: Optional[Dict]) -> Optional[Dict]:
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
    """Синхронний репозиторій для збереження відео-анотацій в MongoDB"""

    def __init__(self, collection_name: str = None):
        """Ініціалізує репозиторій з вказаною колекцією"""
        super().__init__(collection_name or "анотації")
        self.client = MongoClient(Settings.mongo_uri)
        self.db = self.client[Settings.mongo_db_name]
        self.collection = self.db[self.collection_name]

    def create_indexes(self) -> None:
        """Створює унікальний індекс для azure_link"""
        self.collection.create_index("azure_link", unique=True)

    def save_annotation(self, annotation: Union[Dict, VideoAnnotation]) -> str:
        """Зберігає або оновлює анотацію"""
        data = self._prepare_annotation(annotation)

        azure_link = data.get("azure_link")
        existing = self.collection.find_one({"azure_link": azure_link})

        if existing:
            self.collection.replace_one({"_id": existing["_id"]}, data)
            return str(existing["_id"])
        else:
            data["created_at"] = datetime.utcnow()
            result = self.collection.insert_one(data)
            return str(result.inserted_id)

    def get_annotation(self, azure_link: str) -> Optional[Dict]:
        """Отримує анотацію за URL"""
        doc = self.collection.find_one({"azure_link": azure_link})
        return self._normalize_document(doc)

    def get_all_annotations(self) -> List[Dict]:
        """Отримує всі анотації"""
        docs = list(self.collection.find())
        return self._normalize_documents(docs)

    def delete_annotation(self, azure_link: str) -> bool:
        """Видаляє анотацію за URL"""
        result = self.collection.delete_one({"azure_link": azure_link})
        return result.deleted_count > 0

    def close(self) -> None:
        """Закриває з'єднання з MongoDB"""
        self.client.close()


class AsyncVideoAnnotationRepository(AnnotationBase):
    """Асинхронний репозиторій для збереження відео-анотацій в MongoDB"""

    def __init__(self, collection_name: str):
        """Ініціалізує репозиторій з вказаною колекцією"""
        super().__init__(collection_name)
        self.client = AsyncIOMotorClient(Settings.mongo_uri)
        self.db = self.client[Settings.mongo_db_name]
        self.collection = self.db[self.collection_name]

    async def create_indexes(self) -> None:
        """Створює унікальний індекс для azure_link"""
        await self.collection.create_index("azure_link", unique=True)

    async def save_annotation(self, annotation: Union[Dict, VideoAnnotation]) -> str:
        """Зберігає або оновлює анотацію"""
        data = self._prepare_annotation(annotation)

        azure_link = data.get("azure_link")
        existing = await self.collection.find_one({"azure_link": azure_link})

        if existing:
            await self.collection.replace_one({"_id": existing["_id"]}, data)
            return str(existing["_id"])
        else:
            data["created_at"] = datetime.utcnow()
            result = await self.collection.insert_one(data)
            return str(result.inserted_id)

    async def get_annotation(self, azure_link: str) -> Optional[Dict]:
        """Отримує анотацію за URL"""
        doc = await self.collection.find_one({"azure_link": azure_link})
        return self._normalize_document(doc)

    async def get_all_annotations(self) -> List[Dict]:
        """Отримує всі анотації"""
        cursor = self.collection.find()
        docs = await cursor.to_list(length=None)
        return self._normalize_documents(docs)

    async def delete_annotation(self, azure_link: str) -> bool:
        """Видаляє анотацію за URL"""
        result = await self.collection.delete_one({"azure_link": azure_link})
        return result.deleted_count > 0

    def close(self) -> None:
        """Закриває з'єднання з MongoDB"""
        self.client.close()


def create_repository(collection_name: str, async_mode: bool = False):
    """
    Створює репозиторій для роботи з MongoDB

    Args:
        collection_name: Назва колекції
        async_mode: Використовувати асинхронну реалізацію

    Returns:
        Репозиторій для роботи з анотаціями відео
    """
    if async_mode:
        return AsyncVideoAnnotationRepository(collection_name=collection_name)
    else:
        return SyncVideoAnnotationRepository(collection_name=collection_name)
