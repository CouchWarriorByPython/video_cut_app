import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler


class LoggerConfig:
    """Централізована конфігурація логера з підтримкою різних середовищ"""

    def __init__(
            self,
            name: str = "annotator",
            level: str = "INFO",
            log_dir: Optional[Path] = None,
            max_bytes: int = 10 * 1024 * 1024,  # 10MB
            backup_count: int = 5,
            console_output: bool = True,
            is_production: bool = False
    ):
        self.name = name
        self.level = getattr(logging, level.upper())
        self.log_dir = log_dir or Path("logs")
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.console_output = console_output
        self.is_production = is_production

        # Створюємо директорію для логів
        self.log_dir.mkdir(exist_ok=True)

    def setup_logger(self) -> logging.Logger:
        """Налаштовує та повертає логер"""
        logger = logging.getLogger(self.name)

        # Запобігаємо дублюванню обробників
        if logger.handlers:
            return logger

        logger.setLevel(self.level)

        # Формат логів - детальний для розробки, стислий для продакшену
        if self.is_production:
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
            )

        # Файловий обробник з ротацією
        file_handler = RotatingFileHandler(
            self.log_dir / f"{self.name}.log",
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
            # В продакшені консоль тільки WARNING і вище
            console_level = logging.WARNING if self.is_production else self.level
            console_handler.setLevel(console_level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Отримує логер для модуля"""
    from configs import Settings

    logger_name = name or "annotator"

    # Якщо логер вже існує, повертаємо його
    if logger_name in logging.Logger.manager.loggerDict:
        return logging.getLogger(logger_name)

    # Визначаємо чи це продакшен
    is_production = not Settings.is_local_environment()

    # В продакшені використовуємо WARNING, в розробці - DEBUG/INFO
    log_level = "WARNING" if is_production else Settings.log_level

    # Створюємо новий логер
    config = LoggerConfig(
        name=logger_name,
        level=log_level,
        is_production=is_production,
        console_output=True
    )
    return config.setup_logger()


# Глобальний логер для зворотної сумісності
logger = get_logger()