import os
import subprocess
from typing import Optional, Dict, Any
from backend.utils.logger import get_logger
from backend.config.settings import Settings

logger = get_logger(__name__)


def get_video_fps(video_path: str) -> Optional[float]:
    """Визначає FPS відео за допомогою ffprobe"""
    cmd = [
        "ffprobe",
        "-v", "0",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate",
        "-of", "csv=s=x:p=0",
        video_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        r_frame_rate = result.stdout.strip()

        if "/" in r_frame_rate:
            num, den = r_frame_rate.split("/")
            if float(den) == 0:
                logger.error(f"Помилка отримання FPS для {video_path}: denominator == 0")
                return None
            fps = float(num) / float(den)
        else:
            fps = float(r_frame_rate)

        logger.debug(f"FPS для {video_path}: {fps:.2f}")
        return fps

    except Exception as e:
        logger.error(f"Помилка визначення FPS для {video_path}: {str(e)}")
        return None


def trim_video_clip(source_path: str, output_path: str, start_time: str, end_time: str) -> bool:
    """Нарізає відео фрагмент за допомогою FFmpeg"""
    try:
        command = [
            "ffmpeg",
            "-y",
            "-ss", start_time,
            "-to", end_time,
            "-i", source_path,
            "-c", "copy",
            "-loglevel", Settings.ffmpeg_log_level,
            output_path,
        ]

        logger.debug(f"Запуск команди: {' '.join(command)}")

        result = subprocess.run(command, capture_output=True, text=True)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.debug(f"Кліп успішно створено: {output_path}")
            return True
        else:
            logger.error(f"Помилка при створенні кліпу: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Помилка при нарізці відео: {e}")
        return False


def format_filename(
        metadata: Dict[str, Any],
        original_filename: str,
        project: str,
        clip_id: int,
        where: str = "",
        when: str = ""
) -> str:
    """Форматує ім'я файлу на основі метаданих та атрибутів відео"""
    video_base_name = os.path.splitext(os.path.basename(original_filename))[0]
    uav_type = metadata.get("uav_type", "").strip()

    filename_parts = []

    # Додаємо тільки непусті частини
    if uav_type:
        filename_parts.append(uav_type)
    if where:
        filename_parts.append(where)
    if when:
        filename_parts.append(when)

    # Базова частина завжди додається
    filename_parts.append(f"{video_base_name}_{project}_{clip_id}")

    return "_".join(filename_parts) + ".mp4"


def cleanup_file(file_path: str) -> None:
    """Видаляє файл"""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
            logger.debug(f"Видалено файл: {file_path}")
    except Exception as e:
        logger.error(f"Помилка видалення файлу {file_path}: {str(e)}")


def get_local_video_path(filename: str) -> str:
    """Конструює локальний шлях для відео файлу"""
    local_videos_dir = os.path.join(Settings.temp_folder, "source_videos")
    return os.path.join(local_videos_dir, filename)