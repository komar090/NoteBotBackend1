from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.database import db
from datetime import datetime, timezone
import logging
import asyncio

async def check_reminders(bot: Bot):
    reminders = await db.get_active_reminders()
    if not reminders:
        return

    for row in reminders:
        reminder_id = row['id']
        user_id = row['user_id']
        task_id = row['task_id']
        # We can fetch task text if we want, or simple notification
        # Let's fetch task text separately or join in query. 
        # For MVP, let's just say "You have a reminder!"
        
        # Ideally we join tables in get_active_reminders. 
        # Let's assume we want to send the text.
        # I'll add a helper to get task by id or just accept generic message for now
        # Actually better to fix the query in database.py to join, but to avoid rewriting again:
        
        try:
            task_text = row['text']
            recurrence = row['recurrence_rule']
            
            await bot.send_message(user_id, f"🔔 <b>Напоминание!</b>\n{task_text}", parse_mode="HTML")
            await db.mark_reminder_sent(reminder_id)
            
            # Reschedule if recurring
            if recurrence:
                from datetime import timedelta
                next_remind = None
                current_remind_at = datetime.strptime(row['remind_at'], '%Y-%m-%d %H:%M:%S.%f') if '.' in row['remind_at'] else datetime.strptime(row['remind_at'], '%Y-%m-%d %H:%M:%S')
                # Actually sqlite timestamp format might vary, easiest is to use now or parsed. 
                # Let's base next on NOW or PREVIOUS? Usually previous to keep schedule.
                
                if recurrence == "daily":
                    next_remind = current_remind_at + timedelta(days=1)
                elif recurrence == "weekly":
                    next_remind = current_remind_at + timedelta(weeks=1)
                elif recurrence.startswith("custom_"):
                    try:
                        days = int(recurrence.split("_")[1])
                        next_remind = current_remind_at + timedelta(days=days)
                    except ValueError:
                        logging.error(f"Invalid custom recurrence rule: {recurrence}")
                
                if next_remind:
                    await db.add_reminder(task_id, user_id, next_remind, recurrence_rule=recurrence)
                    
        except Exception as e:
            logging.error(f"Failed to send reminder {reminder_id}: {e}")

