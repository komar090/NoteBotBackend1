from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from typing import List
import os
from dotenv import load_dotenv

# Explicitly load .env
load_dotenv()

class Settings(BaseSettings):
    bot_token: SecretStr
    admin_ids: List[int]
    gigachat_auth: SecretStr

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', case_sensitive=False)

config = Settings()
