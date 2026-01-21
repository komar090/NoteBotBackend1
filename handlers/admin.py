from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.database import db

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

router = Router()

class AdminStates(StatesGroup):
    waiting_for_revoke_id = State()

@router.message(Command("godmode"))
async def cmd_godmode(message: Message, is_admin: bool):
    if not is_admin:
        return # Ignore non-admins
    
    await message.answer("🔧 Режим Бога активирован.\n"
                         "Команды:\n"
                         "/grant_premium [ID] - Выдать премиум\n"
                         "/users - Список пользователей и статистика")

@router.message(Command("grant_premium"))
async def cmd_grant(message: Message, is_admin: bool):
    if not is_admin:
        return
    
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.answer("Использование: /grant_premium 123456789")
            return
        
        user_id = int(args[1])
        await db.set_premium(user_id, True)
        await message.answer(f"Админ-права (Premium) выданы пользователю {user_id}")
    except ValueError:
        await message.answer("ID должен быть числом")

@router.message(Command("users"))
async def cmd_users_stats(message: Message, is_admin: bool):
    if not is_admin:
        return
        
    users = await db.get_all_users()
    if not users:
        await message.answer("Пользователей нет.")
        return

    from datetime import datetime
    
    total = len(users)
    premium_count = 0
    trial_count = 0
    
    text_lines = ["<b>👥 Список пользователей</b>\n"]
    
    now = datetime.now()
    
    for user in users:
        uid = user['id']
        username = user['username'] or "Без ника"
        is_prem = bool(user['is_premium'])
        created_at_str = user['created_at'] # string from db
        
        # Calculate time with us
        try:
            # Handle standard SQLite timestamp format
            # Output of CURRENT_TIMESTAMP is usually 'YYYY-MM-DD HH:MM:SS'
            created_dt = datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S')
            delta = now - created_dt
            days = delta.days
            
            time_str = f"{days} д."
        except Exception:
            time_str = "?"
            
        if is_prem:
            premium_count += 1
            if user['trial_used']:
                 trial_count += 1
                 icon = "🎁"
            else:
                 icon = "🌟"
        else:
            icon = "👤"
            
        text_lines.append(f"{icon} <code>{uid}</code> (@{username}) — {time_str}")
        
    text_lines.append(f"\nВсего: {total} | Premium: {premium_count}")
    
    # Send in chunks if too long (Telegram limit 4096)
    full_text = "\n".join(text_lines)
    if len(full_text) > 4000:
        # Simple chunking
        chunk = ""
        for line in text_lines:
            if len(chunk) + len(line) > 4000:
                await message.answer(chunk, parse_mode="HTML")
                chunk = line + "\n"
            else:
                chunk += line + "\n"
        if chunk:
            await message.answer(chunk, parse_mode="HTML")
    else:
        await message.answer(full_text, parse_mode="HTML")

@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery, is_admin: bool):
    if not is_admin:
        return
        
    await callback.message.edit_text(
        "<b>👑 Админ панель</b>\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_users_stats")],
            [InlineKeyboardButton(text="📊 Общая статистика", callback_data="admin_general_stats")],
            [InlineKeyboardButton(text="📢 Запустить рассылку", callback_data="admin_run_marketing")],
            [InlineKeyboardButton(text="🔍 Инспекция пользователей", callback_data="admin_inspect_users")],
            [InlineKeyboardButton(text="➕ Выдать подписку", callback_data="admin_grant_prem")],
            [InlineKeyboardButton(text="➖ Забрать подписку", callback_data="admin_revoke_prem")],
            [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_menu_from_admin")]
        ]),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_users_stats")
async def cb_users_stats(callback: CallbackQuery, is_admin: bool):
    if not is_admin:
        return
    
    # Reuse logic from cmd_users_stats, but for callback edit? 
    # Or just send new message? 
    # If list is long, edit might fail if message type changes too much or multiple messages needed.
    # Safe bet: Answer callback, then send message(s).
    await callback.answer()
    
    users = await db.get_all_users()
    if not users:
        await callback.message.answer("Пользователей нет.")
        return

    from datetime import datetime
    total = len(users)
    premium_count = 0
    text_lines = ["<b>👥 Список пользователей</b>\n"]
    now = datetime.now()
    
    for user in users:
        uid = user['id']
        username = user['username'] or "Без ника"
        is_prem = bool(user['is_premium'])
        created_at_str = user['created_at']
        try:
            created_dt = datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S')
            delta = now - created_dt
            days = delta.days
            time_str = f"{days} д."
        except Exception:
            time_str = "?"
            
        if is_prem:
            premium_count += 1
            icon = "🌟"
        else:
            icon = "👤"
            
        text_lines.append(f"{icon} <code>{uid}</code> (@{username}) — {time_str}")
        
    text_lines.append(f"\nВсего: {total} | Premium: {premium_count}")
    
    full_text = "\n".join(text_lines)
    # Just send as new message to avoid edit limits if huge list
    await callback.message.answer(full_text, parse_mode="HTML")
    
    # Show Admin Panel again?
    await callback.message.answer("👑 Админ панель", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_users_stats")],
            [InlineKeyboardButton(text="➖ Забрать подписку", callback_data="admin_revoke_prem")],
            [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_menu_from_admin")]
    ]))

