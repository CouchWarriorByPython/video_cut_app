import re
import subprocess
import shlex
from typing import Dict, Any, Optional

from backend.config.settings import get_settings
from backend.database import create_cvat_settings_repository
from backend.models.shared import MLProject, CVATSettings
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__, "services.log")


class CVATService:
    """Service for CVAT integration and task management"""

    def __init__(self) -> None:
        self.settings_repo = create_cvat_settings_repository()

    def get_default_project_params(self, project_name: str) -> Dict[str, Any]:
        """Get CVAT project parameters from database or fallback to defaults"""
        try:
            if not self._validate_project_name(project_name):
                logger.warning(f"Invalid project name: {project_name}, using default")
                return self._get_hardcoded_defaults("motion-det")

            settings_doc = self.settings_repo.get_by_field("project_name", project_name)

            if settings_doc:
                return {
                    "project_id": settings_doc.project_id,
                    "overlap": settings_doc.overlap,
                    "segment_size": settings_doc.segment_size,
                    "image_quality": settings_doc.image_quality
                }
            else:
                logger.warning(f"Settings for project {project_name} not found in DB, using defaults")
                return self._get_hardcoded_defaults(project_name)

        except Exception as e:
            logger.error(f"Error getting project parameters for {project_name}: {str(e)}")
            return self._get_hardcoded_defaults(project_name)

    def get_cvat_settings_as_model(self, project_name: str) -> CVATSettings:
        """Get CVAT settings as CVATSettings model"""
        params = self.get_default_project_params(project_name)
        return CVATSettings(
            project_name=MLProject(project_name),
            **params
        )

    def get_cvat_settings_document(self, project_name: str):
        """Get CVATProjectSettingsDocument for project"""
        return self.settings_repo.get_by_field("project_name", project_name)

    def create_task(self, filename: str, file_path: str, project_params: Dict[str, Any]) -> Optional[str]:
        """Create CVAT task using CLI with comprehensive error handling"""
        try:
            if not self._validate_create_task_params(filename, file_path, project_params):
                return None

            project_id = project_params.get("project_id")
            overlap = project_params.get("overlap", 5)
            segment_size = project_params.get("segment_size", 400)
            image_quality = project_params.get("image_quality", 100)

            cli_command = [
                "cvat-cli",
                "--auth", f"{shlex.quote(settings.cvat_username)}:{shlex.quote(settings.cvat_password)}",
                "--server-host", shlex.quote(settings.cvat_host),
                "--server-port", str(settings.cvat_port),
                "create", shlex.quote(filename),
                "local", shlex.quote(file_path),
                "--project_id", str(project_id),
                "--overlap", str(overlap),
                "--segment_size", str(segment_size),
                "--image_quality", str(image_quality),
                "--use_cache",
                "--use_zip_chunks"
            ]

            logger.info(f"Creating CVAT task for {filename} in project {project_id}")
            logger.debug(f"CVAT CLI command: {' '.join(cli_command)}")

            result = subprocess.run(cli_command, capture_output=True, text=True, timeout=300)

            logger.debug(f"CVAT CLI stdout: {result.stdout}")
            logger.debug(f"CVAT CLI stderr: {result.stderr}")
            logger.debug(f"CVAT CLI return code: {result.returncode}")

            if result.returncode == 0:
                task_id = self._extract_task_id_from_output(result.stdout)
                if task_id:
                    logger.info(f"CVAT task created successfully: {task_id} for {filename}")
                    return task_id
                else:
                    logger.error(f"Failed to extract task ID from output for {filename}: {result.stdout}")
                    return None
            else:
                logger.error(f"CVAT task creation failed for {filename}: stdout={result.stdout}, stderr={result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout during CVAT task creation for {filename}")
            return None
        except Exception as e:
            logger.error(f"Error creating CVAT task for {filename}: {str(e)}")
            return None

    @staticmethod
    def _validate_project_name(project_name: str) -> bool:
        """Validate project name against defined ML projects"""
        valid_projects = {project.value for project in MLProject}
        return project_name in valid_projects

    @staticmethod
    def _validate_create_task_params(filename: str, file_path: str, project_params: Dict[str, Any]) -> bool:
        """Validate parameters for task creation"""
        if not filename or not filename.strip():
            logger.error("Filename cannot be empty")
            return False

        if not file_path or not file_path.strip():
            logger.error("File path cannot be empty")
            return False

        project_id = project_params.get("project_id")
        if not project_id or not isinstance(project_id, int) or project_id <= 0:
            logger.error("Invalid project_id in parameters")
            return False

        return True

    @staticmethod
    def _extract_task_id_from_output(output: str) -> Optional[str]:
        """Extract task ID from CVAT CLI output using regex"""
        match = re.search(r"Created task ID: (\d+)", output)
        return match.group(1) if match else None

    @staticmethod
    def _get_hardcoded_defaults(project_name: str) -> Dict[str, Any]:
        """Get hardcoded default parameters for CVAT projects"""
        default_projects: Dict[str, Dict[str, int]] = {
            MLProject.MOTION_DET.value: {"project_id": 5, "overlap": 5, "segment_size": 400, "image_quality": 100},
            MLProject.TRACKING.value: {"project_id": 6, "overlap": 5, "segment_size": 400, "image_quality": 100},
            MLProject.MIL_HARDWARE.value: {"project_id": 7, "overlap": 5, "segment_size": 400, "image_quality": 100},
            MLProject.RE_ID.value: {"project_id": 8, "overlap": 5, "segment_size": 400, "image_quality": 100}
        }

        return default_projects.get(project_name, {
            "project_id": 1,
            "overlap": 5,
            "segment_size": 400,
            "image_quality": 100
        })

    def update_project_settings(self, cvat_settings: CVATSettings) -> bool:
        """Update CVAT project settings in database using CVATSettings model"""
        try:
            if not self._validate_project_name(cvat_settings.project_name.value):
                logger.error(f"Invalid project name for update: {cvat_settings.project_name}")
                return False

            existing_settings = self.settings_repo.get_by_field("project_name", cvat_settings.project_name.value)

            if existing_settings:
                # Check if project_id is being changed and if it conflicts with another project
                if existing_settings.project_id != cvat_settings.project_id:
                    conflicting_project = self.settings_repo.get_by_field("project_id", cvat_settings.project_id)
                    if conflicting_project and str(conflicting_project.id) != str(existing_settings.id):
                        logger.error(f"Cannot update project_id to {cvat_settings.project_id}: already used by project {conflicting_project.project_name}")
                        return False

                success = self.settings_repo.update_by_id(
                    str(existing_settings.id),
                    {
                        "project_id": cvat_settings.project_id,
                        "overlap": cvat_settings.overlap,
                        "segment_size": cvat_settings.segment_size,
                        "image_quality": cvat_settings.image_quality
                    }
                )
            else:
                # Check if project_id is already used by another project
                conflicting_project = self.settings_repo.get_by_field("project_id", cvat_settings.project_id)
                if conflicting_project:
                    logger.error(f"Cannot create project with project_id {cvat_settings.project_id}: already used by project {conflicting_project.project_name}")
                    return False

                new_settings = self.settings_repo.create(
                    project_name=cvat_settings.project_name.value,
                    project_id=cvat_settings.project_id,
                    overlap=cvat_settings.overlap,
                    segment_size=cvat_settings.segment_size,
                    image_quality=cvat_settings.image_quality
                )
                success = bool(new_settings)

            if success:
                logger.info(f"CVAT settings updated for project: {cvat_settings.project_name}")
            else:
                logger.error(f"Failed to update CVAT settings for project: {cvat_settings.project_name}")

            return success

        except Exception as e:
            logger.error(f"Error updating CVAT settings for {cvat_settings.project_name}: {str(e)}")
            return False