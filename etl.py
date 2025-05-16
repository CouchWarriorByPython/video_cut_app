import json
import shutil
import subprocess
import sys
import os
import re
import argparse
from tqdm import tqdm
from azure.storage.blob import BlobServiceClient, ContainerClient

# Adjust path so Python sees config and utils
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(project_root)

from config import logger
from utils import azure, video_trimmer, mongo, remote_host, cvat_cli

# AZURE vars
AZURE_STORAGE_ACCOUNT_NAME = ""
AZURE_STORAGE_CONTAINER_NAME = ""
AZURE_OUTPUT_PREFIX = ""

# Remote Server vars
REMOTE_SERVER_CONFIG_NAME = ""
REMOTE_SERVER_PATH_PREFIX = ""
REMOTE_SERVER_PATH_OUTPUT_PREFIX = ""


def _get_clip_path(subfolder_name: str, path: str):
    last_part = os.path.basename(path)
    if use_ssh:
        new_string = f"{subfolder_name}/{last_part}/"
    else:
        new_string = f"{last_part}/"
    if os.getenv("ENV") == "test":
        new_string = new_string[:-1] + "_test/"
    return new_string


def _download_azure_blobs_from_folder_with_config(
        blob_service_client: BlobServiceClient,
        container_client: ContainerClient,
        config_path: str,
        video_clips_output_path: str,
        source_video_output_path: str,
        blob_prefix: str,
        ssh_client=None,
        use_ssh=False,
):
    """
    Downloads all files from output folder that are specified in config.json file locally or on remote machine.

    :param blob_service_client: The blob service client.
    :param container_client: The blob container with which to interact.
    :param config_path: Path to the config.json file.
    :param video_clips_output_path: Path where video clips will be placed.
    :param source_video_output_path: Path where videos will be placed.
    :param blob_prefix: Optional path in Azure Blob Storage where videos that need to be downloaded are placed.
    :param ssh_client: SSH client.
    :param use_ssh: Boolean flag to use SSH or not.
    """
    # Check existence of remote folder, create if it doesn't exist
    try:
        if use_ssh:
            if remote_host.is_folder_exists(ssh=ssh_client, path=source_video_output_path):
                if not remote_host.is_folder_empty(ssh=ssh_client, path=source_video_output_path):
                    msg = f"The {source_video_output_path} folder is Not Empty. Please choose another path for videos uploading or set `ignore_non_emptiness = True`."
                    logger.error(msg)
                    raise SystemExit(msg)
            else:
                with ssh_client.open_sftp() as sftp_client:
                    sftp_client.mkdir(source_video_output_path)
                    sftp_client.mkdir(video_clips_output_path)
        else:
            if not os.path.exists(source_video_output_path):
                logger.info(f"Local folder {source_video_output_path} does not exist. Creating it.")
                os.makedirs(source_video_output_path, exist_ok=True)
            else:
                if os.listdir(source_video_output_path):
                    msg = f"The {source_video_output_path} folder is Not Empty. Please choose another path for videos uploading or set `ignore_non_emptiness = True`."
                    logger.error(msg)
                    raise SystemExit(msg)
    except Exception as e:
        logger.error(f"Error while checking or creating folder: {e}")
        raise SystemExit(e)

    # List all blobs in the container with the specified prefix
    logger.info(f"Listing blobs with prefix '{blob_prefix}'...")
    blobs = list(container_client.list_blobs(name_starts_with=f"{blob_prefix}/"))

    # Filter out directory placeholders
    blobs = [blob for blob in blobs if not blob.name.endswith("/")]

    if not blobs:
        logger.info(f"No files found with prefix '{blob_prefix}'")
        return
    logger.info(f"Found {len(blobs)} files to download")

    # Download config.json
    config_blob = container_client.get_blob_client(blob=config_path)
    if config_blob.exists():
        config_reader = config_blob.download_blob()
        config = json.load(config_reader)

    if use_ssh:
        # Download video clips
        video_clip_names = config["video_clips"].keys()
        logger.info(f"Found {len(video_clip_names)} video clips to download")
        with ssh_client.open_sftp() as sftp_client:
            with tqdm(
                    total=len(video_clip_names), desc="Downloading files", unit="file"
            ) as pbar:
                for clip_name in video_clip_names:
                    local_file_path = os.path.join(source_video_output_path, clip_name)
                    stream = azure.download_blob_to_stream(
                        blob_service_client,
                        container_client.container_name,
                        f"{blob_prefix}/{clip_name}",
                    )
                    with sftp_client.open(local_file_path, "wb") as f:
                        f.write(stream.read())
                    pbar.update(1)
                    pbar.set_postfix(file=os.path.basename(clip_name))
    else:
        # Download video clips
        video_clip_names = config["video_clips"].keys()
        logger.info(f"Found {len(video_clip_names)} video clips to download")
        with tqdm(
                total=len(video_clip_names), desc="Downloading files", unit="file"
        ) as pbar:
            for clip_name in video_clip_names:
                local_file_path = os.path.join(source_video_output_path, clip_name)
                stream = azure.download_blob_to_stream(
                    blob_service_client,
                    container_client.container_name,
                    f"{blob_prefix}/{clip_name}",
                )
                os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                with open(local_file_path, "wb") as f:
                    f.write(stream.read())
                pbar.update(1)
                pbar.set_postfix(file=os.path.basename(clip_name))

    logger.info(
        f"Download completed. Downloaded {len(video_clip_names)} files to {source_video_output_path}"
    )


