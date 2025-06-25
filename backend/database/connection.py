import mongoengine
from backend.config.settings import get_settings
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__, "database.log")


class DatabaseConnection:
    _connected = False
    _connection = None

    @classmethod
    def connect(cls) -> None:
        if cls._connected:
            return

        try:
            cls._connection = mongoengine.connect(
                db=settings.mongo_db,
                host=settings.mongo_uri,
                alias='default',
                connect=True,
                serverSelectionTimeoutMS=5000
            )
            cls._connected = True
            logger.info(f"Підключено до MongoDB: {settings.mongo_db}")
        except Exception as e:
            logger.error(f"Помилка підключення до MongoDB: {str(e)}")
            raise

    @classmethod
    def disconnect(cls) -> None:
        if cls._connected:
            mongoengine.disconnect()
            cls._connected = False
            cls._connection = None
            logger.info("Відключено від MongoDB")

    @classmethod
    def is_connected(cls) -> bool:
        return cls._connected