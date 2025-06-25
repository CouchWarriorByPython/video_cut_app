from passlib.context import CryptContext

# Єдиний контекст для всього проєкту
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def is_password_strong(password: str) -> tuple[bool, str]:
    """
    Check if password meets strength requirements

    Returns (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Пароль повинен містити мінімум 8 символів"

    if not any(c.isupper() for c in password):
        return False, "Пароль повинен містити хоча б одну велику літеру"

    if not any(c.islower() for c in password):
        return False, "Пароль повинен містити хоча б одну малу літеру"

    if not any(c.isdigit() for c in password):
        return False, "Пароль повинен містити хоча б одну цифру"

    return True, ""