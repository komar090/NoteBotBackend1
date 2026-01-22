from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from config_reader import config

router = Router()

@router.message(F.voice)
async def voice_message_handler(message: Message):
    await message.answer(
        "🎙 <b>Голосовой ввод доступен в Mini App!</b>\n\n"
        "Для записи задачи голосом, откройте наше приложение. Там вы найдете кнопку микрофона.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Перейти в приложение", web_app=WebAppInfo(url=config.web_app_url))]
        ]),
        parse_mode="HTML"
    )
