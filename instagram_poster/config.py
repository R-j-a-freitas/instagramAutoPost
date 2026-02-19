"""
Configuração da aplicação via variáveis de ambiente.
Lê .env (python-dotenv) e expõe constantes validadas.
Suporta credenciais Google em memória (ex.: upload do JSON na UI Streamlit).
"""
import os
import socket
from pathlib import Path
from typing import Any, Optional

import urllib3.util.connection
from dotenv import load_dotenv

# Forçar IPv4 globalmente — evita hang em redes com IPv6 mal configurado
urllib3.util.connection.allowed_gai_family = lambda: socket.AF_INET
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4_only_getaddrinfo

# Carregar .env (tenta vários locais para compatibilidade)
_env_root = Path(__file__).resolve().parent.parent
for _env_path in (_env_root / ".env", _env_root / "instagramAutoPost" / ".env"):
    if _env_path.exists():
        load_dotenv(_env_path)
        break
else:
    load_dotenv(_env_root / ".env")


def _required(key: str) -> str:
    value = os.getenv(key)
    if not value or not value.strip():
        raise ValueError(f"Variável de ambiente obrigatória não definida: {key}")
    return value.strip()


def _optional(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


# --- Google Sheets ---
# OAuth (prioridade): client_id e client_secret para fluxo "Ligar com Google"
GOOGLE_OAUTH_CLIENT_ID: str = _optional("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET: str = _optional("GOOGLE_OAUTH_CLIENT_SECRET", "")
# Fallback: caminho para o ficheiro JSON da service account
GOOGLE_SERVICE_ACCOUNT_JSON: str = _optional("GOOGLE_SERVICE_ACCOUNT_JSON", "")
# Fallback legado
GOOGLE_CREDENTIALS_PATH: str = _optional("GOOGLE_CREDENTIALS_PATH", "")
# ID do Google Sheet (ex.: 1UBdukuHNvpfdcyBxKIQAt5pRIKFrGLYI6tZdYhfYCig)
IG_SHEET_ID: str = _optional("IG_SHEET_ID", "1UBdukuHNvpfdcyBxKIQAt5pRIKFrGLYI6tZdYhfYCig")
# Nome do separador/aba (ex.: Folha1)
SHEET_TAB_NAME: str = _optional("SHEET_TAB_NAME", "Folha1")


def get_ig_sheet_id() -> str:
    """ID do Sheet (env ou override da UI)."""
    return get_runtime_override("IG_SHEET_ID") or IG_SHEET_ID


# Credenciais Google em memória (ex.: carregadas por upload do JSON na UI)
_runtime_google_credentials: Optional[dict[str, Any]] = None
# Overrides em runtime (ex.: preenchidos na UI Streamlit)
_runtime_overrides: dict[str, str] = {}


def set_runtime_override(key: str, value: str) -> None:
    """Define um valor em runtime (ex.: campo preenchido na UI). Use chaves: IG_SHEET_ID, IG_BUSINESS_ID, IG_ACCESS_TOKEN, GEMINI_API_KEY."""
    if value is not None and str(value).strip():
        _runtime_overrides[key] = str(value).strip()
    elif key in _runtime_overrides:
        del _runtime_overrides[key]


def get_runtime_override(key: str) -> Optional[str]:
    return _runtime_overrides.get(key)


def set_google_credentials_dict(credentials_dict: Optional[dict[str, Any]]) -> None:
    """Define as credenciais da service account a partir de um dict (ex.: JSON carregado na UI). Passa None para limpar."""
    global _runtime_google_credentials
    _runtime_google_credentials = credentials_dict


def get_google_credentials_dict() -> Optional[dict[str, Any]]:
    """Retorna as credenciais em memória, se definidas (upload na UI)."""
    return _runtime_google_credentials


def get_google_credentials_path() -> str:
    """Retorna o caminho das credenciais Google (prioridade: GOOGLE_SERVICE_ACCOUNT_JSON)."""
    return GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_CREDENTIALS_PATH


# --- Instagram Graph API ---
# OAuth (prioridade): App ID e Secret para fluxo "Ligar com Instagram"
INSTAGRAM_APP_ID: str = _optional("INSTAGRAM_APP_ID", "")
INSTAGRAM_APP_SECRET: str = _optional("INSTAGRAM_APP_SECRET", "")
# Fallback: credenciais manuais
IG_BUSINESS_ACCOUNT_ID: str = _optional("IG_BUSINESS_ACCOUNT_ID", "")
IG_BUSINESS_ID: str = _optional("IG_BUSINESS_ID", "")  # alias
IG_ACCESS_TOKEN: str = _optional("IG_ACCESS_TOKEN", "")
IG_GRAPH_API_VERSION: str = _optional("IG_GRAPH_API_VERSION", "v20.0")


def get_ig_business_id() -> str:
    """ID da conta de negócios Instagram (OAuth, override da UI ou env)."""
    override = get_runtime_override("IG_BUSINESS_ID")
    if override:
        return override
    try:
        from instagram_poster.oauth_instagram import load_oauth_token
        tok = load_oauth_token()
        if tok and tok.get("ig_business_id"):
            return str(tok["ig_business_id"])
    except Exception:
        pass
    return IG_BUSINESS_ACCOUNT_ID or IG_BUSINESS_ID


def get_ig_access_token() -> str:
    """Token de acesso Instagram (OAuth, override da UI ou env)."""
    override = get_runtime_override("IG_ACCESS_TOKEN")
    if override:
        return override
    try:
        from instagram_poster.oauth_instagram import load_oauth_token
        tok = load_oauth_token()
        if tok and tok.get("access_token"):
            return str(tok["access_token"])
    except Exception:
        pass
    return IG_ACCESS_TOKEN


# --- Geração de imagens (multi-provedor) ---
IMAGE_PROVIDER: str = _optional("IMAGE_PROVIDER", "gemini")
GEMINI_API_KEY: str = _optional("GEMINI_API_KEY", "")
GEMINI_IMAGE_MODEL: str = _optional("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
OPENAI_API_KEY: str = _optional("OPENAI_API_KEY", "")
POLLINATIONS_API_KEY: str = _optional("POLLINATIONS_API_KEY", "")


def get_image_provider() -> str:
    """Provedor de imagens activo (env ou override da UI)."""
    return get_runtime_override("IMAGE_PROVIDER") or IMAGE_PROVIDER


def get_gemini_api_key() -> str:
    """API key Gemini (env ou override da UI)."""
    return get_runtime_override("GEMINI_API_KEY") or GEMINI_API_KEY


def get_openai_api_key() -> str:
    """API key OpenAI (env ou override da UI)."""
    return get_runtime_override("OPENAI_API_KEY") or OPENAI_API_KEY


def get_pollinations_api_key() -> str:
    """API key Pollinations (env ou override da UI). Opcional — sem key funciona com rate-limit."""
    return get_runtime_override("POLLINATIONS_API_KEY") or POLLINATIONS_API_KEY


# --- Upload de imagens geradas (obrigatório para publicar sem ImageURL no Sheet) ---
# Opção 1: URL única (formato: cloudinary://API_KEY:API_SECRET@CLOUD_NAME)
CLOUDINARY_URL: str = _optional("CLOUDINARY_URL", "")
# Opção 2: variáveis separadas (como no dashboard Cloudinary)
CLOUDINARY_CLOUD_NAME: str = _optional("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY: str = _optional("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET: str = _optional("CLOUDINARY_API_SECRET", "")

# --- Autopublish ---
AUTOPUBLISH_ENABLED: str = _optional("AUTOPUBLISH_ENABLED", "false")
AUTOPUBLISH_INTERVAL_MINUTES: str = _optional("AUTOPUBLISH_INTERVAL_MINUTES", "5")


def get_autopublish_enabled() -> bool:
    val = get_runtime_override("AUTOPUBLISH_ENABLED") or AUTOPUBLISH_ENABLED
    return val.lower() in ("true", "1", "yes", "on")


def get_autopublish_interval() -> int:
    val = get_runtime_override("AUTOPUBLISH_INTERVAL_MINUTES") or AUTOPUBLISH_INTERVAL_MINUTES
    try:
        return max(1, int(val))
    except (ValueError, TypeError):
        return 5


# --- Ambiente (dev/prod) ---
ENV: str = _optional("ENV", "dev")
