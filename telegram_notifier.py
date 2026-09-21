import json
import os
import re
import sys
import requests
import urllib3

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SUBSCRIBERS_FILE = "subscribers.json"
NOTIFIED_DEALS_FILE = "notified_deals.json"
STATE_FILE = "bot_state.json"

def load_subscribers(config=None, filepath=SUBSCRIBERS_FILE):
    """Загрузка списка подписчиков (chat_id пользователей и семейных групп)"""
    subs = set()

    # From config
    if config:
        tg_conf = config.get("telegram", {})
        if tg_conf.get("chat_id"):
            subs.add(str(tg_conf["chat_id"]))
        for cid in tg_conf.get("chat_ids", []):
            if cid:
                subs.add(str(cid))

    # From local file
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        cid = item.get("chat_id") if isinstance(item, dict) else item
                        if cid:
                            subs.add(str(cid))
        except Exception as e:
            print(f"⚠️ Ошибка чтения {filepath}: {e}")

    return sorted(list(subs))

def save_subscribers(subs_list, filepath=SUBSCRIBERS_FILE):
    """Сохранение подписчиков в файл"""
    try:
        data = [{"chat_id": cid} for cid in subs_list]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения {filepath}: {e}")
        return False

def load_bot_state(filepath=STATE_FILE):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_update_id": 0}

def save_bot_state(state, filepath=STATE_FILE):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass

