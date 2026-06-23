"""
Загрузка всех настроек из файла .env в одном месте.

Любой другой модуль импортирует настройки отсюда, а не читает os.environ
напрямую. Это удобно для поддержки: видно все параметры на одном экране.
"""

import os

from dotenv import load_dotenv

# Загружаем переменные из .env в окружение процесса (если файл есть).
load_dotenv()


def _get_bool(name: str, default: bool = False) -> bool:
    """Прочитать булеву переменную окружения ('true'/'1'/'yes' => True)."""
    value = os.getenv(name, "")
    if value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_int(name: str, default: int) -> int:
    """Прочитать целочисленную переменную окружения с защитой от мусора."""
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


# --- Google Sheets ---
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

# --- OpenAI ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
OPENAI_MAX_INPUT_CHARS = _get_int("OPENAI_MAX_INPUT_CHARS", 12000)

# --- Telegram ---
TELEGRAM_API_ID = _get_int("TELEGRAM_API_ID", 0)
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "").strip()
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "").strip()
TELEGRAM_POST_LIMIT = _get_int("TELEGRAM_POST_LIMIT", 30)
TELEGRAM_SESSION_NAME = os.getenv("TELEGRAM_SESSION_NAME", "telegram_session").strip()

# --- Режимы запуска и лимиты ---
MAX_ITEMS_PER_RUN = _get_int("MAX_ITEMS_PER_RUN", 100)
DRY_RUN = _get_bool("DRY_RUN", False)
SKIP_OPENAI = _get_bool("SKIP_OPENAI", False)

# --- Логирование ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()
