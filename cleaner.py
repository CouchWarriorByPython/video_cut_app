from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient
from backend.config.settings import Settings


def delete_azure_output_folder() -> bool:
    """
    Видаляє всі blob-и з Azure Blob Storage, які мають префікс azure_output_folder_path.

    Returns:
        bool: True якщо операція пройшла успішно, False інакше
    """
    try:
        credential = ClientSecretCredential(
            tenant_id=Settings.azure_tenant_id,
            client_id=Settings.azure_client_id,
            client_secret=Settings.azure_client_secret
        )

        account_url = Settings.get_azure_account_url()
        blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
        container_client = blob_service_client.get_container_client(Settings.azure_storage_container_name)

        prefix = Settings.azure_output_folder_path.rstrip("/") + "/"
        print(f"🧹 Видалення всіх blob-ів з префіксом '{prefix}'...")

        deleted_count = 0
        for blob in container_client.list_blobs(name_starts_with=prefix):
            blob_client = container_client.get_blob_client(blob.name)
            blob_client.delete_blob()
            print(f"❌ Видалено: {blob.name}")
            deleted_count += 1

        if deleted_count == 0:
            print(f"ℹ️ У '{prefix}' не знайдено жодного blob-файлу.")
        else:
            print(f"✅ Видалено {deleted_count} файлів з Azure Storage.")

        return True

    except Exception as e:
        print(f"❌ Помилка при видаленні папки '{Settings.azure_output_folder_path}': {e}")
        return False


def cleanup_all() -> None:
    """Виконує повне очищення системи та копіювання тестового файлу."""
    print("🚀 Початок повного очищення системи...")
    print("=" * 50)


    print("-" * 30)

    delete_azure_output_folder()

    print("-" * 30)


if __name__ == "__main__":
    cleanup_all()