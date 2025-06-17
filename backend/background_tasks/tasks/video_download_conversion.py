import os
import subprocess
import json
from typing import Dict, Any, Optional
from datetime import datetime

from backend.background_tasks.app import app
from backend.database import create_repository
from backend.services.azure_service import AzureService
from backend.utils.video_utils import get_local_video_path, cleanup_file
from backend.config.settings import Settings
from backend.utils.logger import get_logger

logger = get_logger(__name__, "tasks.log")


@app.task(name="download_and_convert_video", bind=True)
def download_and_convert_video(self, azure_link: str) -> Dict[str, Any]:
    """Завантажує відео з Azure Storage та конвертує його для веб-перегляду"""
    logger.info(f"Початок завантаження та конвертації відео: {azure_link}")

    repo = create_repository("source_videos", async_mode=False)
    azure_service = AzureService()

    def update_download_progress(downloaded_bytes: int, total_bytes: int) -> None:
        """Оновлює прогрес завантаження (0-50%)"""
        if total_bytes > 0:
            download_percent = (downloaded_bytes / total_bytes) * 50
            self.update_state(
                state='PROGRESS',
                meta={
                    'progress': min(int(download_percent), 50),
                    'stage': 'downloading',
                    'message': f'Завантажено {downloaded_bytes // (1024 * 1024)} MB з {total_bytes // (1024 * 1024)} MB'
                }
            )

    def update_conversion_progress(progress_percent: float) -> None:
        """Оновлює прогрес конвертації (60-95%)"""
        conversion_progress = 60 + (progress_percent * 0.35)
        self.update_state(
            state='PROGRESS',
            meta={
                'progress': min(int(conversion_progress), 95),
                'stage': 'converting',
                'message': f'Конвертація: {progress_percent:.1f}%'
            }
        )

    try:
        # Отримуємо анотацію з БД
        annotation = repo.find_by_field("azure_link", azure_link)
        if not annotation:
            self.update_state(
                state='FAILURE',
                meta={'error': 'Відео не знайдено в БД', 'progress': 0}
            )
            return {"status": "error", "message": "Відео не знайдено в БД"}

        filename = annotation["filename"]
        local_path = get_local_video_path(filename)

        # Оновлюємо статус на downloading
        repo.update_by_field("azure_link", azure_link, {"status": "downloading"})

        # Етап 1: Завантаження з Azure Storage (0-50%)
        self.update_state(
            state='PROGRESS',
            meta={
                'progress': 5,
                'stage': 'downloading',
                'message': 'Початок завантаження з Azure Storage...'
            }
        )

        download_result = azure_service.download_video_to_local_with_progress(
            azure_link, local_path, update_download_progress
        )

        if not download_result["success"]:
            repo.update_by_field("azure_link", azure_link, {"status": "download_failed"})
            self.update_state(
                state='FAILURE',
                meta={
                    'error': f'Помилка завантаження: {download_result["error"]}',
                    'progress': 50
                }
            )
            return {
                "status": "error",
                "message": f'Помилка завантаження: {download_result["error"]}'
            }

        # Етап 2: Аналіз відео (50-60%)
        self.update_state(
            state='PROGRESS',
            meta={
                'progress': 55,
                'stage': 'analyzing',
                'message': 'Аналіз характеристик відео...'
            }
        )

        video_info = get_video_info(local_path)
        if not video_info:
            repo.update_by_field("azure_link", azure_link, {"status": "analysis_failed"})

            cleanup_file(local_path)
            self.update_state(
                state='FAILURE',
                meta={
                    'error': 'Не вдалося проаналізувати відео',
                    'progress': 60
                }
            )
            return {"status": "error", "message": "Не вдалося проаналізувати відео"}

        # Етап 3: Конвертація (60-95%)
        repo.update_by_field("azure_link", azure_link, {"status": "converting"})

        self.update_state(
            state='PROGRESS',
            meta={
                'progress': 65,
                'stage': 'converting',
                'message': 'Конвертація відео для веб-перегляду...'
            }
        )

        if Settings.skip_conversion_for_compatible and is_web_compatible(video_info):
            logger.info(f"Відео вже web-сумісне, пропускаємо конвертацію: {azure_link}")
            self.update_state(
                state='PROGRESS',
                meta={
                    'progress': 95,
                    'stage': 'converting',
                    'message': 'Відео вже web-сумісне, пропускаємо конвертацію...'
                }
            )
        else:
            name_without_ext = os.path.splitext(filename)[0]
            converted_filename = f"{name_without_ext}_web.mp4"
            converted_path = get_local_video_path(converted_filename)

            success = convert_to_web_format_with_progress(
                local_path, converted_path, video_info, update_conversion_progress
            )

            if not success:
                repo.update_by_field("azure_link", azure_link, {"status": "conversion_failed"})

                cleanup_file(local_path)
                self.update_state(
                    state='FAILURE',
                    meta={
                        'error': 'Помилка конвертації відео',
                        'progress': 90
                    }
                )
                return {"status": "error", "message": "Помилка конвертації відео"}

            # Заміняємо оригінальний файл конвертованим
            cleanup_file(local_path)
            os.rename(converted_path, local_path)

        # Етап 4: Фіналізація (95-100%)
        self.update_state(
            state='PROGRESS',
            meta={
                'progress': 98,
                'stage': 'finalizing',
                'message': 'Завершення обробки...'
            }
        )

        repo.update_by_field("azure_link", azure_link, {
            "status": "ready", "updated_at": datetime.now().isoformat(sep=" ", timespec="seconds")
        })

        self.update_state(
            state='SUCCESS',
            meta={
                'progress': 100,
                'stage': 'completed',
                'message': 'Відео готове до анотування'
            }
        )

        logger.info(f"Відео успішно завантажено та сконвертовано: {azure_link}")
        return {
            "status": "success",
            "message": "Відео готове до анотування",
            "filename": filename
        }

    except Exception as e:
        logger.error(f"Помилка при обробці відео {azure_link}: {str(e)}")
        try:
            annotation = repo.find_by_field("azure_link", azure_link)
            if annotation:
                repo.update_by_field("azure_link", azure_link, {"status": "processing_failed"})

            # Очищаємо файл при помилці
            if 'local_path' in locals():
                cleanup_file(local_path)
        except:
            pass

        self.update_state(
            state='FAILURE',
            meta={
                'error': str(e),
                'progress': self.request.get('progress', 0)
            }
        )
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


