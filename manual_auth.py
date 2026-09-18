import json
import os
import shutil
import sys
import urllib.parse as urlparse
from lidlplus.api import LidlPlusApi

sys.stdout.reconfigure(encoding='utf-8')

CONFIG_FILE = "config.json"
ONEDRIVE_DIR = r"D:\OneDrive\Antigravity_repository\Разное\Liddl_coupons_parsing"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"country": "CY", "language": "EN", "store_id": "CY0119", "family_accounts": {}}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    # Копируем в OneDrive, если папка существует
    if os.path.exists(ONEDRIVE_DIR):
        try:
            shutil.copy(CONFIG_FILE, os.path.join(ONEDRIVE_DIR, CONFIG_FILE))
            print(f"💾 Конфигурация синхронизирована в OneDrive: {ONEDRIVE_DIR}")
        except Exception as e:
            print(f"⚠️ Не удалось скопировать в OneDrive: {e}")

def auth_account():
    config = load_config()
    existing = list(config.get("family_accounts", {}).keys())
    print("\n" + "="*80)
    print(f"Уже добавлены в config.json: {', '.join(existing) if existing else 'пока никого'}")
    name = input("\n👤 Введите имя (например: Жена, Сын, Мама) или Enter для выхода: ").strip()
    if not name:
        return False

    print(f"\n🌍 Создаем ссылку авторизации для '{name}'...")
    api = LidlPlusApi(config.get("language", "en"), config.get("country", "cy"))
    login_url = api._register_link

    print("\n" + "-"*80)
    print(f"ШАГ 1: Откройте браузер Chrome в режиме ИНКОГНИТО (Ctrl + Shift + N).")
    print(f"ШАГ 2: Нажмите F12 -> включите мобильный вид (Ctrl + Shift + M).")
    print(f"ШАГ 3: Во вкладке Network включите галочку 'Preserve log'.")
    print(f"ШАГ 4: Вставьте эту ссылку в адресную строку и войдите под аккаунтом '{name}':")
    print(f"\n{login_url}\n")
    print(f"ШАГ 5: В самом конце в панели Network найдите красную строчку 'callback?code=...'")
    print(f"       Кликните по ней правой кнопкой -> Copy -> Copy link address.")
    print("-"*80)

    url_or_code = input(f"\n👉 Вставьте скопированную ссылку для '{name}': ").strip()
    if not url_or_code:
        print("Ввод отменен.")
        return True

    code = url_or_code
    if "code=" in url_or_code:
        try:
            parsed = urlparse.urlparse(url_or_code)
            qs = urlparse.parse_qs(parsed.query)
            if "code" in qs:
                code = qs["code"][0]
            else:
                code = url_or_code.split("code=")[1].split("&")[0]
        except:
            code = url_or_code.split("code=")[1].split("&")[0]

    print(f"\n🔄 Обмениваем код на Refresh Token...")
    try:
        api._authorization_code(code)
        token = api.refresh_token
        config["family_accounts"][name] = token
        save_config(config)
        print(f"\n🎉 УСПЕШНО! Токен для '{name}' получен и сохранен в config.json!")
    except Exception as e:
        print(f"\n❌ Ошибка получения токена: {e}")
        print("Код мог устареть или скопирован не полностью. Попробуйте еще раз.")

    return True

def main():
    print("🚀 Мастер добавления аккаунтов семьи в Lidl Plus")
    while True:
        if not auth_account():
            break
    print("\n👋 Все нужные аккаунты добавлены! Теперь можно запускать: python lidl_parser.py")

if __name__ == "__main__":
    main()
