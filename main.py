"""
Главный запуск парсера новостей.

Пайплайн одного прогона:
    1. Прочитать источники из config/sources.py.
    2. По каждому источнику собрать сырые публикации (HTML / RSS / Telegram).
       Если один источник упал — логируем и идём дальше.
    3. Дедупликация ДО обработки (сверка с Google Sheets и внутри прогона).
    4. Каждую новую публикацию отправить в ChatGPT на нормализацию.
    5. Дедупликация ПОСЛЕ обработки (по заголовку и почти-дублям текста).
    6. Записать результат в Google Sheets (News / Raw / Skipped).
    7. Напечатать сводку по прогону.

Режимы (через .env):
    DRY_RUN=true     — не писать в Google Sheets, только собрать и залогировать;
    SKIP_OPENAI=true — не вызывать ChatGPT (проверка только парсинга);
    MAX_ITEMS_PER_RUN — ограничение числа публикаций за прогон.

Запуск:
    python main.py
"""

from datetime import datetime, timezone

from config import settings
from config.sources import SOURCES
from parsers import html_parser, rss_parser, telegram_parser
from processors import openai_processor
from processors.openai_processor import NewsItem
from utils.deduplication import Deduplicator
from utils.logging import RunStats, get_logger

log = get_logger("main")

# Сопоставление типа источника с функцией-парсером.
PARSERS = {
    "html": html_parser.parse,
    "rss": rss_parser.parse,
    "telegram": telegram_parser.parse,
}


def _now_iso() -> str:
    """Текущее время в ISO 8601 (UTC) — момент сбора публикации."""
    return datetime.now(timezone.utc).isoformat()


def collect_raw_items(stats: RunStats) -> list[dict]:
    """
    Собрать сырые публикации со всех источников.

    Падение одного источника не останавливает остальные.
    """
    raw_items: list[dict] = []
    stats.sources_total = len(SOURCES)

    for source in SOURCES:
        name = source.get("name", source.get("url", "<без имени>"))
        source_type = source.get("type", "")
        parser = PARSERS.get(source_type)

        if parser is None:
            log.warning("Неизвестный тип источника '%s' у '%s' — пропускаю", source_type, name)
            stats.sources_failed.append(name)
            continue

        try:
            items = parser(source)
            raw_items.extend(items)
            stats.sources_ok += 1
        except Exception as exc:  # noqa: BLE001 — один источник не должен валить прогон
            log.error("Источник '%s' (%s) упал с ошибкой: %s", name, source_type, exc)
            stats.sources_failed.append(name)

    stats.raw_found = len(raw_items)
    log.info("Всего собрано сырых публикаций: %s", len(raw_items))
    return raw_items


def _skip_openai_passthrough(raw_item: dict) -> NewsItem:
    """
    Заглушка вместо ChatGPT при SKIP_OPENAI=true.

    Просто переносит сырые данные без нормализации — чтобы проверить парсинг.
    """
    return NewsItem(
        is_relevant=True,
        priority="C",
        title=raw_item.get("raw_title", "")[:200],
        company="",
        published_at=raw_item.get("published_at", ""),
        relevance_topic="другое",
        vertical="общее",
        summary="",
        full_text_clean=raw_item.get("raw_text", ""),
        reason="SKIP_OPENAI режим — без обработки ChatGPT",
        language="other",
    )


def run() -> None:
    """Выполнить один полный прогон парсера."""
    stats = RunStats()
    log.info("Старт прогона. DRY_RUN=%s, SKIP_OPENAI=%s", settings.DRY_RUN, settings.SKIP_OPENAI)

    # --- 1-2. Сбор сырых публикаций ---
    raw_items = collect_raw_items(stats)

    # --- Подготовка дедупликатора и хранилища ---
    dedup = Deduplicator()
    storage = None
    if not settings.DRY_RUN:
        # Подключаемся к таблице и подгружаем уже существующие записи.
        from storage.google_sheets import GoogleSheetsStorage

        storage = GoogleSheetsStorage()
        storage.load_existing(dedup)
    else:
        log.info("DRY_RUN: пропускаю подключение к Google Sheets")

    collected_at = _now_iso()
    processed_count = 0

    # --- 3-6. Обработка каждой публикации ---
    for raw_item in raw_items:
        # Лимит публикаций за прогон (защита от расходов).
        if settings.MAX_ITEMS_PER_RUN and processed_count >= settings.MAX_ITEMS_PER_RUN:
            log.info("Достигнут лимит MAX_ITEMS_PER_RUN=%s — останавливаюсь", settings.MAX_ITEMS_PER_RUN)
            break

        # --- 3. Дедупликация ДО обработки ---
        if dedup.is_duplicate_raw(raw_item):
            stats.duplicates_skipped += 1
            continue

        # Сырую публикацию всегда сохраняем в лист Raw (аудит).
        if storage is not None:
            storage.append_raw(collected_at=collected_at, raw_item=raw_item)

        # --- 4. Обработка через ChatGPT (или заглушка) ---
        if settings.SKIP_OPENAI:
            news = _skip_openai_passthrough(raw_item)
        else:
            news, ok = openai_processor.process(raw_item)
            stats.sent_to_openai += 1
            if not ok:
                stats.openai_errors += 1

        processed_count += 1

        # --- Нерелевантные публикации -> лист Skipped ---
        if not news.is_relevant:
            log.debug("Нерелевантно: %s", raw_item.get("url", ""))
            if storage is not None:
                storage.append_skipped(
                    collected_at=collected_at,
                    raw_item=raw_item,
                    reason=news.reason or "не является новостью",
                )
                stats.skipped_written += 1
            continue

        stats.relevant_news += 1

        # --- 5. Дедупликация ПОСЛЕ обработки ---
        if dedup.is_duplicate_news(
            title=news.title,
            source=raw_item.get("source_name", ""),
            published_at=news.published_at,
            full_text_clean=news.full_text_clean,
        ):
            stats.duplicates_skipped += 1
            log.debug("Дубль после обработки: %s", news.title)
            continue

        # --- 6. Запись релевантной новости в лист News ---
        if storage is not None:
            storage.append_news(collected_at=collected_at, raw_item=raw_item, news=news)
            stats.rows_written += 1
        else:
            log.info(
                "[DRY_RUN] [%s] %s | %s | %s",
                news.priority or "-", news.relevance_topic, news.vertical, news.title,
            )

    # --- Закрываем Telegram-клиент, если он использовался ---
    telegram_parser.close()

    # --- 7. Сводка ---
    stats.log_summary(log)


if __name__ == "__main__":
    run()
