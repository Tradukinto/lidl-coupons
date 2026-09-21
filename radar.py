import json
import os
import re
import sys

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Comprehensive bilingual & Greek synonym dictionary for Lidl Cyprus
BILINGUAL_THESAURUS = {
    "йогурт": {
        "name": "Йогурт",
        "icon": "🥛",
        "category": "dairy_cheese",
        "synonyms": ["yogurt", "yoghurt", "γιαουρτι", "γιαούρτι", "skyr", "йогурт", "йогурты"]
    },
    "yogurt": {
        "name": "Йогурт",
        "icon": "🥛",
        "category": "dairy_cheese",
        "synonyms": ["yogurt", "yoghurt", "γιαουρτι", "γιαούρτι", "skyr", "йогурт"]
    },
    "лосось": {
        "name": "Лосось / Форель",
        "icon": "🐟",
        "category": "meat_fish",
        "synonyms": ["salmon", "trout", "σολομος", "σολομός", "σολομού", "πέστροφα", "πεστροφα", "лосось", "семга", "сёмга", "форель"]
    },
    "salmon": {
        "name": "Лосось / Форель",
        "icon": "🐟",
        "category": "meat_fish",
        "synonyms": ["salmon", "trout", "σολομος", "σολομός", "σολομού", "πέστροφα", "лосось", "семга", "форель"]
    },
    "сыр": {
        "name": "Сыр / Фета / Халуми",
        "icon": "🧀",
        "category": "dairy_cheese",
        "synonyms": [
            "cheese", "feta", "halloumi", "gouda", "edam", "mozzarella", "cheddar", 
            "parmesan", "grana", "pecorino", "graviera", "τυρι", "τυρί", "φέτα", 
            "χαλούμι", "γραβιέρα", "сыр", "фета", "халуми", "гауда", "эдам", "моцарелла"
        ]
    },
    "cheese": {
        "name": "Сыр / Фета / Халуми",
        "icon": "🧀",
        "category": "dairy_cheese",
        "synonyms": ["cheese", "feta", "halloumi", "gouda", "edam", "mozzarella", "cheddar", "τυρι", "τυρί", "φέτα", "χαλούμι", "сыр"]
    },
    "сливочное масло": {
        "name": "Сливочное масло",
        "icon": "🧈",
        "category": "dairy_cheese",
        "synonyms": ["butter", "βουτυρο", "βούτυρο", "сливочное масло", "масло сливочное"]
    },
    "butter": {
        "name": "Сливочное масло",
        "icon": "🧈",
        "category": "dairy_cheese",
        "synonyms": ["butter", "βουτυρο", "βούτυρο", "сливочное масло"]
    },
    "авокадо": {
        "name": "Авокадо",
        "icon": "🥑",
        "category": "veg_fruit",
        "synonyms": ["avocado", "αβοκαντο", "αβοκάντο", "авокадо"]
    },
    "avocado": {
        "name": "Авокадо",
        "icon": "🥑",
        "category": "veg_fruit",
        "synonyms": ["avocado", "αβοκαντο", "αβοκάντο", "авокадо"]
    },
    "кофе": {
        "name": "Кофе",
        "icon": "☕",
        "category": "beverages",
        "synonyms": ["coffee", "espresso", "cappuccino", "καφες", "καφές", "кофе", "эспрессо"]
    },
    "coffee": {
        "name": "Кофе",
        "icon": "☕",
        "category": "beverages",
        "synonyms": ["coffee", "espresso", "καφες", "καφές", "кофе"]
    },
    "курица": {
        "name": "Курица / Птица",
        "icon": "🍗",
        "category": "meat_fish",
        "synonyms": ["chicken", "κοτοπουλο", "κοτόπουλο", "курица", "цыпленок"]
    },
    "chicken": {
        "name": "Курица / Птица",
        "icon": "🍗",
        "category": "meat_fish",
        "synonyms": ["chicken", "κοτοπουλο", "κοτόπουλο", "курица"]
    },
    "оливковое масло": {
        "name": "Оливковое масло",
        "icon": "🫒",
        "category": "bakery_grocery",
        "synonyms": ["olive oil", "extra virgin", "ελαιολαδο", "ελαιόλαδο", "оливковое масло"]
    },
    "olive oil": {
        "name": "Оливковое масло",
        "icon": "🫒",
        "category": "bakery_grocery",
        "synonyms": ["olive oil", "extra virgin", "ελαιολαδο", "ελαιόλαδο", "оливковое масло"]
    },
    "орехи": {
        "name": "Орехи",
        "icon": "🥜",
        "category": "sweets_snacks",
        "synonyms": [
            "nuts", "almond", "walnut", "cashew", "pistachio", "hazelnut", 
            "peanut", "ξηρων καρπων", "ξηρών καρπών", "αμυγδαλα", "αμύγδαλα", "καρυδια", 
            "καρύδια", "орехи", "миндаль", "фундук", "кешью", "фисташки", "арахис"
        ]
    },
    "nuts": {
        "name": "Орехи",
        "icon": "🥜",
        "category": "sweets_snacks",
        "synonyms": ["nuts", "almond", "walnut", "cashew", "ξηρων καρπων", "орехи"]
    },
    "шоколад": {
        "name": "Шоколад",
        "icon": "🍫",
        "category": "sweets_snacks",
        "synonyms": ["chocolate", "σοκολατα", "σοκολάτα", "шоколад"]
    },
    "chocolate": {
        "name": "Шоколад",
        "icon": "🍫",
        "category": "sweets_snacks",
        "synonyms": ["chocolate", "σοκολατα", "σοκολάτα", "шоколад"]
    },
    "мороженое": {
        "name": "Мороженое",
        "icon": "🍨",
        "category": "sweets_snacks",
        "synonyms": ["ice cream", "παγωτο", "παγωτό", "gelatelli", "bon gelati", "мороженое"]
    },
    "ice cream": {
        "name": "Мороженое",
        "icon": "🍨",
        "category": "sweets_snacks",
        "synonyms": ["ice cream", "παγωτο", "παγωτό", "gelatelli", "bon gelati", "мороженое"]
    },
    "бананы": {
        "name": "Бананы",
        "icon": "🍌",
        "category": "veg_fruit",
        "synonyms": ["banana", "bananas", "μπανανες", "μπανάνες", "банан", "бананы"]
    },
    "яблоки": {
        "name": "Яблоки",
        "icon": "🍎",
        "category": "veg_fruit",
        "synonyms": ["apple", "apples", "μηλα", "μήλα", "яблок"]
    },
    "помидоры": {
        "name": "Помидоры",
        "icon": "🍅",
        "category": "veg_fruit",
        "synonyms": ["tomato", "tomatoes", "cherry tomato", "ντοματα", "ντομάτα", "ντοματες", "томат", "помидор"]
    },
    "огурцы": {
        "name": "Огурцы",
        "icon": "🥒",
        "category": "veg_fruit",
        "synonyms": ["cucumber", "cucumbers", "αγγουρι", "αγγούρι", "αγγουρια", "огур"]
    },
    "яйца": {
        "name": "Яйца",
        "icon": "🥚",
        "category": "dairy_cheese",
        "synonyms": ["eggs", "αυγα", "αβγα", "αυγά", "αβγά", "яйц"]
    },
    "молоко": {
        "name": "Молоко",
        "icon": "🥛",
        "category": "dairy_cheese",
        "synonyms": ["milk", "γαλα", "γάλα", "молоко"]
    },
    "креветки": {
        "name": "Креветки / Морепродукты",
        "icon": "🍤",
        "category": "meat_fish",
        "synonyms": ["shrimp", "shrimps", "prawn", "prawns", "seafood", "γαριδες", "γαρίδες", "θαλασσινα", "креветк", "морепродукт"]
    },
    "говядина": {
        "name": "Говядина / Бургеры",
        "icon": "🥩",
        "category": "meat_fish",
        "synonyms": ["beef", "beef burger", "μοσχαρι", "μοσχάρι", "κιμας", "говядин", "бургер"]
    },
    "свинина": {
        "name": "Свинина",
        "icon": "🥩",
        "category": "meat_fish",
        "synonyms": ["pork", "χοιρινο", "χοιρινό", "свинин", "бекон"]
    },
    "колбаса": {
        "name": "Колбаса / Сосиски / Ветчина",
        "icon": "🌭",
        "category": "meat_fish",
        "synonyms": [
            "sausage", "sausages", "salami", "ham", "wurst", "cabanossi", 
            "λουκανικα", "λουκάνικα", "ζαμπον", "ζαμπόν", "колбас", "сосиск", "ветчин", "салями"
        ]
    },
    "макароны": {
        "name": "Макароны / Паста",
        "icon": "🍝",
        "category": "bakery_grocery",
        "synonyms": ["pasta", "spaghetti", "penne", "linguine", "combino", "μακαρονια", "μακαρόνια", "макарон", "паста", "спагетти"]
    },
    "хлеб": {
        "name": "Хлеб / Выпечка",
        "icon": "🍞",
        "category": "bakery_grocery",
        "synonyms": ["bread", "toast", "baguette", "ψωμι", "ψωμί", "хлеб", "тост", "багет"]
    },
    "чай": {
        "name": "Чай",
        "icon": "🫖",
        "category": "beverages",
        "synonyms": ["tea", "lord nelson", "τσαϊ", "τσάι", "чай"]
    },
    "сок": {
        "name": "Сок",
        "icon": "🧃",
        "category": "beverages",
        "synonyms": ["juice", "eviva", "solevita", "χυμος", "χυμός", "сок"]
    },
    "пиво": {
        "name": "Пиво",
        "icon": "🍺",
        "category": "beverages",
        "synonyms": ["beer", "perlenbacher", "argus", "μπυρα", "μπύρα", "пиво"]
    },
    "вино": {
        "name": "Вино",
        "icon": "🍷",
        "category": "beverages",
        "synonyms": ["wine", "allini", "κρασι", "κρασί", "sparkling", "prosecco", "вино"]
    },
    "пицца": {
        "name": "Пицца",
        "icon": "🍕",
        "category": "bakery_grocery",
        "synonyms": ["pizza", "πιτσα", "πίτσα", "trattoria alfredo", "пицца"]
    },
    "parkside": {
        "name": "Parkside / Инструменты",
        "icon": "🔧",
        "category": "non_food",
        "synonyms": ["parkside", "инструмент", "парксайд"]
    },
    "парксайд": {
        "name": "Parkside / Инструменты",
        "icon": "🔧",
        "category": "non_food",
        "synonyms": ["parkside", "парксайд"]
    },
    "бытовая химия": {
        "name": "W5 / Бытовая химия",
        "icon": "🧺",
        "category": "non_food",
        "synonyms": ["w5", "detergent", "laundry", "cleaner", "tabs", "порошок", "стирк"]
    },
    "w5": {
        "name": "W5 / Бытовая химия",
        "icon": "🧺",
        "category": "non_food",
        "synonyms": ["w5", "detergent", "cleaner", "бытовая химия"]
    },
    "бумага": {
        "name": "Туалетная бумага / Салфетки",
        "icon": "🧻",
        "category": "non_food",
        "synonyms": ["toilet paper", "kitchen roll", "floralys", "χαρτι υγειας", "χαρτί υγείας", "бумага"]
    }
}

DEFAULT_TRACKED_ITEMS = [
    {
        "id": "yogurt",
        "name": "Йогурт",
        "icon": "🥛",
        "category": "dairy_cheese",
        "keywords": ["yogurt", "yoghurt", "γιαουρτι", "γιαούρτι", "skyr", "йогурт"]
    },
    {
        "id": "salmon",
        "name": "Лосось / Форель",
        "icon": "🐟",
        "category": "meat_fish",
        "keywords": ["salmon", "trout", "σολομος", "σολομός", "σολομού", "πέστροφα", "лосось", "семга", "форель"]
    },
    {
        "id": "cheese",
        "name": "Сыр / Фета / Халуми",
        "icon": "🧀",
        "category": "dairy_cheese",
        "keywords": ["cheese", "feta", "halloumi", "gouda", "edam", "mozzarella", "cheddar", "τυρι", "τυρί", "φέτα", "χαλούμι", "сыр"]
    },
    {
        "id": "butter",
        "name": "Сливочное масло",
        "icon": "🧈",
        "category": "dairy_cheese",
        "keywords": ["butter", "βουτυρο", "βούτυρο", "сливочное масло"]
    },
    {
        "id": "avocado",
        "name": "Авокадо",
        "icon": "🥑",
        "category": "veg_fruit",
        "keywords": ["avocado", "αβοκαντο", "αβοκάντο", "авокадо"]
    },
    {
        "id": "coffee",
        "name": "Кофе",
        "icon": "☕",
        "category": "beverages",
        "keywords": ["coffee", "espresso", "καφες", "καφές", "кофе"]
    },
    {
        "id": "chicken",
        "name": "Курица / Птица",
        "icon": "🍗",
        "category": "meat_fish",
        "keywords": ["chicken", "κοτοπουλο", "κοτόπουλο", "курица", "цыпленок"]
    },
    {
        "id": "olive_oil",
        "name": "Оливковое масло",
        "icon": "🫒",
        "category": "bakery_grocery",
        "keywords": ["olive oil", "ελαιολαδο", "ελαιόλαδο", "оливковое масло"]
    },
    {
        "id": "nuts",
        "name": "Орехи",
        "icon": "🥜",
        "category": "sweets_snacks",
        "keywords": ["nuts", "almond", "walnut", "cashew", "ξηρων καρπων", "орехи"]
    },
    {
        "id": "chocolate",
        "name": "Шоколад",
        "icon": "🍫",
        "category": "sweets_snacks",
        "keywords": ["chocolate", "σοκολατα", "σοκολάτα", "шоколад"]
    },
    {
        "id": "parkside",
        "name": "Parkside / Инструменты",
        "icon": "🔧",
        "category": "non_food",
        "keywords": ["parkside", "инструмент", "парксайд"]
    }
]

TRACKED_ITEMS_FILE = "tracked_items.json"

def normalize_text(text):
    if not text:
        return ""
    text = text.lower()
    accents = {
        'ά': 'α', 'έ': 'ε', 'ή': 'η', 'ί': 'ι', 'ό': 'ο', 'ύ': 'υ', 'ώ': 'ω',
        'ϊ': 'ι', 'ΐ': 'ι', 'ϋ': 'υ', 'ΰ': 'υ',
        'ё': 'е'
    }
    for k, v in accents.items():
        text = text.replace(k, v)
    return re.sub(r'\s+', ' ', text).strip()

def load_tracked_items(filepath=TRACKED_ITEMS_FILE):
    """Загрузка отслеживаемых товаров из файла или создание начального списка"""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                items = json.load(f)
                if isinstance(items, list):
                    return items
        except Exception as e:
            print(f"⚠️ Ошибка чтения {filepath}: {e}")
    
    save_tracked_items(DEFAULT_TRACKED_ITEMS, filepath)
    return DEFAULT_TRACKED_ITEMS

def save_tracked_items(items, filepath=TRACKED_ITEMS_FILE):
    """Сохранение списка отслеживаемых товаров"""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения {filepath}: {e}")
        return False

def expand_keyword_query(query):
    """Расширяет пользовательский запрос синонимами из тезауруса"""
    q_clean = normalize_text(query)
    if not q_clean:
        return None

    # Check exact or partial match in thesaurus
    for key, info in BILINGUAL_THESAURUS.items():
        norm_key = normalize_text(key)
        if norm_key == q_clean or q_clean in norm_key:
            return {
                "id": re.sub(r'[^a-z0-9_]', '', norm_key.replace(" ", "_")) or "item",
                "name": info["name"],
                "icon": info["icon"],
                "category": info["category"],
                "keywords": list(set([normalize_text(s) for s in info["synonyms"]]))
            }

    # Fallback to custom query
    return {
        "id": re.sub(r'[^a-zA-Z0-9_]', '', q_clean.replace(" ", "_")) or "custom",
        "name": query.capitalize(),
        "icon": "🎯",
        "category": "custom",
        "keywords": [q_clean]
    }

def match_text_with_keywords(text, keywords):
    """Проверяет совпадение текста с набором ключевых слов с учетом границ слов"""
    norm_t = normalize_text(text)
    for kw in keywords:
        norm_kw = normalize_text(kw)
        if not norm_kw:
            continue
        # If keyword is short (4 chars or less), use word boundary
        if len(norm_kw) <= 4:
            pattern = r'(?:\b|_|^)' + re.escape(norm_kw) + r'(?:\b|_|$)'
            if re.search(pattern, norm_t):
                return kw
        else:
            if norm_kw in norm_t:
                return kw
    return None

def find_radar_matches(tracked_items, double_deals=None, family_coupons=None, super_savers=None, store_offers=None):
    """Поиск всех совпадений по отслеживаемым товарам во всех разделах каталога"""
    matches = []
    seen_keys = set()

    all_sections = [
        ("double", "🔥 Комбо (Купон + Скидка магазина)", double_deals or []),
        ("coupons", "🎟 Персональный купон семьи", family_coupons or []),
        ("super", "⚡ Super Saver (1 день)", super_savers or []),
        ("store", "🛒 Daily Saver (Магазин)", store_offers or [])
    ]

    for item_def in tracked_items:
        item_id = item_def.get("id")
        item_name = item_def.get("name", item_id)
        item_icon = item_def.get("icon", "🎯")
        keywords = item_def.get("keywords", [])

        for sec_type, sec_label, deals in all_sections:
            for d in deals:
                title = d.get("title") or ""
                pkg = d.get("packaging") or ""
                full_text = f"{title} {pkg}"

                matched_kw = match_text_with_keywords(full_text, keywords)
                if matched_kw:
                    sku = d.get("sku") or ""
                    unique_key = (item_id, sec_type, sku or title)
                    if unique_key in seen_keys:
                        continue
                    seen_keys.add(unique_key)

                    disc = d.get("discount") or d.get("coupon_discount") or d.get("store_discount") or d.get("super_discount") or ""
                    price = d.get("final_pack_price") or d.get("final_price") or d.get("pack_price") or d.get("price") or "-"
                    unit_p = d.get("final_unit_price") or d.get("unit_price") or d.get("store_unit_price") or ""
                    owners = d.get("owners") or ([d.get("owner")] if d.get("owner") else [])
                    validity = d.get("validity_str") or d.get("formatted_date") or ""

                    matches.append({
                        "tracked_item_id": item_id,
                        "tracked_item_name": item_name,
                        "tracked_item_icon": item_icon,
                        "matched_keyword": matched_kw,
                        "deal_type": sec_type,
                        "deal_type_label": sec_label,
                        "sku": sku,
                        "title": title,
                        "price": price,
                        "unit_price": unit_p,
                        "discount": disc,
                        "packaging": pkg,
                        "owners": owners,
                        "validity": validity,
                        "image_url": d.get("image_url") or "",
                        "deal_date": d.get("deal_date") or "",
                        "product_url": d.get("product_url") or ""
                    })

    prio = {"double": 1, "super": 2, "coupons": 3, "store": 4}
    matches.sort(key=lambda m: (prio.get(m["deal_type"], 9), m["title"]))
    return matches
