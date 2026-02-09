"""
Configuração da aplicação via variáveis de ambiente.
Lê .env (python-dotenv) e expõe constantes validadas.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Carregar .env a partir da raiz do projeto
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


def _required(key: str) -> str:
    value = os.getenv(key)
    if not value or not value.strip():
        raise ValueError(f"Variável de ambiente obrigatória não definida: {key}")
    return value.strip()


def _optional(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


# --- Google Sheets ---
# Caminho para o ficheiro JSON da service account (obrigatório para Sheets)
GOOGLE_SERVICE_ACCOUNT_JSON: str = _optional("GOOGLE_SERVICE_ACCOUNT_JSON", "")
# Fallback legado
GOOGLE_CREDENTIALS_PATH: str = _optional("GOOGLE_CREDENTIALS_PATH", "")
# ID do Google Sheet (ex.: 1UBdukuHNvpfdcyBxKIQAt5pRIKFrGLYI6tZdYhfYCig)
IG_SHEET_ID: str = _optional("IG_SHEET_ID", "1UBdukuHNvpfdcyBxKIQAt5pRIKFrGLYI6tZdYhfYCig")
# Nome do separador/aba (ex.: Folha1)
SHEET_TAB_NAME: str = _optional("SHEET_TAB_NAME", "Folha1")


def get_google_credentials_path() -> str:
    """Retorna o caminho das credenciais Google (prioridade: GOOGLE_SERVICE_ACCOUNT_JSON)."""
    return GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_CREDENTIALS_PATH


# --- Instagram Graph API ---
IG_BUSINESS_ACCOUNT_ID: str = _optional("IG_BUSINESS_ACCOUNT_ID", "")
IG_BUSINESS_ID: str = _optional("IG_BUSINESS_ID", "")  # alias
IG_ACCESS_TOKEN: str = _optional("IG_ACCESS_TOKEN", "")
IG_GRAPH_API_VERSION: str = _optional("IG_GRAPH_API_VERSION", "v20.0")


def get_ig_business_id() -> str:
    """ID da conta de negócios Instagram (usado nos endpoints /media e /media_publish)."""
    return IG_BUSINESS_ACCOUNT_ID or IG_BUSINESS_ID


# --- Gemini (Nano Banana) – geração de imagens a partir de Image Text ---
GEMINI_API_KEY: str = _optional("GEMINI_API_KEY", "")
GEMINI_IMAGE_MODEL: str = _optional("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

# --- Upload de imagens geradas (obrigatório para publicar sem ImageURL no Sheet) ---
# Opção 1: URL única (formato: cloudinary://API_KEY:API_SECRET@CLOUD_NAME)
CLOUDINARY_URL: str = _optional("CLOUDINARY_URL", "")
# Opção 2: variáveis separadas (como no dashboard Cloudinary)
CLOUDINARY_CLOUD_NAME: str = _optional("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY: str = _optional("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET: str = _optional("CLOUDINARY_API_SECRET", "")

# --- Ambiente (dev/prod) ---
ENV: str = _optional("ENV", "dev")
