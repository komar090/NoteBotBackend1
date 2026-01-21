from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from datetime import datetime, timedelta, timezone
import logging

from database.database import db
from keyboards.task_kb import get_categories_kb, get_reminder_kb

from utils.gigachat_client import GigaChatClient
from config_reader import config

router = Router()
ai_client = GigaChatClient()

class TaskStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_custom_category_name = State()
    waiting_for_reminder = State()
    waiting_for_custom_interval = State()
    waiting_for_date = State()
    waiting_for_ai_confirmation = State()


# Handle Mini App Data
@router.message(F.content_type == "web_app_data")
async def web_app_data_handler(message: Message, state: FSMContext, is_premium: bool):
    import json
    logging.info("WEB APP DATA HANDLER TRIGGERED!")
    try:
        data = json.loads(message.web_app_data.data)
        logging.info(f"Received data: {data}")
        if data.get('action') == 'create_task':
            text = data.get('text')
            category = data.get('category')
            date_str = data.get('date') # YYYY-MM-DD
            time_str = data.get('time') # HH:MM
            
            if not text:
                return
            
            # Save Task
            task_id = await db.add_task(message.from_user.id, text, category)
            
            remind_at = None
            msg_alert = ""
            
            if date_str:
                # Reuse the logic from ai_confirm_yes or similar
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    if time_str:
                        tm = datetime.strptime(time_str, "%H:%M").time()
                        remind_at = dt.replace(hour=tm.hour, minute=tm.minute)
                    else:
                        remind_at = dt.replace(hour=9, minute=0) # Default 9 AM
                except ValueError:
                    msg_alert = "\n(Ошибка даты, напоминание не установлено)"

            if remind_at:
                await db.add_reminder(task_id, message.from_user.id, remind_at)
                msg_alert = f"\n⏰ Напоминание: {remind_at.strftime('%d.%m %H:%M')}"
            
            await message.answer(
                f"✅ <b>Задача из Mini App сохранена!</b>\n"
                f"📝 {text}\n"
                f"📂 {category}{msg_alert}",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="🚀 Создать задачу", web_app=WebAppInfo(url=config.web_app_url))],
                        [KeyboardButton(text="≡ Меню")]
                    ],
                    resize_keyboard=True
                )
            )
            
    except Exception as e:
        logging.error(f"Web App Data Error: {e}")
        await message.answer("Ошибка обработки данных из приложения.")

# 1. Catch any text message (as a new task) - ONLY if no state is active

