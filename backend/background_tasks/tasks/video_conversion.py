import os
import subprocess
from typing import Dict, Any

from backend.background_tasks.app import app
from backend.database.repositories.source_video import SyncSourceVideoRepository
from backend.utils.video_utils import get_local_video_path, cleanup_file
from backend.config.settings import Settings
from backend.utils.logger import get_logger

logger = get_logger(__name__, "tasks.log")


@app.task(name="convert_video_for_web", bind=True)
def convert_video_for_web(self, azure_link: str) -> Dict[str, Any]:
    """Конвертує відео в web-сумісний формат"""
    logger.info(f"Початок конвертації відео: {azure_link}")

    repo = SyncSourceVideoRepository()

    try:
        annotation = repo.get_annotation(azure_link)
        if not annotation:
            return {
                "status": "error",
                "message": "Відео не знайдено в БД"
            }

        # Оновлюємо статус на "converting"
        annotation["status"] = "converting"
        repo.save_annotation(annotation)

        filename = annotation["filename"]
        original_path = get_local_video_path(filename)

        if not os.path.exists(original_path):
            return {
                "status": "error",
                "message": "Локальний файл не знайдено"
            }

        # Створюємо шлях для конвертованого файлу
        name_without_ext = os.path.splitext(filename)[0]
        converted_filename = f"{name_without_ext}_web.mp4"
        converted_path = get_local_video_path(converted_filename)

        # Конвертуємо відео в web-сумісний формат
        success = convert_to_web_format(original_path, converted_path)

        if success:
            # Видаляємо оригінал, замінюємо на конвертований
            cleanup_file(original_path)
            os.rename(converted_path, original_path)

            # Оновлюємо статус на "ready"
            annotation["status"] = "ready"
            repo.save_annotation(annotation)

            logger.info(f"Відео успішно конвертовано: {azure_link}")
            return {
                "status": "success",
                "message": "Відео конвертовано успішно"
            }
        else:
            # Оновлюємо статус на "conversion_failed"
            annotation["status"] = "conversion_failed"
            repo.save_annotation(annotation)

            return {
                "status": "error",
                "message": "Помилка конвертації відео"
            }

    except Exception as e:
        logger.error(f"Помилка при конвертації відео {azure_link}: {str(e)}")

        # Оновлюємо статус на "conversion_failed"
        try:
            annotation = repo.get_annotation(azure_link)
            if annotation:
                annotation["status"] = "conversion_failed"
                repo.save_annotation(annotation)
        except:
            pass

        return {
            "status": "error",
            "message": str(e)
        }


def convert_to_web_format(input_path: str, output_path: str) -> bool:
    """Конвертує відео в web-сумісний формат за допомогою FFmpeg"""
    try:
        command = [
            "ffmpeg",
            "-y",  # Перезаписати файл
            "-i", input_path,
            "-c:v", "libx264",  # H.264 відео кодек
            "-preset", "medium",  # Баланс між швидкістю та якістю
            "-crf", "23",  # Якість відео (18-28, менше = краща якість)
            "-c:a", "aac",  # AAC аудіо кодек
            "-b:a", "128k",  # Бітрейт аудіо
            "-movflags", "+faststart",  # Оптимізація для веб
            "-pix_fmt", "yuv420p",  # Сумісність з більшістю браузерів
            "-profile:v", "baseline",  # Максимальна сумісність
            "-level", "3.0",
            "-f", "mp4",  # MP4 контейнер
            "-loglevel", Settings.ffmpeg_log_level,
            output_path
        ]

        logger.debug(f"Команда конвертації: {' '.join(command)}")

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.debug(f"Відео успішно конвертовано: {output_path}")
            return True
        else:
            logger.error(f"Помилка конвертації FFmpeg: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Помилка при конвертації відео: {str(e)}")
        return False