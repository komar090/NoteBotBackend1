from aiogram import Router, F, Bot
from aiogram.types import Message, ContentType, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import speech_recognition as sr
import os
from pydub import AudioSegment
import logging
# from handlers.tasks import cmd_text_message # Reuse existing logic? Or just call message.answer

import html 
from database.database import db
from utils.gigachat_client import GigaChatClient

ai_client = GigaChatClient()

router = Router()

@router.message(F.voice)
async def voice_message_handler(message: Message, state: FSMContext, bot: Bot, is_premium: bool):
    if not is_premium:
        await message.answer(
            "🎤 <b>Голосовой ввод — это Premium-функция!</b>\n\n"
            "Наша нейросеть расшифрует ваш голос и сама создаст задачу. Это экономит кучу времени.\n\n"
            "Попробуйте <b>Premium</b> прямо сейчас! 💎",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Подробнее о Premium", callback_data="check_subscription")]
            ]),
            parse_mode="HTML"
        )
        return

    await message.answer("🎤 Слушаю...")
    
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
        # Strategy: Try pydub (needs ffmpeg) -> Try soundfile (standalone lib)
        try:
             # Try 1: Pydub
             audio = AudioSegment.from_file(ogg_filename, format="ogg")
             audio.export(wav_filename, format="wav")
        except Exception as e_pydub:
            logging.warning(f"Pydub conversion failed (FFmpeg missing?): {e_pydub}")
            try:
                # Try 2: Soundfile
                import soundfile as sf
                data, samplerate = sf.read(ogg_filename)
                sf.write(wav_filename, data, samplerate)
            except Exception as e_sf:
                 logging.error(f"Soundfile conversion failed: {e_sf}")
                 await message.answer(
                    "⚠️ **Ошибка обработки аудио**\n"
                    "Не удалось конвертировать голосовое сообщение.\n"
                    "Пожалуйста, установите FFmpeg или используйте текстовый ввод."
                 )
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
                await message.answer("🤔 Не удалось разобрать речь.")
                return
            except sr.RequestError:
                await message.answer("⚠️ Ошибка сервиса распознавания.")
                return
                
        # Success
        await message.answer(f"🗣 **Распознано:**\n_{text}_", parse_mode="Markdown")
        
        from handlers.tasks import TaskStates
        
        # Try AI analysis
        ai_msg = await message.answer("🤖 Нейросеть распознает смысл...")
        ai_data = await ai_client.analyze_task(text)
        await ai_msg.delete()

        if ai_data and ai_data.get('category'):
             # AI Success
            category = ai_data['category']
            clean_text = ai_data.get('clean_text', text)
            date_str = ai_data.get('date')
            time_str = ai_data.get('time')
            
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
            
            await message.answer(
                info_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Да, создать", callback_data="ai_confirm_yes"),
                        InlineKeyboardButton(text="✏️ Нет, вручную", callback_data="ai_confirm_no")
                    ]
                ]),
                parse_mode="HTML"
            )
            await state.set_state(TaskStates.waiting_for_ai_confirmation)
            
        else:
            # Fallback to manual
            await state.update_data(task_text=text)
            custom_cats = await db.get_user_categories(message.from_user.id)
            await state.set_state(TaskStates.waiting_for_category)
            
            safe_text = html.escape(text)
            await message.answer(
                f"📂 Выберите категорию для задачи:\n"
                f"<i>«{safe_text}»</i>",
                reply_markup=get_categories_kb(custom_cats),
                parse_mode="HTML"
            )

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logging.error(f"Voice Error: {e}\n{error_trace}")
        await message.answer(f"Произошла ошибка при обработке голосового сообщения:\n{e}")
    finally:
        # Cleanup files
        if os.path.exists(ogg_filename): os.remove(ogg_filename)
        if os.path.exists(wav_filename): os.remove(wav_filename)
