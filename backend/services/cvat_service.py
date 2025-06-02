import re
import subprocess
from typing import Dict, Any, Optional

from backend.config.settings import Settings
from backend.utils.logger import get_logger

logger = get_logger(__name__, "services.log")

class CVATService:
    """Сервіс для роботи з CVAT"""

    @staticmethod
    def get_default_project_params(project_name: str) -> Dict[str, Any]:
        """Отримує дефолтні CVAT параметри проєкту"""
        default_projects = {
            "motion-det": {
                "project_id": 5,
                "overlap": 5,
                "segment_size": 400,
                "image_quality": 100
            },
            "tracking": {
                "project_id": 6,
                "overlap": 5,
                "segment_size": 400,
                "image_quality": 100
            },
            "mil-hardware": {
                "project_id": 7,
                "overlap": 5,
                "segment_size": 400,
                "image_quality": 100
            },
            "re-id": {
                "project_id": 8,
                "overlap": 5,
                "segment_size": 400,
                "image_quality": 100
            }
        }

        return default_projects.get(project_name, {
            "project_id": 1,
            "overlap": 5,
            "segment_size": 400,
            "image_quality": 100
        })

    @staticmethod
    def create_task(filename: str, file_path: str, project_params: Dict[str, Any]) -> Optional[str]:
        """Створює задачу в CVAT через CLI"""
        try:
            project_id = project_params.get("project_id")
            overlap = project_params.get("overlap", 5)
            segment_size = project_params.get("segment_size", 400)
            image_quality = project_params.get("image_quality", 100)

            if not project_id:
                logger.error("project_id не вказано в параметрах")
                return None

            auth_str = f"cvat-cli --auth {Settings.cvat_username}:{Settings.cvat_password} --server-host {Settings.cvat_host} --server-port {Settings.cvat_port}"

            cli_command = (
                f"{auth_str} create {filename} "
                f"local {file_path} "
                f"--project_id {project_id} "
                f"--overlap {overlap} "
                f"--segment_size {segment_size} "
                f"--image_quality {image_quality} "
                "--use_cache --use_zip_chunks"
            )

            logger.debug(f"Створення CVAT задачі для {filename}")

            result = subprocess.run(cli_command, shell=True, capture_output=True, text=True)

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