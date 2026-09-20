import json
import os
import re
import sys
import base64
import subprocess
import shutil
from datetime import datetime, date, timedelta, timezone
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.stdout.reconfigure(encoding='utf-8')

CONFIG_FILE = "config.json"
APP_VERSION = "16.7.0"
OFFERS_APP_VERSION = "17.0.5"

CURL_BIN = shutil.which("curl.exe") or shutil.which("curl") or "curl"

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

COMMON_WORDS = {
    "and", "the", "for", "with", "from", "slices", "sliced", "natural",
    "roasted", "mixed", "special", "mix", "air", "mild", "fresh", "free",
    "traditional", "style", "pack", "mini", "extra", "whole", "super", "original"
}

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'[\u200b-\u200f\uFEFF\u3164]', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def get_keywords(text):
    text = clean_text(text)
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    cleaned = []
    for w in words:
        if w in COMMON_WORDS:
            continue
        if w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            w = w[:-1]
        cleaned.append(w)
    return set(cleaned)

def extract_unit_price(offer):
    """Извлечение финальной цены за 1 кг или 1 л по акции магазина"""
    pbox = offer.get("priceBox", {})
    item_price = pbox.get("largePartNumeric")

    ppu = offer.get("pricePerUnit") or ""
    m = re.search(r'to\s+([0-9]+[.,][0-9]+)', ppu, re.IGNORECASE)
    if m:
        val = float(m.group(1).replace(",", "."))
        unit = "/л" if "1 l" in ppu.lower() else "/кг"
        return val, unit

    m2 = re.search(r'1\s*(?:kg|l)\s*=\s*([0-9]+[.,][0-9]+)', ppu, re.IGNORECASE)
    if m2:
        val = float(m2.group(1).replace(",", "."))
        unit = "/л" if "1 l" in ppu.lower() else "/кг"
        return val, unit

    desc = clean_text(offer.get("description") or "").lower()
    if item_price:
        if "per kg" in desc or "за кг" in desc:
            return float(item_price), "/кг"
        if "per l" in desc or "за л" in desc:
            return float(item_price), "/л"

    product_ids = offer.get("productIds", [])
    if any(str(pid).startswith("008") for pid in product_ids) and item_price:
        return float(item_price), "/кг"

    pkg = clean_text(offer.get("packaging") or "")
    if item_price:
        if re.search(r'up to \d+\s*kg', pkg, re.IGNORECASE):
            return float(item_price), "/кг"
        mg = re.search(r'(\d+)\s*g\b', pkg, re.IGNORECASE)
        if mg:
            grams = float(mg.group(1))
            if grams > 0:
                return round(float(item_price) / (grams / 1000.0), 2), "/кг"
        mml = re.search(r'(\d+)\s*ml\b', pkg, re.IGNORECASE)
        if mml:
            ml = float(mml.group(1))
            if ml > 0:
                return round(float(item_price) / (ml / 1000.0), 2), "/л"

    return None, ""

def calc_final_unit_price_after_coupon(store_unit_price, coupon_disc_str):
    """Расчет финальной цены за 1 кг/л после наложения персонального купона"""
    if store_unit_price is None:
        return None
    m = re.search(r'([0-9]+)\s*%', coupon_disc_str)
    if m:
        pct = float(m.group(1))
        return round(store_unit_price * (1.0 - pct / 100.0), 2)
    return store_unit_price

def load_config():
    """Загрузка конфигурации из переменной окружения LIDL_CONFIG_JSON или локального config.json"""
    env_cfg = os.environ.get("LIDL_CONFIG_JSON")
    if env_cfg and env_cfg.strip():
        try:
            print("🔑 Конфигурация получена из переменной окружения LIDL_CONFIG_JSON.")
            return json.loads(env_cfg)
        except Exception as e:
            print(f"⚠️ Ошибка парсинга LIDL_CONFIG_JSON из окружения: {e}")

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                print(f"📁 Конфигурация загружена из локального файла {CONFIG_FILE}.")
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Ошибка чтения {CONFIG_FILE}: {e}")

    print(f"❌ Конфигурация не найдена (нет переменной LIDL_CONFIG_JSON и файла {CONFIG_FILE}).")
    return None

