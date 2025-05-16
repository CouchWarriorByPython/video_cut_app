from io import BytesIO
import os

from azure.core.paging import ItemPaged
from azure.storage.blob import BlobServiceClient, ContainerClient, BlobClient
from azure.data.tables import TableServiceClient, TableClient
import logging
import stat
import config
from config import logger

# reduce printing of additional azure http logging
import logging

AZURE_LOGGER = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")
AZURE_LOGGER.setLevel(logging.WARNING)


def __get_connection_str(credentials_config: dict) -> str:
    """
    Azure configuration dictionary that is read from configs/general.yaml file, "azure" section.
    :param credentials_config: .yaml azure/resources/resource_name/credentials
    :return: Connection string to Azure storage
    """
    url = credentials_config["url_pattern"]
    url_variables = dict()
    for variable in credentials_config["url_pattern_variables"]:
        if variable["type"] == "string":
            url_variables[variable["name"]] = variable["value"]
        elif variable["type"] == "environment_variable_name":
            url_variables[variable["name"]] = os.getenv(variable["value"])
    return url.format(**url_variables)


def get_blob_service_client(resource_name: str) -> BlobServiceClient:
    conf = config.AZURE_CONFIG
    for resource in conf['resources']:
        if resource["resource_name"] == resource_name:
            if resource["resource_type"] == 'storage_account':
                client = BlobServiceClient.from_connection_string(
                    conn_str=__get_connection_str(credentials_config=resource["credentials"]))
            elif resource["resource_type"] == 'blob_container_sas':
                client = BlobServiceClient(account_url=__get_connection_str(credentials_config=resource["credentials"]))

    if client is None:
        raise ValueError('No such resource_name in the config.')

    return client


def get_table_service_client(account_name: str) -> TableServiceClient:
    connection_string = __get_connection_str(account_name)
    return TableServiceClient.from_connection_string(connection_string)


def get_blob_container_client(blob_service_client: BlobServiceClient, container_name: str) -> ContainerClient:
    return blob_service_client.get_container_client(container=container_name)


def get_table_client(table_service_client: TableServiceClient, table_name: str) -> TableClient:
    return table_service_client.get_table_client(table_name=table_name)


def get_blob_names_iter(blob_container_client: ContainerClient, blob_prefix: str) -> ItemPaged[str]:
    return blob_container_client.list_blob_names(name_starts_with=blob_prefix)


def upload_blob_from_local_source(container_client: ContainerClient, local_file: str, remote_file: str,
                                  metadata: dict[str, str] = None) -> BlobClient:
    """
    Creates or overwrite blob from a local file source.

    :param container_client: The blob container with which to interact.
    :param local_file: Absolute local path.
    :param remote_file: Target file name with a folder name if it needs to.
    :param metadata: Name-value pairs associated with the blob as metadata.
    :param content_settings:
    :return: A BlobClient to interact with the newly uploaded blob.
    """
    with open(file=local_file, mode="rb") as data:
        return container_client.upload_blob(name=remote_file,
                                            data=data,
                                            overwrite=True,
                                            metadata=metadata,
                                            logger=AZURE_LOGGER)


def upload_blob_stream(container_client: ContainerClient, blob_name: str, data: BytesIO,
                       metadata: dict[str, str] = None) -> BlobClient:
    """
    Creates or overwrite blob from byte stream data source.

    :param container_client: The blob container with which to interact.
    :param data: Byte stream to upload.
    :param blob_name: blob name to upload the data into.
    :param metadata: Name-value pairs associated with the blob as metadata.
    :return:
    """
    blob_client = container_client.get_blob_client(blob=blob_name)
    # blob_type -> "BlockBlob" store text and binary data, up to approximately 4.75 TiB.
    return blob_client.upload_blob(data=data.read(),
                                   blob_type="BlockBlob",
                                   overwrite=True,
                                   metadata=metadata,
                                   logger=AZURE_LOGGER)


def download_blob_to_stream(blob_service_client: BlobServiceClient, container_name: str, blob_name: str) -> BytesIO:
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

    stream = BytesIO()
    blob_client.download_blob().readinto(stream)
    stream.seek(0)
    return stream


def upload_azure_blobs_from_folder(
        container_client: ContainerClient,
        output_folder: str,
        blob_prefix_clips: str,
        ssh_client=None,
        use_ssh=False,
):
    """
    Uploads all files from output folder Azure blob storage locally or on remote machine.

    :param container_client: The blob container with which to interact.
    :param output_folder: Path where the clips which need to be uploaded are located.
    :param blob_prefix_clips: Path to upload clips in Azure blob storage.
    :param ssh_client: SSH client.
    :param use_ssh: Boolean flag to use SSH or not.
    """
    # Ensure container exists
    try:
        container_client.create_container()
    except Exception:
        pass  # Already exists

    files = []

    if use_ssh:
        with ssh_client.open_sftp() as sftp_client:
            for f in sftp_client.listdir_iter(path=output_folder):
                if stat.S_ISREG(f.st_mode) and not f.filename.endswith('/'):
                    remote_file_path = os.path.join(output_folder, f.filename)
                    files.append(remote_file_path)

            for remote_file_path in files:
                relative_path = os.path.relpath(remote_file_path, output_folder)
                blob_path = os.path.join(blob_prefix_clips, relative_path).replace("\\", "/")
                with sftp_client.open(remote_file_path, "rb") as remote_file:
                    stream = BytesIO(remote_file.read())
                    upload_blob_stream(container_client, blob_path, stream)
    else:
        # List files in the local folder
        files = [
            os.path.join(output_folder, file)
            for file in os.listdir(output_folder)
            if os.path.isfile(os.path.join(output_folder, file))
        ]

        for local_file_path in files:
            relative_path = os.path.relpath(local_file_path, output_folder)
            blob_path = os.path.join(blob_prefix_clips, relative_path).replace("\\", "/")
            with open(local_file_path, "rb") as f:
                stream = BytesIO(f.read())
                upload_blob_stream(container_client, blob_path, stream)

    logger.info(f"Upload completed. Uploaded {len(files)} files to {blob_prefix_clips}")