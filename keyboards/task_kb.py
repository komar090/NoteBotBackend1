from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

categories = ["Здоровье", "Работа", "Финансы", "Идеи", "Покупки", "Другое"]

def get_categories_kb(custom_categories: list = None):
    # Default categories
    default_cats = ["Здоровье", "Работа", "Финансы", "Идеи", "Покупки", "Другое"]
    
    # Merge
    all_cats = default_cats.copy()
    if custom_categories:
        all_cats.extend(custom_categories)
        
    keyboard = []
    # 2 buttons per row
    row = []
    for cat in all_cats:
        row.append(InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    # Actions row
    actions_row = [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_task")]
    
    # Add "Add Category" button separately? Or in the list?
    # Better as separate action. But wait, this KB is for SELECTING a category.
    # Adding a category is usually a Settings action or a specific button here "➕ Добавить"
    actions_row.insert(0, InlineKeyboardButton(text="➕ Своя", callback_data="add_custom_category"))
    
    keyboard.append(actions_row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_reminder_kb(is_premium: bool = False):
    keyboard = [
        [
            InlineKeyboardButton(text="🔕 Без уведомлений", callback_data="remind_none"),
        ],
        [
            InlineKeyboardButton(text="⏱ 15 мин", callback_data="remind_15m"),
            InlineKeyboardButton(text="⏱ 1 час", callback_data="remind_1h"),
            InlineKeyboardButton(text="🌅 Завтра", callback_data="remind_tomorrow"),
        ],
        [
             InlineKeyboardButton(text="📅 Точная дата", callback_data="remind_date"),
        ]
    ]
    if is_premium:
        keyboard.append([
            InlineKeyboardButton(text="🔄 Каждое утро (9:00)", callback_data="remind_daily"),
            InlineKeyboardButton(text="📅 Каждую неделю", callback_data="remind_weekly")
        ])
        keyboard.append([
            InlineKeyboardButton(text="⚙️ Свой интервал", callback_data="remind_custom")
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
