import os
import subprocess
import json
from typing import Dict, Any, Optional
from datetime import datetime, UTC

from backend.background_tasks.app import app
from backend.database import create_repository
from backend.services.azure_service import AzureService
from backend.models.database import AzureFilePath, VideoStatus
from backend.utils.azure_path_utils import extract_filename_from_azure_path
from backend.utils.video_utils import get_local_video_path, cleanup_file
from backend.config.settings import Settings
from backend.utils.logger import get_logger

logger = get_logger(__name__, "tasks.log")


@app.task(name="download_and_convert_video", bind=True)
def download_and_convert_video(self, azure_path_dict: Dict[str, str]) -> Dict[str, Any]:
    """Download video from Azure Storage and convert it for web viewing"""
    azure_path = AzureFilePath(**azure_path_dict)
    logger.info(f"Starting download and conversion: {azure_path.blob_path}")

    repo = create_repository("source_videos", async_mode=False)
    azure_service = AzureService()

    def update_download_progress(downloaded_bytes: int, total_bytes: int) -> None:
        """Update download progress (5-50%)"""
        if total_bytes > 0:
            download_percent = 5 + (downloaded_bytes / total_bytes) * 45
            self.update_state(
                state='PROGRESS',
                meta={
                    'progress': min(int(download_percent), 50),
                    'stage': 'downloading',
                    'message': f'Downloaded {downloaded_bytes // (1024 * 1024)} MB of {total_bytes // (1024 * 1024)} MB'
                }
            )

    def update_conversion_progress(progress_percent: float) -> None:
        """Update conversion progress (60-95%)"""
        conversion_progress = 60 + (progress_percent * 0.35)
        self.update_state(
            state='PROGRESS',
            meta={
                'progress': min(int(conversion_progress), 95),
                'stage': 'converting',
                'message': f'Conversion: {progress_percent:.1f}%'
            }
        )

    try:
        annotation = repo.find_by_field("azure_file_path.blob_path", azure_path.blob_path)
        if not annotation:
            self.update_state(
                state='FAILURE',
                meta={'error': 'Video not found in DB', 'progress': 0}
            )
            return {"status": "error", "message": "Video not found in DB"}

        filename = extract_filename_from_azure_path(azure_path)
        local_path = get_local_video_path(filename)

        repo.update_by_field("azure_file_path.blob_path", azure_path.blob_path, {"status": VideoStatus.DOWNLOADING})

        self.update_state(
            state='PROGRESS',
            meta={
                'progress': 5,
                'stage': 'downloading',
                'message': 'Starting download from Azure Storage...'
            }
        )

        download_result = azure_service.download_video_to_local_with_progress(
            azure_path, local_path, update_download_progress
        )

        if not download_result["success"]:
            repo.update_by_field("azure_file_path.blob_path", azure_path.blob_path, {"status": VideoStatus.DOWNLOAD_ERROR})
            self.update_state(
                state='FAILURE',
                meta={
                    'error': f'Download error: {download_result["error"]}',
                    'progress': 50
                }
            )
            return {
                "status": "error",
                "message": f'Download error: {download_result["error"]}'
            }

        self.update_state(
            state='PROGRESS',
            meta={
                'progress': 55,
                'stage': 'analyzing',
                'message': 'Analyzing video characteristics...'
            }
        )

        video_info = get_video_info(local_path)
        if not video_info:
            repo.update_by_field("azure_file_path.blob_path", azure_path.blob_path, {"status": VideoStatus.DOWNLOAD_ERROR})
            cleanup_file(local_path)
            self.update_state(
                state='FAILURE',
                meta={
                    'error': 'Failed to analyze video',
                    'progress': 60
                }
            )
            return {"status": "error", "message": "Failed to analyze video"}

        self.update_state(
            state='PROGRESS',
            meta={
                'progress': 65,
                'stage': 'converting',
                'message': 'Converting video for web viewing...'
            }
        )

        if Settings.skip_conversion_for_compatible and is_web_compatible(video_info):
            logger.info(f"Video is already web-compatible, skipping conversion: {azure_path.blob_path}")
            self.update_state(
                state='PROGRESS',
                meta={
                    'progress': 95,
                    'stage': 'converting',
                    'message': 'Video is already web-compatible, skipping conversion...'
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
                repo.update_by_field("azure_file_path.blob_path", azure_path.blob_path, {"status": VideoStatus.DOWNLOAD_ERROR})
                cleanup_file(local_path)
                self.update_state(
                    state='FAILURE',
                    meta={
                        'error': 'Video conversion error',
                        'progress': 90
                    }
                )
                return {"status": "error", "message": "Video conversion error"}

            cleanup_file(local_path)
            os.rename(converted_path, local_path)

        self.update_state(
            state='PROGRESS',
            meta={
                'progress': 98,
                'stage': 'finalizing',
                'message': 'Finalizing processing...'
            }
        )

        # Оновлюємо тільки поля які є в схемі source_videos
        update_data = {
            "status": VideoStatus.NOT_ANNOTATED,
            "duration_sec": int(video_info.get("duration", 0)),
            "updated_at_utc": datetime.now(UTC).isoformat(sep=" ", timespec="seconds")
        }

        repo.update_by_field("azure_file_path.blob_path", azure_path.blob_path, update_data)

        self.update_state(
            state='SUCCESS',
            meta={
                'progress': 100,
                'stage': 'completed',
                'message': 'Video ready for annotation'
            }
        )

        logger.info(f"Video successfully downloaded and converted: {azure_path.blob_path}")
        return {
            "status": "success",
            "message": "Video ready for annotation",
            "filename": filename,
            "video_info": video_info
        }

    except Exception as e:
        logger.error(f"Error processing video {azure_path.blob_path}: {str(e)}")
        try:
            annotation = repo.find_by_field("azure_file_path.blob_path", azure_path.blob_path)
            if annotation:
                repo.update_by_field("azure_file_path.blob_path", azure_path.blob_path, {"status": VideoStatus.DOWNLOAD_ERROR})

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
    """Get detailed video information"""
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
            "width": int(video_stream.get("width", 0)) if video_stream else 0,
            "height": int(video_stream.get("height", 0)) if video_stream else 0,
            "fps": eval(video_stream.get("r_frame_rate", "0/1")) if video_stream else 0,
            "video_codec": video_stream.get("codec_name", "") if video_stream else "",
            "video_profile": video_stream.get("profile", "") if video_stream else "",
            "audio_codec": audio_stream.get("codec_name", "") if audio_stream else "",
        }

    except Exception as e:
        logger.error(f"Error getting video info {video_path}: {str(e)}")
        return None


def is_web_compatible(video_info: Dict[str, Any]) -> bool:
    """Check if video is already web-compatible"""
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
    """Convert video with progress tracking"""
    try:
        duration = video_info.get("duration", 0)

        command = ["ffmpeg", "-y", "-i", input_path]

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

        logger.debug(f"Conversion command: {' '.join(command)}")

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

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
            logger.debug(f"Video successfully converted: {output_path}")
            return True
        else:
            stderr_output = process.stderr.read() if process.stderr else ""
            logger.error(f"FFmpeg conversion error: {stderr_output}")
            return False

    except Exception as e:
        logger.error(f"Error converting video: {str(e)}")
        return False