def get_main_keyboard():
    """Постоянная клавиатура быстрых действий под полем ввода в Telegram"""
    return {
        "keyboard": [
            [
                {"text": "🎯 Радар сейчас"},
                {"text": "🛒 Витрина Lidl", "web_app": {"url": "https://tradukinto.github.io/lidl-coupons/"}}
            ],
            [
                {"text": "📋 Мой список"},
                {"text": "➕ Добавить товар"}
            ],
            [
                {"text": "🧹 Очистить список"},
                {"text": "ℹ️ Инструкция"}
            ]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }

def send_telegram_message(bot_token, chat_id, text, parse_mode="HTML", reply_markup=None):
    """Отправка сообщения в Telegram с поддержкой клавиатуры и кнопок"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    if reply_markup is False:
        pass
    elif reply_markup is not None:
        payload["reply_markup"] = reply_markup
    else:
        payload["reply_markup"] = get_main_keyboard()

    try:
        res = requests.post(url, json=payload, verify=False, timeout=10)
        return res.json()
    except Exception as e:
        print(f"⚠️ Ошибка отправки сообщения в {chat_id}: {e}")
        return None

def ensure_chat_menu_button(bot_token, chat_id=None):
    """Устанавливает кнопку меню с командами [/] Меню для чата или глобально"""
    url = f"https://api.telegram.org/bot{bot_token}/setChatMenuButton"
    payload = {"menu_button": {"type": "commands"}}
    if chat_id is not None:
        try:
            payload["chat_id"] = int(chat_id)
        except Exception:
            payload["chat_id"] = chat_id
    try:
        res = requests.post(url, json=payload, verify=False, timeout=10)
        return res.json().get("ok", False)
    except Exception as e:
        print(f"⚠️ Ошибка установки ChatMenuButton: {e}")
        return False

def set_bot_commands(bot_token):
    """Установка списка команд в системное меню бота Telegram"""
    url = f"https://api.telegram.org/bot{bot_token}/setMyCommands"
    commands = [
        {"command": "radar", "description": "🎯 Проверить совпадения радара сейчас"},
        {"command": "list", "description": "📋 Мои отслеживаемые товары"},
        {"command": "add", "description": "➕ Добавить товар (/add йогурт)"},
        {"command": "del", "description": "🗑 Удалить товар (/del йогурт)"},
        {"command": "clear", "description": "🧹 Очистить список радара"},
        {"command": "help", "description": "ℹ️ Инструкция и возможности"},
        {"command": "start", "description": "🚀 Главное меню и запуск витрины"}
    ]
    try:
        res = requests.post(url, json={"commands": commands}, verify=False, timeout=10)
        return res.json().get("ok", False)
    except Exception as e:
        print(f"⚠️ Ошибка установки команд бота: {e}")
        return False

def sync_telegram_updates(bot_token, config=None):
    """
    Опрос входящих сообщений (getUpdates) от пользователей и групп.
    Автоматически регистрирует chat_id подписчиков и отвечает на команды /start, /help, /list, /add, /del.
    """
    if not bot_token:
        return []

    set_bot_commands(bot_token)
    ensure_chat_menu_button(bot_token)
    subscribers = set(load_subscribers(config))
    for cid in subscribers:
        ensure_chat_menu_button(bot_token, cid)

    state = load_bot_state()
    last_update_id = state.get("last_update_id", 0)

    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    params = {
        "offset": last_update_id + 1,
        "timeout": 2
    }

    try:
        res = requests.get(url, params=params, verify=False, timeout=10)
        data = res.json()
    except Exception as e:
        print(f"⚠️ Не удалось подключиться к Telegram API: {e}")
        return list(subscribers)

    if not data.get("ok"):
        return list(subscribers)

    updates = data.get("result", [])
    max_id = last_update_id

    for up in updates:
        uid = up.get("update_id", 0)
        if uid > max_id:
            max_id = uid

        msg = up.get("message") or up.get("channel_post") or up.get("my_chat_member", {}).get("chat")
        if not msg:
            continue

        chat = msg.get("chat") or msg
        chat_id = str(chat.get("id"))
        chat_title = chat.get("title") or chat.get("first_name") or chat_id

        if chat_id not in subscribers:
            subscribers.add(chat_id)
            print(f"🔔 Новый подписчик бота: {chat_title} (ID: {chat_id})")

        ensure_chat_menu_button(bot_token, chat_id)

        # Process text commands & button presses
        text = (msg.get("text") or "").strip()
        if not text:
            continue

        text_clean = text.strip()
        cmd_clean = text_clean.lower()
        parts = text_clean.split(maxsplit=1)
        cmd = parts[0].lower().replace("@lidlcouponsbot", "")

        from radar import load_tracked_items, save_tracked_items, expand_keyword_query, find_radar_matches

        if cmd == "/start":
            welcome_msg = (
                f"👋 <b>Привет! Я бот Lidl Пафос.</b>\n\n"
                f"Я отслеживаю скидки магазина и персональные купоны семьи на нужные товары "
                f"(йогурты, лосось, сыр, авокадо, кофе, Parkside и др.) и сразу присылаю уведомления.\n\n"
                f"🎯 <b>Быстрое управление кнопками прямо под экраном:</b>\n"
                f"• 🎯 <b>Радар сейчас</b> — проверить совпадения скидок сейчас\n"
                f"• 🛒 <b>Витрина Lidl</b> — открыть каталог со скидками и купонами семьи\n"
                f"• 📋 <b>Мой список</b> — список отслеживаемых товаров\n"
                f"• ➕ <b>Добавить товар</b> — добавить новый продукт\n"
                f"• 🧹 <b>Очистить список</b> — очистить радар\n"
                f"• ℹ️ <b>Инструкция</b> — справка по всем возможностям\n\n"
                f"📋 Также доступно системное меню по кнопке <b>[/] Меню</b> слева внизу!\n\n"
                f"💡 <i>Вы можете просто написать боту название товара (например: <code>йогурт</code> или <code>сыр</code>), и он автоматически добавит его в радар.</i>"
            )
            send_telegram_message(bot_token, chat_id, welcome_msg)

        elif cmd == "/radar" or cmd_clean in ["🎯 радар сейчас", "радар", "радар сейчас", "проверить радар"]:
            items = load_tracked_items()
            if not items:
                send_telegram_message(
                    bot_token, chat_id,
                    "🎯 <b>Список радара пуст.</b>\n\n"
                    "Нажмите кнопку ➕ <b>Добавить товар</b> или отправьте команду <code>/add &lt;товар&gt;</code> (например: <code>/add yogurt</code>)."
                )
            else:
                try:
                    data_file = os.path.join("web", "data.json")
                    if os.path.exists(data_file):
                        with open(data_file, "r", encoding="utf-8") as df:
                            data = json.load(df)
                        matches = find_radar_matches(
                            items,
                            double_deals=data.get("double_deals", []),
                            family_coupons=data.get("family_coupons", []),
                            super_savers=data.get("super_savers", []),
                            store_offers=data.get("store_offers", [])
                        )
                        if matches:
                            lines = []
                            for m in matches[:12]:
                                type_label = {"double": "🔥 Комбо", "super": "⚡ Super", "coupons": "🎟 Купон", "store": "🛒 Магазин"}.get(m.get("type"), "🎯")
                                price_val = m.get('discounted_price', m.get('price'))
                                price_str = f"<b>{price_val}€</b>" if price_val and price_val != '-' else ""
                                disc_str = f" <b>{m.get('discount')}</b>" if m.get('discount') else ""
                                lines.append(f"• {type_label} <b>{m.get('title')}</b>{disc_str} — {price_str} (#{m.get('matched_keyword')})")
                            msg_text = f"🎯 <b>Найдено скидок по радару ({len(matches)}):</b>\n\n" + "\n".join(lines)
                            if len(matches) > 12:
                                msg_text += f"\n\n<i>...и ещё {len(matches)-12} товаров. Нажмите 🛒 Витрина Lidl для просмотра всех!</i>"
                            send_telegram_message(bot_token, chat_id, msg_text)
                        else:
                            send_telegram_message(bot_token, chat_id, f"🎯 <b>По вашим {len(items)} товарам сейчас нет активных скидок.</b>\nКак только товар появится в каталоге, я сразу пришлю оповещение!")
                    else:
                        send_telegram_message(bot_token, chat_id, "ℹ️ Каталог еще формируется.")
                except Exception as err:
                    send_telegram_message(bot_token, chat_id, f"⚠️ Ошибка проверки радара: {err}")

        elif cmd == "/list" or cmd_clean in ["📋 мой список", "мой список", "список", "мои товары"]:
            items = load_tracked_items()
            if items:
                lines = [f"• {it.get('icon', '🎯')} <b>{it.get('name')}</b>" for it in items]
                reply = (
                    f"📋 <b>Отслеживаемые товары в радаре ({len(items)}):</b>\n\n"
                    + "\n".join(lines)
                    + "\n\n<i>Чтобы добавить товар, отправьте <code>/add название</code></i>\n"
                    + "<i>Чтобы удалить: <code>/del название</code></i>\n"
                    + "<i>Чтобы сбросить всё: нажмите 🧹 Очистить список</i>"
                )
            else:
                reply = "📋 <b>Список отслеживания пуст.</b>\nДобавьте товары кнопкой ➕ <b>Добавить товар</b> или командой <code>/add сыр</code>."
            send_telegram_message(bot_token, chat_id, reply)

        elif (cmd == "/add" and len(parts) > 1) or (cmd in ["добавить", "add"] and len(parts) > 1):
            q = parts[1].strip()
            item_def = expand_keyword_query(q)
            if item_def:
                cur_items = load_tracked_items()
                existing = next((it for it in cur_items if it.get("id") == item_def.get("id") or it.get("name").lower() == item_def.get("name").lower()), None)
                if not existing:
                    cur_items.append(item_def)
                    save_tracked_items(cur_items)
                    reply = (
                        f"✅ Товар {item_def.get('icon', '🎯')} <b>{item_def.get('name')}</b> успешно добавлен в радар!\n"
                        f"Ключевые слова: <code>{', '.join(item_def.get('keywords', []))}</code>\n\n"
                        f"Нажмите 🎯 <b>Радар сейчас</b> для проверки скидок!"
                    )
                else:
                    reply = f"ℹ️ Товар {existing.get('icon', '🎯')} <b>{existing.get('name')}</b> уже отслеживается в радаре."
                send_telegram_message(bot_token, chat_id, reply)
            else:
                # Custom keyword
                cur_items = load_tracked_items()
                custom_id = f"custom_{re.sub(r'[^a-zA-Z0-9а-яА-ЯёЁ]', '', q.lower())}"
                new_item = {
                    "id": custom_id,
                    "name": q.capitalize(),
                    "icon": "🎯",
                    "category": "all",
                    "keywords": [q.lower()]
                }
                cur_items.append(new_item)
                save_tracked_items(cur_items)
                send_telegram_message(bot_token, chat_id, f"✅ Товар 🎯 <b>{q.capitalize()}</b> добавлен в радар по запросу <code>{q.lower()}</code>.\n\nНажмите 🎯 <b>Радар сейчас</b> для проверки!")

        elif (cmd == "/add" and len(parts) == 1) or cmd_clean in ["➕ добавить товар", "добавить товар", "+", "добавить"]:
            add_help = (
                "➕ <b>Как добавить товар в Радар:</b>\n\n"
                "Отправьте команду с названием товара или просто напишите его в чат:\n"
                "• <code>/add yogurt</code> (или <code>/add йогурт</code>)\n"
                "• <code>/add сыр</code> (или <code>/add cheese</code>)\n"
                "• <code>/add лосось</code> (или <code>/add salmon</code>)\n"
                "• <code>/add кофе</code> (или <code>/add coffee</code>)\n"
                "• <code>/add авокадо</code> (или <code>/add avocado</code>)\n"
                "• <code>/add parkside</code>\n\n"
                "💡 <i>Бот понимает синонимы на русском, греческом и английском языках!</i>"
            )
            send_telegram_message(bot_token, chat_id, add_help)

        elif (cmd == "/del" and len(parts) > 1) or (cmd in ["удалить", "del", "remove"] and len(parts) > 1):
            q = parts[1].strip().lower()
            cur_items = load_tracked_items()
            filtered = [it for it in cur_items if it.get("id") != q and it.get("name").lower() != q]
            if len(filtered) < len(cur_items):
                save_tracked_items(filtered)
                send_telegram_message(bot_token, chat_id, f"🗑 Товар <b>{q}</b> удален из радара.")
            else:
                send_telegram_message(bot_token, chat_id, f"⚠️ Товар <b>{q}</b> не найден в списке отслеживаемых. Нажмите 📋 <b>Мой список</b>.")

        elif cmd == "/del" and len(parts) == 1:
            del_help = (
                "🗑 <b>Как удалить товар из Радара:</b>\n\n"
                "Отправьте команду <code>/del название</code> (например: <code>/del yogurt</code> или <code>/del сыр</code>).\n\n"
                "Посмотреть отслеживаемые товары можно по кнопке 📋 <b>Мой список</b>."
            )
            send_telegram_message(bot_token, chat_id, del_help)

        elif cmd == "/clear" or cmd_clean in ["🧹 очистить список", "очистить список", "очистить", "clear"]:
            save_tracked_items([])
            send_telegram_message(bot_token, chat_id, "🧹 <b>Список радара очищен!</b>\nТеперь вы можете добавить нужные товары кнопкой ➕ <b>Добавить товар</b>.")

        elif cmd in ["/help", "help"] or cmd_clean in ["ℹ️ инструкция", "инструкция", "помощь", "справка"]:
            help_msg = (
                f"ℹ️ <b>Возможности бота и витрины Lidl Пафос</b>\n\n"
                f"🎯 <b>Кнопки под полем ввода (1 тап):</b>\n"
                f"• 🎯 <b>Радар сейчас</b> — моментальная проверка скидок\n"
                f"• 🛒 <b>Витрина Lidl</b> — запуск каталога со скидками и купонами\n"
                f"• 📋 <b>Мой список</b> — список отслеживаемых позиций\n"
                f"• ➕ <b>Добавить товар</b> — добавление новых продуктов\n"
                f"• 🧹 <b>Очистить список</b> — сброс списка радара\n"
                f"• ℹ️ <b>Инструкция</b> — эта справка\n\n"
                f"📋 <b>Команды в меню [/] Меню (слева внизу):</b>\n"
                f"• <code>/radar</code> — проверить радар\n"
                f"• <code>/list</code> — список товаров\n"
                f"• <code>/add &lt;товар&gt;</code> — добавить (напр. <code>/add сыр</code>)\n"
                f"• <code>/del &lt;товар&gt;</code> — удалить\n"
                f"• <code>/clear</code> — очистить список\n\n"
                f"📱 <b>Разделы витрины:</b>\n"
                f"🔥 <b>Комбо</b> — магазинная скидка + купон семьи\n"
                f"🎟 <b>Купоны</b> — персональные купоны 4 аккаунтов\n"
                f"⚡ <b>Супер-день</b> — однодневные Great Deals\n"
                f"🛒 <b>Магазин</b> — каталог магазина в Пафосе\n"
                f"🔔 <b>Радар</b> — визуальный поиск с автоподсказками\n"
                f"⭐ <b>Список</b> — список покупок для похода в магазин"
            )
            send_telegram_message(bot_token, chat_id, help_msg)

        else:
            # Direct product name entered without command
            item_def = expand_keyword_query(text_clean)
            if item_def:
                cur_items = load_tracked_items()
                existing = next((it for it in cur_items if it.get("id") == item_def.get("id") or it.get("name").lower() == item_def.get("name").lower()), None)
                if not existing:
                    cur_items.append(item_def)
                    save_tracked_items(cur_items)
                    reply = (
                        f"✅ Товар {item_def.get('icon', '🎯')} <b>{item_def.get('name')}</b> добавлен в радар!\n"
                        f"Ключевые слова: <code>{', '.join(item_def.get('keywords', []))}</code>\n\n"
                        f"Нажмите 🎯 <b>Радар сейчас</b>, чтобы проверить наличие скидок!"
                    )
                else:
                    reply = (
                        f"ℹ️ Товар {existing.get('icon', '🎯')} <b>{existing.get('name')}</b> уже отслеживается в вашем радаре.\n"
                        f"Нажмите 🎯 <b>Радар сейчас</b> для проверки скидок."
                    )
                send_telegram_message(bot_token, chat_id, reply)
            else:
                unknown_msg = (
                    f"❓ Команда <b>{text_clean}</b> не распознана.\n\n"
                    f"Используйте кнопки внизу экрана или выберите команду по кнопке <b>[/] Меню</b> слева внизу."
                )
                send_telegram_message(bot_token, chat_id, unknown_msg)

    if max_id > last_update_id:
        state["last_update_id"] = max_id
        save_bot_state(state)

    subs_list = sorted(list(subscribers))
    save_subscribers(subs_list)
    return subs_list

def load_notified_deals(filepath=NOTIFIED_DEALS_FILE):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_notified_deals(deals, filepath=NOTIFIED_DEALS_FILE):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(deals, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Ошибка сохранения {filepath}: {e}")

def get_deal_cache_key(deal):
    """Уникальный ключ акции для защиты от повторных оповещений"""
    sku = deal.get("sku") or ""
    title = deal.get("title") or ""
    price = deal.get("price") or ""
    disc = deal.get("discount") or ""
    validity = deal.get("validity") or ""
    return f"{deal.get('tracked_item_id')}_{deal.get('deal_type')}_{sku}_{title}_{price}_{disc}_{validity}"

def format_radar_digest(matches):
    """Форматирует красивый дайджест найденных акций для Telegram"""
    if not matches:
        return ""

    # Group matches by tracked item
    by_item = {}
    for m in matches:
        item_id = m.get("tracked_item_id")
        if item_id not in by_item:
            by_item[item_id] = {
                "name": m.get("tracked_item_name"),
                "icon": m.get("tracked_item_icon", "🎯"),
                "deals": []
            }
        by_item[item_id]["deals"].append(m)

    lines = [
        "🎯 <b>РАДАР СКИДОК LIDL ПАФОС</b> 🎯",
        f"<i>Найдены актуальные скидки на отслеживаемые товары:</i>\n"
    ]

    for item_id, group in by_item.items():
        icon = group["icon"]
        name = group["name"]
        deals = group["deals"]
        lines.append(f"{icon} <b>{name}</b> ({len(deals)}):")

        # Top 3-4 deals per item to keep message compact
        for d in deals[:4]:
            t_label = "🔥 Комбо" if d["deal_type"] == "double" else "⚡ Super" if d["deal_type"] == "super" else "🎟 Купон" if d["deal_type"] == "coupons" else "🛒 Акция"
            price_str = f"<b>{d['price']}</b>" if d['price'] != '-' else ""
            unit_str = f" ({d['unit_price']})" if d.get('unit_price') and d['unit_price'] != '-' else ""
            disc_str = f" <b>{d['discount']}</b>" if d.get('discount') else ""
            owners_str = f" [{', '.join(d['owners'])}]" if d.get('owners') else ""
            date_str = f" • <i>{d['validity']}</i>" if d.get('validity') else ""

            line = f" • {t_label}: <b>{d['title']}</b>"
            if disc_str:
                line += f" {disc_str}"
            if price_str:
                line += f" → {price_str}{unit_str}"
            if owners_str:
                line += f" {owners_str}"
            if date_str:
                line += f"{date_str}"
            lines.append(line)

        if len(deals) > 4:
            lines.append(f"   <i>...и еще {len(deals) - 4} предложений в приложении</i>")
        lines.append("")

    lines.append("📱 <i>Полный список и фасовки смотрите в мини-приложении!</i>")
    return "\n".join(lines)

def send_radar_notifications(bot_token, matches, config=None, force=False):
    """
    Проверяет совпадения акций с отслеживаемыми товарами и отправляет уведомление в Telegram.
    Использует кэш `notified_deals.json`, чтобы не повторять уже отправленные акции.
    """
    if not bot_token or not matches:
        return 0

    subscribers = sync_telegram_updates(bot_token, config)
    if not subscribers:
        print("ℹ️ Нет зарегистрированных получателей для Telegram-уведомлений. Отправьте /start боту @lidlcouponsbot.")
        return 0

    notified = load_notified_deals()
    new_matches = []

    for m in matches:
        key = get_deal_cache_key(m)
        if force or key not in notified:
            new_matches.append(m)
            notified[key] = {
                "title": m.get("title"),
                "price": m.get("price"),
                "discount": m.get("discount"),
                "notified_at": str(os.getenv("GITHUB_RUN_ID") or "local")
            }

    if not new_matches:
        print("ℹ️ Новых акций по радару нет (все уже отправлены ранее).")
        return 0

    print(f"📢 Найдено {len(new_matches)} новых акций для отправки в Telegram!")
    msg_text = format_radar_digest(new_matches)

    sent_count = 0
    for chat_id in subscribers:
        res = send_telegram_message(bot_token, chat_id, msg_text)
        if res and res.get("ok"):
            sent_count += 1
            print(f"   ✅ Уведомление успешно доставлено в чат {chat_id}")
        else:
            print(f"   ⚠️ Ошибка отправки в чат {chat_id}: {res}")

    save_notified_deals(notified)
    return sent_count

if __name__ == "__main__":
    import sys
    config = {}
    if os.path.exists("config.json"):
        with open("config.json", encoding="utf-8") as f:
            config = json.load(f)
    token = config.get("telegram", {}).get("bot_token") or "8891599403:AAHhNhQdmzXZWgm74tQVNx1-nB7eB8Ye54A"
    print(f"🤖 Проверка Telegram-бота (токен: ...{token[-8:]})...")
    subs = sync_telegram_updates(token, config)
    print(f"👥 Зарегистрировано подписчиков: {len(subs)} ({subs})")
    if "--test" in sys.argv:
        if subs:
            print("📤 Отправка тестового сообщения подписчикам...")
            for cid in subs:
                send_telegram_message(token, cid, "🔔 <b>Тест бота Lidl Coupons:</b> Радар скидок успешно настроен и готов к отправке акций!")
            print("✅ Тестовые сообщения отправлены.")
        else:
            print("ℹ️ Нет подписчиков для тестирования. Отправьте /start боту @lidlcouponsbot в Telegram.")