async def check_subscriptions(bot: Bot):
    # This runs periodically (e.g. daily)
    try:
        users = await db.get_all_users()
        utc_now = datetime.utcnow()
        
        for user in users:
            if not user['is_premium'] or not user['premium_until']:
                continue
                
            uid = user['id']
            # Parse premium_until
            # It might be string if from sqlite
            prem_until_raw = user['premium_until']
            if isinstance(prem_until_raw, str):
                try:
                    # SQLite timestamp format: YYYY-MM-DD HH:MM:SS or HH:MM:SS.SSSSSS
                    # Usually created by python datetime.utcnow() str
                    if "." in prem_until_raw:
                        prem_until = datetime.strptime(prem_until_raw, '%Y-%m-%d %H:%M:%S.%f')
                    else:
                        prem_until = datetime.strptime(prem_until_raw, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    logging.error(f"Date parse error for user {uid}: {prem_until_raw}")
                    continue
            else:
                 prem_until = prem_until_raw

            # Calculate delta
            delta = prem_until - utc_now
            days_left = delta.days
            
            # We want to notify at 3 days and 1 day.
            # Since check might run any time, we strictly look if we just crossed the boundary?
            # Or simpler:
            # If 2.0 <= days_left < 3.0 (means it is now the "3rd day before")
            # If 0.0 <= days_left < 1.0 (means last 24h)
            # Expired: days_left < 0
            
            # To avoid spam, we rely on the scheduler running once a day, OR we check if we already sent?
            # Without DB column 'last_alert', we accept risk of double send if bot restarts/runs twice same day.
            # But we can minimize.
            
            # Message Logic
            is_trial = user['trial_used'] # This is 1 if trial was ever used. 
            # A better check for current trial status would be needed if trial and paid subs overlap.
            # But for simplicity, if it's the first subscription and it's 3 days, it's a trial.
            
            msg = None
            if 0 > delta.total_seconds():
                # Expired
                await db.set_premium(uid, False)
                if is_trial:
                    msg = "🚫 <b>Ваш пробный период истек.</b>\nФункции ограничены. Чтобы продолжить пользоваться всеми фишками: /start -> Настройки"
                else:
                    msg = "🚫 <b>Ваша подписка Premium истекла.</b>\nФункции ограничены. Продлить: /start -> Настройки"
            elif 0 <= days_left < 1:
                # Less than 1 day
                if is_trial:
                    msg = "⏳ <b>Пробный период закончится через 24 часа!</b>\nУспейте выполнить все важные дела с помощью ИИ."
                else:
                    msg = "⏳ <b>Остался 1 день подписки!</b>\nНе забудьте продлить доступ."
            elif 2 <= days_left < 3:
                # 3 days left
                if not is_trial:
                    msg = "📅 <b>Осталось 3 дня подписки!</b>\nСамое время задуматься о продлении."

            if msg:
                try:
                    await bot.send_message(uid, msg, parse_mode="HTML")
                except Exception as e:
                    logging.warning(f"Failed to notify user {uid} about sub: {e}")

    except Exception as e:
            logging.error(f"Subscription check mechanism failed: {e}")

async def send_morning_digest(bot: Bot):
    """
    Sends a morning summary of active tasks to each user.
    """
    # Removed AI summary in favor of Classic List (Faster/Cleaner)
    
    try:
        users = await db.get_all_users()
        for user in users:
            uid = user['id']
            if not user['is_premium']:
                continue
                
            tasks = await db.get_user_tasks(uid)
            if not tasks:
                continue
            
            # Simple list generation
            task_list = "\n".join([f"• {t['text']}" for t in tasks])
            
            await bot.send_message(
                uid, 
                f"☀️ <b>Доброе утро! Твой план на сегодня:</b>\n\n{task_list}\n\n<i>Продуктивного дня!</i>", 
                parse_mode="HTML"
            )
                
    except Exception as e:
        logging.error(f"Morning digest failed: {e}")

async def send_marketing_mail(bot: Bot, force: bool = False):
    """
    Sends marketing promotions to non-premium users. 
    Runs every 3 days. Includes welcome messages for new users (>24h).
    force: if True, skips time checks (used for manual triggers).
    """
    from config_reader import config
    
    try:
        users = await db.get_all_users()
        sent_count = 0
        now = datetime.now(timezone.utc)
        
        logging.info(f"Starting marketing mail... Total users: {len(users)}, Force: {force}")
        
        for user in users:
            # Skip premium and admins
            if user['is_premium'] or user['id'] in config.admin_ids:
                continue
                
            uid = user['id']
            created_at_str = user['created_at']
            last_promo_str = user['last_promo_sent']
            
            # Parse dates
            try:
                # Handle potential millisecond format or standard format
                fmt = '%Y-%m-%d %H:%M:%S.%f' if '.' in created_at_str else '%Y-%m-%d %H:%M:%S'
                created_at = datetime.strptime(created_at_str, fmt)
                created_at = created_at.replace(tzinfo=timezone.utc)
            except Exception as e:
                logging.warning(f"Failed to parse created_at for user {uid}: {e}")
                continue
                
            last_promo = None
            if last_promo_str:
                try:
                    fmt = '%Y-%m-%d %H:%M:%S.%f' if '.' in last_promo_str else '%Y-%m-%d %H:%M:%S'
                    last_promo = datetime.strptime(last_promo_str, fmt)
                    last_promo = last_promo.replace(tzinfo=timezone.utc)
                except:
                    pass

            should_send = False
            msg_text = ""
            
            if force:
                should_send = True
                msg_text = (
                    "🌟 <b>Специальное предложение для вас!</b>\n\n"
                    "Откройте мощь <b>Note Bot Premium</b>.\n"
                    "Неограниченные категории, голосовой ввод, темы оформления и никакой рекламы.\n\n"
                    "Всего за <b>290₽/мес</b>. Попробуйте <b>Premium</b> и почувствуйте разницу! 💎"
                )
            elif not last_promo:
                # New user check
                if (now - created_at).total_seconds() > 24 * 3600:
                    should_send = True
                    msg_text = (
                        "👋 <b>Как ваши успехи с Note Bot?</b>\n\n"
                        "Знаете ли вы, что ваша продуктивность может вырасти в 2 раза? "
                        "Организуйте свои дела с помощью темных тем, голосового ввода и расширенной статистики!\n\n"
                        "Откройте все возможности с <b>Premium</b>. Это ваш персональный инструмент успеха. 🚀"
                    )
            else:
                # Periodic check (> 3 days)
                if (now - last_promo).total_seconds() > 3 * 24 * 3600:
                    should_send = True
                    msg_text = (
                        "🌟 <b>Сделайте шаг к идеальному порядку!</b>\n\n"
                        "Premium-подписка дает вам:\n"
                        "• 🎤 <b>Голосовой ввод</b> (быстро и удобно)\n"
                        "• 📂 <b>Безлимит</b> на категории и архив\n"
                        "• 🎨 <b>Уникальные темы</b> (Cyberpunk, Aurora)\n"
                        "• ☀️ <b>Утренний дайджест</b> ваших дел\n\n"
                        "Всего за <b>290₽/мес</b>. Начните использовать технологии на максимум! 💎"
                    )
            
            if should_send:
                try:
                    await bot.send_message(
                        uid, 
                        msg_text, 
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💎 Подробнее / Купить", callback_data="check_subscription")]
                        ]),
                        parse_mode="HTML"
                    )
                    await db.update_last_promo_sent(uid)
                    sent_count += 1
                except Exception as e:
                    logging.error(f"Failed to send promo to {uid}: {e}")
        
        # Notify Admin - always if forced, otherwise only if sent > 0
        if config.admin_ids:
            admin_id = config.admin_ids[0]
            if force or sent_count > 0:
                status_emoji = "✅" if sent_count > 0 else "ℹ️"
                await bot.send_message(admin_id, f"{status_emoji} <b>Маркетинговая рассылка завершена</b>\nОхвачено пользователей: <code>{sent_count}</code>", parse_mode="HTML")
            
    except Exception as e:
        import traceback
        logging.error(f"Marketing mail failed: {e}\n{traceback.format_exc()}")
