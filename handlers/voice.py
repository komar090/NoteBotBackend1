from aiogram import Router, F, Bot
from aiogram.types import Message, ContentType, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import speech_recognition as sr
import os
from pydub import AudioSegment
import logging
import html 
from database.database import db
from handlers.tasks import TaskStates, get_categories_kb

router = Router()

@router.message(F.voice)
async def voice_message_handler(message: Message, state: FSMContext, bot: Bot, is_premium: bool):
    if not is_premium:
        await message.answer(
            "🎤 <b>Голосовой ввод — это Premium-функция!</b>\n\n"
            "Записывайте задачи голосом на бегу, а бот превратит их в текст.\n"
            "Быстро, удобно, технологично.\n\n"
            "Попробуйте <b>Premium</b> прямо сейчас! 💎",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Подробнее о Premium", callback_data="check_subscription")]
            ]),
            parse_mode="HTML"
        )
        return

    processing_msg = await message.answer("🎤 Обрабатываю аудио...")
    
    # Paths
    file_id = message.voice.file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path
    
    ogg_filename = f"voice_{file_id}.ogg"
    wav_filename = f"voice_{file_id}.wav"
    
    try:
        # Download
        await bot.download_file(file_path, ogg_filename)
        
        # Convert OGG -> WAV
        try:
             # Try 1: Pydub
             audio = AudioSegment.from_file(ogg_filename, format="ogg")
             audio.export(wav_filename, format="wav")
        except Exception as e_pydub:
            logging.warning(f"Pydub conversion failed: {e_pydub}")
            await processing_msg.edit_text("⚠️ Ошибка конвертации аудио. Проверьте FFMPEG.")
            if os.path.exists(ogg_filename): os.remove(ogg_filename)
            return

        # Recognize
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_filename) as source:
            audio_data = recognizer.record(source)
            try:
                # Use Google Speech Recognition (Free)
                text = recognizer.recognize_google(audio_data, language="ru-RU")
            except sr.UnknownValueError:
                await processing_msg.edit_text("🤔 Не удалось разобрать речь.")
                return
            except sr.RequestError:
                await processing_msg.edit_text("⚠️ Ошибка сервиса распознавания.")
                return
                
        # Success
        user_id = message.from_user.id
        
        # Manual Category Selection (Since AI is removed)
        await state.update_data(task_text=text)
        custom_cats = await db.get_user_categories(user_id)
        
        await processing_msg.delete()
        
        safe_text = html.escape(text)
        await message.answer(
            f"🗣 <b>Распознано:</b>\n«{safe_text}»\n\n"
            f"📂 Выберите категорию для сохранения:",
            reply_markup=get_categories_kb(custom_cats),
            parse_mode="HTML"
        )
        await state.set_state(TaskStates.waiting_for_category)

    except Exception as e:
        import traceback
        logging.error(f"Voice Error: {e}\n{traceback.format_exc()}")
        await message.answer(f"Произошла ошибка при обработке:\n{e}")
    finally:
        # Cleanup files
        if os.path.exists(ogg_filename): os.remove(ogg_filename)
        if os.path.exists(wav_filename): os.remove(wav_filename)
