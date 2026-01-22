from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import json
import hashlib
import hmac
import os
from database.database import db
from config_reader import config
try:
    from pyngrok import ngrok
except ImportError:
    ngrok = None

app = FastAPI()

# Allow CORS for Mini App (it runs in iframe)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup: Connect to DB
@app.on_event("startup")
async def startup():
    await db.connect() # Ensure connection is open
    print("API connected to Database")
    
    # Auto-start Ngrok removed to avoid conflicts with Serveo (Updated 02:25)


@app.on_event("shutdown")
async def shutdown():
    await db.close()

# -- Models --
class TaskCreate(BaseModel):
    user_id: int
    text: str
    category: str
    date: Optional[str] = None
    time: Optional[str] = None

class InitData(BaseModel):
    initData: str

# -- Helpers --
def validate_telegram_data(init_data: str) -> dict:
    """
    Validates the initData string from Telegram Web App.
    Returns the parsed data (user object) if valid.
    Raises HTTPException if invalid.
    """
    if not init_data:
         raise HTTPException(status_code=401, detail="No initData provided")
         
    try:
        from urllib.parse import parse_qsl, unquote
        
        parsed_data = dict(parse_qsl(init_data))
        hash_check = parsed_data.get('hash')
        if not hash_check:
             raise HTTPException(status_code=401, detail="No hash in initData")
             
        # Remove hash from data to validate
        data_check_list = []
        for key in sorted(parsed_data.keys()):
            if key != 'hash':
                data_check_list.append(f"{key}={parsed_data[key]}")
        
        data_check_string = "\n".join(data_check_list)
        
        # Calculate HMAC
        secret_key = hmac.new(b"WebAppData", config.bot_token.get_secret_value().encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if calculated_hash != hash_check:
             raise HTTPException(status_code=403, detail="Data integrity check failed")
             
        # Return user data
        user_data = json.loads(parsed_data.get('user', '{}'))
        return user_data
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {e}")

# -- Endpoints --

@app.get("/")
async def health_check():
    return {"status": "ok", "service": "Note Bot API", "version": "2.0 (AI+Voice)"}

@app.get("/api/")
async def health_check_api():
    return {"status": "ok", "service": "Note Bot API", "version": "2.0 (AI+Voice)"}

@app.get("/api/tasks")
async def get_tasks(initData: str):
    """Get active tasks for the user."""
    user = validate_telegram_data(initData)
    user_id = user['id']
    
    tasks = await db.get_user_tasks(user_id)
    # Convert Row objects to dicts
    return [{"id": t['id'], "text": t['text'], "category": t['category'], "created_at": t['created_at']} for t in tasks]

@app.post("/api/tasks")
async def create_task(task: TaskCreate, initData: str):
    """Create a new task."""
    user = validate_telegram_data(initData)
    # Use user_id from token, but we can verify it matches body if needed
    # For now just trust the user from token
    user_id = user['id']
    
    await db.add_task(user_id, task.text, task.category)
    
    # Simple logic for reminders (add if date/time present)
    # For MVP we can skip complex date parsing here or move logic from handlers
    # Let's keep it simple: Just task
    
    return {"status": "success"}

@app.post("/api/tasks/{task_id}/done")
async def complete_task(task_id: int, initData: str):
    """Mark task as done."""
    user = validate_telegram_data(initData)
    user_id = user['id']
    
    # Ideally check ownership
    # For MVP assume ID is correct
    await db.mark_task_done(task_id)
    return {"status": "success", "id": task_id}



# -- Admin & Advanced Features --

@app.get("/api/me")
async def get_my_info(initData: str):
    """Return user info with admin status."""
    user = validate_telegram_data(initData)
    user_id = user['id']
    
    # Check if admin
    is_admin = user_id in config.admin_ids
    
    return {
        "id": user_id,
        "first_name": user.get("first_name"),
        "is_admin": is_admin
    }
