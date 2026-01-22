from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from database.database import db
from keyboards.settings_kb import get_settings_kb, get_timezone_kb
from config_reader import config

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

router = Router()

class CategoryStates(StatesGroup):
    waiting_for_new_name = State()


@router.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject, is_premium: bool):
    # Handle Referral
    if command.args:
        try:
            referrer_id = int(command.args)
            user_id = message.from_user.id
            if referrer_id != user_id:
                user = await db.get_user(user_id)
                if user and not user['referred_by']:
                    await db.add_referral(user_id, referrer_id)
        except:
            pass

    status_text = "🌟 Premium Пользователь" if is_premium else "👤 Пользователь"
    
    await message.answer(
        f"Привет! Я твой персональный помощник <b>Note Bot</b>.\n\n"
        f"Твой статус: {status_text}\n\n"
        "Всё управление задачами теперь доступно в нашем <b>Mini App</b>. Списки дел, категории, "
        "напоминания и голосовой ввод — всё в одном месте!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Открыть приложение", web_app=WebAppInfo(url=config.web_app_url))],
            [InlineKeyboardButton(text="≡ Обновить", callback_data="refresh_menu")]
        ]),
        parse_mode="HTML"
    )

@router.message(F.text == "≡ Меню")
async def main_menu_handler(message: Message, is_premium: bool):
    await cmd_start(message, None, is_premium)

@router.callback_query(F.data == "refresh_menu")
async def cb_refresh_menu(callback: CallbackQuery, is_premium: bool):
    # Re-run start logic to update ReplyKeyboard and status
    status_text = "🌟 Premium Пользователь" if is_premium else "👤 Пользователь"
    
    # We can't edit a message to have ReplyMarkup if it didn't? 
    # Actually we can just send a new message.
    # User asked for "Restart".
    await callback.message.answer(
        f"🔄 <b>Профиль обновлен!</b>\n\n"
        f"Твой статус: {status_text}\n"
        "Все функции активированы.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="≡ Меню")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(F.text == "📝 Мои задачи")
async def my_tasks_handler_old(message: Message):
    # Deprecated button support or redirect
    await main_menu_handler(message)
    tasks = await db.get_user_tasks(message.from_user.id)
    
    if not tasks:
        await message.answer("У вас пока нет активных задач. Напишите мне что-нибудь!")
        return

    # Header
    await message.answer("<b>📝 Ваши активные задачи:</b>\n"
                         "<i>Нажмите на задачу, чтобы отметить выполненной:</i>", parse_mode="HTML")

    # Generate keyboard: each task is a button
    # Note: Telegram has limits on button text length. Truncate if needed.
    keyboard = []
    for task in tasks:
        # Format: "Category: Text..."
        text_preview = f"{task['category']}: {task['text']}"
        if len(text_preview) > 30:
            text_preview = text_preview[:27] + "..."
            
        keyboard.append([InlineKeyboardButton(
            text=f"⬜️ {text_preview}", 
            callback_data=f"done_{task['id']}"
        )])
    
    # Add stats button at the bottom
    keyboard.append([InlineKeyboardButton(text="📊 Посмотреть статистику", callback_data="show_stats")])
    
    await message.answer("Список:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.message(F.text == "⚙️ Настройки")
async def settings_handler_old(message: Message):
     await main_menu_handler(message)

@router.callback_query(F.data == "check_subscription")
async def cb_sub_status(callback: CallbackQuery, is_premium: bool):
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка: пользователь не найден.")
        return
        
    status = "🌟 Premium" if is_premium else "👤 Стандартный"
    
    if is_premium:
        text = (
            "💎 <b>Ваш статус: Premium</b>\n"
            f"Подписка активна до: <code>{user['premium_until']}</code>\n\n"
            "<b>Вам доступны все функции:</b>\n"
            "✅ Умный разбор задач нейросетью\n"
            "✅ Голосовой ввод (через нейросеть)\n"
            "✅ Утренний ИИ-дайджест дел\n"
            "✅ Свои категории и лимиты сняты\n"
            "✅ Архив выполненных задач"
        )
    else:
        text = (
            "👤 <b>Ваш статус: Обычный</b>\n\n"
            "<b>Premium откроет вам:</b>\n"
            "🚀 <b>Нейросеть:</b> автоматический разбор задач по времени и категориям\n"
            "🎙 <b>Голос:</b> ставьте задачи голосом, нейросеть всё запишет\n"
            "☀️ <b>ИИ-дайджест:</b> резюме дел на день по утрам\n"
            "📂 <b>Категории:</b> управление и создание своих категорий\n"
            "📊 <b>Лимиты:</b> снятие ограничения в 7 активных задач\n\n"
            "<b>Цена: 290₽ / месяц</b>"
        )
    
    # Alert has a 200 char limit, so we MUST use edit_text for this long description
    # Payment Button logic
    buttons = []
    if not is_premium:
        buttons.append([InlineKeyboardButton(text="💳 Оплатить картой (290₽/мес)", callback_data="pay_sbp")])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_settings")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")

@router.callback_query(F.data == "activate_trial")
async def cb_activate_trial(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if user and user['trial_used']:
        await callback.answer("❌ Вы уже использовали пробный период!", show_alert=True)
        return
    
    await db.activate_trial(user_id)
    await callback.message.edit_text(
        "🎉 <b>Пробный период активирован!</b>\n\n"
        "Теперь вам доступны все функции Premium на 3 дня:\n"
        "🤖 ИИ-разбор задач\n"
        "🎙 Голосовой ввод\n"
        "☀️ Утренний дайджест\n\n"
        "Начните пользоваться прямо сейчас!",
        parse_mode="HTML"
    )
    await callback.answer("Доступ активирован!")

@router.callback_query(F.data == "referral_program")
async def cb_referral_program(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    text = (
        "<b>🤝 Реферальная программа</b>\n\n"
        "Приглашайте друзей и получайте бонусы!\n\n"
        "🎁 За каждого приглашенного друга вы получите <b>3 дня Premium</b>.\n"
        "Ваш друг также получит быстрый доступ к удобному планировщику.\n\n"
        "🔗 Ваша ссылка для приглашения:\n"
        f"<code>{ref_link}</code>\n"
        "<i>(Нажмите на ссылку, чтобы скопировать)</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_settings")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "pay_sbp")
async def cb_pay_sbp(callback: CallbackQuery):
    # Try to get admin username
    support_contact = "Поддержку"
    if config.admin_ids:
        try:
            admin_id = config.admin_ids[0]
            chat_info = await callback.bot.get_chat(admin_id)
            if chat_info.username:
                support_contact = f"@{chat_info.username}"
            else:
                support_contact = f"ID {admin_id}"
        except Exception:
            pass

    await callback.message.edit_text(
        "<b>💳 Оплата доступа (1 месяц)</b>\n\n"
        "Стоимость: <b>290 RUB / мес</b>\n"
        "Способ: <b>Перевод на карту</b>\n\n"
        "1. Переведите сумму на карту:\n"
        "💳 <code>2204310189305397</code>\n"
        "<i>(Нажмите на номер, чтобы скопировать)</i>\n\n"
        "2. Отправьте скриншот чека в поддержку:\n"
        f"✉️ Сюда: <b>{support_contact}</b>\n\n"
        "<i>Мы активируем доступ в течение 10 минут.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_settings")]
        ]),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "set_timezone")
