from backend.database.repositories.source_video import SyncSourceVideoRepository, AsyncSourceVideoRepository
from backend.database.repositories.video_clip import SyncVideoClipRepository, AsyncVideoClipRepository


def create_repository(collection_name: str, async_mode: bool = False):
    """
    Створює репозиторій для роботи з MongoDB з оптимізованою логікою індексів

    Args:
        collection_name: Назва колекції
        async_mode: Використовувати асинхронну реалізацію

    Returns:
        Репозиторій для роботи з анотаціями відео
    """
    from backend.utils.logger import get_logger
    logger = get_logger(__name__)

    logger.debug(f"Створення репозиторію: колекція={collection_name}, асинхронний={async_mode}")

    if collection_name == "source_videos":
        if async_mode:
            return AsyncSourceVideoRepository()
        else:
            return SyncSourceVideoRepository()
    elif collection_name == "video_clips":
        if async_mode:
            return AsyncVideoClipRepository()
        else:
            return SyncVideoClipRepository()
    else:
        raise ValueError(f"Невідома колекція: {collection_name}")