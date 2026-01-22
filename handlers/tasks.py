import json
import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, CallbackQuery
from aiogram.fsm.context import FSMContext
from database.database import db
from config_reader import config

router = Router()

# 1. Handle text messages (Redirect to Mini App)
@router.message(F.text, ~F.text.startswith("/"), F.text != "≡ Меню", StateFilter(None))
async def task_text_handler(message: Message):
    await message.answer(
        "👋 <b>Используйте Mini App для управления задачами!</b>\n\n"
        "Мы перенесли всё управление в удобный интерфейс. Просто нажмите кнопку ниже, чтобы создать или просмотреть свои задачи.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Открыть приложение", web_app=WebAppInfo(url=config.web_app_url))]
        ]),
        parse_mode="HTML"
    )

# 2. Handle Mini App Data (if using sendData approach)
@router.message(F.web_app_data)
async def web_app_data_handler(message: Message):
    try:
        data = json.loads(message.web_app_data.data)
        if data.get('action') == 'create_task':
            text = data.get('text')
            category = data.get('category')
            date_str = data.get('date')
            time_str = data.get('time')
            
            if not text:
                return
            
            task_id = await db.add_task(message.from_user.id, text, category)
            
            remind_at = None
            msg_alert = ""
            
            if date_str:
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    if time_str:
                        tm = datetime.strptime(time_str, "%H:%M").time()
                        remind_at = dt.replace(hour=tm.hour, minute=tm.minute)
                    else:
                        remind_at = dt.replace(hour=9, minute=0)
                except ValueError:
                    msg_alert = "\n(Ошибка даты, напоминание не установлено)"

            if remind_at:
                await db.add_reminder(task_id, message.from_user.id, remind_at)
                msg_alert = f"\n⏰ Напоминание: {remind_at.strftime('%d.%m %H:%M')}"
            
            await message.answer(
                f"✅ <b>Задача сохранена!</b>\n"
                f"📝 {text}\n"
                f"📂 {category}{msg_alert}",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="≡ Меню")]],
                    resize_keyboard=True
                )
            )
    except Exception as e:
        logging.error(f"Web App Data Error: {e}")
        await message.answer("Ошибка обработки данных.")

# 3. Catch-all for legacy callbacks (just in case)
@router.callback_query(F.data.startswith("cat_"))
@router.callback_query(F.data.startswith("remind_"))
@router.callback_query(F.data.startswith("done_"))
async def legacy_callback_handler(callback: CallbackQuery):
    await callback.answer("Пожалуйста, используйте Mini App для этого действия.", show_alert=True)
    await callback.message.delete()
