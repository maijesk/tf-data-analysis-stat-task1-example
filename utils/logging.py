"""
Единая настройка логирования для всего проекта.

Используйте так:

    from utils.logging import get_logger
    log = get_logger(__name__)
    log.info("сообщение")
"""

import logging
import sys

from config import settings

_CONFIGURED = False


def _configure_root_logger() -> None:
    """Настроить корневой логгер один раз за процесс."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.setLevel(level)
    # Убираем дубли хендлеров при повторном вызове.
    root.handlers.clear()
    root.addHandler(handler)

    # Сторонние библиотеки слишком болтливы — приглушаем их.
    for noisy in ("telethon", "urllib3", "httpx", "openai", "gspread"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Вернуть готовый логгер с настроенным форматом."""
    _configure_root_logger()
    return logging.getLogger(name)


class RunStats:
    """
    Простой счётчик статистики прогона.

    В конце запуска main.py печатает сводку: сколько источников обработано,
    сколько публикаций найдено, отправлено в OpenAI, записано и т.д.
    """

    def __init__(self) -> None:
        self.sources_total = 0
        self.sources_ok = 0
        self.sources_failed: list[str] = []
        self.raw_found = 0
        self.sent_to_openai = 0
        self.relevant_news = 0
        self.rows_written = 0
        self.skipped_written = 0
        self.duplicates_skipped = 0
        self.openai_errors = 0

    def log_summary(self, log: logging.Logger) -> None:
        log.info("=" * 60)
        log.info("ИТОГИ ЗАПУСКА")
        log.info("Источников всего:            %s", self.sources_total)
        log.info("Источников успешно:          %s", self.sources_ok)
        log.info("Источников с ошибкой:        %s", len(self.sources_failed))
        if self.sources_failed:
            log.info("  упали: %s", ", ".join(self.sources_failed))
        log.info("Сырых публикаций найдено:    %s", self.raw_found)
        log.info("Отправлено в OpenAI:         %s", self.sent_to_openai)
        log.info("Признано новостями:          %s", self.relevant_news)
        log.info("Строк добавлено в News:      %s", self.rows_written)
        log.info("Строк добавлено в Skipped:   %s", self.skipped_written)
        log.info("Дублей пропущено:            %s", self.duplicates_skipped)
        log.info("Ошибок OpenAI API:           %s", self.openai_errors)
        log.info("=" * 60)