@router.message(F.text, ~F.text.startswith("/"), F.text != "≡ Меню", StateFilter(None))
async def task_text_handler(message: Message, state: FSMContext, is_premium: bool):
    # Check task limit for free users
    if not is_premium:
        count = await db.get_active_tasks_count(message.from_user.id)
        if count >= 7:
            user_data = await db.get_user(message.from_user.id)
            trial_used = user_data['trial_used'] if user_data else True
            
            kb_btns = []
            if not trial_used:
                kb_btns.append([InlineKeyboardButton(text="🎁 Попробовать 3 дня бесплатно", callback_data="activate_trial")])
            
            kb_btns.append([InlineKeyboardButton(text="💎 Купить Premium", callback_data="check_subscription")])
            
            trial_text = ""
            if not trial_used:
                 trial_text = "\n\nВы можете активировать <b>бесплатный пробный период на 3 дня</b>, чтобы оценить все возможности!"

            await message.answer(
                "⚠️ <b>Лимит задач исчерпан!</b>\n\n"
                "Для бесплатных пользователей доступно до <b>7 активных задач</b>."
                f"{trial_text}\n\n"
                "Купите <b>Premium</b>, чтобы снять все ограничения! 🚀",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_btns),
                parse_mode="HTML"
            )
            return

    # Try AI analysis only for premium
    ai_data = None
    if is_premium:
        logging.info(f"Received text for processing: {message.text}")
        processing_msg = await message.answer("🤖 Нейросеть анализирует задачу...")
        try:
            ai_data = await ai_client.analyze_task(message.text)
            logging.info(f"AI analysis result: {ai_data}")
        except Exception as e:
            logging.error(f"AI analysis exception: {e}")
            ai_data = None
        await processing_msg.delete()

    if ai_data and ai_data.get('category'):
        # AI successfully extracted data
        category = ai_data['category']
        clean_text = ai_data.get('clean_text', message.text)
        date_str = ai_data.get('date') # YYYY-MM-DD
        time_str = ai_data.get('time') # HH:MM
        
        # Save raw AI data to state
        await state.update_data(
            task_text=clean_text, 
            ai_category=category,
            ai_date=date_str, 
            ai_time=time_str
        )
        
        info_text = (
            f"🤖 <b>Нейросеть поняла так:</b>\n"
            f"📝 Задача: {clean_text}\n"
            f"📂 Категория: {category}\n"
        )
        if date_str:
            info_text += f"📅 Дата: {date_str}\n"
        if time_str:
            info_text += f"⏰ Время: {time_str}\n"
            
        info_text += "\nСоздать задачу?"

        msg_btns = [
            [
                InlineKeyboardButton(text="✅ Да, создать", callback_data="ai_confirm_yes"),
                InlineKeyboardButton(text="✏️ Нет, вручную", callback_data="ai_confirm_no")
            ]
        ]
        
        # If we have a date but no time, we could add quick time selection here 
        # But to keep it simple, let's just show what we found and ask for confirmation.
        # If user says "Yes", we can use 09:00 or ask for time if they want to be precise.

        await message.answer(
            info_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=msg_btns),
            parse_mode="HTML"
        )
        await state.set_state(TaskStates.waiting_for_ai_confirmation)

    else:
        # Fallback to manual flow
        await state.update_data(task_text=message.text)
        custom_cats = await db.get_user_categories(message.from_user.id)
        
        await message.answer(
            f"📝 Заметка: \"{message.text}\"\nВ какую категорию добавим?",
            reply_markup=get_categories_kb(custom_cats)
        )
        await state.set_state(TaskStates.waiting_for_category)

# 2. Handle Category selection
@router.callback_query(TaskStates.waiting_for_category, F.data.startswith("cat_"))
async def category_selected(callback: CallbackQuery, state: FSMContext, is_premium: bool):
    category = callback.data.split("_")[1]
    await state.update_data(category=category)
    
    await callback.message.edit_text(
        f"Категория: {category}\nНужно напоминание?",
        reply_markup=get_reminder_kb(is_premium)
    )
    await state.set_state(TaskStates.waiting_for_reminder)

# 3. Handle Reminder Selection (Quick Options)
@router.callback_query(TaskStates.waiting_for_reminder, F.data == "remind_custom")
async def custom_reminder_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Напишите количество дней для повтора (например: 3):\n"
        "<i>(Бот будет напоминать каждые N дней)</i>",
        parse_mode="HTML"
    )
    await state.set_state(TaskStates.waiting_for_custom_interval)

@router.callback_query(TaskStates.waiting_for_reminder, F.data.in_({"remind_none", "remind_15m", "remind_1h", "remind_tomorrow", "remind_daily", "remind_weekly"}))
async def quick_reminder(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data['task_text']
    category = data['category']
    user_id = callback.from_user.id
    
    remind_at = None
    
    # Use UTC for backend calculation
    now = datetime.now(timezone.utc)
    
    if callback.data == "remind_15m":
        remind_at = now + timedelta(minutes=15)
    elif callback.data == "remind_1h":
        remind_at = now + timedelta(hours=1)
    elif callback.data == "remind_tomorrow":
        remind_at = now + timedelta(days=1)
    
    recurrence = None
    if callback.data == "remind_daily":
        # Set for tomorrow 9 AM UTC (or generic morning)
        # Simplify: Next 9 AM
        remind_at = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if remind_at < now:
             remind_at += timedelta(days=1)
        recurrence = "daily"
    elif callback.data == "remind_weekly":
        remind_at = now + timedelta(weeks=1)
        recurrence = "weekly"

    # Save Task
    task_id = await db.add_task(user_id, text, category)
    
    # Save Reminder if needed
    # Save Reminder if needed
    if remind_at:
        await db.add_reminder(task_id, user_id, remind_at, recurrence_rule=recurrence)
        time_str = remind_at.strftime("%H:%M UTC")
        if recurrence:
             msg_text = f"✅ Задача сохранена!\nКатегория: {category}\nПовтор: {recurrence}"
        else:
             msg_text = f"✅ Задача сохранена!\nКатегория: {category}\nНапоминание: {time_str}"
    else:
        msg_text = f"✅ Заметка сохранена!\nКатегория: {category}"
        
    # Delete the inline interaction message (clean up)
    await callback.message.delete()
    
    # Send confirmation with Main Menu
    await callback.message.answer(
        msg_text,
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="≡ Меню")]
            ],
            resize_keyboard=True
        )
    )
    
    await state.clear()


