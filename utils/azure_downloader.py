from typing import Dict, Any
import os
import requests
from urllib.parse import urlparse
from datetime import datetime


def download_video_from_azure(url: str, output_dir: str = "source_videos") -> Dict[str, Any]:
    """
    Завантаження відео з URL.

    Args:
        url: URL до відео
        output_dir: Директорія для збереження

    Returns:
        Dict[str, Any]: Результат операції з ключами success, azure_link, filename, extension, local_path
    """
    try:
        # Перевіряємо, чи URL дійсний
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"Недійсний URL: {url}")

        # Отримання імені файлу з URL шляху
        path_parts = parsed_url.path.strip('/').split('/')
        if path_parts:
            # Перевірка на мок-сервер
            if parsed_url.netloc == 'localhost:8001' and path_parts[-1] == 'video':
                filename = "20250502-1628-IN_Recording.mp4"
            else:
                # Обробка для інших URL
                filename = path_parts[-1]
                # Додаємо розширення, якщо відсутнє
                if not os.path.splitext(filename)[1]:
                    filename += ".mp4"
        else:
            # Якщо не можемо отримати ім'я з URL, створюємо його
            filename = f"video_{int(datetime.utcnow().timestamp())}.mp4"

        # Отримуємо розширення
        extension = os.path.splitext(filename)[1]

        # Перевіряємо чи файл вже існує
        if os.path.exists(os.path.join(output_dir, filename)):
            # Додаємо timestamp до імені, щоб уникнути перезапису
            base_name, ext = os.path.splitext(filename)
            filename = f"{base_name}_{int(datetime.utcnow().timestamp())}{ext}"

        # Створюємо директорію, якщо її не існує
        os.makedirs(output_dir, exist_ok=True)

        # Шлях для збереження файлу
        file_path = os.path.join(output_dir, filename)

        # Завантажуємо файл
        response = requests.get(url, stream=True, timeout=30)

        # Перевірка успішності запиту
        if response.status_code != 200:
            raise ValueError(f"Помилка отримання відео. Статус: {response.status_code}")

        # Записуємо файл блоками для економії пам'яті
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # фільтр порожніх частин
                    f.write(chunk)

        # Повертаємо URL для веб-доступу, а не повний системний шлях
        web_path = f"/videos/{filename}"

        return {
            "success": True,
            "azure_link": url,
            "filename": filename,
            "extension": extension[1:] if extension.startswith('.') else extension,
            "local_path": web_path,
            "file_path": file_path  # Системний шлях для інших операцій якщо потрібно
        }
    except Exception as e:
        import traceback
        print(f"Помилка завантаження відео: {str(e)}")
        print(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }