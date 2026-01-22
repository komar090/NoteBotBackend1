import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from gigachat import GigaChat
from config_reader import config

logger = logging.getLogger(__name__)

class GigaChatClient:
    def __init__(self):
        self.auth = config.gigachat_auth.get_secret_value()
        
    async def analyze_task(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Analyzes the task text using GigaChat to extract category, date, time, and cleaned text.
        Returns a dictionary with result or error detail.
        """
        import asyncio
        try:
            # Increased timeout to 25s for slow models
            return await asyncio.wait_for(asyncio.to_thread(self._analyze_task_sync, text), timeout=25.0)
        except asyncio.TimeoutError:
            logger.error("GigaChat analysis timed out")
            # Return error in text so user sees it
            return {"text": f"[AI TIMEOUT] {text}", "category": "Личное", "date": None, "time": None}

    def _analyze_task_sync(self, text: str) -> Optional[Dict[str, Any]]:
        # Получаем текущую дату и день недели для контекста
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        days_of_week = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
        current_day = days_of_week[now.weekday()]
        
        prompt = (
            f"Сегодня {current_date} ({current_day}). Проанализируй текст задачи: \"{text}\".\n"
            "Выдели следующие сущности:\n"
            "1. 'category' - выбери одну из: [Личное, Работа, Покупки, Идеи, Финансы].\n"
            "   - 'Личное': спорт, отдых, быт, здоровье, звонки близким.\n"
            "   - 'Работа': встречи, задачи, дедлайны, звонки по работе.\n"
            "   - 'Покупки': еда, вещи, заказы.\n"
            "   - 'Идеи': креатив, мысли на будущее, планы.\n"
            "   - 'Финансы': оплата счетов, долги, налоги.\n"
            "   Если не ясно, выбери наиболее подходящую или 'Личное'.\n"
            "2. 'date' - дата выполнения в формате YYYY-MM-DD. \n"
            "   - Если указано 'завтра', 'послезавтра', 'в понедельник' - вычисли точную дату относительно сегодня.\n"
            "   - Если дата не указана, верни null.\n"
            "3. 'time' - время напоминания в формате HH:MM.\n"
            "   - Если указано 'в 5 вечера', преобразуй в 17:00.\n"
            "   - Если время не указано, верни null.\n"
            "4. 'clean_text' - текст задачи без слов-маркеров времени и даты (удали 'завтра', 'в 10:00' и т.д.).\n"
            "Верни ТОЛЬКО валидный JSON объект.\n"
            "Пример:\n"
            "Input: \"завтра купить молока\"\n"
            "Output: {\"category\": \"Покупки\", \"date\": \"2026-01-22\", \"time\": null, \"clean_text\": \"купить молока\"}"
        )

        try:
            with GigaChat(credentials=self.auth, verify_ssl_certs=False) as giga:
                response = giga.chat(prompt)
                content = response.choices[0].message.content
                
                # Извлечение JSON, если ИИ добавил лишний текст
                start_index = content.find('{')
                end_index = content.rfind('}')
                if start_index != -1 and end_index != -1:
                    content = content[start_index:end_index+1]
                
                logging.info(f"GigaChat cleaned response: {content}")
                
                try:
                    data = json.loads(content)
                    return data
                except json.JSONDecodeError:
                     return {"text": f"[AI JSON ERROR] {content[:50]}...", "category": "Личное", "date": None, "time": None}
                
        except Exception as e:
            logger.error(f"GigaChat analysis failed: {e}")
            return {"text": f"[AI EXCEPTION] {e}", "category": "Личное", "date": None, "time": None}

    async def summarize_tasks(self, tasks: list) -> Optional[str]:
        """
        Generates a morning summary of tasks using GigaChat.
        """
        if not tasks:
            return None
            
        import asyncio
        try:
            return await asyncio.wait_for(asyncio.to_thread(self._summarize_tasks_sync, tasks), timeout=15.0)
        except asyncio.TimeoutError:
            logger.error("GigaChat summarization timed out")
            return None

    def _summarize_tasks_sync(self, tasks: list) -> Optional[str]:
        tasks_text = "\n".join([f"- {t['text']} (Категория: {t['category']})" for t in tasks])
        
        prompt = (
            "Ты — персональный ассистент. Составь краткое и вдохновляющее резюме задач на сегодняшний день.\n"
            "Сгруппируй их по категориям, если это уместно. Будь вежлив и краток.\n"
            "Текст должен быть на русском языке. Используй эмодзи.\n\n"
            f"Список задач:\n{tasks_text}"
        )

        try:
            with GigaChat(credentials=self.auth, verify_ssl_certs=False) as giga:
                response = giga.chat(prompt)
                return response.choices[0].message.content
        except Exception as e:
            logger.error(f"GigaChat summarization failed: {e}")
            return None
