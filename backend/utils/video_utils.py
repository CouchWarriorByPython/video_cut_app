import os
import subprocess
import json
from typing import Optional, Dict, Any
from backend.utils.logger import get_logger
from backend.config.settings import get_settings

settings = get_settings()
logger = get_logger(__name__, "utils.log")


def get_video_info(video_path: str) -> Optional[Dict[str, Any]]:
    """Отримує детальну інформацію про відео"""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        probe_data = json.loads(result.stdout)

        video_stream = None
        audio_stream = None

        for stream in probe_data.get("streams", []):
            if stream.get("codec_type") == "video" and not video_stream:
                video_stream = stream
            elif stream.get("codec_type") == "audio" and not audio_stream:
                audio_stream = stream

        format_info = probe_data.get("format", {})

        return {
            "container": format_info.get("format_name", "").split(",")[0],
            "duration": float(format_info.get("duration", 0)),
            "size": int(format_info.get("size", 0)),
            "bitrate": int(format_info.get("bit_rate", 0)),
            "video_codec": video_stream.get("codec_name", "") if video_stream else "",
            "video_profile": video_stream.get("profile", "") if video_stream else "",
            "width": int(video_stream.get("width", 0)) if video_stream else 0,
            "height": int(video_stream.get("height", 0)) if video_stream else 0,
            "fps": eval(video_stream.get("r_frame_rate", "0/1")) if video_stream else 0,
            "audio_codec": audio_stream.get("codec_name", "") if audio_stream else "",
            "audio_bitrate": int(audio_stream.get("bit_rate", 0)) if audio_stream else 0,
            "audio_channels": int(audio_stream.get("channels", 0)) if audio_stream else 0,
        }

    except Exception as e:
        logger.error(f"Помилка отримання інформації про відео {video_path}: {str(e)}")
        return None


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
            "ffmpeg", "-y",
            "-ss", start_time,
            "-to", end_time,
            "-i", source_path,
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-loglevel", settings.ffmpeg_log_level,
            output_path
        ]

        logger.debug(f"Trim command: {' '.join(command)}")

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            if file_size > 0:
                logger.info(f"Кліп успішно створено: {output_path} (розмір: {file_size} bytes)")
                return True

        logger.error(f"Помилка нарізки відео. FFmpeg stderr: {result.stderr}")
        return False

    except Exception as e:
        logger.error(f"Помилка при нарізці відео: {str(e)}")
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

    if uav_type:
        filename_parts.append(uav_type)
    if where:
        filename_parts.append(where)
    if when:
        filename_parts.append(when)

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
    local_videos_dir = os.path.join(settings.temp_folder, "source_videos")
    return os.path.join(local_videos_dir, filename)