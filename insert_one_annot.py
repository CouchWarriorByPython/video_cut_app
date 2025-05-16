# Приклад: insert_one_annot.py
from db_connector import create_repository


def main():
    # Тестовий документ анотації
    test_annotation = {
        "source": "test_video",
        "metadata": {
            "skip": False,
            "uav_type": "",
            "video_content": "",
            "is_urban": False,
            "has_osd": False,
            "is_analog": False,
            "night_video": False,
            "multiple_streams": False,
            "has_infantry": False,
            "has_explosions": False
        },
        "clips": {
            "motion-det": [
                {"id": 0, "start_time": "00:00:09:507", "end_time": "00:01:05:803"},
                {"id": 1, "start_time": "00:01:29:632", "end_time": "00:01:50:179"}
            ],
            "tracking": [
                {"id": 0, "start_time": "00:00:19:604", "end_time": "00:00:46:472"},
                {"id": 1, "start_time": "00:01:29:632", "end_time": "00:01:50:179"}
            ],
            "mil-hardware": [
                {"id": 0, "start_time": "00:00:25:440", "end_time": "00:01:16:137"},
                {"id": 1, "start_time": "00:01:29:632", "end_time": "00:01:50:179"}
            ],
            "re-id": [
                {"id": 0, "start_time": "00:00:35:166", "end_time": "00:00:58:022"},
                {"id": 1, "start_time": "00:01:29:632", "end_time": "00:01:50:179"}
            ]
        }
    }

    # Створюємо репозиторій
    repo = create_repository(collection_name="анотації_соурс_відео")

    try:
        # Створюємо індекси (потрібно тільки один раз)
        repo.create_indexes()

        # Зберігаємо анотацію (новий документ або оновлюємо існуючий)
        result = repo.save_annotation(test_annotation)
        print(result)

        # Перевіряємо що документ збережено
        annotation = repo.get_annotation("test_video")
        if annotation:
            print(f"Документ збережено. Source: {annotation['source']}")

    finally:
        repo.close()


if __name__ == "__main__":
    main()