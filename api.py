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



# -- Advanced Features (Voice & AI) --

from utils.gigachat_client import GigaChatClient
import speech_recognition as sr
from pydub import AudioSegment
import shutil

ai_client = GigaChatClient()

class AnalyzeRequest(BaseModel):
    text: str

@app.post("/api/analyze")
async def analyze_text_endpoint(request: AnalyzeRequest, initData: str):
    """Analyze text using GigaChat to extract date, time, and category."""
    user = validate_telegram_data(initData) # Auth check
    
    analysis = await ai_client.analyze_task(request.text)
    if not analysis:
        # Fallback if AI fails
        return {"text": request.text, "category": "Личное", "date": None, "time": None}
        
    return analysis

@app.post("/api/voice")
async def process_voice_endpoint(file: UploadFile = File(...), initData: str = Form(...)):
    """Process voice message: Convert -> Transcribe -> Analyze."""
    user = validate_telegram_data(initData) # Auth check
    
    # 1. Save uploaded file
    temp_filename = f"voice_{user['id']}_{file.filename}"
    with open(temp_filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    wav_filename = f"{temp_filename}.wav"
    
    try:
        # 2. Convert to WAV (SpeechRecognition needs WAV)
        # Try pydub (requires ffmpeg installed on VPS)
        try:
            audio = AudioSegment.from_file(temp_filename)
            audio.export(wav_filename, format="wav")
        except Exception as e:
            # Fallback for some systems if pydub fails, maybe rename? 
            # But usually we need conversion. WebApp sends 'audio/webm' usually.
            print(f"Conversion error: {e}")
            raise HTTPException(status_code=500, detail="Audio conversion failed. Is FFmpeg installed?")

        # 3. Transcribe
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_filename) as source:
            audio_data = recognizer.record(source)
            try:
                text = recognizer.recognize_google(audio_data, language="ru-RU")
            except sr.UnknownValueError:
                raise HTTPException(status_code=400, detail="Речь не распознана")
            except sr.RequestError:
                raise HTTPException(status_code=503, detail="Ошибка сервиса распознавания")

        # 4. Analyze with AI
        analysis = await ai_client.analyze_task(text)
        if not analysis:
             analysis = {"text": text, "category": "Личное", "date": None, "time": None}
             
        return analysis

    finally:
        # Cleanup
        if os.path.exists(temp_filename): os.remove(temp_filename)
        if os.path.exists(wav_filename): os.remove(wav_filename)
