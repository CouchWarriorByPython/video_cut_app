import redis
from typing import Dict, Any
from datetime import datetime, timedelta
import json

from backend.config.settings import get_settings

from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__, "services.log")


class VideoLockService:
    """Сервіс для блокування відео через Redis"""

    def __init__(self):
        self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        self.lock_timeout = 3600  # 1 година в секундах

    def lock_video(self, video_id: str, user_id: str, user_email: str) -> Dict[str, Any]:
        """Блокує відео для користувача"""
        try:
            lock_key = f"video_lock:{video_id}"

            # Перевіряємо чи відео вже заблоковане
            existing_lock = self.redis_client.get(lock_key)
            if existing_lock:
                lock_data = json.loads(existing_lock)

                # Якщо відео заблоковане тим же користувачем - продовжуємо роботу
                if lock_data['user_id'] == user_id:
                    # Продовжуємо існуюче блокування
                    ttl = self.redis_client.ttl(lock_key)
                    logger.info(f"Відео {video_id} вже заблоковане користувачем {user_email}, продовжуємо роботу")

                    return {
                        "success": True,
                        "message": "Продовжуємо роботу з відео",
                        "expires_at": (datetime.now() + timedelta(seconds=ttl)).isoformat()
                    }
                else:
                    # Відео заблоковане іншим користувачем
                    return {
                        "success": False,
                        "error": f"Відео вже заблоковане користувачем {lock_data['user_email']}",
                        "locked_by": lock_data['user_email'],
                        "locked_at": lock_data['locked_at']
                    }

            # Створюємо нове блокування
            lock_data = {
                "user_id": user_id,
                "user_email": user_email,
                "locked_at": datetime.now().isoformat()
            }

            # Встановлюємо блокування з TTL
            self.redis_client.setex(lock_key, self.lock_timeout, json.dumps(lock_data))

            logger.info(f"Відео {video_id} заблоковано користувачем {user_email}")

            return {
                "success": True,
                "message": "Відео успішно заблоковано",
                "expires_at": (datetime.now() + timedelta(seconds=self.lock_timeout)).isoformat()
            }

        except Exception as e:
            logger.error(f"Помилка блокування відео {video_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def unlock_video(self, video_id: str, user_id: str) -> Dict[str, Any]:
        """Розблоковує відео"""
        try:
            lock_key = f"video_lock:{video_id}"

            existing_lock = self.redis_client.get(lock_key)
            if not existing_lock:
                return {
                    "success": True,
                    "message": "Відео не було заблоковане"
                }

            lock_data = json.loads(existing_lock)

            # Перевіряємо чи може цей користувач розблокувати
            if lock_data['user_id'] != user_id:
                return {
                    "success": False,
                    "error": "Ви не можете розблокувати відео іншого користувача"
                }

            # Видаляємо блокування
            self.redis_client.delete(lock_key)

            logger.info(f"Відео {video_id} розблоковано користувачем {lock_data['user_email']}")

            return {
                "success": True,
                "message": "Відео успішно розблоковано"
            }

        except Exception as e:
            logger.error(f"Помилка розблокування відео {video_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_video_lock_status(self, video_id: str) -> Dict[str, Any]:
        """Отримує статус блокування відео"""
        try:
            lock_key = f"video_lock:{video_id}"

            existing_lock = self.redis_client.get(lock_key)
            if not existing_lock:
                return {
                    "locked": False
                }

            lock_data = json.loads(existing_lock)
            ttl = self.redis_client.ttl(lock_key)

            return {
                "locked": True,
                "locked_by": lock_data['user_email'],
                "locked_at": lock_data['locked_at'],
                "expires_in_seconds": ttl if ttl > 0 else 0,
                "user_id": lock_data['user_id']
            }

        except Exception as e:
            logger.error(f"Помилка перевірки блокування {video_id}: {str(e)}")
            return {
                "locked": False,
                "error": str(e)
            }

    def get_all_video_locks(self, video_ids: list[str]) -> Dict[str, Dict[str, Any]]:
        """Отримує статуси блокування для множини відео"""
        try:
            locks = {}

            for video_id in video_ids:
                locks[video_id] = self.get_video_lock_status(video_id)

            return locks

        except Exception as e:
            logger.error(f"Помилка отримання блокувань: {str(e)}")
            return {}

    def cleanup_expired_locks(self) -> int:
        """Очищає прострочені блокування (викликається автоматично Redis TTL)"""
        try:
            pattern = "video_lock:*"
            keys = self.redis_client.keys(pattern)

            expired_count = 0
            for key in keys:
                ttl = self.redis_client.ttl(key)
                if ttl == -1:  # Ключ без TTL
                    self.redis_client.delete(key)
                    expired_count += 1

            if expired_count > 0:
                logger.info(f"Очищено {expired_count} прострочених блокувань")

            return expired_count

        except Exception as e:
            logger.error(f"Помилка очищення блокувань: {str(e)}")
            return 0