def convert_to_web_format_with_progress(
        input_path: str,
        output_path: str,
        video_info: Dict[str, Any],
        progress_callback
) -> bool:
    """Конвертує відео з відстеженням прогресу"""
    try:
        # Отримуємо тривалість відео для розрахунку прогресу
        duration = video_info.get("duration", 0)

        command = ["ffmpeg", "-y", "-i", input_path]

        # Додаємо параметри кодування (спрощена версія з попереднього коду)
        command.extend([
            "-c:v", "libx264",
            "-preset", Settings.video_conversion_preset,
            "-crf", str(Settings.video_conversion_crf),
            "-profile:v", "high",
            "-level", "4.0",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            "-f", "mp4",
            "-progress", "pipe:1",
            "-loglevel", "error",
            output_path
        ])

        logger.debug(f"Команда конвертації: {' '.join(command)}")

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Відстежуємо прогрес через FFmpeg progress output
        while True:
            line = process.stdout.readline()
            if not line:
                break

            if line.startswith("out_time_ms="):
                try:
                    time_ms = int(line.split("=")[1])
                    time_seconds = time_ms / 1000000
                    if duration > 0:
                        progress_percent = min((time_seconds / duration) * 100, 100)
                        progress_callback(progress_percent)
                except (ValueError, IndexError):
                    continue

        process.wait()

        if process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            progress_callback(100)
            logger.debug(f"Відео успішно конвертовано: {output_path}")
            return True
        else:
            stderr_output = process.stderr.read() if process.stderr else ""
            logger.error(f"Помилка конвертації FFmpeg: {stderr_output}")
            return False

    except Exception as e:
        logger.error(f"Помилка при конвертації відео: {str(e)}")
        return False