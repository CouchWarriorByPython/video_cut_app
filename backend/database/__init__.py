from backend.database.unified_repository import UnifiedRepository

def create_repository(collection_name: str, async_mode: bool = False) -> UnifiedRepository:
    """Створює репозиторій для роботи з MongoDB колекцією"""
    return UnifiedRepository(collection_name, async_mode)