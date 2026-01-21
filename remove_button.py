import asyncio
from aiogram import Bot
from config_reader import config
from aiogram.types import MenuButtonDefault

async def main():
    try:
        bot = Bot(token=config.bot_token.get_secret_value())
        # Reset the persistent menu button (the blue one on the left) to default
        await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
        print("✅ Menu Button has been reset successfully!")
        print("The blue 'Create Task' button on the left should disappear.")
        await bot.session.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
