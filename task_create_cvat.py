#!/usr/bin/env python3
"""
Скрипт для тестування обробки відео та створення CVAT задач
Читає дані з MongoDB та виконує повний цикл обробки
"""

import os
import sys
import tempfile
import shutil
import argparse
from typing import Dict, Any, Optional
from pathlib import Path

# Додаємо поточну директорію до Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from configs import Settings
from db_connector import create_repository
from utils.logger import get_logger
from utils.celery_utils import (
    format_filename,
    trim_video_clip,
    create_cvat_task,
)

logger = get_logger("cvat_test")


class CVATTestProcessor:
    """Клас для тестування обробки відео та створення CVAT задач"""

    def __init__(self):
        self.repo = create_repository(collection_name="анотації_соурс_відео")
        self.clips_repo = create_repository(collection_name="video_clips")

    def validate_environment(self) -> bool:
        """Перевіряє налаштування середовища"""
        logger.info("Перевірка налаштувань середовища")

        # Перевіряємо CVAT
        if not Settings.validate_cvat_config():
            logger.error("CVAT налаштування не знайдені. Перевірте CVAT_USERNAME та CVAT_PASSWORD")
            return False

        # Перевіряємо шляхи
        upload_path = Path(Settings.upload_folder)
        if not upload_path.exists():
            logger.error(f"Папка для відео не існує: {Settings.upload_folder}")
            return False

        logger.info(f"Папка для відео: {upload_path.absolute()}")

        # Перевіряємо CVAT проєкти
        logger.info("CVAT проєкти:")
        for project_name, params in Settings.cvat_projects.items():
            logger.info(f"  {project_name}: project_id={params['project_id']}")

        return True

    def get_processing_videos(self) -> list:
        """Отримує список відео зі статусом 'processing' або 'annotated'"""
        try:
            all_videos = self.repo.get_all_annotations()
            processing_videos = [
                video for video in all_videos
                if video.get('status') in ['processing', 'annotated']
                   and video.get('clips')
                   and not video.get('metadata', {}).get('skip', False)
            ]
            logger.info(f"Знайдено {len(processing_videos)} відео для обробки")
            return processing_videos
        except Exception as e:
            logger.error(f"Помилка отримання відео з бази: {str(e)}")
            return []

    def process_video_clips(self, video_data: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """Обробляє кліпи одного відео"""
        azure_link = video_data.get('azure_link')
        logger.info(f"Початок обробки відео: {azure_link}")

        # Перевіряємо наявність файлу
        local_path = video_data.get('local_path')
        if not local_path:
            logger.error(f"Локальний шлях не знайдено для {azure_link}")
            return {"status": "error", "message": "Відсутній локальний шлях"}

        video_filename = os.path.basename(local_path)
        absolute_path = os.path.join(Settings.upload_folder, video_filename)

        if not os.path.exists(absolute_path):
            logger.error(f"Файл не знайдено: {absolute_path}")
            return {"status": "error", "message": f"Файл не знайдено: {absolute_path}"}

        logger.info(f"Файл відео знайдено: {absolute_path}")

        # Отримуємо дані для обробки
        metadata = video_data.get('metadata', {})
        clips = video_data.get('clips', {})
        source_id = video_data.get('id')
        where = video_data.get('where', '')
        when = video_data.get('when', '')

        logger.info(f"Метадані: {metadata}")
        logger.info(f"Кліпи: {list(clips.keys())}")

        results = []
        global_clip_id = 0

        for project, project_clips in clips.items():
            logger.info(f"Обробка проєкту: {project}, кліпів: {len(project_clips)}")

            # Отримуємо параметри CVAT для проєкту
            cvat_params = video_data.get('cvat_params', {}).get(project, {})
            if not cvat_params:
                cvat_params = Settings.get_cvat_project_params(project)

            if not cvat_params:
                logger.warning(f"Параметри CVAT не знайдені для проєкту: {project}")
                continue

            logger.info(f"CVAT параметри для {project}: {cvat_params}")

            for idx, clip in enumerate(project_clips):
                clip_result = self.process_single_clip(
                    source_id=source_id,
                    project=project,
                    project_clip_id=idx,
                    global_clip_id=global_clip_id,
                    video_filename=video_filename,
                    absolute_path=absolute_path,
                    start_time=clip["start_time"],
                    end_time=clip["end_time"],
                    metadata=metadata,
                    cvat_params=cvat_params,
                    where=where,
                    when=when,
                    dry_run=dry_run
                )
                results.append(clip_result)
                global_clip_id += 1

        return {
            "status": "success",
            "azure_link": azure_link,
            "processed_clips": len(results),
            "results": results
        }

    def process_single_clip(
            self,
            source_id: str,
            project: str,
            project_clip_id: int,
            global_clip_id: int,
            video_filename: str,
            absolute_path: str,
            start_time: str,
            end_time: str,
            metadata: Dict[str, Any],
            cvat_params: Dict[str, Any],
            where: str = "",
            when: str = "",
            dry_run: bool = False
    ) -> Dict[str, Any]:
        """Обробляє один кліп"""
        logger.info(f"Обробка кліпу {global_clip_id} для проєкту {project}: {start_time} - {end_time}")

        try:
            # Формуємо ім'я файлу
            filename_base = format_filename(
                metadata=metadata,
                original_filename=video_filename,
                clip_id=global_clip_id,
                where=where,
                when=when
            )

            filename = f"{filename_base}.mp4"
            logger.info(f"Ім'я кліпу: {filename}")

            if dry_run:
                logger.info(f"DRY RUN: Пропускаємо фактичну обробку кліпу {filename}")
                return {
                    "status": "dry_run",
                    "filename": filename,
                    "project": project,
                    "clip_id": global_clip_id
                }

            # Створюємо тимчасову директорію для кліпу
            with tempfile.TemporaryDirectory() as temp_dir:
                clip_path = os.path.join(temp_dir, filename)

                # Нарізаємо відео
                success = trim_video_clip(
                    source_path=absolute_path,
                    output_path=clip_path,
                    start_time=start_time,
                    end_time=end_time
                )

                if not success:
                    return {
                        "status": "error",
                        "message": f"Не вдалося створити кліп: {filename}",
                        "filename": filename
                    }

                logger.info(f"Кліп успішно створено: {clip_path}")

                # Зберігаємо локальну копію
                video_base_name = os.path.splitext(video_filename)[0]
                local_clips_folder = os.path.join(Settings.clips_folder, video_base_name)
                os.makedirs(local_clips_folder, exist_ok=True)

                local_clip_path = os.path.join(local_clips_folder, filename)
                shutil.copy2(clip_path, local_clip_path)
                logger.info(f"Локальна копія збережена: {local_clip_path}")

                # Створюємо CVAT задачу з локального файлу
                cvat_task_id = create_cvat_task(
                    filename=filename_base,
                    file_path=local_clip_path,  # Використовуємо локальний шлях
                    project_params=cvat_params
                )

                if cvat_task_id:
                    logger.info(f"CVAT задача створена: {cvat_task_id}")
                else:
                    logger.warning("Не вдалося створити CVAT задачу")

                # Зберігаємо інформацію про кліп в базу
                clip_data = {
                    "source_id": source_id,
                    "project": project,
                    "clip_id": global_clip_id,
                    "project_clip_id": project_clip_id,
                    "filename": filename_base,
                    "extension": "mp4",
                    "cvat_task_id": cvat_task_id,
                    "status": "processing" if cvat_task_id else "error",
                    "azure_link": filename,  # Використовуємо назву файлу як унікальний ідентифікатор
                    "local_path": local_clip_path,
                    "fps": Settings.default_fps
                }

                clip_id_db = self.clips_repo.save_annotation(clip_data)
                logger.info(f"Інформація про кліп збережена в базу: {clip_id_db}")

                return {
                    "status": "success",
                    "filename": filename,
                    "project": project,
                    "clip_id": global_clip_id,
                    "cvat_task_id": cvat_task_id,
                    "local_path": local_clip_path,
                    "db_id": clip_id_db
                }

        except Exception as e:
            logger.error(f"Помилка обробки кліпу {global_clip_id}: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "clip_id": global_clip_id
            }

    def close(self):
        """Закриває підключення"""
        if self.repo:
            self.repo.close()
        if self.clips_repo:
            self.clips_repo.close()


def main():
    """Головна функція"""
    parser = argparse.ArgumentParser(description="Тестування обробки відео та створення CVAT задач")
    parser.add_argument("--azure-link", type=str, help="Azure link конкретного відео для обробки")
    parser.add_argument("--dry-run", action="store_true", help="Тестовий запуск без фактичної обробки")
    parser.add_argument("--validate-only", action="store_true", help="Тільки перевірка налаштувань")

    args = parser.parse_args()

    # Створюємо процесор
    processor = CVATTestProcessor()

    try:
        # Перевіряємо налаштування
        if not processor.validate_environment():
            logger.error("Перевірка налаштувань не пройшла")
            return 1

        if args.validate_only:
            logger.info("Перевірка налаштувань пройшла успішно")
            return 0

        # Отримуємо відео для обробки
        if args.azure_link:
            video_data = processor.repo.get_annotation(args.azure_link)
            if not video_data:
                logger.error(f"Відео не знайдено: {args.azure_link}")
                return 1
            videos = [video_data]
        else:
            videos = processor.get_processing_videos()

        if not videos:
            logger.info("Немає відео для обробки")
            return 0

        # Обробляємо відео
        for video in videos:
            logger.info(f"=" * 50)
            result = processor.process_video_clips(video, dry_run=args.dry_run)

            if result["status"] == "success":
                logger.info(f"Відео успішно оброблено: {result['azure_link']}")
                logger.info(f"Оброблено кліпів: {result['processed_clips']}")
            else:
                logger.error(f"Помилка обробки відео: {result.get('message')}")

        logger.info("Обробка завершена")
        return 0

    except Exception as e:
        logger.error(f"Критична помилка: {str(e)}")
        return 1
    finally:
        processor.close()


if __name__ == "__main__":
    exit(main())