import os
import subprocess
import config

from config import logger


def get_command_auth_str(remote_name: str):
    remote_config = config.general_config["remote"][remote_name]
    host = remote_config["host"]
    user = remote_config["cvat_ui_user_var_name"]
    password = remote_config["cvat_ui_pass_var_name"]
    cvat_username = os.getenv(user)
    cvat_password = os.getenv(password)
    return f"cvat-cli --auth {cvat_username}:{cvat_password} --server-host {host}"


def execute_command(remote_name: str, cli_command: str):
    auth_str = get_command_auth_str(remote_name=remote_name)
    command = f"{auth_str} {cli_command}"
    logger.info(f"Command: {command}")
    return subprocess.run(command, shell=True, capture_output=True)