async def cb_set_timezone(callback: CallbackQuery):
    await callback.message.edit_text(
        "Выберите ваш часовой пояс:",
        reply_markup=get_timezone_kb()
    )

@router.callback_query(F.data == "back_settings")
async def cb_back_settings(callback: CallbackQuery, is_premium: bool):
    user_data = await db.get_user(callback.from_user.id)
    current_tz = user_data['timezone'] if user_data else "UTC"
    status = "🌟 Premium" if is_premium else "👤 Стандарт"
    
    await callback.message.edit_text(
        f"<b>Настройки</b>\n\n"
        f"Ваш статус: {status}\n"
        f"Текущий часовой пояс: {current_tz}\n",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🕒 Изменить часовой пояс", callback_data="set_timezone")],
            [InlineKeyboardButton(text="📂 Управление категориями " + ("" if is_premium else "🔒"), callback_data="manage_categories")],
            [InlineKeyboardButton(text="💳 Статус подписки", callback_data="check_subscription")],
            [InlineKeyboardButton(text="🤝 Реферальная программа", callback_data="referral_program")],
            [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="show_help")],
            [InlineKeyboardButton(text="🆘 Тех. поддержка", url="tg://user?id=272195202")],
            [InlineKeyboardButton(text="🗑 Удалить все записи", callback_data="delete_all_request")]
        ]),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("tz_"))
async def cb_tz_selected(callback: CallbackQuery, is_premium: bool):
    selected_tz = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    await db.set_timezone(user_id, selected_tz)
    await callback.answer(f"Часовой пояс изменен на {selected_tz}")
    
    # Return to settings view
    user_data = await db.get_user(user_id) # Refresh to be sure or just use selected_tz
    status = "🌟 Premium" if is_premium else "👤 Стандарт"
    
    await callback.message.edit_text(
        f"✅ Часовой пояс установлен: {selected_tz}\n\n"
        f"**Настройки**\n"
        f"Ваш статус: {status}\n"
        f"Текущий часовой пояс: {selected_tz}\n",
        reply_markup=get_settings_kb(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "delete_all_request")
async def cb_delete_request(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить всё", callback_data="confirm_delete_all"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="back_settings")
        ]
    ])
    await callback.message.edit_text(
        "⚠️ <b>Вы уверены?</b>\n\n"
        "Это действие <b>необратимо</b> удалит все ваши задачи и напоминания.\n"
        "Ваш профиль и настройки (часовой пояс, премиум) останутся.",
        reply_markup=kb,
        parse_mode="HTML"
    )


    
