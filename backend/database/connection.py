from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
from backend.config.settings import Settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseConnection:
    """Менеджер підключень до MongoDB"""

    _sync_client = None
    _async_client = None

    @classmethod
    def get_sync_client(cls) -> MongoClient:
        """Отримує синхронний клієнт MongoDB"""
        if cls._sync_client is None:
            try:
                cls._sync_client = MongoClient(Settings.mongo_uri)
                logger.debug(f"Створено синхронне підключення до MongoDB: {Settings.mongo_db_name}")
            except Exception as e:
                logger.error(f"Помилка підключення до MongoDB: {str(e)}")
                raise
        return cls._sync_client

    @classmethod
    def get_async_client(cls) -> AsyncIOMotorClient:
        """Отримує асинхронний клієнт MongoDB"""
        if cls._async_client is None:
            try:
                cls._async_client = AsyncIOMotorClient(Settings.mongo_uri)
                logger.debug(f"Створено асинхронне підключення до MongoDB: {Settings.mongo_db_name}")
            except Exception as e:
                logger.error(f"Помилка асинхронного підключення до MongoDB: {str(e)}")
                raise
        return cls._async_client

    @classmethod
    def get_sync_database(cls):
        """Отримує синхронну базу даних"""
        client = cls.get_sync_client()
        return client[Settings.mongo_db_name]

    @classmethod
    def get_async_database(cls):
        """Отримує асинхронну базу даних"""
        client = cls.get_async_client()
        return client[Settings.mongo_db_name]

    @classmethod
    def close_connections(cls) -> None:
        """Закриває всі підключення"""
        if cls._sync_client:
            cls._sync_client.close()
            cls._sync_client = None

        if cls._async_client:
            cls._async_client.close()
            cls._async_client = None

        logger.debug("Всі підключення до MongoDB закрито")