"""
Обработка сырых публикаций через ChatGPT API (OpenAI).

Что делает модуль:
    * принимает raw-объект публикации;
    * отправляет его в OpenAI с жёсткой JSON Schema (Structured Outputs);
    * получает строго структурированный JSON;
    * валидирует ответ через Pydantic;
    * при ошибке API НЕ роняет процесс, а возвращает fallback-версию.

Модель и лимиты настраиваются через .env (OPENAI_MODEL, OPENAI_MAX_INPUT_CHARS).
"""

import json
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from config import settings
from utils.logging import get_logger

log = get_logger(__name__)

# Допустимые категории — модель обязана выбрать одну из них.
CATEGORIES = [
    "банки",
    "финтех",
    "инвестиции",
    "платежи",
    "карты",
    "кредиты",
    "страхование",
    "e-commerce",
    "технологии",
    "regulation",
    "другое",
]

SYSTEM_PROMPT = """\
Ты обрабатываешь сырые публикации из сайтов, RSS и Telegram-каналов.
Твоя задача — понять, является ли публикация новостью, очистить её от мусора и привести к единому формату.

Правила:
- Не выдумывай факты.
- Используй только информацию из переданного текста.
- Если данных нет, оставляй поле пустым.
- Не добавляй внешние знания.
- Не пересказывай слишком длинно.
- Заголовок должен быть коротким и понятным.
- Summary — 1-2 предложения.
- Категорию выбирай только из списка:
  банки, финтех, инвестиции, платежи, карты, кредиты, страхование, e-commerce, технологии, regulation, другое.
- Importance:
  low — локальная или малозначимая новость;
  medium — новость важна для рынка или отдельного крупного игрока;
  high — стратегически важная новость, крупная сделка, запуск большого продукта, regulation, сильное влияние на рынок.
- Если публикация не является новостью (реклама, опрос, чат, объявление без новостной ценности),
  поставь is_relevant_news = false и кратко объясни причину в поле reason.
"""


# --------------------------------------------------------------------------- #
# Pydantic-модель ответа = одновременно валидация и источник JSON Schema.
# --------------------------------------------------------------------------- #
class NewsItem(BaseModel):
    """Строгая структура ответа ChatGPT для одной публикации."""

    is_relevant_news: bool = Field(description="Является ли публикация новостью")
    title: str = Field(default="", description="Краткий заголовок новости")
    published_at: str = Field(default="", description="Дата в ISO 8601 или пусто")
    summary: str = Field(default="", description="Краткое описание в 1-2 предложения")
    full_text_clean: str = Field(default="", description="Очищенный текст без мусора")
    category: Literal[
        "банки", "финтех", "инвестиции", "платежи", "карты", "кредиты",
        "страхование", "e-commerce", "технологии", "regulation", "другое",
    ] = Field(default="другое")
    tags: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    country: str = Field(default="", description="Страна, если можно определить")
    importance: Literal["low", "medium", "high"] = Field(default="low")
    reason: str = Field(default="", description="Почему это важно / почему нерелевантно")
    language: Literal["ru", "en", "az", "other"] = Field(default="other")


# Один клиент OpenAI на весь процесс.
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Создать (или вернуть) клиент OpenAI."""
    global _client
    if _client is None:
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("Не задан OPENAI_API_KEY в .env")
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def _build_user_message(raw_item: dict) -> str:
    """Собрать текст запроса к модели из raw-объекта (с обрезкой по лимиту)."""
    raw_text = raw_item.get("raw_text", "")
    # Ограничиваем длину — защита от лишних расходов на токены.
    max_chars = settings.OPENAI_MAX_INPUT_CHARS
    if max_chars and len(raw_text) > max_chars:
        raw_text = raw_text[:max_chars]

    parts = [
        f"Тип источника: {raw_item.get('source_type', '')}",
        f"Источник: {raw_item.get('source_name', '')}",
        f"Подсказка категории: {raw_item.get('category_hint', '')}",
        f"Сырой заголовок: {raw_item.get('raw_title', '')}",
        f"Дата (если есть): {raw_item.get('published_at', '')}",
        f"Ссылка: {raw_item.get('url', '')}",
        "",
        "Сырой текст публикации:",
        raw_text,
    ]
    return "\n".join(parts)


def _fallback_news_item(raw_item: dict, reason: str) -> NewsItem:
    """
    Запасная версия новости, если OpenAI недоступен или вернул ошибку.

    Сохраняем сырые данные, чтобы публикация не потерялась. Помечаем как
    нерелевантную, чтобы непроверенное не попало в основную таблицу как факт.
    """
    return NewsItem(
        is_relevant_news=False,
        title=raw_item.get("raw_title", "")[:200],
        published_at=raw_item.get("published_at", ""),
        summary="",
        full_text_clean=raw_item.get("raw_text", ""),
        category="другое",
        reason=f"fallback: {reason}",
        language="other",
    )


def process(raw_item: dict) -> tuple[NewsItem, bool]:
    """
    Обработать одну публикацию через ChatGPT.

    Возвращает кортеж (NewsItem, ok):
        ok == True  — ответ получен и провалидирован;
        ok == False — была ошибка OpenAI, вернулся fallback.

    Никогда не бросает исключение наружу — один сбой не должен ронять прогон.
    """
    try:
        client = _get_client()
        # Structured Outputs: модель обязана вернуть JSON по схеме NewsItem.
        completion = client.beta.chat.completions.parse(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_message(raw_item)},
            ],
            response_format=NewsItem,
            temperature=0,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            # Модель отказалась/не смогла структурировать — fallback.
            refusal = completion.choices[0].message.refusal or "пустой ответ"
            log.warning("OpenAI: пустой parsed-ответ (%s)", refusal)
            return _fallback_news_item(raw_item, refusal), False
        return parsed, True

    except ValidationError as exc:
        log.warning("OpenAI: ответ не прошёл валидацию Pydantic: %s", exc)
        return _fallback_news_item(raw_item, "validation_error"), False
    except Exception as exc:  # noqa: BLE001 — ловим любую ошибку API/сети
        log.warning("OpenAI: ошибка обработки публикации: %s", exc)
        return _fallback_news_item(raw_item, str(exc)), False
