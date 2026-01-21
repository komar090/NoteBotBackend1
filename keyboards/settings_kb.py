from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_settings_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕒 Изменить часовой пояс", callback_data="set_timezone")],
        [InlineKeyboardButton(text="💳 Статус подписки", callback_data="check_subscription")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="show_help")],
        [InlineKeyboardButton(text="🆘 Тех. поддержка", url="tg://user?id=272195202")],
        [InlineKeyboardButton(text="🗑 Удалить все записи", callback_data="delete_all_request")]
    ])

def get_timezone_kb():
    # Common Russian Timezones
    zones = [
        ("Kaliningrad (UTC+2)", "Europe/Kaliningrad"),
        ("Moscow (UTC+3)", "Europe/Moscow"),
        ("Samara (UTC+4)", "Europe/Samara"),
        ("Yekaterinburg (UTC+5)", "Asia/Yekaterinburg"),
        ("Omsk (UTC+6)", "Asia/Omsk"),
        ("Novosibirsk (UTC+7)", "Asia/Novosibirsk"),
        ("Irkutsk (UTC+8)", "Asia/Irkutsk"),
        ("Vladivostok (UTC+10)", "Asia/Vladivostok"),
        ("Magadan (UTC+11)", "Asia/Magadan"),
        ("Kamchatka (UTC+12)", "Asia/Kamchatka"),
    ]
    
    keyboard = []
    row = []
    for label, zone in zones:
        row.append(InlineKeyboardButton(text=label, callback_data=f"tz_{zone}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_settings")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
