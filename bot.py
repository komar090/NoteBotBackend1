import asyncio
import logging
from aiogram import Bot, Dispatcher
from config_reader import config
from database.database import db
from middlewares.auth import AuthMiddleware



from handlers import setup, admin, tasks, voice

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

import ctypes

def set_console_icon():
    try:
        kernel32 = ctypes.WinDLL('kernel32')
        user32 = ctypes.WinDLL('user32')
        shell32 = ctypes.WinDLL('shell32')
        
        # Set AppUserModelID to separate from generic Python
        # This is critical for Taskbar Pinning to work with custom icon
        my_appid = u"my.note.bot.app.1.0"
        shell32.SetCurrentProcessExplicitAppUserModelID(my_appid)
        
        # Set title to easily find window if needed, though GetConsoleWindow is best
        kernel32.SetConsoleTitleW("Note Bot")
        
        hwnd = kernel32.GetConsoleWindow()
        if not hwnd:
            logging.error("No console window handle found.")
            return

        icon_path = "d:\\Note bot\\icon.ico"
        
        # Flags: LR_LOADFROMFILE (0x10) | LR_DEFAULTSIZE (0x40)
        # Using 0,0 with LR_DEFAULTSIZE loads system metric size
        h_icon_small = user32.LoadImageW(None, icon_path, 1, 0, 0, 0x00000010 | 0x00000040)
        h_icon_big = user32.LoadImageW(None, icon_path, 1, 0, 0, 0x00000010 | 0x00000040)
        
        if h_icon_small:
            # WM_SETICON = 0x0080
            # ICON_SMALL = 0
            user32.SendMessageW(hwnd, 0x0080, 0, h_icon_small)
        else:
            logging.error(f"Failed to load small icon. Error: {ctypes.GetLastError()}")

        if h_icon_big:
             # ICON_BIG = 1
            user32.SendMessageW(hwnd, 0x0080, 1, h_icon_big)
        else:
             logging.error(f"Failed to load big icon. Error: {ctypes.GetLastError()}")
             
    except Exception as e:
        import traceback
        logging.error(f"Failed to set icon exception: {traceback.format_exc()}")


async def main():
    set_console_icon()
    # Initialize DB
    await db.create_tables()

    # Initialize Bot and Dispatcher
    bot = Bot(token=config.bot_token.get_secret_value())
    dp = Dispatcher()

    # Register Middlewares
    dp.message.middleware(AuthMiddleware())
    # Callback queries also need auth if we check permissions there, 
    # but for now let's add it to messages. Ideally adding to outer middleware.
    dp.callback_query.middleware(AuthMiddleware())

    # Register Routers
    dp.include_router(voice.router)
    dp.include_router(setup.router)
    dp.include_router(tasks.router)
    dp.include_router(admin.router)

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from utils.scheduler import check_reminders, check_subscriptions, send_morning_digest, send_marketing_mail

    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders, 'interval', seconds=60, args=[bot])
    # Run morning digest at 09:00 system time
    scheduler.add_job(send_morning_digest, 'cron', hour=9, minute=0, args=[bot])
    # Run marketing check every 12 hours
    scheduler.add_job(send_marketing_mail, 'interval', hours=12, args=[bot])
    # Run subscription check every 12 hours to be safe (will alert if in window)
    # Note: Logic 2<=days<3 means a 24h window. 12h run means we might alert twice?
    # Yes. Let's stick to 24h.
    scheduler.add_job(check_subscriptions, 'interval', hours=24, args=[bot])
    scheduler.start()
    
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
