"""
Общие инструменты для всех парсеров.

Главная задача — единый формат "сырой" публикации (raw-объект), который
возвращает любой парсер, независимо от типа источника. Дальше этот объект
уходит в ChatGPT на нормализацию.
"""

from utils.deduplication import make_hash


def make_raw_item(
    *,
    source_type: str,
    source_name: str,
    source_url: str,
    raw_title: str = "",
    raw_text: str = "",
    raw_summary: str = "",
    published_at: str = "",
    url: str = "",
    telegram_message_id: str = "",
    category_hint: str = "",
) -> dict:
    """
    Собрать единый raw-объект публикации.

    Все парсеры обязаны возвращать именно такую структуру — тогда остальной
    код (дедупликация, OpenAI, запись в таблицу) не зависит от типа источника.
    """
    raw_text = (raw_text or "").strip()
    item = {
        "source_type": source_type,
        "source_name": source_name,
        "source_url": source_url,
        "raw_title": (raw_title or "").strip(),
        "raw_text": raw_text,
        "raw_summary": (raw_summary or "").strip(),
        "published_at": (published_at or "").strip(),
        "url": (url or "").strip(),
        "telegram_message_id": str(telegram_message_id or "").strip(),
        "category_hint": (category_hint or "").strip(),
    }
    # Хэш считаем сразу — он нужен и для дедупликации, и для записи в таблицу.
    item["hash"] = make_hash(raw_text, source_name)
    return item
