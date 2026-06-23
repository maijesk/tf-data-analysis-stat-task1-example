"""
Парсер RSS / Atom лент через библиотеку feedparser.

feedparser сам разбирается с разными форматами лент, поэтому код простой.
"""

import feedparser

from parsers.base import make_raw_item
from utils.logging import get_logger

log = get_logger(__name__)


def _entry_date(entry) -> str:
    """Достать дату публикации записи в виде строки (если она есть)."""
    # feedparser кладёт распарсенную дату в published / updated.
    for field in ("published", "updated"):
        value = getattr(entry, field, "") or entry.get(field, "")
        if value:
            return str(value)
    return ""


def _entry_text(entry) -> str:
    """
    Собрать максимально полный текст записи.

    У разных лент текст лежит в разных полях, берём лучшее из доступного.
    """
    # content обычно самый полный.
    if getattr(entry, "content", None):
        parts = [c.get("value", "") for c in entry.content if c.get("value")]
        if parts:
            return "\n".join(parts)
    # summary / description — запасной вариант.
    return entry.get("summary", "") or entry.get("description", "")


def parse(source: dict) -> list[dict]:
    """
    Прочитать RSS-ленту и вернуть список сырых публикаций.

    source — словарь из config/sources.py (ожидается type == "rss").
    """
    url = source["url"]
    name = source.get("name", url)
    category_hint = source.get("category_hint", "")

    log.info("RSS: читаю ленту %s (%s)", name, url)
    feed = feedparser.parse(url)

    # feedparser не бросает исключения — проверяем bozo-флаг сам.
    if getattr(feed, "bozo", 0) and not feed.entries:
        raise RuntimeError(f"Не удалось прочитать RSS-ленту: {feed.get('bozo_exception')}")

    items: list[dict] = []
    for entry in feed.entries:
        raw_text = _entry_text(entry)
        items.append(
            make_raw_item(
                source_type="rss",
                source_name=name,
                source_url=url,
                raw_title=entry.get("title", ""),
                raw_text=raw_text,
                raw_summary=entry.get("summary", ""),
                published_at=_entry_date(entry),
                url=entry.get("link", ""),
                category_hint=category_hint,
            )
        )

    log.info("RSS: %s — найдено %s записей", name, len(items))
    return items
