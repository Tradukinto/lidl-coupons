import json
import os
import re
import sys
import base64
import subprocess
import shutil
from datetime import datetime
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

sys.stdout.reconfigure(encoding='utf-8')

CONFIG_FILE = "config.json"
APP_VERSION = "16.7.0"
OFFERS_APP_VERSION = "17.0.5"

CURL_BIN = shutil.which("curl.exe") or shutil.which("curl") or "curl"

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

    pkg = offer.get("packaging") or ""
    if "kg" in pkg.lower():
        pbox = offer.get("priceBox", {})
        price = pbox.get("largePartNumeric")
        if price:
            return float(price), "/кг"

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

def fetch_product_code(country, store_id, promotion_id, cache={}):
    """Извлечение официального кода товара (SKU) из детального эндпоинта промо-акции"""
    if not promotion_id:
        return ""
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
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if res.returncode == 0 and res.stdout and res.stdout.startswith("{"):
        try:
            data = json.loads(res.stdout)
            main_prods = data.get("productCodes", {}).get("mainProducts", [])
            codes = [mp.get("code") for mp in main_prods if mp.get("code")]
            if len(codes) > 3:
                res_code = f"Категория ({len(codes)} тов.)"
            elif codes:
                res_code = ", ".join(codes)
            else:
                res_code = ""
            cache[promotion_id] = res_code
            return res_code
        except Exception:
            pass
    cache[promotion_id] = ""
    return ""

def find_double_discounts(store_offers, family_coupons):
    """Поиск пересечений: где скидка магазина суммируется со скидкой купона семьи"""
    double_deals = []

    for o in store_offers:
        o_title = clean_text(o.get("title") or "")
        o_brand = clean_text(o.get("brand") or "")
        full_offer_name = f"{o_brand} {o_title}".strip()
        o_words = get_keywords(full_offer_name)
        sku = ", ".join(o.get("productIds", []))
        pbox = o.get("priceBox", {})
        store_disc = pbox.get("discountMessage", "")
        item_price = pbox.get("largePartNumeric")
        item_price_str = f"{item_price:.2f} €" if item_price is not None else "-"
        packaging = clean_text(o.get("packaging") or "")
        offer_img = o.get("imageUrl") or o.get("image") or ""

        unit_val, unit_name = extract_unit_price(o)
        store_unit_price_str = f"{unit_val:.2f} €{unit_name}" if unit_val else "-"

        for c in family_coupons:
            c_title = clean_text(c["Товар"])
            c_words = get_keywords(c_title)
            c_disc = c["Скидка"]
            member = c["У кого"]
            coupon_img = c.get("imageUrl") or ""

            overlap = o_words.intersection(c_words)
            is_match = (len(overlap) >= 2) or (
                len(overlap) == 1 and any(w in overlap for w in [
                    "burger", "edam", "pepper", "grape", "kiwi", "lime", 
                    "cheddar", "gouda", "yoghurt", "bacon", "salami", "pear", "peach"
                ])
            )

            if "juice" in full_offer_name.lower() and "juice" not in c_title.lower():
                is_match = False

            is_veg = "vegetables" in c_title.lower() and (
                any(w in full_offer_name.lower() for w in ["pepper", "salad", "tomato", "carrot", "cucumber", "avocado"])
                or sku.startswith("008") and any(w in full_offer_name.lower() for w in ["pepper", "avocado"])
            )

            if is_match or is_veg:
                final_unit_val = calc_final_unit_price_after_coupon(unit_val, c_disc)
                final_unit_str = f"{final_unit_val:.2f} €{unit_name}" if final_unit_val else "-"

                final_pack_val = calc_final_unit_price_after_coupon(item_price, c_disc)
                final_pack_str = f"{final_pack_val:.2f} €" if final_pack_val else "-"

                double_deals.append({
                    "Код (SKU)": sku,
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

def export_web_data(coupons, store_offers, double_deals, output_path="web/data.json", config={}):
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

        web_family_coupons.append({
            "title": title,
            "discount": disc,
            "sku": sku_val,
            "unit_price": unit_price,
            "image_url": img,
            "owners": sorted(list(owners)),
            "is_shared": len(owners) >= 2
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
            "store_offers_count": len(web_store_offers)
        },
        "double_deals": web_double_deals,
        "family_coupons": web_family_coupons,
        "store_offers": web_store_offers
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"📱 Данные для веб-приложения успешно сохранены: {output_path} ({len(web_double_deals)} комбо, {len(web_family_coupons)} купонов, {len(web_store_offers)} акций)")
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

    # 3. Поиск двойных скидок (пересечений)
    double_deals = find_double_discounts(store_offers, coupons)

    # 4. Экспорт для веб-приложения Telegram Mini App
    export_web_data(coupons, store_offers, double_deals, output_path="web/data.json", config=config)

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
