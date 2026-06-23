"""
Конфигурация источников новостей.

Чтобы добавить новый источник — просто допишите словарь в список SOURCES.
Никакой код менять не нужно.

Поля:
    name          — человекочитаемое название источника (попадёт в таблицу);
    url           — ссылка на страницу / RSS-ленту / Telegram-канал;
    type          — тип источника: "html", "rss" или "telegram";
    category_hint — подсказка категории для ChatGPT (можно оставить "");
    username      — ТОЛЬКО для Telegram: username канала без "@".

Для HTML-источников можно дополнительно указать кастомные CSS-селекторы
(см. parsers/html_parser.py). Это необязательно — без них работает
универсальный парсер.
"""

SOURCES = [
    # --- Пример: обычный новостной сайт (HTML) ---
    {
        "name": "Example Bank News",
        "url": "https://example.com/news",
        "type": "html",
        "category_hint": "банки",
        # Необязательные кастомные селекторы для конкретного сайта:
        # "link_selector": "a.article-link",
        # "title_selector": "h1.article-title",
        # "date_selector": "time.published",
        # "text_selector": "div.article-body",
    },
    # --- Пример: RSS-лента ---
    {
        "name": "Example Fintech RSS",
        "url": "https://example.com/rss",
        "type": "rss",
        "category_hint": "финтех",
    },
    # --- Пример: публичный Telegram-канал ---
    {
        "name": "Example Telegram Channel",
        "url": "https://t.me/channel_name",
        "username": "channel_name",
        "type": "telegram",
        "category_hint": "банковские новости",
    },
]
