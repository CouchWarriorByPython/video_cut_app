import os
import subprocess
import json
from typing import Dict, Any, Optional, Callable

from backend.database import create_source_video_repository
from backend.services.azure_service import AzureService
from backend.models.shared import AzureFilePath, VideoStatus
from backend.utils.azure_path_utils import extract_filename_from_azure_path
from backend.utils.video_utils import get_local_video_path, cleanup_file
from backend.config.settings import get_settings
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__, "services.log")


class VideoProcessingService:
    """Service for video download and conversion operations"""

    def __init__(self):
        self.repo = create_source_video_repository()
        self.azure_service = AzureService()

    def download_and_convert_video(
        self,
        azure_path: AzureFilePath,
        download_progress_callback: Optional[Callable[[int, int], None]] = None,
        conversion_progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """Download video from Azure Storage and convert it for web viewing"""
        logger.info(f"Starting download and conversion: {azure_path.blob_path}")

        try:
            video = self.repo.get_by_field("azure_file_path.blob_path", azure_path.blob_path)
            if not video:
                return {"status": "error", "message": "Video not found in DB"}

            filename = extract_filename_from_azure_path(azure_path)
            local_path = get_local_video_path(filename)

            self.repo.update_by_id(str(video.id), {"status": VideoStatus.DOWNLOADING})

            download_result = self.azure_service.download_video_to_local_with_progress(
                azure_path, local_path, download_progress_callback
            )

            if not download_result["success"]:
                self.repo.update_by_id(str(video.id), {"status": VideoStatus.DOWNLOAD_ERROR})
                return {
                    "status": "error",
                    "message": f'Download error: {download_result["error"]}'
                }

            video_info = self._get_video_info(local_path)
            if not video_info:
                self.repo.update_by_id(str(video.id), {"status": VideoStatus.DOWNLOAD_ERROR})
                cleanup_file(local_path)
                return {"status": "error", "message": "Failed to analyze video"}

            if settings.skip_conversion_for_compatible and self._is_web_compatible(video_info):
                logger.info(f"Video is already web-compatible, skipping conversion: {azure_path.blob_path}")
            else:
                converted_success = self._convert_to_web_format(
                    local_path, video_info, conversion_progress_callback
                )
                if not converted_success:
                    self.repo.update_by_id(str(video.id), {"status": VideoStatus.DOWNLOAD_ERROR})
                    cleanup_file(local_path)
                    return {"status": "error", "message": "Video conversion error"}

            update_data = {
                "status": VideoStatus.NOT_ANNOTATED,
                "duration_sec": int(video_info.get("duration", 0))
            }

            self.repo.update_by_id(str(video.id), update_data)

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
                video = self.repo.get_by_field("azure_file_path.blob_path", azure_path.blob_path)
                if video:
                    self.repo.update_by_id(str(video.id), {"status": VideoStatus.DOWNLOAD_ERROR})

                if 'local_path' in locals():
                    cleanup_file(local_path)
            except:
                pass

            return {"status": "error", "message": str(e)}

    def _get_video_info(self, video_path: str) -> Optional[Dict[str, Any]]:
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

    def _is_web_compatible(self, video_info: Dict[str, Any]) -> bool:
        """Check if video is already web-compatible"""
        video_codec = video_info.get("video_codec", "").lower()
        audio_codec = video_info.get("audio_codec", "").lower()
        container = video_info.get("container", "").lower()

        is_h264 = "h264" in video_codec or "avc" in video_codec
        is_aac_audio = "aac" in audio_codec
        is_mp4_container = container in ["mp4", "mov"]

        return is_h264 and is_aac_audio and is_mp4_container

    def _convert_to_web_format(
            self,
            local_path: str,
            video_info: Dict[str, Any],
            progress_callback: Optional[Callable[[float], None]] = None
    ) -> bool:
        """Convert video to web format using CPU only"""
        try:
            filename = os.path.basename(local_path)
            name_without_ext = os.path.splitext(filename)[0]
            converted_filename = f"{name_without_ext}_web.mp4"
            converted_path = get_local_video_path(converted_filename)

            duration = video_info.get("duration", 0)

            command = ["ffmpeg", "-y", "-i", local_path]

            command.extend([
                "-c:v", "libx264",
                "-preset", settings.video_conversion_preset,
                "-crf", str(settings.video_conversion_crf),
                "-profile:v", "high",
                "-level", "4.0",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                "-pix_fmt", "yuv420p",
                "-f", "mp4",
                "-progress", "pipe:1",
                "-loglevel", "error",
                converted_path
            ])

            logger.debug(f"Conversion command: {' '.join(command)}")
            logger.info("Using CPU for video conversion")

            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            while True:
                line = process.stdout.readline()
                if not line:
                    break

                if line.startswith("out_time_ms=") and progress_callback:
                    try:
                        time_ms = int(line.split("=")[1])
                        time_seconds = time_ms / 1000000
                        if duration > 0:
                            progress_percent = min((time_seconds / duration) * 100, 100)
                            progress_callback(progress_percent)
                    except (ValueError, IndexError):
                        continue

            process.wait()

            if process.returncode == 0 and os.path.exists(converted_path) and os.path.getsize(converted_path) > 0:
                if progress_callback:
                    progress_callback(100)
                cleanup_file(local_path)
                os.rename(converted_path, local_path)
                logger.info("Video successfully converted using CPU")
                return True
            else:
                stderr_output = process.stderr.read() if process.stderr else ""
                logger.error(f"FFmpeg conversion error: {stderr_output}")
                return False

        except Exception as e:
            logger.error(f"Error converting video: {str(e)}")
            return False