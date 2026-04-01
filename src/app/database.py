import os
from pathlib import Path
from supabase import create_client, Client
from pydantic_settings import BaseSettings, SettingsConfigDict

# Localizar o arquivo .env de forma absoluta em relação a este arquivo
# database.py está em src/app/database.py -> .env está em ../../.env
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DOTENV_PATH = BASE_DIR / ".env"

class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    google_api_key: str = ""
    ai_provider: str = "gemini"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "mistral-nemo:latest"
    
    # Configurar para ler do arquivo .env absoluto
    model_config = SettingsConfigDict(
        env_file=str(DOTENV_PATH),
        env_file_encoding='utf-8',
        extra='ignore' # Ignorar variáveis extras no .env
    )

# Inicializar settings
try:
    if DOTENV_PATH.exists():
        print(f"✅ Carregando configurações de: {DOTENV_PATH}")
        settings = Settings()
    else:
        print(f"⚠️ Arquivo .env não encontrado em {DOTENV_PATH}. Usando variáveis de ambiente do sistema.")
        settings = Settings(_env_file=None)
except Exception as e:
    print(f"❌ Erro ao carregar Settings: {e}")
    # Fallback para tentar ler do CWD se tudo falhar
    settings = Settings(_env_file=".env")

def get_supabase() -> Client:
    return create_client(settings.supabase_url, settings.supabase_key)
