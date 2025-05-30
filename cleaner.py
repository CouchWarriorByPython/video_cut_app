from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient
from pymongo import MongoClient
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


def clear_video_clips_collection() -> bool:
    """
    Очищає колекцію video_clips у MongoDB.

    Returns:
        bool: True якщо операція пройшла успішно, False інакше
    """
    client = None
    try:
        print("🗄️ Підключення до MongoDB...")
        client = MongoClient(Settings.mongo_uri)
        db = client[Settings.mongo_db_name]
        clips_collection = db["video_clips"]

        print("🧹 Очищення колекції video_clips...")
        result = clips_collection.delete_many({})
        deleted_count = result.deleted_count

        if deleted_count == 0:
            print("ℹ️ Колекція video_clips була порожньою.")
        else:
            print(f"✅ Видалено {deleted_count} записів з колекції video_clips.")

        return True

    except Exception as e:
        print(f"❌ Помилка при очищенні колекції video_clips: {e}")
        return False
    finally:
        if client:
            client.close()
            print("🔒 З'єднання з MongoDB закрито.")


def reset_source_videos_status() -> bool:
    """
    Скидає статус всіх відео в колекції source_videos на 'not_annotated'.

    Returns:
        bool: True якщо операція пройшла успішно, False інакше
    """
    client = None
    try:
        print("🔄 Скидання статусу відео в source_videos...")
        client = MongoClient(Settings.mongo_uri)
        db = client[Settings.mongo_db_name]
        source_collection = db["source_videos"]

        result = source_collection.update_many(
            {"status": {"$ne": "not_annotated"}},
            {"$set": {"status": "not_annotated"}}
        )

        updated_count = result.modified_count

        if updated_count == 0:
            print("ℹ️ Всі відео вже мають статус 'not_annotated'.")
        else:
            print(f"✅ Оновлено статус для {updated_count} відео.")

        return True

    except Exception as e:
        print(f"❌ Помилка при скиданні статусу відео: {e}")
        return False
    finally:
        if client:
            client.close()


def cleanup_all() -> None:
    """
    Повне очищення системи - видаляє всі кліпи з Azure та MongoDB,
    скидає статуси відео для можливості повторної обробки.
    """
    print("🚀 Початок повного очищення системи...")
    print("=" * 50)

    success_count = 0
    total_operations = 3

    if delete_azure_output_folder():
        success_count += 1

    print("-" * 30)

    if clear_video_clips_collection():
        success_count += 1

    print("-" * 30)

    if reset_source_videos_status():
        success_count += 1

    print("=" * 50)

    if success_count == total_operations:
        print("🎉 Повне очищення системи завершено успішно!")
        print("📝 Тепер можна запускати нарізку з чистого листа.")
    else:
        print(f"⚠️ Завершено з помилками: {success_count}/{total_operations} операцій виконано успішно.")
        print("🔍 Перевірте логи вище для деталей помилок.")


if __name__ == "__main__":
    cleanup_all()