# News Parser → ChatGPT → Google Sheets

Парсер новостей из разных источников (сайты, RSS, Telegram-каналы), который
нормализует каждую публикацию через **ChatGPT API (OpenAI)** и записывает
результат в **Google Sheets**.

Парсер не просто складывает сырой текст — он использует ChatGPT как слой
интеллектуальной обработки: очищает текст, формирует заголовок и краткое
описание, определяет категорию, важность и решает, является ли публикация
новостью.

---

## Содержание

- [Как это работает](#как-это-работает)
- [Структура проекта](#структура-проекта)
- [Быстрый старт](#быстрый-старт-локально)
- [Настройка OpenAI API](#настройка-openai-api)
- [Настройка Google Sheets API](#настройка-google-sheets-api)
- [Настройка Telegram API](#настройка-telegram-api)
- [Как добавить источник](#как-добавить-источник)
- [Режимы запуска и контроль расходов](#режимы-запуска-и-контроль-расходов)
- [Ежедневный запуск](#ежедневный-запуск)
- [Структура таблицы](#структура-таблицы-google-sheets)
- [Дедупликация](#дедупликация)
- [Частые проблемы](#частые-проблемы)

---

## Как это работает

```
Источники (HTML / RSS / Telegram)
        │
        ▼
  Сырые публикации (единый raw-объект)
        │
        ▼
  Дедупликация ДО обработки  ──► дубль? пропускаем (не тратим OpenAI)
        │
        ▼
  ChatGPT API (нормализация в строгий JSON, валидация Pydantic)
        │
        ├──► не новость ──► лист "Skipped"
        │
        ▼
  Дедупликация ПОСЛЕ обработки
        │
        ▼
  Google Sheets: лист "News" (+ "Raw" для аудита)
```

---

## Структура проекта

```
.
├── config/
│   ├── sources.py          # конфиг источников — сюда добавляете сайты/RSS/каналы
│   └── settings.py         # чтение всех настроек из .env
├── parsers/
│   ├── base.py             # единый формат сырой публикации
│   ├── html_parser.py      # парсер сайтов (requests + BeautifulSoup)
│   ├── rss_parser.py       # парсер RSS (feedparser)
│   └── telegram_parser.py  # парсер Telegram-каналов (Telethon)
├── processors/
│   └── openai_processor.py # обработка через ChatGPT API + JSON Schema + Pydantic
├── storage/
│   └── google_sheets.py    # запись в Google Sheets (gspread)
├── utils/
│   ├── deduplication.py    # дедупликация до и после обработки
│   └── logging.py          # логирование и сводка по прогону
├── main.py                 # главный запуск (весь пайплайн)
├── requirements.txt
├── .env.example            # шаблон настроек
└── .github/workflows/
    └── daily_parser.yml    # ежедневный запуск через GitHub Actions
```

---

## Быстрый старт (локально)

Нужен **Python 3.11+**.

```bash
# 1. Клонируем и заходим в папку
git clone <repo-url>
cd <repo>

# 2. Виртуальное окружение
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Зависимости
pip install -r requirements.txt

# 4. Настройки
cp .env.example .env
# затем откройте .env и заполните ключи (см. инструкции ниже)

# 5. Проверка БЕЗ расходов: парсинг без OpenAI и без записи в таблицу
#    (поставьте в .env: SKIP_OPENAI=true и DRY_RUN=true), затем:
python main.py
```

Когда всё настроено — уберите `DRY_RUN`/`SKIP_OPENAI` и запустите `python main.py`.

---

## Настройка OpenAI API

1. Зарегистрируйтесь на <https://platform.openai.com> и пополните баланс.
2. Создайте ключ: **API keys → Create new secret key**.
3. Скопируйте ключ в `.env`:
   ```env
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-4.1-mini
   OPENAI_MAX_INPUT_CHARS=12000
   ```
4. Модель меняется через `OPENAI_MODEL` без правки кода. `gpt-4.1-mini` — дешёвый
   и достаточный для нормализации новостей вариант.

Код использует **Structured Outputs**: модель обязана вернуть JSON строго по
схеме (`processors/openai_processor.py`, класс `NewsItem`), ответ дополнительно
валидируется через Pydantic. Если API недоступен — публикация не теряется,
сохраняется fallback-версия и помечается как нерелевантная.

---

## Настройка Google Sheets API

Нужен **сервисный аккаунт** Google (робот, от чьего имени пишем в таблицу).

1. Откройте <https://console.cloud.google.com> и создайте проект (или выберите
   существующий).
2. Включите два API: **Google Sheets API** и **Google Drive API**
   (APIs & Services → Library → найти → Enable).
3. Создайте сервисный аккаунт: **APIs & Services → Credentials →
   Create Credentials → Service account**. Имя любое.
4. У созданного аккаунта откройте вкладку **Keys → Add key → Create new key →
   JSON**. Скачается JSON-файл с ключом.
5. Положите этот файл в корень проекта как `service_account.json` и укажите в `.env`:
   ```env
   GOOGLE_SERVICE_ACCOUNT_FILE=service_account.json
   ```
   (Для GitHub Actions вместо файла используйте `GOOGLE_SERVICE_ACCOUNT_JSON` —
   весь JSON одной строкой, см. раздел про Actions.)
6. Создайте Google-таблицу. Из её ссылки возьмите ID:
   `https://docs.google.com/spreadsheets/d/`**`ЭТОТ_ID`**`/edit` → в `.env`:
   ```env
   GOOGLE_SHEET_ID=ЭТОТ_ID
   ```
7. **Важно:** откройте таблицу и нажмите **Share / Поделиться**, добавьте e-mail
   сервисного аккаунта (он в JSON-файле, поле `client_email`, вид
   `...@...iam.gserviceaccount.com`) с правами **Editor**. Без этого робот не
   сможет писать в таблицу.

Листы `News`, `Raw`, `Skipped` и их заголовки создаются автоматически при первом
запуске.

---

## Настройка Telegram API

Используется **Telethon** (не Bot API), потому что бот не может читать
произвольные каналы, если его туда не добавили. Telethon работает как обычный
клиент Telegram и читает любые **публичные** каналы по username.

1. Откройте <https://my.telegram.org> → **API development tools**.
2. Создайте приложение — получите **api_id** и **api_hash**.
3. Заполните `.env`:
   ```env
   TELEGRAM_API_ID=123456
   TELEGRAM_API_HASH=ваш_hash
   TELEGRAM_PHONE=+994501234567
   TELEGRAM_POST_LIMIT=30
   TELEGRAM_SESSION_NAME=telegram_session
   ```
4. **Первый запуск только локально и интерактивно** — Telethon запросит код
   подтверждения из Telegram (и пароль 2FA, если включён) и создаст
   session-файл `telegram_session.session`:
   ```bash
   python main.py
   ```
   После этого код больше не спрашивается.

### Безопасная работа с session-файлом

- Session-файл = доступ к вашему аккаунту Telegram. **Никогда не коммитьте его**
  (он уже в `.gitignore`).
- Для **GitHub Actions** session-файл нельзя ввести интерактивно. Поэтому:
  1. Создайте session локально (как выше).
  2. Закодируйте файл в base64 и положите содержимое в секрет
     `TELEGRAM_SESSION_B64`:
     ```bash
     base64 -w0 telegram_session.session     # Linux
     base64 telegram_session.session         # macOS (без -w0)
     ```
  3. Workflow сам восстановит файл перед запуском (см. `daily_parser.yml`).
- Если Telegram-источники не нужны — просто не добавляйте их в `config/sources.py`,
  переменные Telegram можно оставить пустыми.

---

## Как добавить источник

Все источники описываются в **`config/sources.py`** в списке `SOURCES`.
Менять код не нужно — только дописать словарь.

### Как добавить сайт (HTML)

```python
{
    "name": "Название сайта",
    "url": "https://example.com/news",   # страница со списком новостей
    "type": "html",
    "category_hint": "авто, классифайд",
}
```

Универсальный парсер сам найдёт ссылки на новости, зайдёт в каждую и вытащит
заголовок, дату и текст. Если на конкретном сайте парсинг неточный — добавьте
**кастомные CSS-селекторы** (необязательные поля):

```python
{
    "name": "Сложный сайт",
    "url": "https://example.com/news",
    "type": "html",
    "category_hint": "e-commerce, маркетплейс",
    "link_selector":  "a.article-link",    # как находить ссылки на новости
    "title_selector": "h1.article-title",  # заголовок внутри статьи
    "date_selector":  "time.published",    # дата
    "text_selector":  "div.article-body",  # тело статьи
}
```

Так можно постепенно добавлять точные правила под отдельные сайты, не ломая
универсальный парсер для остальных.

### Как добавить RSS

```python
{
    "name": "RSS источник",
    "url": "https://example.com/rss",
    "type": "rss",
    "category_hint": "недвижимость",
}
```

### Как добавить Telegram-канал

```python
{
    "name": "Telegram канал",
    "url": "https://t.me/channel_name",
    "username": "channel_name",   # без @
    "type": "telegram",
    "category_hint": "маркетплейс, C2C",
}
```

---

## Режимы запуска и контроль расходов

Управляются через `.env`:

| Переменная | Назначение |
|---|---|
| `DRY_RUN=true` | Собрать и залогировать публикации, но **ничего не писать** в Google Sheets. |
| `SKIP_OPENAI=true` | Не вызывать ChatGPT — проверить только парсинг (без расходов на OpenAI). |
| `MAX_ITEMS_PER_RUN=100` | Максимум публикаций за один запуск (0 = без ограничения). |
| `OPENAI_MAX_INPUT_CHARS=12000` | Обрезка длины текста, отправляемого в модель. |

Дополнительно расходы экономятся за счёт дедупликации: дубли не отправляются
в OpenAI вообще.

Рекомендуемый порядок проверки нового источника:
1. `SKIP_OPENAI=true` + `DRY_RUN=true` → убедиться, что парсинг находит публикации.
2. `SKIP_OPENAI=false` + `DRY_RUN=true` → проверить нормализацию ChatGPT в логах.
3. Снять оба флага → боевой запуск с записью в таблицу.

---

## Ежедневный запуск

### Вариант 1. GitHub Actions (рекомендуется)

Файл `.github/workflows/daily_parser.yml` уже настроен на запуск раз в день
(06:00 UTC) и кнопку ручного запуска.

1. Зайдите в репозиторий → **Settings → Secrets and variables → Actions**.
2. Добавьте секреты (имена как в `.env`):
   `GOOGLE_SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON` (весь JSON одной строкой),
   `OPENAI_API_KEY`, `OPENAI_MODEL`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`,
   `TELEGRAM_PHONE`, `TELEGRAM_SESSION_B64` (см. раздел Telegram).
3. Поменять время — отредактируйте `cron` в workflow.

### Вариант 2. Локально через cron / Task Scheduler

**Linux/macOS (cron)** — запуск каждый день в 09:00:
```bash
crontab -e
# добавьте строку (путь подставьте свой):
0 9 * * * cd /path/to/project && /path/to/project/.venv/bin/python main.py >> parser.log 2>&1
```

**Windows (Task Scheduler):** создайте задачу → триггер «ежедневно» → действие
«Запуск программы»: укажите `python.exe` из `.venv` и аргумент `main.py`, рабочая
папка — корень проекта.

---

## Структура таблицы Google Sheets

**Лист `News`** (карточки новостей для дайджеста АВИ): `collected_at`,
`source_type`, `source`, `original_url`, `title`, `company`, `published_at`,
`priority` (A/B/C), `relevance_topic`, `vertical`, `what_happened`,
`how_it_works`, `audience`, `why_for_avi`, `figures`, `summary`,
`full_text_clean`, `tags`, `companies`, `language`, `is_relevant`, `hash`,
`telegram_message_id`.

> Колонки `what_happened` / `how_it_works` / `audience` / `why_for_avi` /
> `figures` — это буллеты карточки из шаблона дайджеста АВИ. `relevance_topic` —
> одно из направлений (AI для покупателя, AI для продавца, marketplace/UX,
> вертикали, trust & safety, бизнес-модель, бенчмаркинг конкурентов, другое).

**Лист `Raw`** (все сырые публикации, для аудита): `collected_at`, `source_type`,
`source`, `url`, `raw_title`, `raw_text`, `published_at`, `telegram_message_id`,
`hash`.

**Лист `Skipped`** (нерелевантные публикации): `collected_at`, `source_type`,
`source`, `url`, `raw_text`, `reason`, `hash`.

---

## Дедупликация

**До обработки** (экономим вызовы OpenAI) публикация пропускается, если:
- её `url` уже есть в таблице;
- пара `telegram_message_id + source` уже есть;
- `hash(raw_text + source)` уже есть.

**После обработки** новость не добавляется, если:
- тройка `title + source + published_at` уже есть;
- очищенный текст почти совпадает с уже существующей новостью (коэффициент
  Жаккара ≥ 0.85).

Перед добавлением новых строк код **читает уже существующие записи** из листов
`News` и `Raw` и сверяется с ними — дубли между запусками тоже отлавливаются.

---

## Частые проблемы

| Симптом | Причина / решение |
|---|---|
| `Не заданы учётные данные Google` | Не заполнен `GOOGLE_SERVICE_ACCOUNT_FILE`/`JSON` в `.env`. |
| `PermissionError` / 403 от Google | Не дали сервисному аккаунту доступ к таблице (Share → Editor). |
| `Не задан OPENAI_API_KEY` | Заполните ключ в `.env` или поставьте `SKIP_OPENAI=true`. |
| Telethon просит код в Actions | Нет `TELEGRAM_SESSION_B64`. Создайте session локально и положите в секрет. |
| HTML-парсер находит мало новостей | Добавьте кастомные селекторы для сайта в `config/sources.py`. |
| Нужно проверить без расходов | Поставьте `DRY_RUN=true` и `SKIP_OPENAI=true`. |

---

## Лицензия

Используйте свободно в своих проектах.
