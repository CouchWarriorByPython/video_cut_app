import re
import subprocess
import shlex
from typing import Dict, Any, Optional

from backend.config.settings import Settings
from backend.database import create_repository
from backend.utils.logger import get_logger

logger = get_logger(__name__, "services.log")


class CVATService:
    """Сервіс для роботи з CVAT"""

    def __init__(self):
        self.settings_repo = create_repository("cvat_project_settings", async_mode=False)

    def get_default_project_params(self, project_name: str) -> Dict[str, Any]:
        """Отримує параметри проєкту з БД або дефолтні значення"""
        try:
            settings = self.settings_repo.find_by_field("project_name", project_name)

            if settings:
                return {
                    "project_id": settings["project_id"],
                    "overlap": settings["overlap"],
                    "segment_size": settings["segment_size"],
                    "image_quality": settings["image_quality"]
                }
            else:
                logger.warning(f"Налаштування для проєкту {project_name} не знайдені в БД, використовуємо дефолтні")
                return self._get_hardcoded_defaults(project_name)

        except Exception as e:
            logger.error(f"Помилка отримання параметрів проєкту {project_name}: {str(e)}")
            return self._get_hardcoded_defaults(project_name)

    def _get_hardcoded_defaults(self, project_name: str) -> Dict[str, Any]:
        """Дефолтні хардкод параметри як fallback"""
        default_projects = {
            "motion-det": {"project_id": 5, "overlap": 5, "segment_size": 400, "image_quality": 100},
            "tracking": {"project_id": 6, "overlap": 5, "segment_size": 400, "image_quality": 100},
            "mil-hardware": {"project_id": 7, "overlap": 5, "segment_size": 400, "image_quality": 100},
            "re-id": {"project_id": 8, "overlap": 5, "segment_size": 400, "image_quality": 100}
        }

        return default_projects.get(project_name, {
            "project_id": 1,
            "overlap": 5,
            "segment_size": 400,
            "image_quality": 100
        })

    def create_task(self, filename: str, file_path: str, project_params: Dict[str, Any]) -> Optional[str]:
        """Створює задачу в CVAT через CLI"""
        try:
            project_id = project_params.get("project_id")
            overlap = project_params.get("overlap", 5)
            segment_size = project_params.get("segment_size", 400)
            image_quality = project_params.get("image_quality", 100)

            if not project_id:
                logger.error("project_id не вказано в параметрах")
                return None

            cli_command = [
                "cvat-cli",
                "--auth", f"{shlex.quote(Settings.cvat_username)}:{shlex.quote(Settings.cvat_password)}",
                "--server-host", shlex.quote(Settings.cvat_host),
                "--server-port", str(Settings.cvat_port),
                "create", shlex.quote(filename),
                "local", shlex.quote(file_path),
                "--project_id", str(project_id),
                "--overlap", str(overlap),
                "--segment_size", str(segment_size),
                "--image_quality", str(image_quality),
                "--use_cache",
                "--use_zip_chunks"
            ]

            logger.debug(f"Створення CVAT задачі для {filename}")

            result = subprocess.run(cli_command, capture_output=True, text=True)

            if result.returncode == 0:
                output = result.stdout
                match = re.search(r"Created task ID: (\d+)", output)
                task_id = match.group(1) if match else None

                if task_id:
                    logger.info(f"CVAT задача створена: {task_id}")
                    return task_id
                else:
                    logger.warning(f"Не вдалося витягти task ID з виводу: {output}")
                    return None
            else:
                logger.error(f"Помилка створення CVAT задачі: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Помилка при створенні CVAT задачі для {filename}: {str(e)}")
            return None