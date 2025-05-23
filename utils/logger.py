import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler


class LoggerConfig:
    """Централізована конфігурація логера для всього проєкту"""

    def __init__(
            self,
            name: str = "annotator",
            level: str = "INFO",
            log_dir: Optional[Path] = None,
            max_bytes: int = 10 * 1024 * 1024,  # 10MB
            backup_count: int = 5,
            console_output: bool = True
    ):
        self.name = name
        self.level = getattr(logging, level.upper())
        self.log_dir = log_dir or Path("logs")
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.console_output = console_output

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
            console_handler.setLevel(self.level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Отримує логер для модуля"""
    logger_name = name or "annotator"

    # Якщо логер вже існує, повертаємо його
    if logger_name in logging.Logger.manager.loggerDict:
        return logging.getLogger(logger_name)

    # Створюємо новий логер
    config = LoggerConfig(name=logger_name)
    return config.setup_logger()


# Глобальний логер для зворотної сумісності
logger = get_logger()