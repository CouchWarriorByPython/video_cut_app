import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler

from backend.config.settings import Settings


class LoggerConfig:
    """Централізована конфігурація логера з підтримкою різних середовищ"""

    def __init__(
            self,
            name: str = "annotator",
            level: str = "INFO",
            log_dir: Path = Path(Settings.logs_folder),
            max_bytes: int = Settings.log_max_bytes,
            backup_count: int = Settings.log_backup_count,
            console_output: bool = True,
            is_production: bool = False,
            log_file: Optional[str] = None  # Додаємо можливість явно вказати файл
    ):
        self.name = name
        self.level = getattr(logging, level.upper())
        self.log_dir = log_dir or Path("logs")
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.console_output = console_output
        self.is_production = is_production
        self.log_file = log_file or "app.log"

        # Створюємо директорію для логів
        self.log_dir.mkdir(exist_ok=True)

    def setup_logger(self) -> logging.Logger:
        """Налаштовує та повертає логер"""
        logger = logging.getLogger(self.name)

        # Запобігаємо дублюванню обробників
        if logger.handlers:
            return logger

        logger.setLevel(self.level)

        # Формат логів
        if self.is_production:
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s'
            )

        # Файловий обробник з ротацією
        file_handler = RotatingFileHandler(
            self.log_dir / self.log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(self.level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Консольний обробник
        if self.console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_level = logging.WARNING if self.is_production else self.level
            console_handler.setLevel(console_level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        # Додатковий обробник для помилок
        if self.level <= logging.ERROR:
            error_handler = RotatingFileHandler(
                self.log_dir / "errors.log",
                maxBytes=self.max_bytes,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            logger.addHandler(error_handler)

        return logger


def get_logger(name: Optional[str] = None, log_file: Optional[str] = None) -> logging.Logger:
    """
    Отримує логер для модуля

    Args:
        name: Ім'я логера (зазвичай __name__)
        log_file: Файл для логування (api.log, tasks.log, тощо)
    """
    from backend.config.settings import Settings

    logger_name = name or "annotator"

    # Якщо логер вже існує, повертаємо його
    existing_logger = logging.getLogger(logger_name)
    if existing_logger.handlers:
        return existing_logger

    # Визначаємо чи це продакшен
    is_production = not Settings.is_local_environment()

    # В продакшені використовуємо WARNING, в розробці - DEBUG/INFO
    log_level = "WARNING" if is_production else Settings.log_level

    # Створюємо новий логер
    config = LoggerConfig(
        name=logger_name,
        level=log_level,
        is_production=is_production,
        console_output=True,
        log_file=log_file
    )
    return config.setup_logger()
