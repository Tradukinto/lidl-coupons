Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "python """ & Replace(WScript.ScriptFullName, "start_bot_background.vbs", "telegram_notifier.py") & """ --daemon", 0, False
