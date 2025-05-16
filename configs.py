import os
from typing import Optional, ClassVar
from dotenv import load_dotenv


class Settings:
    """
    Клас з налаштуваннями програми.
    Всі параметри конфігурації зберігаються як атрибути класу.
    """
    mongo_uri: ClassVar[str] = "mongodb://anot_user:anot_pass@localhost:27017/annotator"
    mongo_db_name: ClassVar[str] = "annotator"

    @classmethod
    def load_from_env(cls) -> None:
        """Оновлення налаштувань із .env файлу та змінних середовища"""
        load_dotenv()

        # MongoDB - отримуємо значення з env
        mongo_uri: Optional[str] = os.getenv("MONGO_URI")
        if mongo_uri:
            cls.mongo_uri = mongo_uri

        mongo_db: Optional[str] = os.getenv("MONGO_DB")
        if mongo_db:
            cls.mongo_db_name = mongo_db


Settings.load_from_env()