@router.callback_query(F.data == "admin_revoke_prem")
async def cb_revoke_start(callback: CallbackQuery, state: FSMContext, is_admin: bool):
    if not is_admin: return
    
    # Get all users to filter or get only premium? DB method get_all_users returns all. 
    # Let's filter here.
    users = await db.get_all_users()
    premium_users = [u for u in users if u['is_premium']]
    
    if not premium_users:
        await callback.message.edit_text(
            "Нет пользователей с Premium подпиской.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")]
            ])
        )
        return

    keyboard = []
    # Limit to 50 to avoid limits for now (simple cleanup)
    for user in premium_users[:50]:
        uid = user['id']
        name = user['username'] or f"User {uid}"
        # Button: "Username (ID)" -> revoke_12345
        keyboard.append([InlineKeyboardButton(text=f"❌ {name}", callback_data=f"revoke_{uid}")])
        
    keyboard.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin_panel")])
    
    await callback.message.edit_text(
        "<b>➖ Забрать подписку</b>\n"
        "Нажмите на пользователя, чтобы отключить Premium:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("revoke_"))
async def cb_revoke_confirm(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    
    await db.set_premium(user_id, False)
    await callback.answer(f"🚫 Подписка у {user_id} отключена.", show_alert=True)
    
    # Refresh list
    await cb_revoke_start(callback, None, True)

@router.callback_query(F.data == "admin_grant_prem")
async def cb_grant_start(callback: CallbackQuery, state: FSMContext, is_admin: bool):
    if not is_admin: return
    
    users = await db.get_all_users()
    # Filter non-premium users
    # Sort by ID desc (newest first)
    non_prem_users = sorted([u for u in users if not u['is_premium']], key=lambda x: x['id'], reverse=True)
    
    if not non_prem_users:
        await callback.message.edit_text(
            "Нет пользователей без подписки.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")]
            ])
        )
        return

    keyboard = []
    # Show top 30 newest users
    for user in non_prem_users[:30]:
        uid = user['id']
        name = user['username'] or f"User {uid}"
        keyboard.append([InlineKeyboardButton(text=f"✅ {name}", callback_data=f"grant_{uid}")])
        
    keyboard.append([InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin_panel")])
    
    await callback.message.edit_text(
        "<b>➕ Выдать подписку</b>\n"
        "Нажмите на пользователя (показаны последние 30):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("grant_"))
async def cb_grant_confirm(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    
    await db.set_premium(user_id, True)
    await callback.answer(f"✅ Подписка выдана пользователю {user_id}.", show_alert=True)
    
    # Notify the user
    try:
        await callback.bot.send_message(
            user_id,
            "🎉 <b>Поздравляем! Вам выдан статус Premium!</b> 🌟\n\n"
            "Теперь вам доступны:\n"
            "• 🔄 Регулярные напоминания\n"
            "• 📂 Свои категории\n"
            "• 📊 Расширенная статистика\n\n"
            "Нажмите кнопку ниже, чтобы обновить профиль.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить профиль", callback_data="refresh_menu")]
            ]),
            parse_mode="HTML"
        )
    except Exception:
        # User might have blocked the bot, ignore
        pass
    
    # Refresh list
    await cb_grant_start(callback, None, True)

# Remove the text input handler as it's no longer needed
# @router.message(AdminStates.waiting_for_revoke_id) ... (Deleted)

@router.callback_query(F.data == "back_to_menu_from_admin")
async def cb_back_admin(callback: CallbackQuery):
    # This should match main_menu_handler logic
    # But since main_menu_handler checks message.from_user.id, we can import it or duplicate logic
    # Let's duplicate as it is simple.
    # Wait, we need 'config' here too if we duplicate.
    from config_reader import config
    
    keyboard = [
        [InlineKeyboardButton(text="📝 Мои задачи", callback_data="my_tasks_cb")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="back_settings")]
    ]
    if callback.from_user.id in config.admin_ids:
        keyboard.append([InlineKeyboardButton(text="👑 Админ панель", callback_data="admin_panel")])
        
    await callback.message.edit_text(
        "<b>📂 Главное меню</b>\n\n"
        "Выберите нужное действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_inspect_users")
