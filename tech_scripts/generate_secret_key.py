# scripts/generate_secret_key.py
import secrets
import base64


def generate_secret_key():
    """Генерує криптографічно стійкий SECRET_KEY для JWT"""
    # Генеруємо 32 байти випадкових даних
    random_bytes = secrets.token_bytes(32)

    # Кодуємо в base64 для зручності використання
    secret_key = base64.urlsafe_b64encode(random_bytes).decode('utf-8')

    return secret_key


if __name__ == "__main__":
    key = generate_secret_key()
    print("Згенерований SECRET_KEY:")
    print(key)
    print("\nСкопіюйте цей ключ у ваш .env файл")
    print("⚠️  ВАЖЛИВО: Зберігайте цей ключ у безпеці і не діліться ним!")