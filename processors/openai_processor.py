"""
Обработка сырых публикаций через ChatGPT API (OpenAI) под задачу АВИ.

Контекст: бот работает как новостной аналитик продуктовой команды Авито,
развивающей ИИ-ассистента АВИ. Из каждой публикации он должен понять, полезна
ли она для развития АВИ / классифайда / marketplace UX / buyer-seller experience
и AI-фич, и привести её к единому формату дайджеста.

Что делает модуль:
    * принимает raw-объект публикации;
    * отправляет его в OpenAI с жёсткой JSON Schema (Structured Outputs);
    * получает строго структурированный JSON в формате карточки новости;
    * валидирует ответ через Pydantic;
    * при ошибке API НЕ роняет процесс, а возвращает fallback-версию.

Модель и лимиты настраиваются через .env (OPENAI_MODEL, OPENAI_MAX_INPUT_CHARS).
"""

from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from config import settings
from utils.logging import get_logger

log = get_logger(__name__)

# Направления (к чему относится новость) — один из 7 блоков пользы + "другое".
RELEVANCE_TOPICS = [
    "AI для покупателя",       # ИИ-поиск, ассистент, подбор, сравнение, рекомендации
    "AI для продавца",         # автоописание, объявление по фото, цена, автоответы
    "marketplace/UX",          # фильтры, карточка, выдача, отзывы, доставка, оплата, чат
    "вертикали",               # авто, недвижимость, работа, resale, электроника и т.д.
    "trust & safety",          # антифрод, проверка продавца, модерация, верификация
    "бизнес-модель",           # комиссии, продвижение, подписки, монетизация ассистентов
    "бенчмаркинг конкурентов", # запуск фичи у конкурента, изменение клиентского пути
    "другое",
]

# Вертикаль Авито, к которой ближе всего новость.
VERTICALS = [
    "авто", "недвижимость", "работа", "мода/resale",
    "электроника", "запчасти", "услуги", "C2C-товары", "общее",
]

SYSTEM_PROMPT = """\
Ты — новостной аналитик продуктовой команды Авито, которая развивает ИИ-ассистента АВИ.
Тебе на вход приходят сырые публикации из сайтов, RSS и Telegram-каналов.
Твоя задача — понять, полезна ли публикация для развития АВИ, классифайда, marketplace UX,
buyer/seller experience и AI-фич, очистить её от мусора и привести к единому формату карточки.

Отбирай только новости, из которых команда может забрать продуктовый инсайт, конкурентный
сигнал, UX-бенчмарк или идею для гипотезы. Не собирай всё подряд.

Новость ПОЛЕЗНА (is_relevant = true), если относится хотя бы к одному направлению:
1. AI-фичи для покупателя: ИИ-поиск, чат-ассистент, подбор товара/объявления, сравнение
   вариантов, визуальный поиск, рекомендации, объяснение "почему подходит", персонализация.
2. AI-фичи для продавца: автогенерация описания, создание объявления по фото, подсказка цены,
   улучшение фото, автоответы покупателям, модерация, инструменты роста продаж.
3. Классифайд / marketplace / e-commerce UX: новые фильтры, карточка товара/объявления,
   сравнение, избранное, выдача, отзывы, рейтинг продавца, безопасная сделка, доставка,
   оплата, чат покупателя и продавца.
4. Вертикали Авито: авто, недвижимость, работа, мода/resale, электроника, запчасти, услуги, C2C.
5. Trust & Safety: антифрод, проверка продавца, защита покупателя, dispute flow, модерация,
   AI-детект мошенничества, верификация объявлений.
6. Бизнес-модель: новые комиссии, платное продвижение, подписки для продавцов, lead fee,
   transaction fee, AI-премиум, монетизация ассистентов.
7. Бенчмаркинг конкурентов: запуск новой фичи у конкурента, изменение клиентского пути,
   новые метрики, публичные результаты теста, заметное изменение стратегии.

Новость НЕ берём (is_relevant = false), если она:
- просто про скидки, распродажи или промоакции;
- про HR, найм, офисы, награды, благотворительность;
- про финансовые результаты без продуктовых выводов;
- про рекламную кампанию без новой фичи;
- про общий AI без связи с покупкой, продажей, поиском, рекомендациями или маркетплейсами;
- основана только на слухах без нормального источника;
- не даёт понятного вывода для АВИ.

Приоритет (priority):
- "A" — важно: напрямую применимо к АВИ (AI-поиск, AI-сравнение, новый ассистент,
  фича прямого конкурента, сильный UX-бенчмарк);
- "B" — полезно: не про прямого конкурента, но даёт идею для продукта, UX, монетизации
  или trust-сценария;
- "C" — фоново: интересно, но не срочно.
Если is_relevant = false — priority оставь пустым ("").

Правила заполнения полей:
- Не выдумывай факты. Используй только информацию из переданного текста. Внешние знания не добавляй.
- Если данных нет — оставляй поле пустым. Не придумывай цифры, сроки и механику.
- title — в формате "[Компания] запустила / тестирует / обновила [фичу]". Коротко и понятно.
- what_happened — что произошло, 1-2 предложения.
- how_it_works — как работает механика, простым языком.
- audience — для кого: покупатели / продавцы / соискатели / арендодатели / дилеры / бизнес.
- why_for_avi — какой инсайт или бенчмарк может забрать команда АВИ.
- figures — цифры, если есть: цена, метрики, сроки, география, доступность. Если цифр в
  источнике нет — оставь пустым.
- summary — 1-2 предложения, человеческим языком, для быстрого чтения.
- Не используй слова "революционный", "уникальный", "инновационный", если их нет в источнике.
- Пиши коротко и по делу: новость должна читаться за 20-30 секунд.
"""