# 4. Handle Date Selection (Calendar)
@router.callback_query(TaskStates.waiting_for_reminder, F.data == "remind_date")
async def date_reminder_start(callback: CallbackQuery, state: FSMContext):
    calendar = SimpleCalendar()
    await callback.message.edit_text(
        "Выберите дату:",
        reply_markup=await calendar.start_calendar()
    )
    await state.set_state(TaskStates.waiting_for_date)

@router.callback_query(SimpleCalendarCallback.filter(), TaskStates.waiting_for_date)
async def process_simple_calendar(callback: CallbackQuery, callback_data: dict, state: FSMContext):
    calendar = SimpleCalendar()
    selected, date = await calendar.process_selection(callback, callback_data)
    
    if selected:
        data = await state.get_data()
        text = data['task_text']
        category = data['category']
        user_id = callback.from_user.id
        
        # Set Default Time 9:00 AM UTC for selected date
        # If date is datetime object (which it usually is from aiogram_calendar), use it.
        remind_at = date.replace(hour=9, minute=0, second=0, microsecond=0)
        
        task_id = await db.add_task(user_id, text, category)
        await db.add_reminder(task_id, user_id, remind_at)
        
        await callback.message.delete()
        await callback.message.answer(
            f"✅ Задача сохранена на {date.strftime('%d/%m/%Y')}!",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="≡ Меню")]
                ],
                resize_keyboard=True
            )
        )
        await state.clear()

@router.message(TaskStates.waiting_for_custom_interval)
async def process_custom_interval(message: Message, state: FSMContext, **kwargs):
    logging.info(f"Custom interval received: {message.text}")
    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите положительное число (количество дней).")
        return

    data = await state.get_data()
    text = data['task_text']
    category = data['category']
    user_id = message.from_user.id
    
    # Calculate initial time: Tomorrow 9:00 AM (similar to Daily logic)
    # Or just +days from now? User asked "When repeats will be".
    # Usually people want "Every 3 days starting now".
    # Let's do: Start now + interval. Or Start Tomorrow 9am + Interval loop.
    # Logic: First reminder in X days.
    
    now = datetime.now(timezone.utc)
    remind_at = now + timedelta(days=days)
    recurrence = f"custom_{days}"
    
    task_id = await db.add_task(user_id, text, category)
    await db.add_reminder(task_id, user_id, remind_at, recurrence_rule=recurrence)
    
    await message.answer(
        f"✅ Задача сохранена!\n"
        f"Повтор каждые {days} дн.\n"
        f"Первое напоминание: {remind_at.strftime('%d/%m %H:%M UTC')}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="≡ Меню")]],
            resize_keyboard=True
        )
    )
    await state.clear()

@router.callback_query(F.data == "cancel_task")
async def cancel_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Создание отменено")

@router.callback_query(F.data == "add_custom_category")
async def cb_add_category(callback: CallbackQuery, state: FSMContext, is_premium: bool):
    if not is_premium:
        await callback.answer("👑 Это Premium-функция!", show_alert=True)
        return

    await callback.message.edit_text(
        "Напишите название новой категории (макс. 15 символов):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="cancel_task")]
        ])
    )
    await state.set_state(TaskStates.waiting_for_custom_category_name)



