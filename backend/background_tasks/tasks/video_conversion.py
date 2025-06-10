import os
import subprocess
import json
from typing import Dict, Any, Optional

from backend.background_tasks.app import app
from backend.database.repositories.source_video import SyncSourceVideoRepository
from backend.utils.video_utils import get_local_video_path, cleanup_file
from backend.config.settings import Settings
from backend.utils.logger import get_logger

logger = get_logger(__name__, "tasks.log")


@app.task(name="convert_video_for_web", bind=True)
def convert_video_for_web(self, azure_link: str) -> Dict[str, Any]:
    """Конвертує відео в web-сумісний формат з оптимізацією"""
    logger.info(f"Початок конвертації відео: {azure_link}")

    repo = SyncSourceVideoRepository()

    try:
        annotation = repo.get_annotation(azure_link)
        if not annotation:
            return {"status": "error", "message": "Відео не знайдено в БД"}

        annotation["status"] = "converting"
        repo.save_annotation(annotation)

        filename = annotation["filename"]
        original_path = get_local_video_path(filename)

        if not os.path.exists(original_path):
            return {"status": "error", "message": "Локальний файл не знайдено"}

        video_info = get_video_info(original_path)
        if not video_info:
            return {"status": "error", "message": "Не вдалося отримати інформацію про відео"}

        if Settings.skip_conversion_for_compatible and is_web_compatible(video_info):
            logger.info(f"Відео вже web-сумісне, пропускаємо конвертацію: {azure_link}")
            annotation["status"] = "ready"
            repo.save_annotation(annotation)
            return {"status": "success", "message": "Відео вже web-сумісне"}

        name_without_ext = os.path.splitext(filename)[0]
        converted_filename = f"{name_without_ext}_web.mp4"
        converted_path = get_local_video_path(converted_filename)

        success = convert_to_web_format_optimized(original_path, converted_path, video_info)

        if success:
            cleanup_file(original_path)
            os.rename(converted_path, original_path)

            annotation["status"] = "ready"
            repo.save_annotation(annotation)

            logger.info(f"Відео успішно конвертовано: {azure_link}")
            return {"status": "success", "message": "Відео конвертовано успішно"}
        else:
            annotation["status"] = "conversion_failed"
            repo.save_annotation(annotation)
            return {"status": "error", "message": "Помилка конвертації відео"}

    except Exception as e:
        logger.error(f"Помилка при конвертації відео {azure_link}: {str(e)}")
        try:
            annotation = repo.get_annotation(azure_link)
            if annotation:
                annotation["status"] = "conversion_failed"
                repo.save_annotation(annotation)
        except:
            pass
        return {"status": "error", "message": str(e)}


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
            "video_codec": video_stream.get("codec_name", "") if video_stream else "",
            "video_profile": video_stream.get("profile", "") if video_stream else "",
            "audio_codec": audio_stream.get("codec_name", "") if audio_stream else "",
        }

    except Exception as e:
        logger.error(f"Помилка отримання інформації про відео {video_path}: {str(e)}")
        return None


def is_web_compatible(video_info: Dict[str, Any]) -> bool:
    """Перевіряє чи відео вже web-сумісне"""
    video_codec = video_info.get("video_codec", "").lower()
    audio_codec = video_info.get("audio_codec", "").lower()
    container = video_info.get("container", "").lower()

    is_h264 = "h264" in video_codec or "avc" in video_codec
    is_aac_audio = "aac" in audio_codec
    is_mp4_container = container in ["mp4", "mov"]

    return is_h264 and is_aac_audio and is_mp4_container


def get_hardware_encoder() -> Optional[str]:
    """Визначає доступний апаратний енкодер (тільки для production)"""
    if not Settings.enable_hardware_acceleration:
        logger.info("Апаратне прискорення відключено в налаштуваннях")
        return None

    if Settings.get_environment_name().lower() in ("development", "dev"):
        logger.info("Development режим - використовуємо CPU")
        return None

    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("Знайдено NVIDIA GPU")
            return "h264_nvenc"
    except FileNotFoundError:
        pass

    try:
        result = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
        if "h264_qsv" in result.stdout:
            logger.info("Знайдено Intel Quick Sync")
            return "h264_qsv"
    except:
        pass

    try:
        result = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
        if "h264_vaapi" in result.stdout:
            logger.info("Знайдено VAAPI")
            return "h264_vaapi"
    except:
        pass

    logger.info("Апаратні енкодери не знайдено")
    return None


def convert_to_web_format_optimized(input_path: str, output_path: str, video_info: Dict[str, Any]) -> bool:
    """Оптимізована конвертація з автовибором параметрів"""
    try:
        command = ["ffmpeg", "-y", "-i", input_path]

        hw_encoder = get_hardware_encoder()

        if hw_encoder:
            logger.info(f"Використовуємо апаратний енкодер: {hw_encoder}")

            if hw_encoder == "h264_nvenc":
                command.extend([
                    "-c:v", "h264_nvenc",
                    "-preset", "p4",
                    "-cq", str(Settings.video_conversion_crf),
                    "-profile:v", "high",
                ])
            elif hw_encoder == "h264_qsv":
                command.extend([
                    "-c:v", "h264_qsv",
                    "-preset", Settings.video_conversion_preset,
                    "-global_quality", str(Settings.video_conversion_crf),
                    "-profile:v", "high",
                ])
            elif hw_encoder == "h264_vaapi":
                command.extend([
                    "-c:v", "h264_vaapi",
                    "-qp", str(Settings.video_conversion_crf),
                    "-profile:v", "100",
                ])
        else:
            logger.info("Використовуємо CPU кодування")

            file_size_mb = os.path.getsize(input_path) / (1024 * 1024)

            if file_size_mb > 500:
                preset = "veryfast"
                crf = str(Settings.video_conversion_crf + 2)
            elif file_size_mb > 100:
                preset = Settings.video_conversion_preset
                crf = str(Settings.video_conversion_crf)
            else:
                preset = Settings.video_conversion_preset
                crf = str(Settings.video_conversion_crf)

            command.extend([
                "-c:v", "libx264",
                "-preset", preset,
                "-crf", crf,
                "-profile:v", "high",
                "-level", "4.0",
            ])

        audio_codec = video_info.get("audio_codec", "").lower()
        if "aac" in audio_codec:
            command.extend(["-c:a", "copy"])
        else:
            command.extend([
                "-c:a", "aac",
                "-b:a", "128k",
            ])

        command.extend([
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            "-f", "mp4",
            "-loglevel", Settings.ffmpeg_log_level,
            output_path
        ])

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