@router.callback_query(F.data == "confirm_delete_all")
async def cb_delete_confirm(callback: CallbackQuery, is_premium: bool):
    await db.delete_all_user_data(callback.from_user.id)
    await callback.answer("🗑 Все задачи и напоминания удалены.", show_alert=True)
    
    # Manually recreate settings view to avoid direct handler call complexity
    user_data = await db.get_user(callback.from_user.id)
    current_tz = user_data['timezone'] if user_data else "UTC"
    status = "🌟 Premium" if is_premium else "👤 Стандарт"
    
    await callback.message.edit_text(
        f"<b>Настройки</b>\n\n"
        f"Ваш статус: {status}\n"
        f"Текущий часовой пояс: {current_tz}\n",
        reply_markup=get_settings_kb(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("done_"))
async def cb_task_done(callback: CallbackQuery):
    task_id = int(callback.data.split("_")[1])
    await db.mark_task_done(task_id)
    
    await callback.answer("✅ Задача выполнена! Молодец!", show_alert=False)
    
    # Re-fetch tasks to update list
    tasks = await db.get_user_tasks(callback.from_user.id)
    if not tasks:
         # No more tasks
         await callback.message.edit_text("🎉 Все задачи выполнены! Список пуст.")
         return

    # Re-build keyboard
    keyboard = []
    for task in tasks:
        text_preview = f"{task['category']}: {task['text']}"
        if len(text_preview) > 30:
            text_preview = text_preview[:27] + "..."
        keyboard.append([InlineKeyboardButton(text=f"⬜️ {text_preview}", callback_data=f"done_{task['id']}")])
    
    keyboard.append([InlineKeyboardButton(text="📊 Посмотреть статистику", callback_data="show_stats")])
    
    # We edit the message that contained the keyboard
    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.callback_query(F.data == "show_stats")
async def cb_show_stats(callback: CallbackQuery):
    stats = await db.get_user_stats(callback.from_user.id)
    total = stats['total']
    done = stats['done']
    
    if total == 0:
        percent = 0
    else:
        percent = int((done / total) * 100)
    
    # Visual Bar
    bar_len = 10
    filled_len = int(bar_len * percent / 100)
    bar = "▓" * filled_len + "░" * (bar_len - filled_len)
    
    text = (
        f"<b>📊 Ваша продуктивность</b>\n\n"
        f"Всего задач: {total}\n"
        f"Выполнено: {done}\n\n"
        f"Прогресс: <b>{percent}%</b>\n"
        f"[{bar}]\n\n"
        f"<i>Так держать!</i>"
    )
    
    await callback.answer()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к задачам", callback_data="my_tasks_cb")]
    ])
    await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "my_tasks_cb")
async def cb_back_to_tasks(callback: CallbackQuery):
    # Call the logic of my_tasks_handler
    # We can refactor my_tasks_handler to be reusable or just copy logic.
    # Refactoring is cleaner. But for speed:
    tasks = await db.get_user_tasks(callback.from_user.id)
    if not tasks:
        await callback.message.edit_text("У вас пока нет активных задач.")
        return

    # Header is typically separate message in my_tasks_handler. 
    # Here we are editing one message.
    # Let's just show list.
    
    keyboard = []
    for task in tasks:
        text_preview = f"{task['category']}: {task['text']}"
        if len(text_preview) > 30:
            text_preview = text_preview[:27] + "..."
        keyboard.append([InlineKeyboardButton(text=f"⬜️ {text_preview}", callback_data=f"done_{task['id']}")])
    
    keyboard.append([InlineKeyboardButton(text="📊 Посмотреть статистику", callback_data="show_stats")])
    keyboard.append([InlineKeyboardButton(text="🗄 Архив (выполненные)", callback_data="view_archive")])
    
    await callback.message.edit_text(
        "<b>📝 Ваши активные задачи:</b>\n<i>Нажмите для выполнения:</i>", 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "view_archive")
async def cb_view_archive(callback: CallbackQuery):
    tasks = await db.get_done_tasks(callback.from_user.id)
    if not tasks:
        await callback.answer("Архив пуст", show_alert=True)
        return
        
    text_lines = ["<b>🗄 Ваши выполненные задачи:</b>\n"]
    # Show last 20
    for i, task in enumerate(tasks[:20], 1):
        created = task['created_at'].split()[0] if ' ' in task['created_at'] else task['created_at']
        text_lines.append(f"{i}. {task['text']} (<i>{created}</i>)")
        
    if len(tasks) > 20:
        text_lines.append(f"\n<i>...и еще {len(tasks)-20} задач</i>")
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к активным", callback_data="my_tasks_cb")]
    ])
    
    await callback.message.edit_text("\n".join(text_lines), reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "show_help")
