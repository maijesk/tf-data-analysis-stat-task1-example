"""
Парсер публичных Telegram-каналов через Telethon (НЕ Bot API).

Почему Telethon, а не Bot API:
    Бот не может читать произвольный канал, если его туда не добавили
    администратором. Telethon работает от лица пользователя (как обычный
    клиент Telegram) и читает любые ПУБЛИЧНЫЕ каналы по username.

Авторизация:
    Нужны TELEGRAM_API_ID, TELEGRAM_API_HASH и TELEGRAM_PHONE (см. .env).
    При первом запуске Telethon попросит код подтверждения из Telegram и
    создаст session-файл. Дальше код больше не спрашивается.
"""

from telethon.sync import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    UsernameNotOccupiedError,
    UsernameInvalidError,
)

from config import settings
from parsers.base import make_raw_item
from utils.logging import get_logger

log = get_logger(__name__)

# Один клиент на весь процесс — переиспользуем для всех каналов.
_client: TelegramClient | None = None


def _get_client() -> TelegramClient:
    """Создать (или вернуть существующий) подключённый Telethon-клиент."""
    global _client
    if _client is not None:
        return _client

    if not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH:
        raise RuntimeError(
            "Не заданы TELEGRAM_API_ID / TELEGRAM_API_HASH в .env — "
            "Telegram-источники работать не будут."
        )

    client = TelegramClient(
        settings.TELEGRAM_SESSION_NAME,
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH,
    )
    # start() сам авторизует по номеру телефона и переиспользует session-файл.
    client.start(phone=settings.TELEGRAM_PHONE or None)
    _client = client
    log.info("Telegram: клиент авторизован (session: %s)", settings.TELEGRAM_SESSION_NAME)
    return client


def _channel_username(source: dict) -> str:
    """Достать username канала из конфига (поле username или из ссылки t.me/...)."""
    username = (source.get("username") or "").strip().lstrip("@")
    if username:
        return username
    # Вытаскиваем из url вида https://t.me/channel_name
    url = source.get("url", "")
    if "t.me/" in url:
        return url.split("t.me/")[-1].strip("/").lstrip("@")
    return ""


def parse(source: dict) -> list[dict]:
    """
    Прочитать последние посты публичного Telegram-канала.

    Количество постов берётся из TELEGRAM_POST_LIMIT в .env.
    Возвращает список сырых публикаций.
    """
    username = _channel_username(source)
    name = source.get("name", username)
    if not username:
        raise RuntimeError(f"Для Telegram-источника '{name}' не указан username")

    client = _get_client()
    limit = settings.TELEGRAM_POST_LIMIT
    category_hint = source.get("category_hint", "")

    log.info("Telegram: читаю канал @%s (последние %s постов)", username, limit)

    try:
        entity = client.get_entity(username)
        messages = client.get_messages(entity, limit=limit)
    except (UsernameNotOccupiedError, UsernameInvalidError):
        raise RuntimeError(f"Канал @{username} не найден (неверный username)")
    except ChannelPrivateError:
        raise RuntimeError(f"Канал @{username} закрытый или недоступен")

    items: list[dict] = []
    for msg in messages:
        text = (msg.message or "").strip()
        if not text:
            # Пост без текста (только фото/видео) — нормализовать нечего, пропускаем.
            continue

        post_url = f"https://t.me/{username}/{msg.id}"
        published = msg.date.isoformat() if msg.date else ""
        # Первая строка поста — неплохой "сырой заголовок".
        raw_title = text.split("\n", 1)[0][:200]

        items.append(
            make_raw_item(
                source_type="telegram",
                source_name=name,
                source_url=source.get("url", f"https://t.me/{username}"),
                raw_title=raw_title,
                raw_text=text,
                published_at=published,
                url=post_url,
                telegram_message_id=msg.id,
                category_hint=category_hint,
            )
        )

    log.info("Telegram: @%s — собрано %s постов с текстом", username, len(items))
    return items


def close() -> None:
    """Корректно закрыть Telegram-клиент в конце работы."""
    global _client
    if _client is not None:
        try:
            _client.disconnect()
        except Exception:  # noqa: BLE001
            pass
        _client = None