def renew_token(refresh_token):
    """Обмен refresh_token на свежий access_token"""
    default_secret = base64.b64encode("LidlPlusNativeClient:secret".encode()).decode()
    cmd = [
        CURL_BIN, "-s", "-X", "POST",
        "https://accounts.lidl.com/connect/token",
        "-H", f"Authorization: Basic {default_secret}",
        "-H", "Content-Type: application/x-www-form-urlencoded",
        "--data", f"grant_type=refresh_token&refresh_token={refresh_token}",
        "--max-time", "15"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0 or not res.stdout:
        raise Exception(f"Ошибка сети при обновлении токена: {res.stderr}")

    data = json.loads(res.stdout)
    if "access_token" not in data:
        raise Exception(f"Не удалось получить access_token: {data.get('error_description', data)}")
    return data["access_token"]

def fetch_promotions(access_token, country, language):
    """Получение персональных купонов через API Lidl Plus"""
    cmd = [
        CURL_BIN, "-s",
        "https://coupons.lidlplus.com/app/api/v2/promotionsList",
        "-H", f"Authorization: Bearer {access_token}",
        "-H", f"App-Version: {APP_VERSION}",
        "-H", "Operating-System: iOS",
        "-H", "App: com.lidl.eci.lidlplus",
        "-H", f"Accept-Language: {language.lower()}",
        "-H", f"Country: {country.upper()}",
        "--max-time", "15"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0 or not res.stdout:
        raise Exception(f"Ошибка сети при запросе купонов: {res.stderr}")

    data = json.loads(res.stdout)
    promotions = []
    for section in data.get("sections", []):
        promotions.extend(section.get("promotions", []))
    return promotions

def activate_promotion(access_token, coupon_id, country, language):
    """Автоматическая активация персонального купона"""
    cmd = [
        CURL_BIN, "-s", "-X", "POST",
        f"https://coupons.lidlplus.com/app/api/v1/promotions/{coupon_id}/activation",
        "-H", f"Authorization: Bearer {access_token}",
        "-H", f"App-Version: {APP_VERSION}",
        "-H", "Operating-System: iOS",
        "-H", "App: com.lidl.eci.lidlplus",
        "-H", f"Accept-Language: {language.lower()}",
        "-H", f"Country: {country.upper()}",
        "-H", "Content-Length: 0",
        "-d", "",
        "--max-time", "15"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return res.returncode == 0

def fetch_daily_savers(country, store_id, language="en"):
    """Получение акций магазина (Daily / Weekly Savers)"""
    cmd = [
        CURL_BIN, "-s",
        f"https://offers.lidlplus.com/app/api/v4/{country.upper()}/{store_id}/offers",
        "-H", f"App-Version: {OFFERS_APP_VERSION}",
        "-H", "Operating-System: iOS",
        "-H", "App: com.lidl.eci.lidlplus",
        "-H", f"Accept-Language: {language.lower()}",
        "--max-time", "15"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0 or not res.stdout:
        print(f"⚠️ Не удалось загрузить акции магазина: {res.stderr}")
        return []

    try:
        data = json.loads(res.stdout)
        return data.get("offers", [])
    except Exception as e:
        print(f"⚠️ Ошибка разбора ответа акций магазина: {e}")
        return []

def process_accounts(config):
    country = config.get("country", "CY")
    language = config.get("language", "EN")
    accounts = config.get("family_accounts", {})

    all_coupons = []

    for name, refresh_token in accounts.items():
        if not refresh_token or refresh_token.startswith("YOUR_REFRESH_TOKEN"):
            print(f"⚠️ Пропущен аккаунт '{name}' (токен не настроен).")
            continue

        print(f"🔄 Обработка аккаунта: {name}...")
        try:
            access_token = renew_token(refresh_token)
            promotions = fetch_promotions(access_token, country, language)
            print(f"   📦 Найдено купонов: {len(promotions)}")

            for promo in promotions:
                title = clean_text(promo.get("title", "Без названия"))
                discount = promo.get("discount", {}).get("title", "")
                is_activated = promo.get("isActivated", False)
                promo_id = promo.get("id")
                catalog_promo_id = promo.get("promotionId", "")
                image_url = promo.get("imageUrl") or promo.get("image") or ""

                if not is_activated and promo_id:
                    print(f"   👉 Активируем: {title} ({discount})...")
                    if activate_promotion(access_token, promo_id, country, language):
                        is_activated = True
                        print("   ✅ Активирован!")
                    else:
                        print("   ❌ Не удалось активировать")

                all_coupons.append({
                    "Товар": title,
                    "Скидка": discount,
                    "У кого": name,
                    "Статус": "Активирован" if is_activated else "Не активен",
                    "promotionId": catalog_promo_id,
                    "imageUrl": image_url
                })

        except Exception as e:
            print(f"❌ Ошибка при работе с аккаунтом '{name}': {e}")

    return all_coupons

def fetch_promo_details(country, store_id, promotion_id, cache={}):
    """Извлечение полных деталей акции: все коды товаров (SKU) и описание из API"""
    if not promotion_id:
        return {"display_sku": "", "codes": [], "title": "", "description": ""}
    if promotion_id in cache:
        return cache[promotion_id]

    url = f"https://offers.lidlplus.com/app/api/v4/{country.upper()}/{store_id}/offers/{promotion_id}"
    cmd = [
        CURL_BIN, "-s", url,
        "-H", f"App-Version: {OFFERS_APP_VERSION}",
        "-H", "Operating-System: iOS",
        "-H", "App: com.lidl.eci.lidlplus",
        "-H", "Accept-Language: en",
        "-H", f"Country: {country.upper()}",
        "--max-time", "6"
    ]
    res = subprocess.run(cmd, capture_output=True)
    raw = res.stdout.decode("utf-8", errors="ignore") if res.stdout else ""
    if res.returncode == 0 and raw and raw.startswith("{"):
        try:
            data = json.loads(raw)
            main_prods = data.get("productCodes", {}).get("mainProducts", []) or []
            sec_prods = data.get("productCodes", {}).get("secondaryProducts", []) or []
            all_prods = main_prods + sec_prods
            codes = [str(mp.get("code")).strip() for mp in all_prods if mp.get("code")]
            
            if len(codes) > 3:
                disp = f"Категория ({len(codes)} тов.)"
            elif codes:
                disp = ", ".join(codes)
            else:
                disp = ""
            
            detail = {
                "display_sku": disp,
                "codes": codes,
                "title": data.get("title") or "",
                "description": data.get("description") or "",
                "pricePerUnit": data.get("pricePerUnit"),
                "packaging": data.get("packaging")
            }
            cache[promotion_id] = detail
            return detail
        except Exception:
            pass
    fallback = {"display_sku": "", "codes": [], "title": "", "description": ""}
    cache[promotion_id] = fallback
    return fallback

def fetch_product_code(country, store_id, promotion_id, cache={}):
    """Извлечение отображаемого артикула SKU (для совместимости)"""
    detail = fetch_promo_details(country, store_id, promotion_id)
    return detail.get("display_sku", "")

def find_double_discounts(store_offers, family_coupons, country="CY", store_id="CY0119"):
    """Поиск пересечений: где скидка магазина суммируется со скидкой купона семьи"""
    double_deals = []

    # Предзагрузка деталей купонов для категорийных совпадений по кодам
    promo_cache = {}
    for c in family_coupons:
        pid = c.get("promotionId")
        if pid and pid not in promo_cache:
            promo_cache[pid] = fetch_promo_details(country, store_id, pid)

    for o in store_offers:
        o_title = clean_text(o.get("title") or "")
        o_brand = clean_text(o.get("brand") or "")
        full_offer_name = f"{o_brand} {o_title}".strip()
        o_words = get_keywords(full_offer_name)
        store_skus = [str(x).strip() for x in o.get("productIds", [])]
        sku = ", ".join(store_skus)
        pbox = o.get("priceBox", {})
        store_disc = pbox.get("discountMessage", "")
        item_price = pbox.get("largePartNumeric")
        item_price_str = f"{item_price:.2f} €" if item_price is not None else "-"
        packaging = clean_text(o.get("packaging") or "")
        offer_img = o.get("imageUrl") or o.get("image") or ""

        unit_val, unit_name = extract_unit_price(o)
        store_unit_price_str = f"{unit_val:.2f} €{unit_name}" if unit_val else "-"

        # Множество кодов магазина для быстрого поиска
        store_sku_set = set(store_skus) | {s.lstrip('0') for s in store_skus}

        for c in family_coupons:
            c_title = clean_text(c["Товар"])
            c_words = get_keywords(c_title)
            c_disc = c["Скидка"]
            member = c["У кого"]
            coupon_img = c.get("imageUrl") or ""
            pid = c.get("promotionId")
            detail = promo_cache.get(pid, {})
            coupon_codes = detail.get("codes", [])
            coupon_codes_set = set(coupon_codes) | {code.lstrip('0') for code in coupon_codes}

            # 1. Проверка прямого совпадения по кодам товаров (SKU)
            # Включает категорийные купоны (например 'On vegetables' содержит 97 кодов, 'On household paper' 71 код)
            sku_match = bool(coupon_codes_set and (coupon_codes_set & store_sku_set))

            # 2. Проверка по ключевым словам
            overlap = o_words.intersection(c_words)
            keyword_match = (len(overlap) >= 2) or (
                len(overlap) == 1 and any(w in overlap for w in [
                    "burger", "edam", "pepper", "grape", "kiwi", "lime", 
                    "cheddar", "gouda", "yoghurt", "bacon", "salami", "pear", "peach"
                ])
            )

            if "juice" in full_offer_name.lower() and "juice" not in c_title.lower():
                keyword_match = False

            # 3. Дополнительная проверка на категорию овощей, если в купоне есть vegetables
            is_veg = "vegetables" in c_title.lower() and (
                any(w in full_offer_name.lower() for w in ["pepper", "salad", "tomato", "carrot", "cucumber", "avocado"])
                or sku.startswith("008") and any(w in full_offer_name.lower() for w in ["pepper", "avocado"])
            )

            if sku_match or keyword_match or is_veg:
                final_unit_val = calc_final_unit_price_after_coupon(unit_val, c_disc)
                final_unit_str = f"{final_unit_val:.2f} €{unit_name}" if final_unit_val else "-"

                final_pack_val = calc_final_unit_price_after_coupon(item_price, c_disc)
                final_pack_str = f"{final_pack_val:.2f} €" if final_pack_val else "-"

                deal_sku = sku if sku else detail.get("display_sku", "")

                double_deals.append({
                    "Код (SKU)": deal_sku,
                    "Товар": full_offer_name,
                    "Скидка магазина": store_disc,
                    "Купон": f"{c_title} ({c_disc})",
                    "У кого купон": member,
                    "Цена в магазине": item_price_str,
                    "Финальная цена за 1 кг/л": final_unit_str,
                    "Финальная цена за пачку": final_pack_str,
                    "Фасовка": packaging,
                    "imageUrl": offer_img or coupon_img,
                    "store_unit_price": store_unit_price_str,
                    "coupon_title": c_title,
                    "coupon_disc": c_disc
                })

    return double_deals

def fetch_super_savers(country="CY", language="el"):
    """Сбор специальных акций Super Savers / Great Deals с официального сайта Lidl Cyprus.
    Собирает акции, действующие сегодня, а также предстоящие акции (на ближайшие дни).
    Исключает полностью просроченные акции.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    }
    now_utc = datetime.now(timezone.utc)
    today = date.today()
    curr_year, curr_week, _ = today.isocalendar()
    year_short = int(str(curr_year)[-2:])
    min_week = curr_week - 1
    min_year = year_short
    if min_week < 1:
        min_week = 52
        min_year = year_short - 1

    base_url = "https://www.lidl.com.cy"

    try:
        r = requests.get(base_url, headers=headers, verify=False, timeout=12)
        if r.status_code != 200:
            print(f"⚠️ Не удалось загрузить главную страницу Lidl: status {r.status_code}")
            return []
    except Exception as e:
        print(f"⚠️ Ошибка запроса к сайту Lidl: {e}")
        return []

    # Находим все ссылки на кампании текущей и будущих недель (-26kwXX)
    raw_links = set(re.findall(r'(/c/el-CY/[^"\'\s<>]+-26kw\d+/[as]\d+)', r.text))
    campaign_links = []
    for link in sorted(raw_links):
        m_kw = re.search(r'-(\d{2})kw(\d{1,2})/', link)
        if m_kw:
            yr = int(m_kw.group(1))
            wk = int(m_kw.group(2))
            if yr > year_short or (yr == year_short and wk >= min_week) or (yr == min_year and wk >= min_week):
                campaign_links.append(link)

    super_savers = []
    seen_products = set()

    for link in campaign_links:
        page_url = base_url + link if link.startswith('/') else link
        try:
            resp = requests.get(page_url, headers=headers, verify=False, timeout=10)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, 'html.parser')
        except Exception:
            continue

        page_h1 = soup.find('h1')
        campaign_name = page_h1.get_text(strip=True) if page_h1 else link.split('/')[3]

        for it in soup.find_all(attrs={"data-grid-data": True}):
            try:
                d = json.loads(it['data-grid-data'])
            except Exception:
                continue

            title = clean_text(d.get('fullTitle') or d.get('title') or '')
            if not title:
                continue

            stock = d.get('stockAvailability', {})
            b_v2 = stock.get('badgeInfoV2', [])
            badges = stock.get('badgeInfo', {}).get('badges', [])
            badge_text = badges[0].get('text') if badges else ""
            badge_type = badges[0].get('type') if badges else ""

            chosen_range = None
            for bv in b_v2:
                vf = bv.get('validFrom')
                vu = bv.get('validUntil')
                if vf and vu:
                    df = datetime.fromtimestamp(vf, timezone.utc)
                    du = datetime.fromtimestamp(vu, timezone.utc)
                    if df <= now_utc <= du:
                        chosen_range = ('ACTIVE_TODAY', df, du)
                        break
                    elif df > now_utc and (df - now_utc).days <= 14:
                        if not chosen_range:
                            chosen_range = ('FUTURE', df, du)

            if not chosen_range:
                m = re.search(r'(\d{1,2})\.(\d{1,2})', badge_text)
                if m and badge_type != 'IN_STORE_PAST_DATE_RANGE':
                    d_day = int(m.group(1))
                    d_mon = int(m.group(2))
                    d_date = date(today.year, d_mon, d_day)
                    if d_date == today:
                        chosen_range = ('ACTIVE_TODAY', datetime(today.year, d_mon, d_day, tzinfo=timezone.utc), datetime(today.year, d_mon, d_day, 23, 59, 59, tzinfo=timezone.utc))
                    elif d_date > today and (d_date - today).days <= 14:
                        chosen_range = ('FUTURE', datetime(today.year, d_mon, d_day, tzinfo=timezone.utc), datetime(today.year, d_mon, d_day, tzinfo=timezone.utc) + timedelta(days=3))

            if not chosen_range:
                continue

            status, df, du = chosen_range
            cy_from = (df + timedelta(hours=3)).date()
            cy_until = (du + timedelta(hours=3)).date()

            if status == 'ACTIVE_TODAY':
                until_weekday = WEEKDAYS_RU[cy_until.weekday()]
                if cy_until == today:
                    formatted_date = f"⚡ Только сегодня, {cy_until.strftime('%d.%m')} ({until_weekday})"
                else:
                    formatted_date = f"⚡ Действует сегодня (до {cy_until.strftime('%d.%m')} {until_weekday})"
                status_order = 0
                deal_date_iso = today.isoformat()
            else:
                from_weekday = WEEKDAYS_RU[cy_from.weekday()]
                if cy_from == today + timedelta(days=1):
                    formatted_date = f"⚡ Завтра, {cy_from.strftime('%d.%m')} ({from_weekday})"
                else:
                    formatted_date = f"⚡ с {cy_from.strftime('%d.%m')} ({from_weekday})"
                status_order = 1
                deal_date_iso = cy_from.isoformat()

            price_obj = d.get('price', {})
            item_price = price_obj.get('price')
            old_price = price_obj.get('oldPrice') or price_obj.get('discount', {}).get('deletedPrice')
            pct = price_obj.get('discount', {}).get('percentageDiscount')
            if pct:
                discount_str = f"-{pct}%"
            elif old_price and item_price and old_price > item_price:
                calc_pct = round((old_price - item_price) / old_price * 100)
                discount_str = f"-{calc_pct}%"
            else:
                discount_str = ""

            packaging = clean_text(price_obj.get('packaging', {}).get('text') or '')
            base_price = clean_text(price_obj.get('basePrice', {}).get('text') or '')
            image_url = d.get('image') or ''

            ians = [str(x).strip() for x in d.get('ians', []) if str(x).strip()]
            product_id = str(d.get('productId') or '').strip()
            erp_number = str(d.get('erpNumber') or '').strip()
            sku = ians[0] if ians else (product_id or erp_number)

            canonical = d.get('canonicalPath') or d.get('canonicalUrl') or ''
            product_url = (base_url + canonical) if canonical.startswith('/') else canonical

            dedup_key = (sku, title, deal_date_iso)
            if dedup_key in seen_products:
                continue
            seen_products.add(dedup_key)

            super_savers.append({
                "sku": sku,
                "title": title,
                "price": item_price,
                "price_str": f"{item_price:.2f} €" if item_price is not None else "-",
                "old_price": old_price,
                "old_price_str": f"{old_price:.2f} €" if old_price is not None else "",
                "discount": discount_str,
                "packaging": packaging,
                "unit_price": base_price,
                "image_url": image_url,
                "formatted_date": formatted_date,
                "raw_date": cy_from.strftime('%d.%m'),
                "deal_date": deal_date_iso,
                "status_order": status_order,
                "badge": badge_text,
                "campaign": campaign_name,
                "product_url": product_url,
                "ians": ians,
                "productId": product_id,
                "erpNumber": erp_number
            })

    super_savers.sort(key=lambda x: (x["status_order"], x["deal_date"], x["title"]))
    return super_savers

def find_super_saver_doubles(super_savers, family_coupons, country="CY", store_id="CY0119"):
    """Поиск комбо-скидок: где акция Super Saver пересекается с персональным купоном семьи"""
    doubles = []
    promo_cache = {}
    for c in family_coupons:
        pid = c.get("promotionId")
        if pid and pid not in promo_cache:
            promo_cache[pid] = fetch_promo_details(country, store_id, pid)

    for ss in super_savers:
        ss_codes = set(ss['ians']) | {x.zfill(7) for x in ss['ians']} | {x.lstrip('0') for x in ss['ians']}
        if ss.get('productId'):
            p_id = str(ss['productId'])
            ss_codes.update({p_id, p_id.zfill(7), p_id.lstrip('0')})
        if ss.get('erpNumber'):
            e_id = str(ss['erpNumber'])
            ss_codes.update({e_id, e_id.zfill(7), e_id.lstrip('0')})

        ss_title = ss['title']
        ss_words = get_keywords(ss_title)
        title_lower = ss_title.lower()

        for c in family_coupons:
            c_title = c.get("Товар", "")
            c_title_lower = c_title.lower()
            c_words = get_keywords(c_title)
            c_disc = c.get("Скидка", "")
            member = c.get("У кого", "")
            pid = c.get("promotionId")
            detail = promo_cache.get(pid, {})
            c_codes = detail.get("codes", [])
            c_codes_set = set(c_codes) | {code.lstrip('0') for code in c_codes} | {code.zfill(7) for code in c_codes}

            # 1. Прямое совпадение по SKU / IAN кодам
            sku_match = bool(c_codes_set and (c_codes_set & ss_codes))

            # 2. Совпадение по ключевым словам
            overlap = ss_words.intersection(c_words)
            kw_match = len(overlap) >= 2 or (len(overlap) == 1 and any(w in overlap for w in ["nuts", "alesto", "sondey", "chocolate", "potato", "pineapple", "blueberries", "nike", "esmara"]))

            # Исключаем йогурты и десерты от сопоставления со свежими фруктами
            is_yoghurt_or_dessert = any(w in c_title_lower for w in ["yoghurt", "yogurt", "dessert", "juice"])

            # 3. Категорийные совпадения
            is_veg = "vegetables" in c_title_lower and any(w in title_lower for w in ["πατάτες", "τοματίνια", "potato"])
            is_fruit = ("fruit" in c_title_lower or "berries" in c_title_lower) and not is_yoghurt_or_dessert and any(w in title_lower for w in ["μύρτιλα", "ανανάς", "σταφύλια", "berries", "pineapple"])
            is_nuts = ("nuts" in c_title_lower or "alesto" in c_title_lower or "peanut" in c_title_lower or "hazelnut" in c_title_lower) and ("alesto" in title_lower or "mix ξηρών" in title_lower)
            is_choc = "chocolate" in c_title_lower and not any(w in c_title_lower for w in ["kinder", "bar"]) and any(w in title_lower for w in ["σοκολάτα", "fin carré", "carré", "chocolate"])

            if sku_match or kw_match or is_veg or is_fruit or is_nuts or is_choc:
                item_price = ss.get("price")
                final_price = calc_final_unit_price_after_coupon(item_price, c_disc)
                final_price_str = f"{final_price:.2f} €" if final_price else "-"

                doubles.append({
                    "sku": ss["sku"],
                    "title": ss["title"],
                    "super_price": ss["price_str"],
                    "final_price": final_price_str,
                    "super_discount": ss["discount"],
                    "coupon_discount": c_disc,
                    "coupon_title": c_title,
                    "owner": member,
                    "packaging": ss["packaging"],
                    "unit_price": ss["unit_price"],
                    "image_url": ss["image_url"],
                    "formatted_date": ss["formatted_date"],
                    "deal_date": ss["deal_date"],
                    "status_order": ss.get("status_order", 0),
                    "badge": ss["badge"],
                    "campaign": ss["campaign"],
                    "product_url": ss["product_url"]
                })
    return doubles

def export_web_data(coupons, store_offers, double_deals, super_savers=None, super_saver_doubles=None, output_path="web/data.json", config={}):
    """Экспорт структурированных данных в формат JSON для мобильного Telegram Mini App"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    country = config.get("country", "CY")
    store_id = config.get("store_id", "CY0119")
    store_name = config.get("store_name", "Pafos / Touristika (Tombs of the Kings 104)")
    family_members = list(config.get("family_accounts", {}).keys())

    # 1. Группировка двойных скидок
    grouped_double = {}
    for d in double_deals:
        key = (
            d["Код (SKU)"], d["Товар"], d["Скидка магазина"], d["coupon_disc"],
            d["Финальная цена за 1 кг/л"], d["Финальная цена за пачку"],
            d["Цена в магазине"], d["store_unit_price"], d["Фасовка"], d["imageUrl"]
        )
        if key not in grouped_double:
            grouped_double[key] = set()
        grouped_double[key].add(d["У кого купон"])

    web_double_deals = []
    for key, owners in grouped_double.items():
        sku, title, s_disc, c_disc, f_unit, f_pack, s_pack, s_unit, pkg, img = key
        web_double_deals.append({
            "sku": sku,
            "title": title,
            "store_discount": s_disc,
            "coupon_discount": c_disc,
            "final_unit_price": f_unit,
            "final_pack_price": f_pack,
            "store_pack_price": s_pack,
            "store_unit_price": s_unit,
            "packaging": pkg,
            "image_url": img,
            "owners": sorted(list(owners))
        })
    web_double_deals.sort(key=lambda x: x["title"])

    # 2. Группировка купонов семьи
    # Поиск соответствий с магазином для цен за кг
    match_map = {}
    for d in double_deals:
        sku = str(d.get("Код (SKU)", "")).zfill(7)
        c_title = d.get("coupon_title", "")
        c_disc = d.get("coupon_disc", "")
        u_price = d.get("Финальная цена за 1 кг/л", "")
        match_map[(c_title, c_disc)] = (sku, u_price)

    # Кэш артикулов (SKU)
    sku_cache = {}
    for c in coupons:
        p_id = c.get("promotionId")
        if p_id and p_id not in sku_cache:
            sku_cache[p_id] = fetch_product_code(country, store_id, p_id)

    grouped_coupons = {}
    for c in coupons:
        key = (c["Товар"], c["Скидка"], c.get("promotionId", ""), c.get("imageUrl", ""))
        if key not in grouped_coupons:
            grouped_coupons[key] = set()
        grouped_coupons[key].add(c["У кого"])

    web_family_coupons = []
    for (title, disc, p_id, img), owners in grouped_coupons.items():
        sku_val = sku_cache.get(p_id, "")
        unit_price = ""
        if (title, disc) in match_map:
            m_sku, m_uprice = match_map[(title, disc)]
            if not sku_val and m_sku:
                sku_val = m_sku
            unit_price = m_uprice

        is_monetary = bool("€" in disc and "%" not in disc)
        web_family_coupons.append({
            "title": title,
            "discount": disc,
            "sku": sku_val,
            "unit_price": unit_price,
            "image_url": img,
            "owners": sorted(list(owners)),
            "is_shared": len(owners) >= 2,
            "is_monetary": is_monetary
        })
    web_family_coupons.sort(key=lambda x: x["title"])

    # 3. Полный каталог акций магазина
    web_store_offers = []
    for o in store_offers:
        full_title = clean_text(f"{o.get('brand') or ''} {o.get('title') or ''}")
        pbox = o.get("priceBox", {})
        disc = pbox.get("discountMessage") or ""
        new_p = pbox.get("largePartNumeric")
        product_codes = ", ".join(o.get("productIds", []))
        packaging = clean_text(o.get("packaging") or "")
        img = o.get("imageUrl") or o.get("image") or ""

        unit_val, unit_name = extract_unit_price(o)
        unit_price_str = f"{unit_val:.2f} €{unit_name}" if unit_val else "-"
        price_str = f"{new_p:.2f} €" if new_p is not None else "-"

        web_store_offers.append({
            "title": full_title,
            "sku": product_codes,
            "discount": disc,
            "unit_price": unit_price_str,
            "pack_price": price_str,
            "packaging": packaging,
            "image_url": img
        })
    web_store_offers.sort(key=lambda x: x["title"])

    # 4. Денежные купоны (скидки на весь чек в евро)
    web_monetary_coupons = []
    for c in coupons:
        disc = clean_text(c.get("Скидка", ""))
        title = clean_text(c.get("Товар", "Скидка на чек"))
        if "€" in disc and "%" not in disc:
            web_monetary_coupons.append({
                "title": f"Скидка {disc} на весь чек",
                "discount": disc,
                "owner": c.get("У кого", ""),
                "description": "Скидка на всю сумму покупки при сканировании карты Lidl Plus",
                "image_url": c.get("imageUrl", "")
            })

    # 5. Специальные акции Super Savers
    web_super_savers = []
    if super_savers:
        for ss in super_savers:
            web_super_savers.append({
                "sku": ss.get("sku", ""),
                "title": ss.get("title", ""),
                "price": ss.get("price_str", "-"),
                "numeric_price": ss.get("price"),
                "old_price": ss.get("old_price_str", ""),
                "discount": ss.get("discount", ""),
                "packaging": ss.get("packaging", ""),
                "unit_price": ss.get("unit_price", ""),
                "image_url": ss.get("image_url", ""),
                "formatted_date": ss.get("formatted_date", ""),
                "raw_date": ss.get("raw_date", ""),
                "deal_date": ss.get("deal_date", ""),
                "status_order": ss.get("status_order", 0),
                "badge": ss.get("badge", ""),
                "campaign": ss.get("campaign", ""),
                "product_url": ss.get("product_url", "")
            })
        web_super_savers.sort(key=lambda x: (x.get("status_order", 0), x["deal_date"], x["title"]))

    # 6. Пересечения Super Savers с купонами семьи
    web_super_doubles = []
    if super_saver_doubles:
        grouped_ss_doubles = {}
        for d in super_saver_doubles:
            key = (
                d["sku"], d["title"], d["super_price"], d["super_discount"],
                d["packaging"], d["unit_price"], d["image_url"],
                d["formatted_date"], d["deal_date"], d.get("status_order", 0), d["campaign"], d["product_url"]
            )
            if key not in grouped_ss_doubles:
                grouped_ss_doubles[key] = {
                    "owners": set(),
                    "coupons": set(),
                    "final_prices": []
                }
            grouped_ss_doubles[key]["owners"].add(d["owner"])
            grouped_ss_doubles[key]["coupons"].add(f"{d['coupon_title']} ({d['coupon_discount']})")
            if d.get("final_price") and d["final_price"] != "-":
                grouped_ss_doubles[key]["final_prices"].append(d["final_price"])

        for key, info in grouped_ss_doubles.items():
            sku, title, s_price, s_disc, pkg, u_price, img, f_date, d_date, s_order, camp, p_url = key
            best_final_price = sorted(info["final_prices"])[0] if info["final_prices"] else s_price
            coupon_disc_str = ", ".join(sorted(info["coupons"]))
            web_super_doubles.append({
                "sku": sku,
                "title": title,
                "super_price": s_price,
                "final_price": best_final_price,
                "super_discount": s_disc,
                "coupon_discount": coupon_disc_str,
                "packaging": pkg,
                "unit_price": u_price,
                "image_url": img,
                "formatted_date": f_date,
                "deal_date": d_date,
                "status_order": s_order,
                "campaign": camp,
                "product_url": p_url,
                "owners": sorted(list(info["owners"]))
            })
        web_super_doubles.sort(key=lambda x: (x.get("status_order", 0), x["deal_date"], x["title"]))

    now = datetime.now()
    now_str = now.strftime("%d.%m.%Y %H:%M")

    payload = {
        "generated_at": now.isoformat(),
        "generated_at_str": now_str,
        "store": {
            "id": store_id,
            "name": store_name,
            "country": country
        },
        "family_members": family_members,
        "stats": {
            "double_deals_count": len(web_double_deals),
            "family_coupons_count": len(web_family_coupons),
            "store_offers_count": len(web_store_offers),
            "super_savers_count": len(web_super_savers),
            "super_saver_doubles_count": len(web_super_doubles),
            "shared_coupons_count": sum(1 for c in web_family_coupons if c.get("is_shared")),
            "monetary_coupons_count": len(web_monetary_coupons)
        },
        "monetary_coupons": web_monetary_coupons,
        "double_deals": web_double_deals,
        "family_coupons": web_family_coupons,
        "store_offers": web_store_offers,
        "super_savers": web_super_savers,
        "super_saver_doubles": web_super_doubles
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"📱 Данные для веб-приложения успешно сохранены: {output_path} ({len(web_double_deals)} комбо, {len(web_family_coupons)} купонов, {len(web_store_offers)} акций, {len(web_super_savers)} Super Savers)")
    return payload

def generate_excel_report(coupons, store_offers, double_deals, excel_filename="lidl_discounts_paphos.xlsx", country="CY", store_id="CY0119"):
    """Генерация структурированного Excel-файла с персональными скидками и выделением совпадений"""
    wb = openpyxl.Workbook()

    thin_side = Side(style='thin', color='B0B0B0')
    border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    # ---------------------------------------------------------
    # ЛИСТ 1: Персональные скидки
    # ---------------------------------------------------------
    ws1 = wb.active
    ws1.title = "Персональные скидки"
    ws1.views.sheetView[0].showGridLines = True

    ws1['A1'] = "Персональные скидки"
    ws1['A1'].font = Font(name='Calibri', size=12, bold=True)
    ws1.row_dimensions[1].height = 25

    headers1 = ["Товар", "Код", "%", "Итог. цена за 1 кг", "Вова", "Света", "Влада", "Сева"]
    ws1.row_dimensions[2].height = 22

    for col_idx, h in enumerate(headers1, start=1):
        c = ws1.cell(row=2, column=col_idx, value=h)
        c.font = Font(name='Calibri', size=11, bold=True, italic=True)
        c.border = border
        c.alignment = Alignment(horizontal='left' if col_idx == 1 else 'center', vertical='center')

    match_map = {}
    for d in double_deals:
        sku = str(d.get("Код (SKU)", "")).zfill(7)
        c_title = d.get("coupon_title", "")
        c_disc = d.get("coupon_disc", "")
        u_price = d.get("Финальная цена за 1 кг/л", "")
        match_map[(c_title, c_disc)] = (sku, u_price)

    PALETTE = [
        "D9E1F2", "E2EFDA", "FCE4D6", "FFF2CC", "E8D7F1",
        "FADBD8", "D1ECF1", "D5F5E3", "FCF3CF", "E8DAEF", "D0ECE7", "EDBB99"
    ]

    df_c = pd.DataFrame(coupons)
    summary_c = df_c.groupby(["Товар", "Скидка"]).agg({
        "У кого": lambda x: sorted(set(x)),
        "promotionId": "first"
    }).reset_index()
    summary_c = summary_c.sort_values(by="Товар", ascending=True)

    sku_cache = {}
    for _, row in summary_c.iterrows():
        p_id = row.get("promotionId")
        if p_id and p_id not in sku_cache:
            sku_cache[p_id] = fetch_product_code(country, store_id, p_id)

    coincidence_idx = 0
    cur_row = 3

    for _, row in summary_c.iterrows():
        ws1.row_dimensions[cur_row].height = 20
        title = str(row["Товар"]).strip()
        disc = str(row["Скидка"]).strip()
        members = row["У кого"]
        promo_cat_id = row.get("promotionId")

        sku_val = sku_cache.get(promo_cat_id, "")

        price_val = ""
        if (title, disc) in match_map:
            matched_sku, matched_price = match_map[(title, disc)]
            if not sku_val and matched_sku:
                sku_val = matched_sku
            if "€" in matched_price and "/кг" in matched_price:
                p_clean = matched_price.replace("€/кг", "").replace("€/л", "").strip()
                price_val = f"€ {p_clean}"
            elif "€" in matched_price and "/л" in matched_price:
                p_clean = matched_price.replace("€/л", "").strip()
                price_val = f"€ {p_clean} /л"

        has_coincidence = len(members) >= 2
        fill_color = None
        if has_coincidence:
            fill_color = PALETTE[coincidence_idx % len(PALETTE)]
            coincidence_idx += 1

        vals = [
            title,
            sku_val,
            disc,
            price_val,
            "1" if "Вова" in members else "",
            "1" if "Света" in members else "",
            "1" if "Влада" in members else "",
            "1" if "Сева" in members else ""
        ]

        for col_idx, val in enumerate(vals, start=1):
            cell = ws1.cell(row=cur_row, column=col_idx, value=val)
            cell.font = Font(name='Calibri', size=11)
            cell.border = border
            cell.alignment = Alignment(horizontal='left' if col_idx == 1 else 'center', vertical='center')

            if fill_color:
                if col_idx in [1, 2, 3, 4] or (col_idx == 5 and "Вова" in members) or (col_idx == 6 and "Света" in members) or (col_idx == 7 and "Влада" in members) or (col_idx == 8 and "Сева" in members):
                    cell.fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")

        cur_row += 1

    col_widths1 = {1: 34, 2: 12, 3: 10, 4: 20, 5: 9, 6: 9, 7: 9, 8: 9}
    for c_idx, w in col_widths1.items():
        ws1.column_dimensions[get_column_letter(c_idx)].width = w

    # ---------------------------------------------------------
    # ЛИСТ 2: Двойная выгода
    # ---------------------------------------------------------
    ws2 = wb.create_sheet(title="Двойная выгода")
    ws2.views.sheetView[0].showGridLines = True
    headers2 = ["Код (SKU)", "Товар", "Скидка магазина", "Купон", "Финальная цена за 1 кг/л", "Финальная цена за пачку", "У кого купон"]
    ws2.append(headers2)
    ws2.row_dimensions[1].height = 24
    for c_idx in range(1, len(headers2) + 1):
        cell = ws2.cell(row=1, column=c_idx)
        cell.font = Font(name='Calibri', size=11, bold=True)
        cell.fill = PatternFill(start_color="FFE2EFDA", end_color="FFE2EFDA", fill_type="solid")
        cell.border = border
        cell.alignment = Alignment(horizontal='center', vertical='center')

    df_d = pd.DataFrame(double_deals)
    if not df_d.empty:
        summary_double = df_d.groupby([
            "Код (SKU)", "Товар", "Скидка магазина", "Купон", "Финальная цена за 1 кг/л", "Финальная цена за пачку"
        ])["У кого купон"].apply(lambda x: ", ".join(sorted(set(x)))).reset_index()

        for r_idx, r in summary_double.iterrows():
            row_num = r_idx + 2
            ws2.row_dimensions[row_num].height = 20
            row_vals = [
                r["Код (SKU)"], r["Товар"], r["Скидка магазина"], r["Купон"],
                r["Финальная цена за 1 кг/л"], r["Финальная цена за пачку"], r["У кого купон"]
            ]
            for col_idx, val in enumerate(row_vals, start=1):
                cell = ws2.cell(row=row_num, column=col_idx, value=val)
                cell.font = Font(name='Calibri', size=11)
                cell.border = border
                cell.alignment = Alignment(horizontal='left' if col_idx in [2, 4] else 'center', vertical='center')

    col_widths2 = {1: 14, 2: 36, 3: 16, 4: 36, 5: 25, 6: 22, 7: 22}
    for c_idx, w in col_widths2.items():
        ws2.column_dimensions[get_column_letter(c_idx)].width = w

    # ---------------------------------------------------------
    # ЛИСТ 3: Акции магазина
    # ---------------------------------------------------------
    ws3 = wb.create_sheet(title="Акции магазина")
    ws3.views.sheetView[0].showGridLines = True
    headers3 = ["Код (SKU)", "Скидка", "Товар", "Финальная цена за 1 кг/л", "Цена за пачку", "Фасовка"]
    ws3.append(headers3)
    ws3.row_dimensions[1].height = 24
    for c_idx in range(1, len(headers3) + 1):
        cell = ws3.cell(row=1, column=c_idx)
        cell.font = Font(name='Calibri', size=11, bold=True)
        cell.fill = PatternFill(start_color="FFF2F2F2", end_color="FFF2F2F2", fill_type="solid")
        cell.border = border
        cell.alignment = Alignment(horizontal='center', vertical='center')

    for r_idx, o in enumerate(store_offers):
        row_num = r_idx + 2
        ws3.row_dimensions[row_num].height = 20
        full_title = clean_text(f"{o.get('brand') or ''} {o.get('title') or ''}")
        pbox = o.get("priceBox", {})
        disc = pbox.get("discountMessage") or ""
        new_p = pbox.get("largePartNumeric")
        product_codes = ", ".join(o.get("productIds", []))
        packaging = clean_text(o.get("packaging") or "")

        unit_val, unit_name = extract_unit_price(o)
        unit_price_str = f"{unit_val:.2f} €{unit_name}" if unit_val else "-"
        price_str = f"{new_p:.2f} €" if new_p is not None else "-"

        vals = [product_codes, disc, full_title, unit_price_str, price_str, packaging]
        for col_idx, val in enumerate(vals, start=1):
            cell = ws3.cell(row=row_num, column=col_idx, value=val)
            cell.font = Font(name='Calibri', size=11)
            cell.border = border
            cell.alignment = Alignment(horizontal='left' if col_idx in [3, 6] else 'center', vertical='center')

    col_widths3 = {1: 14, 2: 12, 3: 38, 4: 25, 5: 16, 6: 25}
    for c_idx, w in col_widths3.items():
        ws3.column_dimensions[get_column_letter(c_idx)].width = w

    wb.save(excel_filename)
    return excel_filename

def main():
    print("🚀 Запуск сбора купонов семьи и акций магазина Lidl...\n")
    config = load_config()
    if not config:
        return

    country = config.get("country", "CY")
    language = config.get("language", "EN")
    store_id = config.get("store_id", "CY0119")
    store_name = config.get("store_name", "Pafos / Touristika (Tombs of the Kings)")

    # 1. Сбор и автоактивация персональных купонов семьи
    coupons = process_accounts(config)

    # 2. Сбор общих скидок магазина (Daily / Weekly Savers)
    print(f"\n🛒 Загрузка акций магазина {store_name} [{store_id}]...")
    store_offers = fetch_daily_savers(country, store_id, language="en")
    print(f"   📦 Загружено акций магазина: {len(store_offers)}")

    # 3. Поиск двойных скидок (пересечений Daily Savers с купонами семьи)
    double_deals = find_double_discounts(store_offers, coupons, country=country, store_id=store_id)

    # 4. Сбор акций Super Savers (Great Deals) с фильтрацией просроченных
    print(f"\n⚡ Загрузка акций Super Savers (Great Deals)...")
    super_savers = fetch_super_savers(country=country)
    print(f"   ⚡ Загружено актуальных Super Savers: {len(super_savers)}")
    super_saver_doubles = find_super_saver_doubles(super_savers, coupons, country=country, store_id=store_id)
    print(f"   ✨ Найдено пересечений Super Savers с купонами: {len(super_saver_doubles)}")

    # 5. Экспорт для веб-приложения Telegram Mini App
    export_web_data(coupons, store_offers, double_deals, super_savers=super_savers, super_saver_doubles=super_saver_doubles, output_path="web/data.json", config=config)

    # 5. Сохранение локальных отчетов (CSV и Excel)
    if double_deals:
        df_double = pd.DataFrame(double_deals)
        summary_double = df_double.groupby([
            "Код (SKU)", "Товар", "Скидка магазина", "Купон", "Финальная цена за 1 кг/л", "Финальная цена за пачку", "Цена в магазине"
        ])["У кого купон"].apply(lambda x: ", ".join(sorted(set(x)))).reset_index()

        cols = ["Код (SKU)", "Товар", "Скидка магазина", "Купон", "Финальная цена за 1 кг/л", "Финальная цена за пачку", "У кого купон"]
        summary_double = summary_double[cols]
        summary_double.to_csv("double_discounts_paphos.csv", index=False, encoding="utf-8-sig")

    if coupons:
        df_coupons = pd.DataFrame(coupons)
        summary_coupons = df_coupons.groupby(["Товар", "Скидка"])["У кого"].apply(lambda x: ", ".join(sorted(set(x)))).reset_index()
        summary_coupons.to_csv("coupons_family_summary.csv", index=False, encoding="utf-8-sig")

    if store_offers:
        offers_rows = []
        for o in store_offers:
            full_title = clean_text(f"{o.get('brand') or ''} {o.get('title') or ''}")
            pbox = o.get("priceBox", {})
            disc = pbox.get("discountMessage") or ""
            new_p = pbox.get("largePartNumeric")
            product_codes = ", ".join(o.get("productIds", []))
            packaging = clean_text(o.get("packaging") or "")

            unit_val, unit_name = extract_unit_price(o)
            unit_price_str = f"{unit_val:.2f} €{unit_name}" if unit_val else "-"
            price_str = f"{new_p:.2f} €" if new_p is not None else "-"

            offers_rows.append({
                "Код (SKU)": product_codes,
                "Скидка": disc,
                "Товар": full_title,
                "Финальная цена за 1 кг/л": unit_price_str,
                "Цена за пачку": price_str,
                "Фасовка": packaging
            })
        pd.DataFrame(offers_rows).to_csv("daily_savers_paphos.csv", index=False, encoding="utf-8-sig")

    # Генерация Excel-отчета
    excel_file = "lidl_discounts_paphos.xlsx"
    try:
        generate_excel_report(coupons, store_offers, double_deals, excel_file, country=country, store_id=store_id)
        print(f"📊 Excel-отчет успешно создан: {excel_file}")
    except Exception as e:
        print(f"⚠️ Не удалось сгенерировать Excel: {e}")

    print("\n✅ Готово! Все купоны активированы, цены пересчитаны, web/data.json сформирован.")

if __name__ == "__main__":
    main()
