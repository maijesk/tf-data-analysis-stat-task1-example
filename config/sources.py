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
универсальный парсер. Если конкретный сайт парсится плохо (мало новостей
или мусорный текст), добавьте под него селекторы:

    "link_selector":  "a.article-link",   # как находить ссылки на новости
    "title_selector": "h1.article-title", # заголовок внутри статьи
    "date_selector":  "time.published",   # дата
    "text_selector":  "div.article-body", # тело статьи

ВНИМАНИЕ: часть источников ниже — это SPA / закрытые newsroom / зарубежные
сайты с защитой от ботов. Универсальный HTML-парсер достанет не все из них.
Рекомендуемый порядок: запустить с SKIP_OPENAI=true и DRY_RUN=true, по логам
посмотреть, какие источники реально отдают новости, и для проблемных добавить
RSS (если есть) или кастомные селекторы.
"""

SOURCES = [
    # ====================================================================
    #  РОССИЙСКИЕ КЛАССИФАЙДЫ И ВЕРТИКАЛИ (авто / недвижимость / работа)
    # ====================================================================
    {"name": "Авто.ру Журнал", "url": "https://auto.ru/mag/", "type": "html", "category_hint": "авто, классифайд, ИИ-подбор"},
    {"name": "Новости Авто.ру", "url": "https://auto.ru/mag/tag/autoru/", "type": "html", "category_hint": "авто, продуктовые запуски Авто.ру"},
    {"name": "Drom Новости", "url": "https://news.drom.ru/", "type": "html", "category_hint": "авто, классифайд, рынок б/у"},
    {"name": "Циан Журнал", "url": "https://www.cian.ru/journal/", "type": "html", "category_hint": "недвижимость, поиск объектов"},
    {"name": "Циан Press Center", "url": "https://press.cian.ru/", "type": "html", "category_hint": "недвижимость, запуски Циан"},
    {"name": "Домклик Журнал", "url": "https://journal.domclick.ru/", "type": "html", "category_hint": "недвижимость, ипотека"},
    {"name": "Яндекс Недвижимость Журнал", "url": "https://realty.yandex.ru/journal/", "type": "html", "category_hint": "недвижимость, AI-поиск жилья"},
    {"name": "hh.ru статьи", "url": "https://hh.ru/articles", "type": "html", "category_hint": "работа, поиск вакансий"},
    {"name": "hh.ru исследования", "url": "https://hh.ru/article/research", "type": "html", "category_hint": "работа, рынок труда"},
    {"name": "SuperJob исследования", "url": "https://www.superjob.ru/research/", "type": "html", "category_hint": "работа, зарплаты, job matching"},
    {"name": "Работа.ру пресс-центр", "url": "https://www.rabota.ru/press", "type": "html", "category_hint": "работа, фичи поиска"},

    # ====================================================================
    #  РОССИЙСКИЕ МАРКЕТПЛЕЙСЫ И E-COMMERCE
    # ====================================================================
    {"name": "VK пресс-релизы", "url": "https://vk.company/ru/press/releases/", "type": "html", "category_hint": "VK, Юла, социальная коммерция"},
    {"name": "Ozon Seller Edu", "url": "https://seller-edu.ozon.ru/", "type": "html", "category_hint": "маркетплейс, инструменты продавцов"},
    {"name": "Ozon Seller News", "url": "https://seller.ozon.ru/news/", "type": "html", "category_hint": "маркетплейс, обновления"},
    {"name": "Wildberries для продавцов", "url": "https://seller.wildberries.ru/", "type": "html", "category_hint": "маркетплейс, seller tools"},
    {"name": "Wildberries Developers", "url": "https://dev.wildberries.ru/", "type": "html", "category_hint": "маркетплейс, API, автоматизация"},
    {"name": "Яндекс Маркет для продавцов", "url": "https://partner.market.yandex.ru/", "type": "html", "category_hint": "маркетплейс, инструменты продавцов"},
    {"name": "Яндекс Маркет блог", "url": "https://market.yandex.ru/journal", "type": "html", "category_hint": "e-commerce, поиск, рекомендации"},
    {"name": "Retail.ru", "url": "https://www.retail.ru/", "type": "html", "category_hint": "e-commerce, ритейл"},
    {"name": "E-pepper", "url": "https://e-pepper.ru/news/", "type": "html", "category_hint": "маркетплейсы, e-commerce-фичи"},
    {"name": "New Retail", "url": "https://new-retail.ru/", "type": "html", "category_hint": "ритейл, AI, customer experience"},

    # ====================================================================
    #  РОССИЙСКИЕ IT / БИЗНЕС / ПРОДУКТОВЫЕ МЕДИА
    # ====================================================================
    {"name": "vc.ru", "url": "https://vc.ru/", "type": "html", "category_hint": "продуктовые запуски, стартапы"},
    {"name": "RB.ru", "url": "https://rb.ru/", "type": "html", "category_hint": "стартапы, AI, бизнес-модели"},
    {"name": "CNews", "url": "https://www.cnews.ru/", "type": "html", "category_hint": "IT, AI, внедрения"},
    {"name": "TAdviser", "url": "https://www.tadviser.ru/", "type": "html", "category_hint": "AI-проекты, IT-рынок"},
    {"name": "Sostav", "url": "https://www.sostav.ru/", "type": "html", "category_hint": "маркетинг, продуктовые кампании"},
    {"name": "Plusworld", "url": "https://plusworld.ru/", "type": "html", "category_hint": "платежи, финтех, agentic commerce"},

    # ====================================================================
    #  ЗАРУБЕЖНЫЕ МАРКЕТПЛЕЙСЫ И C2C / RESALE
    # ====================================================================
    {"name": "eBay Newsroom", "url": "https://www.ebayinc.com/stories/news/", "type": "html", "category_hint": "marketplace, AI, seller tools"},
    {"name": "eBay Innovation", "url": "https://innovation.ebayinc.com/", "type": "html", "category_hint": "AI/ML, поиск, рекомендации"},
    {"name": "Etsy News", "url": "https://www.etsy.com/news", "type": "html", "category_hint": "C2C, handmade, seller tools"},
    {"name": "Vinted Newsroom", "url": "https://company.vinted.com/newsroom/", "type": "html", "category_hint": "resale, trust, доставка, C2C"},
    {"name": "Depop News", "url": "https://news.depop.com/", "type": "html", "category_hint": "fashion resale, AI-листинг"},
    {"name": "Mercari News", "url": "https://about.mercari.com/en/press/news/", "type": "html", "category_hint": "C2C, AI-listing, безопасные сделки"},
    {"name": "Poshmark Newsroom", "url": "https://newsroom.poshmark.com/", "type": "html", "category_hint": "fashion resale, social commerce"},
    {"name": "Meta Newsroom", "url": "https://about.fb.com/news/", "type": "html", "category_hint": "Facebook Marketplace, AI-фичи"},
    {"name": "OfferUp Blog", "url": "https://blog.offerup.com/", "type": "html", "category_hint": "local classifieds, trust, авто"},
    {"name": "Carousell Press", "url": "https://press.carousell.com/", "type": "html", "category_hint": "C2C, AI-first marketplace"},
    {"name": "Craigslist Blog", "url": "https://blog.craigslist.org/", "type": "html", "category_hint": "локальные объявления, UX-паттерны"},

    # ====================================================================
    #  ЗАРУБЕЖНАЯ НЕДВИЖИМОСТЬ / АВТО / РАБОТА
    # ====================================================================
    {"name": "Zillow Newsroom", "url": "https://www.zillowgroup.com/news/", "type": "html", "category_hint": "недвижимость, AI-поиск, home discovery"},
    {"name": "Realtor.com News", "url": "https://news.realtor.com/", "type": "html", "category_hint": "недвижимость, buyer journey"},
    {"name": "Rightmove News", "url": "https://www.rightmove.co.uk/news/", "type": "html", "category_hint": "недвижимость UK, поиск"},
    {"name": "Autotrader News", "url": "https://www.autotrader.com/car-news", "type": "html", "category_hint": "авто, обзоры, сравнение"},
    {"name": "Cars.com News", "url": "https://www.cars.com/news/", "type": "html", "category_hint": "авто, dealer tools, сравнение"},
    {"name": "Indeed Hiring Lab", "url": "https://www.hiringlab.org/", "type": "html", "category_hint": "job market, matching, AI в найме"},
    {"name": "LinkedIn Talent Blog", "url": "https://www.linkedin.com/business/talent/blog", "type": "html", "category_hint": "AI в работе, job matching"},

    # ====================================================================
    #  ГЛОБАЛЬНЫЙ E-COMMERCE / AI SHOPPING / АССИСТЕНТЫ
    # ====================================================================
    {"name": "Amazon Retail News", "url": "https://www.aboutamazon.com/news/retail", "type": "html", "category_hint": "Rufus, AI shopping, рекомендации"},
    {"name": "Walmart Newsroom", "url": "https://corporate.walmart.com/news", "type": "html", "category_hint": "AI shopping, retail UX"},
    {"name": "Shopify Changelog", "url": "https://changelog.shopify.com/", "type": "html", "category_hint": "merchant tools, checkout, AI для продавцов"},
    {"name": "Google Shopping Blog", "url": "https://blog.google/products/shopping/", "type": "html", "category_hint": "AI shopping, визуальный поиск, product discovery"},
    {"name": "OpenAI News", "url": "https://openai.com/news/", "type": "html", "category_hint": "shopping agents, ChatGPT commerce, ассистенты"},

    # ====================================================================
    #  СИГНАЛЬНЫЕ ИСТОЧНИКИ (ранние UX / AI бенчмарки)
    # ====================================================================
    {"name": "Product Hunt — AI", "url": "https://www.producthunt.com/categories/artificial-intelligence", "type": "html", "category_hint": "AI-продукты, ранние запуски"},
    {"name": "Marketplace Pulse", "url": "https://www.marketplacepulse.com/", "type": "html", "category_hint": "маркетплейсы, аналитика"},
    {"name": "Baymard Institute", "url": "https://baymard.com/blog", "type": "html", "category_hint": "UX-исследования, бенчмарки"},
]
