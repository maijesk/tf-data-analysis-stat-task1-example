"""
Запись результатов в Google Sheets через gspread + сервисный аккаунт.

В таблице три листа:
    News    — нормализованные релевантные новости;
    Raw     — все сырые публикации (для аудита и отладки);
    Skipped — нерелевантные публикации (is_relevant == false).

Перед записью класс читает уже существующие строки, чтобы:
    * наполнить дедупликатор (свериться с тем, что уже записано);
    * не создавать листы/заголовки повторно.
"""

import json

import gspread
from google.oauth2.service_account import Credentials

from config import settings
from utils.logging import get_logger

log = get_logger(__name__)

# Права доступа: таблицы + диск (gspread открывает файл по ключу).
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Заголовки колонок для каждого листа (порядок важен — он же порядок записи).
# Лист News построен под карточку новости для дайджеста АВИ.
NEWS_HEADERS = [
    "collected_at", "source_type", "source", "original_url", "title", "company",
    "published_at", "priority", "relevance_topic", "vertical",
    "what_happened", "how_it_works", "audience", "why_for_avi", "figures",
    "summary", "full_text_clean", "tags", "companies", "language",
    "is_relevant", "hash", "telegram_message_id",
]
RAW_HEADERS = [
    "collected_at", "source_type", "source", "url", "raw_title",
    "raw_text", "published_at", "telegram_message_id", "hash",
]
SKIPPED_HEADERS = [
    "collected_at", "source_type", "source", "url", "raw_text", "reason", "hash",
]


class GoogleSheetsStorage:
    """Тонкая обёртка над gspread для трёх рабочих листов."""

    def __init__(self) -> None:
        self._gc = self._authorize()
        self._spreadsheet = self._gc.open_by_key(settings.GOOGLE_SHEET_ID)
        self._news_ws = self._ensure_worksheet("News", NEWS_HEADERS)
        self._raw_ws = self._ensure_worksheet("Raw", RAW_HEADERS)
        self._skipped_ws = self._ensure_worksheet("Skipped", SKIPPED_HEADERS)

    # ------------------------------------------------------------------ #
    # Авторизация
    # ------------------------------------------------------------------ #
    @staticmethod
    def _authorize() -> gspread.Client:
        """
        Авторизоваться в Google по сервисному аккаунту.

        Приоритет: GOOGLE_SERVICE_ACCOUNT_JSON (строка) > файл по пути.
        """
        if settings.GOOGLE_SERVICE_ACCOUNT_JSON:
            info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        elif settings.GOOGLE_SERVICE_ACCOUNT_FILE:
            creds = Credentials.from_service_account_file(
                settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
            )
        else:
            raise RuntimeError(
                "Не заданы учётные данные Google: укажите GOOGLE_SERVICE_ACCOUNT_JSON "
                "или GOOGLE_SERVICE_ACCOUNT_FILE в .env"
            )
        if not settings.GOOGLE_SHEET_ID:
            raise RuntimeError("Не задан GOOGLE_SHEET_ID в .env")
        return gspread.authorize(creds)

    def _ensure_worksheet(self, title: str, headers: list[str]):
        """Найти лист по имени или создать его с нужными заголовками."""
        try:
            ws = self._spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = self._spreadsheet.add_worksheet(
                title=title, rows=1000, cols=max(len(headers), 10)
            )
            ws.append_row(headers, value_input_option="RAW")
            log.info("Sheets: создан лист '%s'", title)
            return ws

        # Если лист пустой — проставим заголовки.
        if not ws.get_all_values():
            ws.append_row(headers, value_input_option="RAW")
        return ws

    # ------------------------------------------------------------------ #
    # Чтение существующих данных (для дедупликации)
    # ------------------------------------------------------------------ #
    def load_existing(self, deduplicator) -> None:
        """
        Прочитать существующие строки листов News и Raw и наполнить дедупликатор.

        Так мы сверяемся с тем, что уже записано в таблице в прошлые запуски.
        """
        # --- News ---
        for row in self._news_ws.get_all_records():
            deduplicator.add_existing_news(
                url=str(row.get("original_url", "")),
                telegram_message_id=str(row.get("telegram_message_id", "")),
                source=str(row.get("source", "")),
                hash_value=str(row.get("hash", "")),
                title=str(row.get("title", "")),
                published_at=str(row.get("published_at", "")),
                full_text_clean=str(row.get("full_text_clean", "")),
            )
        # --- Raw --- (ловим публикации, которые уже видели, даже если их отсеяли)
        for row in self._raw_ws.get_all_records():
            deduplicator.add_existing_raw(
                url=str(row.get("url", "")),
                telegram_message_id=str(row.get("telegram_message_id", "")),
                source=str(row.get("source", "")),
                hash_value=str(row.get("hash", "")),
            )
        log.info("Sheets: загружены существующие записи для дедупликации")

    # ------------------------------------------------------------------ #
    # Запись
    # ------------------------------------------------------------------ #
    @staticmethod
    def _join(values: list[str]) -> str:
        """Списки (tags/companies/people) храним в ячейке как строку через запятую."""
        return ", ".join(v for v in (values or []) if v)

    def append_news(self, *, collected_at: str, raw_item: dict, news) -> None:
        """Добавить одну строку в лист News (карточка новости АВИ)."""
        row = [
            collected_at,
            raw_item.get("source_type", ""),
            raw_item.get("source_name", ""),
            raw_item.get("url", ""),
            news.title,
            news.company,
            news.published_at,
            news.priority,
            news.relevance_topic,
            news.vertical,
            news.what_happened,
            news.how_it_works,
            news.audience,
            news.why_for_avi,
            news.figures,
            news.summary,
            news.full_text_clean,
            self._join(news.tags),
            self._join(news.companies),
            news.language,
            "TRUE" if news.is_relevant else "FALSE",
            raw_item.get("hash", ""),
            raw_item.get("telegram_message_id", ""),
        ]
        self._news_ws.append_row(row, value_input_option="RAW")

    def append_raw(self, *, collected_at: str, raw_item: dict) -> None:
        """Добавить одну строку в лист Raw."""
        row = [
            collected_at,
            raw_item.get("source_type", ""),
            raw_item.get("source_name", ""),
            raw_item.get("url", ""),
            raw_item.get("raw_title", ""),
            raw_item.get("raw_text", ""),
            raw_item.get("published_at", ""),
            raw_item.get("telegram_message_id", ""),
            raw_item.get("hash", ""),
        ]
        self._raw_ws.append_row(row, value_input_option="RAW")

    def append_skipped(self, *, collected_at: str, raw_item: dict, reason: str) -> None:
        """Добавить одну строку в лист Skipped (нерелевантная публикация)."""
        row = [
            collected_at,
            raw_item.get("source_type", ""),
            raw_item.get("source_name", ""),
            raw_item.get("url", ""),
            raw_item.get("raw_text", ""),
            reason,
            raw_item.get("hash", ""),
        ]
        self._skipped_ws.append_row(row, value_input_option="RAW")
