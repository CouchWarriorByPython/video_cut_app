#!/usr/bin/env python3
"""Скрипт для автоматичної міграції на pydantic-settings"""

import os
import re
from pathlib import Path
from typing import List, Tuple

# Мапінг старих назв на нові
FIELD_MAPPING = {
    "Settings.mongo_uri": "settings.mongo_uri",
    "Settings.mongo_db_name": "settings.mongo_db",
    "Settings.azure_tenant_id": "settings.azure_tenant_id",
    "Settings.azure_client_id": "settings.azure_client_id",
    "Settings.azure_client_secret": "settings.azure_client_secret",
    "Settings.azure_storage_account_name": "settings.azure_storage_account_name",
    "Settings.azure_storage_container_name": "settings.azure_storage_container_name",
    "Settings.azure_output_folder_path": "settings.azure_output_folder_path",
    "Settings.azure_input_folder_path": "settings.azure_input_folder_path",
    "Settings.cvat_host": "settings.cvat_host",
    "Settings.cvat_port": "settings.cvat_port",
    "Settings.cvat_username": "settings.cvat_username",
    "Settings.cvat_password": "settings.cvat_password",
    "Settings.temp_folder": "settings.temp_folder",
    "Settings.logs_folder": "settings.logs_folder",
    "Settings.log_level": "settings.log_level",
    "Settings.log_max_bytes": "settings.log_max_bytes",
    "Settings.log_backup_count": "settings.log_backup_count",
    "Settings.ffmpeg_log_level": "settings.ffmpeg_log_level",
    "Settings.fast_api_host": "settings.fast_api_host",
    "Settings.fast_api_port": "settings.fast_api_port",
    "Settings.reload": "settings.reload",
    "Settings.azure_download_chunk_size": "settings.azure_download_chunk_size",
    "Settings.azure_max_concurrency": "settings.azure_max_concurrency",
    "Settings.video_conversion_preset": "settings.video_conversion_preset",
    "Settings.video_conversion_crf": "settings.video_conversion_crf",
    "Settings.enable_hardware_acceleration": "settings.enable_hardware_acceleration",
    "Settings.skip_conversion_for_compatible": "settings.skip_conversion_for_compatible",
    "Settings.max_conversion_workers": "settings.max_conversion_workers",
    "Settings.jwt_secret_key": "settings.secret_key",  # Renamed field
    "Settings.jwt_algorithm": "settings.jwt_algorithm",
    "Settings.access_token_expire_minutes": "settings.access_token_expire_minutes",
    "Settings.refresh_token_expire_minutes": "settings.refresh_token_expire_minutes",
    "Settings.admin_email": "settings.super_admin_email",  # Renamed field
    "Settings.admin_password": "settings.super_admin_password",  # Renamed field
    "Settings.get_azure_account_url()": "settings.azure_account_url",
    "Settings.is_local_environment()": "settings.is_local_environment",
    "Settings.get_environment_name()": "settings.environment",
}

IMPORT_REPLACEMENTS = [
    # Старий імпорт -> новий імпорт
    ("from backend.config.settings import Settings", "from backend.config.settings import get_settings"),
]


def find_python_files(root_dir: str) -> List[Path]:
    """Знаходить всі Python файли в проєкті"""
    backend_path = Path(root_dir) / "backend"
    return list(backend_path.rglob("*.py"))


def update_imports(content: str) -> Tuple[str, bool]:
    """Оновлює імпорти Settings"""
    updated = False
    for old_import, new_import in IMPORT_REPLACEMENTS:
        if old_import in content:
            content = content.replace(old_import, new_import)
            # Додаємо отримання settings після імпорту
            if "\nsettings = get_settings()" not in content:
                content = content.replace(
                    new_import,
                    f"{new_import}\n\nsettings = get_settings()"
                )
            updated = True
    return content, updated


def update_field_usage(content: str) -> Tuple[str, bool]:
    """Оновлює використання полів Settings"""
    updated = False

    # Сортуємо за довжиною щоб уникнути часткових замін
    sorted_mappings = sorted(FIELD_MAPPING.items(), key=lambda x: len(x[0]), reverse=True)

    for old_field, new_field in sorted_mappings:
        if old_field in content:
            content = content.replace(old_field, new_field)
            updated = True

    return content, updated


def migrate_file(file_path: Path) -> bool:
    """Мігрує один файл"""
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content

        # Пропускаємо сам settings.py
        if file_path.name == "settings.py" and "pydantic_settings" in content:
            return False

        # Оновлюємо імпорти
        content, imports_updated = update_imports(content)

        # Оновлюємо використання полів
        content, fields_updated = update_field_usage(content)

        if imports_updated or fields_updated:
            file_path.write_text(content, encoding='utf-8')
            print(f"✅ Оновлено: {file_path}")
            return True

        return False

    except Exception as e:
        print(f"❌ Помилка при обробці {file_path}: {e}")
        return False


def main():
    """Основна функція міграції"""
    print("🚀 Початок міграції на pydantic-settings...")

    # Знаходимо всі Python файли
    python_files = find_python_files(".")
    print(f"📁 Знайдено {len(python_files)} Python файлів")

    updated_count = 0
    for file_path in python_files:
        if migrate_file(file_path):
            updated_count += 1

    print(f"\n✨ Міграція завершена! Оновлено {updated_count} файлів")
    print("\n⚠️  Перевірте наступне:")
    print("1. Оновіть requirements.txt - додайте pydantic-settings==2.7.0")
    print("2. Перевірте .env файл - всі змінні повинні бути присутні")
    print("3. Запустіть тести щоб переконатись що все працює")


if __name__ == "__main__":
    main()