async def cb_show_help(callback: CallbackQuery):
    text = (
        "<b>📚 Краткая инструкция</b>\n\n"
        "<b>1. Как добавить задачу?</b>\n"
        "Просто напишите мне текст задачи. Например: <i>«Купить молоко»</i>. "
        "Я спрошу категорию и нужно ли напоминание.\n\n"
        "<b>2. Как выполнить задачу?</b>\n"
        "Нажмите <b>📝 Мои задачи</b>. В списке нажмите на квадратик ⬜️ рядом с задачей.\n\n"
        "<b>3. Напоминания</b>\n"
        "Я умею напоминать через время (15 мин, 1 час) или в точную дату через календарь.\n\n"
        "<b>4. Статистика</b>\n"
        "В меню задач есть кнопка 📊, чтобы увидеть ваш прогресс.\n\n"
        "<b>5. Premium</b>\n"
        "В настройках можно оформить подписку (290₽/мес). Это откроет доступ к новым функциям первым."
    )
    
    # Add back button? Or just close?
    # Usually help is a separate message so user can read it.
    # Let's add simple close button or back to settings.
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад в настройки", callback_data="back_settings")]])
    
    # Edit the settings message to show help
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


# --- Category Management ---

@router.callback_query(F.data == "manage_categories")
async def cb_manage_categories(callback: CallbackQuery, is_premium: bool):
    if not is_premium:
        await callback.answer("👑 Управление категориями доступно только в Premium!", show_alert=True)
        return
        
    custom_cats = await db.get_user_categories(callback.from_user.id)
    if not custom_cats:
        await callback.message.edit_text(
            "<b>📂 Управление категориями</b>\n\n"
            "У вас пока нет своих категорий. Вы можете добавить их при создании новой задачи.\n\n"
            "Стандартные категории изменить нельзя.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_settings")]
            ]),
            parse_mode="HTML"
        )
        return

    text = "<b>📂 Ваши категории:</b>\n\n" + "\n".join([f"• {c}" for c in custom_cats])
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data="category_rename_list")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data="category_delete_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_settings")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "category_delete_list")
async def cb_delete_cat_list(callback: CallbackQuery):
    custom_cats = await db.get_user_categories(callback.from_user.id)
    keyboard = []
    for cat in custom_cats:
        keyboard.append([InlineKeyboardButton(text=f"❌ {cat}", callback_data=f"delcat_{cat}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data="manage_categories")])
    
    await callback.message.edit_text("Выберите категорию для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.callback_query(F.data.startswith("delcat_"))
async def cb_confirm_delete_cat(callback: CallbackQuery):
    cat_name = callback.data.split("_")[1]
    await db.delete_category(callback.from_user.id, cat_name)
    await callback.answer(f"Категория «{cat_name}» удалена")
    await cb_manage_categories(callback, True)

@router.callback_query(F.data == "category_rename_list")
async def cb_rename_cat_list(callback: CallbackQuery):
    custom_cats = await db.get_user_categories(callback.from_user.id)
    keyboard = []
    for cat in custom_cats:
        keyboard.append([InlineKeyboardButton(text=f"✏️ {cat}", callback_data=f"rencat_{cat}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data="manage_categories")])
    
    await callback.message.edit_text("Выберите категорию для переименования:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.callback_query(F.data.startswith("rencat_"))
async def cb_rename_cat_start(callback: CallbackQuery, state: FSMContext):
    cat_name = callback.data.split("_")[1]
    await state.update_data(old_cat_name=cat_name)
    await callback.message.edit_text(f"Введите новое название для категории «{cat_name}»:")
    await state.set_state(CategoryStates.waiting_for_new_name)

@router.message(CategoryStates.waiting_for_new_name)
async def category_rename_handler(message: Message, state: FSMContext):
    new_name = message.text.strip()
    if len(new_name) > 15:
        await message.answer("Слишком длинное название! Попробуйте еще раз.")
        return
        
    data = await state.get_data()
    old_name = data['old_cat_name']
    
    await db.rename_category(message.from_user.id, old_name, new_name)
    await state.clear()
    
    await message.answer(f"✅ Категория «{old_name}» переименована в «{new_name}».")
    # Simulate back to manage categories
    # We need a callback or message for this. Let's just send a "Menu" button.
    await message.answer("Что дальше?", reply_markup=ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="≡ Меню")]],
        resize_keyboard=True
    ))

