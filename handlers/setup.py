from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from database.database import db
from config_reader import config

router = Router()

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
        except Exception:
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
    status_text = "🌟 Premium Пользователь" if is_premium else "👤 Пользователь"
    
    await callback.message.answer(
        f"🔄 <b>Профиль обновлен!</b>\n\n"
        f"Твой статус: {status_text}\n"
        "Все функции активны в приложении.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="≡ Меню")]],
            resize_keyboard=True
        ),
        parse_mode="HTML"
    )
    await callback.answer()
