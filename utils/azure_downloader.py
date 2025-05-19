from typing import Dict, Any, Tuple
import os
import re


def parse_azure_url(url: str) -> Tuple[str, str, str]:
    """
    Парсить Azure URL, витягує шлях та ім'я файлу.

    Args:
        url: Повний URL до файлу

    Returns:
        Tuple[str, str, str]: (ім'я_файлу_без_розширення, шлях_до_файлу, розширення)
    """
    # Екстракція імені файлу з URL
    file_pattern = r'([^\/]+?)(\.[^\.\/]+)?$'
    file_match = re.search(file_pattern, url)

    if not file_match:
        raise ValueError("Не вдалося виділити ім'я файлу з URL")

    filename = file_match.group(1)
    extension = file_match.group(2) or '.mp4'  # За замовчуванням .mp4

    # Екстракція шляху до файлу
    path_pattern = r'(.*?)\/[^\/]+?$'
    path_match = re.search(path_pattern, url)

    path = ""
    if path_match:
        full_path = path_match.group(1)
        # Вилучаємо доменну частину, залишаємо тільки структуру папок
        path_parts = full_path.split('/')
        if len(path_parts) > 2:  # Є принаймні протокол, домен і папка
            path = '/'.join(path_parts[3:]) + '/'

    return filename, path, extension


def download_video_from_azure(url: str, output_dir: str = "videos") -> Dict[str, Any]:
    """
    Заглушка для завантаження відео з Azure.

    Args:
        url: URL до відео в Azure
        output_dir: Директорія для збереження

    Returns:
        Dict[str, Any]: Результат операції
    """
    try:
        # Парсимо URL
        filename, path, extension = parse_azure_url(url)

        # Створюємо директорію, якщо її не існує
        os.makedirs(output_dir, exist_ok=True)

        # Імітуємо завантаження
        # В реальному сценарії тут був би код для завантаження з Azure

        return {
            "success": True,
            "source": filename,
            "azure_path": path,
            "extension": extension,
            "local_path": os.path.join(output_dir, f"{filename}{extension}")
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }