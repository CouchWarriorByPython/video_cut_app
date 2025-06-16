from typing import Dict, List, Optional, Any
from datetime import datetime
from bson import ObjectId
from backend.database.base_repository import BaseRepository
from backend.database.connection import DatabaseConnection


class UnifiedRepository(BaseRepository):
    """Уніфікований репозиторій для роботи з будь-якою колекцією MongoDB"""

    INDEX_CONFIGURATIONS = {
        "source_videos": [
            {"fields": [("azure_link", 1)], "unique": True, "name": "azure_link_unique"},
            {"fields": [("status", 1)], "unique": False, "name": "status_index"}
        ],
        "video_clips": [
            {
                "fields": [("source_id", 1), ("project", 1), ("clip_id", 1)],
                "unique": True,
                "name": "source_project_clip_unique"
            },
            {"fields": [("azure_link", 1)], "unique": False, "name": "azure_link_index"},
            {"fields": [("status", 1)], "unique": False, "name": "status_index"}
        ],
        "users": [
            {"fields": [("email", 1)], "unique": True, "name": "email_unique"},
            {"fields": [("is_active", 1)], "unique": False, "name": "active_users_index"}
        ],
        "cvat_project_settings": [
            {"fields": [("project_name", 1)], "unique": True, "name": "project_name_unique"},
            {"fields": [("project_id", 1)], "unique": True, "name": "project_id_unique"}
        ]
    }

    VALIDATION_RULES = {
        "source_videos": {
            "required_fields": ["azure_link", "filename"],
            "unique_fields": ["azure_link"]
        },
        "video_clips": {
            "required_fields": ["source_id", "project", "clip_id", "azure_link"],
            "unique_fields": [["source_id", "project", "clip_id"]]
        },
        "users": {
            "required_fields": ["email", "hashed_password", "role"],
            "unique_fields": ["email"]
        }
    }

    def __init__(self, collection_name: str, async_mode: bool = False):
        super().__init__(collection_name, async_mode)
        self.validation_rules = self.VALIDATION_RULES.get(collection_name, {})

    @property
    def collection(self):
        if self._collection is None:
            if self.async_mode:
                db = DatabaseConnection.get_async_database()
            else:
                db = DatabaseConnection.get_sync_database()
            self._collection = db[self.collection_name]
        return self._collection

    def get_index_configuration(self) -> List[Dict[str, Any]]:
        return self.INDEX_CONFIGURATIONS.get(self.collection_name, [])

    def create_indexes(self) -> None:
        """Створення індексів для колекції (синхронна версія)"""
        if self.async_mode:
            raise RuntimeError("Використовуйте create_indexes_async() для асинхронного режиму")

        try:
            index_config = self.get_index_configuration()
            self._create_sync_indexes(index_config)
            self.logger.debug(f"Індекси створено для колекції {self.collection_name}")
        except Exception as e:
            self.logger.error(f"Помилка створення індексів для {self.collection_name}: {str(e)}")
            raise

    async def create_indexes_async(self) -> None:
        """Створення індексів для колекції (асинхронна версія)"""
        if not self.async_mode:
            raise RuntimeError("Використовуйте create_indexes() для синхронного режиму")

        try:
            index_config = self.get_index_configuration()
            await self._create_async_indexes(index_config)
            self.logger.debug(f"Індекси створено для колекції {self.collection_name}")
        except Exception as e:
            self.logger.error(f"Помилка створення індексів для {self.collection_name}: {str(e)}")
            raise

    def _create_sync_indexes(self, index_config: List[Dict]) -> None:
        """Створення синхронних індексів"""
        existing_indexes = list(self.collection.list_indexes())
        existing_names = {idx.get("name") for idx in existing_indexes}

        for config in index_config:
            if config["name"] not in existing_names:
                index_kwargs = {
                    "unique": config.get("unique", False),
                    "name": config["name"]
                }

                if len(config["fields"]) == 1:
                    field, direction = config["fields"][0]
                    self.collection.create_index([(field, direction)], **index_kwargs)
                else:
                    self.collection.create_index(config["fields"], **index_kwargs)

    async def _create_async_indexes(self, index_config: List[Dict]) -> None:
        """Створення асинхронних індексів"""
        existing_indexes = []
        async for idx in self.collection.list_indexes():
            existing_indexes.append(idx)

        existing_names = {idx.get("name") for idx in existing_indexes}

        for config in index_config:
            if config["name"] not in existing_names:
                index_kwargs = {
                    "unique": config.get("unique", False),
                    "name": config["name"]
                }

                if len(config["fields"]) == 1:
                    field, direction = config["fields"][0]
                    await self.collection.create_index([(field, direction)], **index_kwargs)
                else:
                    await self.collection.create_index(config["fields"], **index_kwargs)

    def validate_document(self, data: Dict) -> None:
        """Валідація документа перед збереженням"""
        required_fields = self.validation_rules.get("required_fields", [])

        for field in required_fields:
            if field not in data or not data[field]:
                raise ValueError(f"Обов'язкове поле '{field}' відсутнє або порожнє")

    def save_document(self, data: Dict, update_mode: str = "replace") -> str:
        """Універсальне збереження документа (синхронна версія)"""
        if self.async_mode:
            raise RuntimeError("Використовуйте save_document_async() для асинхронного режиму")

        try:
            self.validate_document(data)
            prepared_data = self.prepare_document_for_save(data.copy())

            unique_fields = self.validation_rules.get("unique_fields", [])
            existing_doc = None

            if unique_fields:
                existing_doc = self._find_by_unique_fields_sync(prepared_data, unique_fields)

            if existing_doc:
                return self._update_document_sync(existing_doc["_id"], prepared_data, update_mode)
            else:
                return self._insert_document_sync(prepared_data)

        except Exception as e:
            self.logger.error(f"Помилка збереження документа в {self.collection_name}: {str(e)}")
            raise

    async def save_document_async(self, data: Dict, update_mode: str = "replace") -> str:
        """Універсальне збереження документа (асинхронна версія)"""
        if not self.async_mode:
            raise RuntimeError("Використовуйте save_document() для синхронного режиму")

        try:
            self.validate_document(data)
            prepared_data = self.prepare_document_for_save(data.copy())

            unique_fields = self.validation_rules.get("unique_fields", [])
            existing_doc = None

            if unique_fields:
                existing_doc = await self._find_by_unique_fields_async(prepared_data, unique_fields)

            if existing_doc:
                return await self._update_document_async(existing_doc["_id"], prepared_data, update_mode)
            else:
                return await self._insert_document_async(prepared_data)

        except Exception as e:
            self.logger.error(f"Помилка збереження документа в {self.collection_name}: {str(e)}")
            raise

    def _find_by_unique_fields_sync(self, data: Dict, unique_fields: List) -> Optional[Dict]:
        """Пошук документа за унікальними полями (синхронна версія)"""
        for field_spec in unique_fields:
            if isinstance(field_spec, list):
                query = {field: data.get(field) for field in field_spec if field in data}
                if len(query) == len(field_spec):
                    return self.collection.find_one(query)
            else:
                if field_spec in data:
                    query = {field_spec: data[field_spec]}
                    return self.collection.find_one(query)
        return None

    async def _find_by_unique_fields_async(self, data: Dict, unique_fields: List) -> Optional[Dict]:
        """Пошук документа за унікальними полями (асинхронна версія)"""
        for field_spec in unique_fields:
            if isinstance(field_spec, list):
                query = {field: data.get(field) for field in field_spec if field in data}
                if len(query) == len(field_spec):
                    return await self.collection.find_one(query)
            else:
                if field_spec in data:
                    query = {field_spec: data[field_spec]}
                    return await self.collection.find_one(query)
        return None

    def _update_document_sync(self, doc_id: ObjectId, data: Dict, mode: str) -> str:
        """Оновлення існуючого документа (синхронна версія)"""
        if mode == "replace":
            self.collection.replace_one({"_id": doc_id}, data)
        elif mode == "update":
            self.collection.update_one({"_id": doc_id}, {"$set": data})

        self.logger.debug(f"Документ оновлено в {self.collection_name}: {doc_id}")
        return str(doc_id)

    async def _update_document_async(self, doc_id: ObjectId, data: Dict, mode: str) -> str:
        """Оновлення існуючого документа (асинхронна версія)"""
        if mode == "replace":
            await self.collection.replace_one({"_id": doc_id}, data)
        elif mode == "update":
            await self.collection.update_one({"_id": doc_id}, {"$set": data})

        self.logger.debug(f"Документ оновлено в {self.collection_name}: {doc_id}")
        return str(doc_id)

    def _insert_document_sync(self, data: Dict) -> str:
        """Вставка нового документа (синхронна версія)"""
        result = self.collection.insert_one(data)
        self.logger.debug(f"Новий документ створено в {self.collection_name}: {result.inserted_id}")
        return str(result.inserted_id)

    async def _insert_document_async(self, data: Dict) -> str:
        """Вставка нового документа (асинхронна версія)"""
        result = await self.collection.insert_one(data)
        self.logger.debug(f"Новий документ створено в {self.collection_name}: {result.inserted_id}")
        return str(result.inserted_id)

    def find_by_id(self, doc_id: str) -> Optional[Dict]:
        """Пошук документа за ID (синхронна версія)"""
        if self.async_mode:
            raise RuntimeError("Використовуйте find_by_id_async() для асинхронного режиму")

        try:
            object_id = self.convert_id_to_object(doc_id)
            doc = self.collection.find_one({"_id": object_id})
            return self.normalize_document(doc)
        except Exception as e:
            self.logger.error(f"Помилка пошуку документа за ID {doc_id}: {str(e)}")
            raise

    async def find_by_id_async(self, doc_id: str) -> Optional[Dict]:
        """Пошук документа за ID (асинхронна версія)"""
        if not self.async_mode:
            raise RuntimeError("Використовуйте find_by_id() для синхронного режиму")

        try:
            object_id = self.convert_id_to_object(doc_id)
            doc = await self.collection.find_one({"_id": object_id})
            return self.normalize_document(doc)
        except Exception as e:
            self.logger.error(f"Помилка пошуку документа за ID {doc_id}: {str(e)}")
            raise

    def find_by_field(self, field: str, value: Any) -> Optional[Dict]:
        """Пошук документа за полем (синхронна версія)"""
        if self.async_mode:
            raise RuntimeError("Використовуйте find_by_field_async() для асинхронного режиму")

        try:
            doc = self.collection.find_one({field: value})
            return self.normalize_document(doc)
        except Exception as e:
            self.logger.error(f"Помилка пошуку документа за {field}={value}: {str(e)}")
            raise

    async def find_by_field_async(self, field: str, value: Any) -> Optional[Dict]:
        """Пошук документа за полем (асинхронна версія)"""
        if not self.async_mode:
            raise RuntimeError("Використовуйте find_by_field() для синхронного режиму")

        try:
            doc = await self.collection.find_one({field: value})
            return self.normalize_document(doc)
        except Exception as e:
            self.logger.error(f"Помилка пошуку документа за {field}={value}: {str(e)}")
            raise

    def find_all(self, filter_query: Optional[Dict] = None, limit: Optional[int] = None) -> List[Dict]:
        """Отримання всіх документів з фільтрацією (синхронна версія)"""
        if self.async_mode:
            raise RuntimeError("Використовуйте find_all_async() для асинхронного режиму")

        try:
            query = filter_query or {}
            cursor = self.collection.find(query)
            if limit:
                cursor = cursor.limit(limit)
            docs = list(cursor)

            self.logger.debug(f"Знайдено {len(docs)} документів в {self.collection_name}")
            return self.normalize_documents(docs)
        except Exception as e:
            self.logger.error(f"Помилка отримання документів з {self.collection_name}: {str(e)}")
            raise

    async def find_all_async(self, filter_query: Optional[Dict] = None, limit: Optional[int] = None) -> List[Dict]:
        """Отримання всіх документів з фільтрацією (асинхронна версія)"""
        if not self.async_mode:
            raise RuntimeError("Використовуйте find_all() для синхронного режиму")

        try:
            query = filter_query or {}
            cursor = self.collection.find(query)
            if limit:
                cursor = cursor.limit(limit)
            docs = await cursor.to_list(length=None)

            self.logger.debug(f"Знайдено {len(docs)} документів в {self.collection_name}")
            return self.normalize_documents(docs)
        except Exception as e:
            self.logger.error(f"Помилка отримання документів з {self.collection_name}: {str(e)}")
            raise

    def delete_by_id(self, doc_id: str) -> bool:
        """Видалення документа за ID (синхронна версія)"""
        if self.async_mode:
            raise RuntimeError("Використовуйте delete_by_id_async() для асинхронного режиму")

        try:
            object_id = self.convert_id_to_object(doc_id)
            result = self.collection.delete_one({"_id": object_id})
            success = result.deleted_count > 0
            if success:
                self.logger.info(f"Документ видалено з {self.collection_name}: {doc_id}")
            return success
        except Exception as e:
            self.logger.error(f"Помилка видалення документа {doc_id}: {str(e)}")
            raise

    async def delete_by_id_async(self, doc_id: str) -> bool:
        """Видалення документа за ID (асинхронна версія)"""
        if not self.async_mode:
            raise RuntimeError("Використовуйте delete_by_id() для синхронного режиму")

        try:
            object_id = self.convert_id_to_object(doc_id)
            result = await self.collection.delete_one({"_id": object_id})
            success = result.deleted_count > 0
            if success:
                self.logger.info(f"Документ видалено з {self.collection_name}: {doc_id}")
            return success
        except Exception as e:
            self.logger.error(f"Помилка видалення документа {doc_id}: {str(e)}")
            raise

    def soft_delete_by_id(self, doc_id: str) -> bool:
        """М'яке видалення документа (синхронна версія)"""
        if self.async_mode:
            raise RuntimeError("Використовуйте soft_delete_by_id_async() для асинхронного режиму")

        try:
            object_id = self.convert_id_to_object(doc_id)
            update_data = {
                "is_active": False,
                "updated_at": datetime.now().isoformat(sep=" ", timespec="seconds")
            }
            result = self.collection.update_one({"_id": object_id}, {"$set": update_data})
            success = result.modified_count > 0
            if success:
                self.logger.info(f"Документ деактивовано в {self.collection_name}: {doc_id}")
            return success
        except Exception as e:
            self.logger.error(f"Помилка деактивації документа {doc_id}: {str(e)}")
            raise

    async def soft_delete_by_id_async(self, doc_id: str) -> bool:
        """М'яке видалення документа (асинхронна версія)"""
        if not self.async_mode:
            raise RuntimeError("Використовуйте soft_delete_by_id() для синхронного режиму")

        try:
            object_id = self.convert_id_to_object(doc_id)
            update_data = {
                "is_active": False,
                "updated_at": datetime.now().isoformat(sep=" ", timespec="seconds")
            }
            result = await self.collection.update_one({"_id": object_id}, {"$set": update_data})
            success = result.modified_count > 0
            if success:
                self.logger.info(f"Документ деактивовано в {self.collection_name}: {doc_id}")
            return success
        except Exception as e:
            self.logger.error(f"Помилка деактивації документа {doc_id}: {str(e)}")
            raise