@router.message(TaskStates.waiting_for_custom_category_name)
async def custom_category_name_handler(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) > 15:
        await message.answer("Слишком длинное название! Попробуйте короче.")
        return
        
    await db.add_category(message.from_user.id, name)
    
    # Restore flow: Ask for category again, now with new one included
    data = await state.get_data()
    task_text = data.get("task_text")
    
    custom_cats = await db.get_user_categories(message.from_user.id)
    
    await message.answer(
        f"✅ Категория «{name}» добавлена!\n\n"
        f"📝 Заметка: \"{task_text}\"\nВ какую категорию добавим?",
        reply_markup=get_categories_kb(custom_cats)
    )
    await state.set_state(TaskStates.waiting_for_category)

@router.callback_query(TaskStates.waiting_for_ai_confirmation, F.data == "ai_confirm_no")
async def ai_confirm_no(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    # Use clean text if available, or just fallback? 
    # Let's keep original text if user rejected AI, maybe AI messed up text cleaning.
    # Actually, let's use the text we have. User can edit later? No, bot doesn't support edit.
    # Better to just go to manual flow with current text.
    
    # We need to make sure 'task_text' is set correctly in state (it was updated in task_text_handler)
    
    custom_cats = await db.get_user_categories(callback.from_user.id)
    await callback.message.edit_text(
        f"📝 Заметка: \"{data.get('task_text')}\"\nВ какую категорию добавим?",
        reply_markup=get_categories_kb(custom_cats)
    )
    await state.set_state(TaskStates.waiting_for_category)

@router.callback_query(TaskStates.waiting_for_ai_confirmation, F.data == "ai_confirm_yes")
async def ai_confirm_yes(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get('task_text')
    category = data.get('ai_category')
    date_str = data.get('ai_date')
    time_str = data.get('ai_time')
    user_id = callback.from_user.id
    
    # Save Task
    task_id = await db.add_task(user_id, text, category)
    
    remind_at = None
    if date_str:
        # Flexible Date Parsing
        date_formats = ["%Y-%m-%d", "%d.%m.%Y", "%d.%m", "%d/%m/%Y", "%d/%m"]
        dt = None
        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # If format has no year (e.g. %d.%m), add current year
                if fmt in ["%d.%m", "%d/%m"]:
                    current_year = datetime.now().year
                    dt = dt.replace(year=current_year)
                    # If date has passed, assume next year? 
                    if dt < datetime.now():
                         dt = dt.replace(year=current_year + 1)
                break
            except ValueError:
                continue
        
        if dt:
            # Flexible Time Parsing
            tm = None
            if time_str:
                time_formats = ["%H:%M", "%H-%M", "%H.%M"]
                for t_fmt in time_formats:
                    try:
                        tm = datetime.strptime(time_str, t_fmt).time()
                        break
                    except ValueError:
                        continue
            
            if tm:
                remind_at = dt.replace(hour=tm.hour, minute=tm.minute)
            else:
                remind_at = dt.replace(hour=9, minute=0)
        else:
             logging.error(f"Date parsing failed for all formats: {date_str}")
    
    msg_text = f"✅ Задача сохранена!\nКатегория: {category}"
    
    if remind_at:
        await db.add_reminder(task_id, user_id, remind_at)
        # Note: formatting for user might need timezone adjustment
        msg_text += f"\nНапоминание: {remind_at.strftime('%d/%m %H:%M')}"
    elif date_str:
        # Date was detected but parsing failed or only date was provided
        # Let's fallback to asking for time or default 9:00
        # For now, let's keep 9:00 as simplified
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            remind_at = dt.replace(hour=9, minute=0)
            await db.add_reminder(task_id, user_id, remind_at)
            msg_text += f"\nНапоминание: {remind_at.strftime('%d/%m')} в 09:00 (стандартно)"
        except:
            pass
    
    await callback.message.edit_text(msg_text)
    
    # Show Menu
    await callback.message.answer(
        "Что дальше?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="≡ Меню")]],
            resize_keyboard=True
        )
    )
    await state.clear()
