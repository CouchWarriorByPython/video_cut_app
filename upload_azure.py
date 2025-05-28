from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient
from configs import Settings
from pathlib import Path


def upload_video_to_azure(source: str) -> None:
    """
    Завантажує відеофайл в Azure Blob Storage у папку, вказану в Settings.azure_output_folder_path.

    :param source: Локальний шлях до відеофайлу (наприклад, 'videos/20250502-1628-IN_Recording.mp4')
    """
    try:
        # Авторизація через Service Principal
        credential = ClientSecretCredential(
            tenant_id=Settings.azure_tenant_id,
            client_id=Settings.azure_client_id,
            client_secret=Settings.azure_client_secret
        )

        # Підключення до Blob Service
        account_url = Settings.get_azure_account_url()
        blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
        container_client = blob_service_client.get_container_client(Settings.azure_storage_container_name)

        # Формуємо шлях у blob (наприклад, annotation/20250502-1628-IN_Recording.mp4)
        file_name = Path(source).name
        blob_path = f"{Settings.azure_input_folder_path.rstrip('/')}/{file_name}"

        print(f"📤 Завантаження '{source}' → '{blob_path}'")

        # Завантажуємо файл
        with open(source, "rb") as data:
            blob_client = container_client.get_blob_client(blob_path)
            blob_client.upload_blob(data, overwrite=True)

        print(f"✅ Файл '{file_name}' успішно завантажено в Azure Blob Storage!")

    except Exception as e:
        print(f"❌ Помилка при завантаженні: {e}")


upload_video_to_azure("20250502-1628-IN_Recording.mp4")