async def cb_inspect_users_list(callback: CallbackQuery, is_admin: bool):
    if not is_admin: return
    
    users = await db.get_all_users()
    if not users:
        await callback.message.edit_text("Пользователей нет.", 
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")]]))
        return

    keyboard = []
    # Show last 30 users for inspection
    sorted_users = sorted(users, key=lambda x: x['id'], reverse=True)
    for user in sorted_users[:30]:
        uid = user['id']
        name = user['username'] or f"User {uid}"
        keyboard.append([InlineKeyboardButton(text=f"👤 {name} ({uid})", callback_data=f"inspect_user_{uid}")])
        
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")])
    
    await callback.message.edit_text(
        "<b>🔍 Выберите пользователя для инспекции:</b>\n"
        "(Показаны последние 30)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("inspect_user_"))
async def cb_inspect_user_details(callback: CallbackQuery, is_admin: bool):
    if not is_admin: return
    
    user_id = int(callback.data.split("_")[-1])
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
        
    stats = await db.get_user_stats(user_id)
    
    text = (
        f"<b>👤 Инспекция пользователя</b>\n\n"
        f"<b>ID:</b> <code>{user_id}</code>\n"
        f"<b>Username:</b> @{user['username'] or '—'}\n"
        f"<b>Premium:</b> {'✅ Да' if user['is_premium'] else '❌ Нет'}\n"
        f"<b>Регистрация:</b> {user['created_at']}\n\n"
        f"<b>📊 Статистика:</b>\n"
        f"• Всего задач: {stats['total']}\n"
        f"• Выполнено: {stats['done']}\n"
        f"• Активных: {stats['total'] - stats['done']}"
    )
    
    keyboard = [
        [InlineKeyboardButton(text="📝 Посмотреть записи", callback_data=f"view_user_notes_{user_id}")],
        [InlineKeyboardButton(text="⬅️ К списку", callback_data="admin_inspect_users")]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")

@router.callback_query(F.data.startswith("view_user_notes_"))
async def cb_view_user_notes(callback: CallbackQuery, is_admin: bool):
    if not is_admin: return
    
    user_id = int(callback.data.split("_")[-1])
    tasks = await db.get_user_tasks(user_id)
    
    if not tasks:
        await callback.answer("У пользователя нет активных записей", show_alert=True)
        return
        
    await callback.answer()
    
    text_lines = [f"<b>📝 Активные записи пользователя {user_id}:</b>\n"]
    for i, task in enumerate(tasks, 1):
        created = task['created_at'].split()[0] if ' ' in task['created_at'] else task['created_at']
        line = f"{i}. {task['text']} (<i>{created}</i>)"
        text_lines.append(line)
        
    full_text = "\n".join(text_lines)
    
    # Check length
    if len(full_text) > 4000:
        chunks = []
        current_chunk = ""
        for i, line in enumerate(text_lines):
            if len(current_chunk) + len(line) > 4000:
                chunks.append(current_chunk)
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"
        chunks.append(current_chunk)
        
        for chunk in chunks:
            await callback.message.answer(chunk, parse_mode="HTML")
    else:
        await callback.message.answer(full_text, parse_mode="HTML")

    await callback.message.answer(
        "Вернуться к инспекции?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 К профилю пользователя", callback_data=f"inspect_user_{user_id}")],
            [InlineKeyboardButton(text="⬅️ К списку всех", callback_data="admin_inspect_users")]
        ])
    )

@router.callback_query(F.data == "admin_general_stats")
async def cb_admin_general_stats(callback: CallbackQuery, is_admin: bool):
    if not is_admin: return
    
    users = await db.get_all_users()
    total_users = len(users)
    premium_users = len([u for u in users if u['is_premium']])
    trial_users = len([u for u in users if u['is_premium'] and u['trial_used']])
    
    # Try to get task stats for all
    total_tasks = 0
    done_tasks = 0
    for u in users:
        s = await db.get_user_stats(u['id'])
        total_tasks += s['total']
        done_tasks += s['done']
    
    # Text-based Chart for Premium vs Free
    prem_percent = int((premium_users / total_users * 100)) if total_users > 0 else 0
    bar_len = 10
    filled = int(bar_len * prem_percent / 100)
    bar = "⭐" * filled + "⚪" * (bar_len - filled)
    
    text = (
        f"<b>📊 Общая статистика бота</b>\n\n"
        f"👥 <b>Пользователи:</b> {total_users}\n"
        f"🌟 <b>Premium:</b> {premium_users}\n"
        f"🎁 <b>Пробный период:</b> {trial_users}\n"
        f"[{bar}] {prem_percent}%\n\n"
        f"📝 <b>Всего задач в БД:</b> {total_tasks}\n"
        f"✅ <b>Выполнено:</b> {done_tasks}\n"
        f"⏳ <b>В процессе:</b> {total_tasks - done_tasks}\n"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")]
        ]),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_run_marketing")
async def cb_admin_run_marketing(callback: CallbackQuery, is_admin: bool):
    if not is_admin: return
    
    await callback.answer("⏳ Запуск маркетинговой рассылки...", show_alert=True)
    
    from utils.scheduler import send_marketing_mail
    import asyncio
    asyncio.create_task(send_marketing_mail(callback.bot, force=True))

