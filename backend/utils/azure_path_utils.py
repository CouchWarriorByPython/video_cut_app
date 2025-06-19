import urllib.parse
from typing import Dict, Any
from urllib.parse import urlparse
from backend.models.database import AzureFilePath
from backend.utils.logger import get_logger

logger = get_logger(__name__, "utils.log")


def parse_azure_blob_url_to_path(azure_url: str) -> AzureFilePath:
    """Parse Azure blob URL to AzureFilePath structure"""
    try:
        decoded_url = urllib.parse.unquote(azure_url)
        parsed = urlparse(decoded_url)

        # Extract account name from hostname
        account_name = parsed.netloc.split('.')[0]

        # Split path to get container and blob path
        path_parts = parsed.path.strip('/').split('/', 1)

        if len(path_parts) < 2:
            raise ValueError("Invalid Azure blob URL format")

        container_name = path_parts[0]
        blob_path = path_parts[1]

        return AzureFilePath(
            account_name=account_name,
            container_name=container_name,
            blob_path=blob_path
        )
    except Exception as e:
        logger.error(f"Error parsing Azure URL {azure_url}: {str(e)}")
        raise


def azure_path_to_url(azure_path: AzureFilePath) -> str:
    """Convert AzureFilePath to full Azure blob URL"""
    return f"https://{azure_path.account_name}.blob.core.windows.net/{azure_path.container_name}/{azure_path.blob_path}"


def azure_path_to_legacy_format(azure_path: AzureFilePath) -> str:
    """Convert AzureFilePath to legacy azure_link format for compatibility"""
    return azure_path_to_url(azure_path)


def generate_clip_azure_path(source_path: AzureFilePath, clip_filename: str,
                             output_folder: str = "clips") -> AzureFilePath:
    """Generate Azure path for clip based on source video path"""
    # Extract directory from source blob path
    source_dir = "/".join(source_path.blob_path.split("/")[:-1])

    # Create clip path in clips subfolder
    clip_blob_path = f"{source_dir}/{output_folder}/{clip_filename}"

    return AzureFilePath(
        account_name=source_path.account_name,
        container_name=source_path.container_name,
        blob_path=clip_blob_path
    )


def extract_filename_from_azure_path(azure_path: AzureFilePath) -> str:
    """Extract filename from Azure blob path"""
    return azure_path.blob_path.split("/")[-1]


def get_file_extension_from_azure_path(azure_path: AzureFilePath) -> str:
    """Get file extension from Azure blob path"""
    filename = extract_filename_from_azure_path(azure_path)
    return filename.split(".")[-1].lower() if "." in filename else ""


def validate_azure_path_structure(azure_path: AzureFilePath) -> bool:
    """Validate AzureFilePath structure"""
    if not azure_path.account_name or not azure_path.container_name or not azure_path.blob_path:
        return False

    if not azure_path.account_name.replace("-", "").replace("_", "").isalnum():
        return False

    if not azure_path.container_name.replace("-", "").replace("_", "").isalnum():
        return False

    return True


def azure_path_dict_to_object(path_dict: Dict[str, Any]) -> AzureFilePath:
    """Convert dictionary to AzureFilePath object"""
    return AzureFilePath(
        account_name=path_dict["account_name"],
        container_name=path_dict["container_name"],
        blob_path=path_dict["blob_path"]
    )


def azure_path_object_to_dict(azure_path: AzureFilePath) -> Dict[str, Any]:
    """Convert AzureFilePath object to dictionary"""
    return {
        "account_name": azure_path.account_name,
        "container_name": azure_path.container_name,
        "blob_path": azure_path.blob_path
    }