# --------------------------------------------------------------------------- #
# Pydantic-модель ответа = одновременно валидация и источник JSON Schema.
# Поля повторяют карточку новости в дайджесте АВИ.
# --------------------------------------------------------------------------- #
class NewsItem(BaseModel):
    """Строгая структура ответа ChatGPT для одной публикации (формат карточки АВИ)."""

    is_relevant: bool = Field(description="Полезна ли новость для команды АВИ")
    priority: Literal["A", "B", "C", ""] = Field(
        default="", description="A — важно, B — полезно, C — фоново; пусто если нерелевантно"
    )
    title: str = Field(default="", description="[Компания] запустила/тестирует/обновила [фичу]")
    company: str = Field(default="", description="Главная компания новости")
    published_at: str = Field(default="", description="Дата в ISO 8601 или пусто")

    relevance_topic: Literal[
        "AI для покупателя", "AI для продавца", "marketplace/UX", "вертикали",
        "trust & safety", "бизнес-модель", "бенчмаркинг конкурентов", "другое",
    ] = Field(default="другое", description="Направление, к которому относится новость")
    vertical: Literal[
        "авто", "недвижимость", "работа", "мода/resale",
        "электроника", "запчасти", "услуги", "C2C-товары", "общее",
    ] = Field(default="общее", description="Вертикаль Авито")

    # Буллеты карточки (как в шаблоне дайджеста).
    what_happened: str = Field(default="", description="Что произошло")
    how_it_works: str = Field(default="", description="Как работает")
    audience: str = Field(default="", description="Для кого")
    why_for_avi: str = Field(default="", description="Почему важно для АВИ")
    figures: str = Field(default="", description="Цифры: цена, метрики, сроки, гео (если есть)")

    summary: str = Field(default="", description="Краткое описание в 1-2 предложения")
    full_text_clean: str = Field(default="", description="Очищенный текст без мусора")
    tags: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    language: Literal["ru", "en", "other"] = Field(default="other")
    reason: str = Field(default="", description="Почему нерелевантно / примечание")


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
        f"Подсказка тематики источника: {raw_item.get('category_hint', '')}",
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
    нерелевантную, чтобы непроверенное не попало в основной дайджест как факт.
    """
    return NewsItem(
        is_relevant=False,
        priority="",
        title=raw_item.get("raw_title", "")[:200],
        company="",
        published_at=raw_item.get("published_at", ""),
        relevance_topic="другое",
        vertical="общее",
        summary="",
        full_text_clean=raw_item.get("raw_text", ""),
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
