from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Callable, Dict, Any, Awaitable
from database.database import db
from config_reader import config

class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user = event.from_user
        if not user:
            return await handler(event, data)

        # 1. Register or update user
        db_user = await db.get_user(user.id)
        if not db_user:
            await db.add_user(user.id, user.username or "Unknown")
            is_premium_db = False
        else:
            is_premium_db = bool(db_user['is_premium'])

        # 2. Check Admin status
        is_admin = user.id in config.admin_ids

        # 3. Determine final Premium status
        # Admin is always premium
        is_premium = is_admin or is_premium_db

        # 4. Inject into data
        data['is_premium'] = is_premium
        data['is_admin'] = is_admin
        
        return await handler(event, data)
