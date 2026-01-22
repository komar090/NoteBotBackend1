import aiosqlite
from datetime import datetime
import os
import logging

class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self.conn = None

    async def connect(self):
        if not self.conn:
            self.conn = await aiosqlite.connect(self.db_path)
            self.conn.row_factory = aiosqlite.Row

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def create_tables(self):
        await self.connect()
        # Users table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                timezone TEXT DEFAULT 'UTC',
                is_premium BOOLEAN DEFAULT 0,
                premium_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Migration for existing tables (safe to run)
        try:
            await self.conn.execute("ALTER TABLE users ADD COLUMN premium_until TIMESTAMP")
        except Exception:
            pass # Column likely exists
            
        try:
            await self.conn.execute("ALTER TABLE users ADD COLUMN last_promo_sent TIMESTAMP")
        except Exception:
            pass

        try:
            await self.conn.execute("ALTER TABLE users ADD COLUMN trial_used BOOLEAN DEFAULT 0")
        except Exception:
            pass

        try:
            await self.conn.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
        except Exception:
            pass
        
        # Tasks table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                category TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Reminders table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                user_id INTEGER,
                remind_at TIMESTAMP,
                type TEXT,
                recurrence_rule TEXT,
                is_sent BOOLEAN DEFAULT 0,
                FOREIGN KEY (task_id) REFERENCES tasks (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Categories table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                UNIQUE(user_id, name)
            )
        """)
        await self.conn.commit()

    async def add_user(self, user_id: int, username: str):
        # Connection is expected to be open
        await self.conn.execute(
            "INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)",
            (user_id, username)
        )
        await self.conn.commit()

    async def get_user(self, user_id: int):
        async with self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

    async def set_timezone(self, user_id: int, timezone: str):
        await self.conn.execute("UPDATE users SET timezone = ? WHERE id = ?", (timezone, user_id))
        await self.conn.commit()

    async def set_premium(self, user_id: int, is_premium: bool, days: int = 31):
        if is_premium:
            from datetime import timedelta
            # Set to now + days
            utc_now = datetime.utcnow()
            premium_until = utc_now + timedelta(days=days)
            await self.conn.execute("UPDATE users SET is_premium = 1, premium_until = ? WHERE id = ?", (premium_until, user_id))
        else:
            # Revoke
            await self.conn.execute("UPDATE users SET is_premium = 0, premium_until = NULL WHERE id = ?", (user_id,))
            
        await self.conn.commit()

    async def activate_trial(self, user_id: int):
        from datetime import timedelta
        utc_now = datetime.utcnow()
        premium_until = utc_now + timedelta(days=3)
        await self.conn.execute(
            "UPDATE users SET is_premium = 1, premium_until = ?, trial_used = 1 WHERE id = ?",
            (premium_until, user_id)
        )
        await self.conn.commit()

    async def add_referral(self, user_id: int, referrer_id: int):
        # Update referred_by for the new user
        await self.conn.execute("UPDATE users SET referred_by = ? WHERE id = ?", (referrer_id, user_id))
        
        # Reward the referrer: +3 days of premium
        from datetime import timedelta
        
        # Check if referrer already has premium
        async with self.conn.execute("SELECT is_premium, premium_until FROM users WHERE id = ?", (referrer_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                is_premium = row['is_premium']
                premium_until_raw = row['premium_until']
                
                new_until = None
                if is_premium and premium_until_raw:
                    # Extend
                    if isinstance(premium_until_raw, str):
                        fmt = '%Y-%m-%d %H:%M:%S.%f' if '.' in premium_until_raw else '%Y-%m-%d %H:%M:%S'
                        current_until = datetime.strptime(premium_until_raw, fmt)
                    else:
                        current_until = premium_until_raw
                    new_until = current_until + timedelta(days=3)
                else:
                    # New premium
                    new_until = datetime.utcnow() + timedelta(days=3)
                
                await self.conn.execute(
                    "UPDATE users SET is_premium = 1, premium_until = ? WHERE id = ?",
                    (new_until, referrer_id)
                )
        
        await self.conn.commit()

    # Task methods
    async def add_task(self, user_id: int, text: str, category: str):
        cursor = await self.conn.execute(
            "INSERT INTO tasks (user_id, text, category) VALUES (?, ?, ?)",
            (user_id, text, category)
        )
        await self.conn.commit()
        return cursor.lastrowid

    async def add_reminder(self, task_id: int, user_id: int, remind_at: datetime, type: str = "once", recurrence_rule: str = None):
        await self.conn.execute(
            "INSERT INTO reminders (task_id, user_id, remind_at, type, recurrence_rule) VALUES (?, ?, ?, ?, ?)",
            (task_id, user_id, remind_at, type, recurrence_rule)
        )
        await self.conn.commit()

    async def get_active_reminders(self):
        query = """
            SELECT reminders.*, tasks.text 
            FROM reminders 
            JOIN tasks ON reminders.task_id = tasks.id 
            WHERE is_sent = 0 AND remind_at <= CURRENT_TIMESTAMP
        """
        async with self.conn.execute(query) as cursor:
                return await cursor.fetchall()

    async def mark_reminder_sent(self, reminder_id: int):
        await self.conn.execute("UPDATE reminders SET is_sent = 1 WHERE id = ?", (reminder_id,))
        await self.conn.commit()

    async def get_user_tasks(self, user_id: int):
        async with self.conn.execute("SELECT * FROM tasks WHERE user_id = ? AND status = 'active' ORDER BY created_at DESC", (user_id,)) as cursor:
            return await cursor.fetchall()
            
    async def mark_task_done(self, task_id: int):
        await self.conn.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (task_id,))
        await self.conn.commit()

    async def get_user_stats(self, user_id: int):
        # Total tasks
        async with self.conn.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ?", (user_id,)) as cursor:
            total = (await cursor.fetchone())[0]
        
        # Completed tasks
        async with self.conn.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND status = 'done'", (user_id,)) as cursor:
            done = (await cursor.fetchone())[0]
            
        return {"total": total, "done": done}

    async def delete_all_user_data(self, user_id: int):
        # Delete related reminders first
        await self.conn.execute("DELETE FROM reminders WHERE user_id = ?", (user_id,))
        await self.conn.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
        # Also could delete categories, but optional. Let's keep them or delete?
        # Let's delete custom categories too for full cleanup
        await self.conn.execute("DELETE FROM categories WHERE user_id = ?", (user_id,))
        await self.conn.commit()

    async def add_category(self, user_id: int, name: str):
        # Check if exists to avoid duplicates (unique constraint or check)
        # We'll just insert regular
        await self.conn.execute("INSERT OR IGNORE INTO categories (user_id, name) VALUES (?, ?)", (user_id, name))
        await self.conn.commit()

    async def get_user_categories(self, user_id: int):
        async with self.conn.execute("SELECT name FROM categories WHERE user_id = ?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
    
    # Update create_tables to include categories
    # Note: Since create_tables was already run, we might need a migration or just ignore if exists.
    # User might need to delete db file to reset or we add 'CREATE TABLE IF NOT EXISTS'


    async def get_all_users(self):
        async with self.conn.execute("SELECT * FROM users") as cursor:
            return await cursor.fetchall()

    async def get_active_tasks_count(self, user_id: int):
        async with self.conn.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND status = 'active'", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def update_last_promo_sent(self, user_id: int):
        await self.conn.execute("UPDATE users SET last_promo_sent = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
        await self.conn.commit()

    async def get_done_tasks(self, user_id: int):
        async with self.conn.execute("SELECT * FROM tasks WHERE user_id = ? AND status = 'done' ORDER BY created_at DESC", (user_id,)) as cursor:
            return await cursor.fetchall()

    async def delete_category(self, user_id: int, name: str):
        await self.conn.execute("DELETE FROM categories WHERE user_id = ? AND name = ?", (user_id, name))
        await self.conn.commit()

    async def rename_category(self, user_id: int, old_name: str, new_name: str):
        # Update category name in categories table
        await self.conn.execute("UPDATE categories SET name = ? WHERE user_id = ? AND name = ?", (new_name, user_id, old_name))
        # Also update category name in tasks table for consistency
        await self.conn.execute("UPDATE tasks SET category = ? WHERE user_id = ? AND category = ?", (new_name, user_id, old_name))
        await self.conn.commit()

db = Database()