if __name__ == "__main__":
    """
    The script that automatically creates CVAT-tasks.
    How it works:
    1. Downloads files from Azure blob Storage which are located in blob_prefix and described in config.json
    2. Trims downloaded video to clips, described in config.json
    3. Created tasks on CVAT server using trimmed clips
    4. Uploads clips into Azure blob storage
    5. Uploads metadata into mongo table

    How to use:
    Example for local use:
    python create_cvat_task.py --blob_prefix path/to/azure --config_path path/to/config/config.json

    Example for remote use:
    python create_cvat_task.py --blob_prefix path/to/azure --config_path path/to/config/config.json --use_ssh

    """
    logger.info("create cvat task ----- start.")
    parser = argparse.ArgumentParser(
        description="Script that utomatically creates CVAT-tasks."
    )
    parser.add_argument(
        "--blob_prefix",
        required=True,
        type=str,
        help="Remote blob container folder name to copy blobs from."
             "Example: data_external/kondor/motion_det_batch2",
    )
    parser.add_argument(
        "--config_path",
        required=True,
        type=str,
        help="Path to config file."
             "Example: data_external/kondor/motion_det_batch2/config.json",
    )
    parser.add_argument(
        "--use_ssh",
        action="store_true",
        help="Set this flag if you need to use SSH client",
    )

    args = parser.parse_args()
    blob_prefix = args.blob_prefix
    config_path = args.config_path
    use_ssh = args.use_ssh
    env = os.getenv("ENV")

    azure_input_path = (
        f"{AZURE_STORAGE_ACCOUNT_NAME}/{AZURE_STORAGE_CONTAINER_NAME}/{blob_prefix}/"
    )
    azure_output_path = f"{AZURE_STORAGE_ACCOUNT_NAME}/{AZURE_STORAGE_CONTAINER_NAME}/{AZURE_OUTPUT_PREFIX}/"

    logger.info("download_azure_blobs ----- start.")
    # Create azure and ssh clients
    blob_service_client = azure.get_blob_service_client(AZURE_STORAGE_ACCOUNT_NAME)
    container_client = azure.get_blob_container_client(
        blob_service_client, AZURE_STORAGE_CONTAINER_NAME
    )
    if use_ssh:
        ssh_client = remote_host.get_ssh_client(remote_name=REMOTE_SERVER_CONFIG_NAME)
        sftp_client = ssh_client.open_sftp()
    else:
        ssh_client = None
        sftp_client = None

    cvat_video_clips_path = _get_clip_path(
        REMOTE_SERVER_PATH_OUTPUT_PREFIX, blob_prefix
    )
    if use_ssh:
        video_clips_output_path = f"{REMOTE_SERVER_PATH_PREFIX}/{cvat_video_clips_path}"
    else:
        video_clips_output_path = cvat_video_clips_path
    source_video_output_path = f"{video_clips_output_path}tmp"

    # Download files from Azure to remote machine
    _download_azure_blobs_from_folder_with_config(
        blob_service_client=blob_service_client,
        container_client=container_client,
        config_path=config_path,
        video_clips_output_path=video_clips_output_path,
        source_video_output_path=source_video_output_path,
        blob_prefix=blob_prefix,
        ssh_client=ssh_client,
        use_ssh=use_ssh,
    )
    logger.info("download_azure_blobs ----- finish.")

    logger.info("trim_videos_from_folder ----- start.")
    # Open config.json
    config_blob = container_client.get_blob_client(blob=config_path)
    if config_blob.exists():
        config_reader = config_blob.download_blob()
        config = json.load(config_reader)

    task_params = config["task_params"]
    video_clips = config["video_clips"]
    # Trim viddeos
    logger.info("trim_videos_from_folder ----- start.")
    names_list = video_trimmer.trim_videos_from_folder(
        source_video_output_path=source_video_output_path,
        video_clips_output_path=video_clips_output_path,
        video_clips=video_clips,
        use_ssh=use_ssh,
        ssh_client=ssh_client,
    )
    logger.info("trim_videos_from_folder ----- finish.")

    # Task creation using cvat-cli
    logger.info("task creation ----- start.")
    if use_ssh:
        dir = sftp_client.listdir(video_clips_output_path)
        dir.remove("tmp")
    else:
        dir = os.listdir(video_clips_output_path)
        dir.remove("tmp")
    tasks_metadata = []
    results = []
    for file in dir:
        task_name = os.path.splitext(file)[0]
        trimmed_metadata = next(
            (item for item in names_list if item.get("azure_output_filename") == file),
            None,
        )
        if trimmed_metadata:
            parameters = {k: v for k, v in trimmed_metadata.items()}
        else:
            parameters = {}

        ### CVAT command
        if env == "test":
            task_params["project_id"] = 23
        arg_string = " ".join(f"--{k} {v}" for k, v in task_params.items())
        auth_string = cvat_cli.get_command_auth_str(
            remote_name=REMOTE_SERVER_CONFIG_NAME
        )
        if use_ssh:
            cli_command = (
                f"create {task_name} share {cvat_video_clips_path}{file} {arg_string}"
            )
        else:
            cli_command = (
                f"create {task_name} local {cvat_video_clips_path}{file} {arg_string}"
            )

        result = cvat_cli.execute_command(
            remote_name=REMOTE_SERVER_CONFIG_NAME, cli_command=cli_command
        )
        match = re.search(r"Created task ID: (\d+)", result.stdout.decode("utf-8"))
        task_id = match.group(1) if match else None
        task_config = {
            "_id": f"{task_id}::{task_name}",
            "task_id": task_id,
            "task_name": task_name,
            "azure_input_path": azure_input_path,
            "azure_output_path": azure_output_path,
            "task_params": task_params,
            **parameters,
        }
        tasks_metadata.append(task_config)
        results.append(result)
    logger.info("task creation ----- finish.")

    # Upload trimmed videos into Azure blob storage
    logger.info("upload trimmed videos ----- start.")
    azure.upload_azure_blobs_from_folder(
        container_client=container_client,
        output_folder=video_clips_output_path,
        blob_prefix_clips=f"{AZURE_OUTPUT_PREFIX}/",
        ssh_client=ssh_client,
        use_ssh=use_ssh,
    )
    logger.info("upload trimmed videos ----- finish.")
    # Upload Mongo table
    logger.info("upload into mongo table ----- start.")
    mclient = mongo.get_client(cluster_name="georect")
    db = mclient["ml_pipelines_dev"]
    if env == "test":
        collection = db["annotation_data_test"]
    elif env == "production":
        collection = db["annotation_data"]
    collection.insert_many(tasks_metadata)
    logger.info("upload into mongo table ----- finish.")

    if use_ssh:
        # Remove tmp folder with downloaded files
        ssh_client.exec_command(f"rm -rf {source_video_output_path}/")
    else:
        shutil.rmtree(source_video_output_path)