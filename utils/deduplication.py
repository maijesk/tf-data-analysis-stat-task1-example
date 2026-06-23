"""
Дедупликация публикаций — до и после обработки ChatGPT.

Логика хранится в одном месте, чтобы её было легко понять и поддерживать.

ДО обработки (экономим вызовы OpenAI), пропускаем публикацию если:
    * её url уже есть в таблице;
    * пара (telegram_message_id + source) уже есть;
    * hash(raw_text + source) уже есть.

ПОСЛЕ обработки пропускаем новость если:
    * тройка (title + source + published_at) уже есть;
    * очищенный текст почти совпадает с уже существующей новостью.
"""

import hashlib
import re


def make_hash(raw_text: str, source_name: str) -> str:
    """
    Стабильный хэш публикации по сырому тексту и имени источника.

    Используется как уникальный идентификатор строки в таблицах.
    """
    base = f"{(raw_text or '').strip()}|{(source_name or '').strip()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def _normalize_text(text: str) -> str:
    """Привести текст к виду, удобному для сравнения (нижний регистр, без лишних пробелов)."""
    text = (text or "").lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)  # убираем пунктуацию
    return text.strip()


def _similarity(a: str, b: str) -> float:
    """
    Грубая оценка схожести двух текстов по пересечению слов (коэффициент Жаккара).

    Возвращает число от 0.0 (нет общих слов) до 1.0 (полностью совпадают).
    Не требует внешних библиотек и достаточно для отлова почти-дублей.
    """
    set_a = set(_normalize_text(a).split())
    set_b = set(_normalize_text(b).split())
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


class Deduplicator:
    """
    Хранит "отпечатки" уже существующих записей и проверяет новые публикации.

    Перед запуском наполняется данными из Google Sheets (метод from_existing_rows),
    чтобы свериться с тем, что уже записано в таблице ранее.
    """

    # Порог схожести очищенных текстов, выше которого считаем новости дублями.
    SIMILARITY_THRESHOLD = 0.85

    def __init__(self) -> None:
        # Наборы для быстрых проверок ДО обработки.
        self._urls: set[str] = set()
        self._telegram_keys: set[str] = set()  # "message_id|source"
        self._hashes: set[str] = set()
        # Данные для проверок ПОСЛЕ обработки.
        self._title_keys: set[str] = set()  # "title|source|published_at"
        self._clean_texts: list[str] = []

    # ------------------------------------------------------------------ #
    # Наполнение существующими данными из таблицы
    # ------------------------------------------------------------------ #
    def add_existing_news(
        self,
        *,
        url: str = "",
        telegram_message_id: str = "",
        source: str = "",
        hash_value: str = "",
        title: str = "",
        published_at: str = "",
        full_text_clean: str = "",
    ) -> None:
        """Зарегистрировать одну уже существующую новость из листа News."""
        if url:
            self._urls.add(url.strip())
        if telegram_message_id and source:
            self._telegram_keys.add(f"{telegram_message_id}|{source}".strip())
        if hash_value:
            self._hashes.add(hash_value.strip())
        if title and source:
            self._title_keys.add(f"{title}|{source}|{published_at}".strip().lower())
        if full_text_clean:
            self._clean_texts.append(full_text_clean)

    def add_existing_raw(
        self, *, url: str = "", telegram_message_id: str = "",
        source: str = "", hash_value: str = "",
    ) -> None:
        """Зарегистрировать одну уже существующую сырую запись из листа Raw."""
        if url:
            self._urls.add(url.strip())
        if telegram_message_id and source:
            self._telegram_keys.add(f"{telegram_message_id}|{source}".strip())
        if hash_value:
            self._hashes.add(hash_value.strip())

    # ------------------------------------------------------------------ #
    # Проверки ДО обработки ChatGPT
    # ------------------------------------------------------------------ #
    def is_duplicate_raw(self, raw_item: dict) -> bool:
        """
        Вернуть True, если сырую публикацию НЕ нужно обрабатывать (дубль).

        Также помечает её как "виденную" в рамках текущего запуска, чтобы
        не пропустить одинаковые публикации внутри одного прогона.
        """
        url = (raw_item.get("url") or "").strip()
        source = (raw_item.get("source_name") or "").strip()
        tg_id = str(raw_item.get("telegram_message_id") or "").strip()
        raw_hash = raw_item.get("hash") or make_hash(
            raw_item.get("raw_text", ""), source
        )

        if url and url in self._urls:
            return True
        if tg_id and source and f"{tg_id}|{source}" in self._telegram_keys:
            return True
        if raw_hash in self._hashes:
            return True

        # Не дубль — запоминаем, чтобы поймать повтор в этом же запуске.
        if url:
            self._urls.add(url)
        if tg_id and source:
            self._telegram_keys.add(f"{tg_id}|{source}")
        self._hashes.add(raw_hash)
        return False

    # ------------------------------------------------------------------ #
    # Проверки ПОСЛЕ обработки ChatGPT
    # ------------------------------------------------------------------ #
    def is_duplicate_news(
        self, *, title: str, source: str, published_at: str, full_text_clean: str
    ) -> bool:
        """
        Вернуть True, если обработанную новость не нужно добавлять (дубль).

        Регистрирует новость как существующую, если она НЕ дубль.
        """
        title_key = f"{title}|{source}|{published_at}".strip().lower()
        if title and title_key in self._title_keys:
            return True

        for existing in self._clean_texts:
            if _similarity(full_text_clean, existing) >= self.SIMILARITY_THRESHOLD:
                return True

        # Не дубль — запоминаем.
        if title:
            self._title_keys.add(title_key)
        if full_text_clean:
            self._clean_texts.append(full_text_clean)
        return False
