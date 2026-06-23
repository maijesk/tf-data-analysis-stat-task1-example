"""
Универсальный парсер новостных сайтов (HTML) через requests + BeautifulSoup.

Идея:
    1. Скачиваем страницу-список новостей.
    2. Находим ссылки на отдельные новости.
    3. Заходим в каждую новость и вытаскиваем title / date / text.
    4. Если у источника заданы кастомные CSS-селекторы — используем их,
       иначе работают универсальные fallback-правила.

ВАЖНО: это базовый универсальный парсер. Он не идеален для всех сайтов,
но даёт рабочую основу. Для конкретного сайта можно задать селекторы прямо
в config/sources.py:

    "link_selector":  "a.article-link"   # как находить ссылки на новости
    "title_selector": "h1.article-title" # где заголовок внутри новости
    "date_selector":  "time"             # где дата
    "text_selector":  "div.article-body" # где тело статьи
"""

from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from parsers.base import make_raw_item
from utils.logging import get_logger

log = get_logger(__name__)

# Притворяемся обычным браузером — многие сайты отклоняют запросы без User-Agent.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 20  # секунд
# Сколько новостей максимум брать с одной страницы-списка (защита от перебора).
MAX_ARTICLES_PER_PAGE = 20


def _fetch(url: str) -> str:
    """Скачать HTML страницы. Бросает исключение при ошибке сети/HTTP."""
    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    # requests иногда неверно угадывает кодировку — доверяем apparent_encoding.
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding
    return response.text


def _same_domain(base_url: str, link: str) -> bool:
    """Проверить, что ссылка ведёт на тот же домен (чтобы не уйти на рекламу)."""
    return urlparse(base_url).netloc == urlparse(link).netloc


def _find_article_links(soup: BeautifulSoup, base_url: str, source: dict) -> list[str]:
    """
    Найти ссылки на отдельные новости на странице-списке.

    Если в конфиге задан link_selector — используем его, иначе эвристика:
    берём ссылки внутри <article>/<h2>/<h3> и достаточно длинные ссылки
    того же домена.
    """
    links: list[str] = []
    seen: set[str] = set()

    custom = source.get("link_selector")
    if custom:
        anchors = soup.select(custom)
    else:
        # Эвристика: заголовки статей обычно лежат в article/h2/h3.
        anchors = soup.select("article a, h2 a, h3 a, a.title, a[rel='bookmark']")
        if not anchors:
            anchors = soup.find_all("a")

    for a in anchors:
        href = a.get("href")
        if not href:
            continue
        full = urljoin(base_url, href.strip())
        # Отбрасываем якоря, mailto, чужие домены и повторы.
        if not full.startswith("http"):
            continue
        if not _same_domain(base_url, full):
            continue
        if full == base_url or full in seen:
            continue
        # Слишком короткий путь — скорее всего раздел, а не статья.
        if len(urlparse(full).path.strip("/")) < 8:
            continue
        seen.add(full)
        links.append(full)
        if len(links) >= MAX_ARTICLES_PER_PAGE:
            break

    return links


def _extract_title(soup: BeautifulSoup, source: dict) -> str:
    """Достать заголовок статьи (кастомный селектор -> og:title -> <h1> -> <title>)."""
    custom = source.get("title_selector")
    if custom:
        node = soup.select_one(custom)
        if node:
            return node.get_text(strip=True)

    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()

    if soup.h1:
        return soup.h1.get_text(strip=True)
    if soup.title:
        return soup.title.get_text(strip=True)
    return ""


def _extract_date(soup: BeautifulSoup, source: dict) -> str:
    """Достать дату публикации из типичных мест разметки."""
    custom = source.get("date_selector")
    if custom:
        node = soup.select_one(custom)
        if node:
            return node.get("datetime", "") or node.get_text(strip=True)

    # Часто дата лежит в мета-тегах или <time datetime="...">.
    for selector, attr in [
        ("meta[property='article:published_time']", "content"),
        ("meta[name='pubdate']", "content"),
        ("meta[itemprop='datePublished']", "content"),
        ("time[datetime]", "datetime"),
    ]:
        node = soup.select_one(selector)
        if node and node.get(attr):
            return node[attr].strip()

    time_tag = soup.find("time")
    if time_tag:
        return time_tag.get_text(strip=True)
    return ""


def _extract_text(soup: BeautifulSoup, source: dict) -> str:
    """
    Достать основной текст статьи.

    С кастомным text_selector берём конкретный блок. Без него — пытаемся
    угадать контейнер статьи, в крайнем случае собираем все абзацы <p>.
    """
    custom = source.get("text_selector")
    if custom:
        node = soup.select_one(custom)
        if node:
            return node.get_text(separator="\n", strip=True)

    # Пробуем типичные контейнеры тела статьи.
    for selector in [
        "article",
        "div.article-body",
        "div.article__text",
        "div.post-content",
        "div.entry-content",
        "main",
    ]:
        node = soup.select_one(selector)
        if node:
            paragraphs = [p.get_text(strip=True) for p in node.find_all("p")]
            text = "\n".join(p for p in paragraphs if p)
            if len(text) > 100:  # достаточно содержательно
                return text

    # Полный fallback: все абзацы на странице.
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
    return "\n".join(p for p in paragraphs if p)


def _parse_article(url: str, source: dict) -> dict | None:
    """Скачать и разобрать одну новость. Вернуть raw-объект или None при ошибке."""
    try:
        html = _fetch(url)
    except Exception as exc:  # noqa: BLE001 — одна статья не должна валить весь источник
        log.warning("HTML: не удалось скачать статью %s: %s", url, exc)
        return None

    soup = BeautifulSoup(html, "lxml")
    title = _extract_title(soup, source)
    text = _extract_text(soup, source)

    if not text:
        log.debug("HTML: пустой текст у статьи %s — пропускаю", url)
        return None

    return make_raw_item(
        source_type="html",
        source_name=source.get("name", source["url"]),
        source_url=source["url"],
        raw_title=title,
        raw_text=text,
        published_at=_extract_date(soup, source),
        url=url,
        category_hint=source.get("category_hint", ""),
    )


def parse(source: dict) -> list[dict]:
    """
    Главная точка входа парсера сайта.

    Возвращает список сырых публикаций со страницы-списка новостей.
    """
    list_url = source["url"]
    name = source.get("name", list_url)

    log.info("HTML: открываю страницу-список %s (%s)", name, list_url)
    list_html = _fetch(list_url)
    soup = BeautifulSoup(list_html, "lxml")

    links = _find_article_links(soup, list_url, source)
    log.info("HTML: %s — найдено %s ссылок на новости", name, len(links))

    items: list[dict] = []
    for link in links:
        article = _parse_article(link, source)
        if article:
            items.append(article)

    log.info("HTML: %s — успешно разобрано %s новостей", name, len(items))
    return items
