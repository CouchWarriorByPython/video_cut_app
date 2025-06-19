from typing import Dict, List, Optional, Union, Any, TypeVar, Generic
from abc import ABC, abstractmethod
from bson import ObjectId
from datetime import datetime, UTC
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo.collection import Collection
from backend.utils.logger import get_logger

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """Базовий абстрактний репозиторій для роботи з MongoDB"""

    def __init__(self, collection_name: str, async_mode: bool = False):
        self.collection_name = collection_name
        self.async_mode = async_mode
        self.logger = get_logger(f"{self.__class__.__name__}")
        self._collection: Optional[Union[Collection, AsyncIOMotorCollection]] = None

    @property
    @abstractmethod
    def collection(self) -> Union[Collection, AsyncIOMotorCollection]:
        """Отримання колекції MongoDB"""
        pass

    @abstractmethod
    def get_index_configuration(self) -> List[Dict[str, Any]]:
        """Конфігурація індексів для колекції"""
        pass

    def normalize_document(self, doc: Optional[Dict]) -> Optional[Dict]:
        """Нормалізація MongoDB документа"""
        if not doc:
            return None

        if "_id" in doc:
            doc["_id"] = str(doc["_id"])

        for key, value in doc.items():
            if isinstance(value, ObjectId):
                doc[key] = str(value)

        return doc

    def normalize_documents(self, docs: List[Dict]) -> List[Dict]:
        """Нормалізація списку документів"""
        return [self.normalize_document(doc) for doc in docs if doc]

    def prepare_document_for_save(self, data: Dict) -> Dict:
        """Підготовка документа до збереження"""
        current_time = datetime.now(UTC).isoformat(sep=" ", timespec="seconds")

        if "_id" not in data and "created_at_utc" not in data:
            data["created_at_utc"] = current_time

        data["updated_at_utc"] = current_time

        # Округлення size_MB до 2 знаків після коми
        if "size_MB" in data and data["size_MB"] is not None:
            data["size_MB"] = round(data["size_MB"], 2)

        data_without_id = {k: v for k, v in data.items() if k != "_id"}
        return data_without_id

    def convert_id_to_object(self, doc_id: Union[str, ObjectId]) -> ObjectId:
        """Конвертація string ID в ObjectId"""
        return ObjectId(doc_id) if isinstance(doc_id, str) else doc_id