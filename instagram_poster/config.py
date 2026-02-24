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
HUGGINGFACE_TOKEN: str = _optional("HUGGINGFACE_TOKEN", "")
FIREFLY_CLIENT_ID: str = _optional("FIREFLY_CLIENT_ID", "")
FIREFLY_CLIENT_SECRET: str = _optional("FIREFLY_CLIENT_SECRET", "")


def get_image_provider() -> str:
    """Provedor de imagens activo (override da UI, depois .env). Lê os.getenv em cada chamada para refletir alterações ao .env sem reiniciar."""
    override = get_runtime_override("IMAGE_PROVIDER")
    if override:
        return override
    return (os.getenv("IMAGE_PROVIDER") or IMAGE_PROVIDER or "gemini").strip()


def get_gemini_api_key() -> str:
    """API key Gemini (env ou override da UI)."""
    return get_runtime_override("GEMINI_API_KEY") or GEMINI_API_KEY


def get_openai_api_key() -> str:
    """API key OpenAI (env ou override da UI)."""
    return get_runtime_override("OPENAI_API_KEY") or OPENAI_API_KEY


def get_pollinations_api_key() -> str:
    """API key Pollinations (env ou override da UI). Opcional — sem key funciona com rate-limit."""
    return get_runtime_override("POLLINATIONS_API_KEY") or POLLINATIONS_API_KEY


# --- Geração de conteúdo (texto para posts) ---
CONTENT_GENERATION_EXTRA_PROMPT: str = _optional("CONTENT_GENERATION_EXTRA_PROMPT", "")
_CONTENT_SYSTEM_PROMPT_OVERRIDE_FILE = _env_root / "content_system_prompt_override.txt"

# Prompt de sistema padrão (referência na Configuração e fallback na página Conteúdo)
DEFAULT_CONTENT_SYSTEM_PROMPT = r"""You are a content creator for the Instagram account @keepcalmnbepositive.

## Account context

- Niche: personal development, positive mindset, self-compassion, emotional healing, healthy boundaries, rest, slow growth.
- Tone: calm, encouraging, practical. No toxic positivity, no aggressive "hustle" culture.
- Goal: help people think and feel in a kinder, more conscious and responsible way, without guilt or unrealistic demands.

## Google Sheet structure

Each row has these columns (fixed order):

1. Date – post date (YYYY-MM-DD)
2. Time – post time (HH:MM)
3. Image Text – the short quote/phrase that will be overlaid on the image
4. Caption – the post caption in English, a mini-text/reflection with 2-6 short paragraphs
5. Gemini_Prompt – technical prompt to generate the background image, in English, describing what the image should show (NO text in the image)
6. Status – always "ready"
7. Published – always empty string
8. ImageURL – always empty string
9. Image Prompt – always "yes"

## Rules for each field

### Date and Time
- For Date use literally the placeholder "YYYY-MM-DD" (will be filled later).
- For Time always use "21:30".

### Image Text (quote)
- Short, strong phrase that stands on its own.
- In simple English, first person, aligned with the account style.
- Style examples (do NOT repeat these, only use as reference):
  - "Today I focus on what I can do, not on what I can't control."
  - "Resting is not losing time. Resting prepares me for the time ahead."
  - "I give myself permission to grow at my own pace."
- Avoid empty cliches like "good vibes only", "think positive".
- Each quote should focus on a concrete micro-theme (self-talk, boundaries, rest, gratitude, anxiety, etc.).

### Caption
- Text in English, 2-6 short paragraphs.
- Typical structure:
  - 1-2 sentences expanding the quote idea.
  - Practical explanation of the concept.
  - 1 small exercise/action for today (e.g., "Today, try...", "Write down...", "Notice when...").
  - 0-2 relevant hashtags at the end (ideally include #keepcalmnbepositive).
- Style: direct conversation with the reader ("you", "your mind", "your body"). Gentle but honest.

### Gemini_Prompt (for image generation)
- Written in English.
- Describes a concrete image that matches the quote and caption.
- IMPORTANT rules:
  - Do NOT include any text, letters, or words in the image.
  - Mention: main scene, environment, color palette, emotion/mood.
  - If there are people: no close-up faces; can be from behind, silhouette, or distant.
- Example style (do NOT copy, only reference for detail level):
  - "Serene breathing moment: a person sitting near a window with plants, hands resting gently on their chest. Soft blue and green tones, lots of calm space. No text in the image."

### Status, Published, ImageURL, Image Prompt
- Status: always "ready"
- Published: always ""
- ImageURL: always ""
- Image Prompt: always "yes"

## Output format

Return a JSON object with a single key "posts" containing an array of objects.
Each object must have exactly these keys: "Date", "Time", "Image Text", "Caption", "Gemini_Prompt", "Status", "Published", "ImageURL", "Image Prompt".

Vary the micro-themes across posts. Be creative but stay consistent with @keepcalmnbepositive style."""


def get_content_extra_prompt() -> str:
    """Instruções adicionais / foco actual para a geração de conteúdo (env ou override da UI)."""
    return get_runtime_override("CONTENT_GENERATION_EXTRA_PROMPT") or CONTENT_GENERATION_EXTRA_PROMPT


def get_content_system_prompt_override() -> Optional[str]:
    """
    Lê o prompt de sistema personalizado do ficheiro content_system_prompt_override.txt.
    Devolve None se o ficheiro não existir ou estiver vazio (usa o prompt padrão).
    """
    path = _CONTENT_SYSTEM_PROMPT_OVERRIDE_FILE
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8").strip()
    return content if content else None


def get_content_system_prompt_override_path() -> Path:
    """Caminho do ficheiro de override do prompt de sistema (para a UI gravar)."""
    return _CONTENT_SYSTEM_PROMPT_OVERRIDE_FILE


def get_default_content_system_prompt() -> str:
    """Prompt de sistema padrão da geração de conteúdo (referência e base)."""
    return DEFAULT_CONTENT_SYSTEM_PROMPT


def get_huggingface_token() -> str:
    """Token Hugging Face (env ou override da UI). Grátis em huggingface.co/settings/tokens."""
    return get_runtime_override("HUGGINGFACE_TOKEN") or HUGGINGFACE_TOKEN


def get_firefly_client_id() -> str:
    """Client ID Adobe Firefly (env ou override da UI)."""
    return get_runtime_override("FIREFLY_CLIENT_ID") or FIREFLY_CLIENT_ID


def get_firefly_client_secret() -> str:
    """Client Secret Adobe Firefly (env ou override da UI)."""
    return get_runtime_override("FIREFLY_CLIENT_SECRET") or FIREFLY_CLIENT_SECRET


# --- Upload de imagens geradas (obrigatório para publicar sem ImageURL no Sheet) ---
# Opção 1: URL única (formato: cloudinary://API_KEY:API_SECRET@CLOUD_NAME)
CLOUDINARY_URL: str = _optional("CLOUDINARY_URL", "")
# Opção 2: variáveis separadas (como no dashboard Cloudinary)
CLOUDINARY_CLOUD_NAME: str = _optional("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY: str = _optional("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET: str = _optional("CLOUDINARY_API_SECRET", "")


def get_cloudinary_url() -> str:
    """CLOUDINARY_URL (env ou override da UI). Formato: cloudinary://API_KEY:API_SECRET@CLOUD_NAME."""
    return get_runtime_override("CLOUDINARY_URL") or CLOUDINARY_URL

# --- Autopublish ---
AUTOPUBLISH_ENABLED: str = _optional("AUTOPUBLISH_ENABLED", "false")
AUTOPUBLISH_INTERVAL_MINUTES: str = _optional("AUTOPUBLISH_INTERVAL_MINUTES", "5")
AUTOPUBLISH_STORY_WITH_POST: str = _optional("AUTOPUBLISH_STORY_WITH_POST", "false")
AUTOPUBLISH_STORY_WITH_MUSIC: str = _optional("AUTOPUBLISH_STORY_WITH_MUSIC", "false")
AUTOPUBLISH_STORY_REUSE_SCHEDULE: str = _optional("AUTOPUBLISH_STORY_REUSE_SCHEDULE", "false")
AUTOPUBLISH_STORY_REUSE_INTERVAL_MINUTES: str = _optional("AUTOPUBLISH_STORY_REUSE_INTERVAL_MINUTES", "120")
AUTOPUBLISH_REEL_EVERY_5: str = _optional("AUTOPUBLISH_REEL_EVERY_5", "true")
AUTOPUBLISH_REEL_ALLOW_REUSED_POSTS: str = _optional("AUTOPUBLISH_REEL_ALLOW_REUSED_POSTS", "false")
AUTOPUBLISH_REEL_REUSE_SCHEDULE: str = _optional("AUTOPUBLISH_REEL_REUSE_SCHEDULE", "false")
AUTOPUBLISH_REEL_REUSE_INTERVAL_MINUTES: str = _optional("AUTOPUBLISH_REEL_REUSE_INTERVAL_MINUTES", "120")
AUTOPUBLISH_COMMENT_AUTOREPLY: str = _optional("AUTOPUBLISH_COMMENT_AUTOREPLY", "false")


def get_autopublish_enabled() -> bool:
    val = get_runtime_override("AUTOPUBLISH_ENABLED") or os.getenv("AUTOPUBLISH_ENABLED") or AUTOPUBLISH_ENABLED
    return val.lower() in ("true", "1", "yes", "on")


def get_autopublish_interval() -> int:
    val = get_runtime_override("AUTOPUBLISH_INTERVAL_MINUTES") or os.getenv("AUTOPUBLISH_INTERVAL_MINUTES") or AUTOPUBLISH_INTERVAL_MINUTES
    try:
        return max(1, int(val))
    except (ValueError, TypeError):
        return 5


def get_autopublish_story_with_post() -> bool:
    """Se True, publica também uma Story no Instagram quando um post é publicado automaticamente."""
    val = get_runtime_override("AUTOPUBLISH_STORY_WITH_POST") or os.getenv("AUTOPUBLISH_STORY_WITH_POST") or AUTOPUBLISH_STORY_WITH_POST
    return val.lower() in ("true", "1", "yes", "on")


def get_autopublish_story_with_music() -> bool:
    """Se True, as Stories são publicadas como vídeo com música (imagem + áudio da pasta MUSIC)."""
    val = get_runtime_override("AUTOPUBLISH_STORY_WITH_MUSIC") or os.getenv("AUTOPUBLISH_STORY_WITH_MUSIC") or AUTOPUBLISH_STORY_WITH_MUSIC
    return val.lower() in ("true", "1", "yes", "on")


def get_autopublish_story_reuse_schedule_enabled() -> bool:
    """Se True, publica uma Story (com imagem de um post já publicado) a cada X tempo (intervalo definido)."""
    val = get_runtime_override("AUTOPUBLISH_STORY_REUSE_SCHEDULE") or os.getenv("AUTOPUBLISH_STORY_REUSE_SCHEDULE") or AUTOPUBLISH_STORY_REUSE_SCHEDULE
    return val.lower() in ("true", "1", "yes", "on")


def get_autopublish_story_reuse_interval_minutes() -> int:
    """Intervalo em minutos para a Story agendada (reutilizar post já publicado)."""
    val = get_runtime_override("AUTOPUBLISH_STORY_REUSE_INTERVAL_MINUTES") or os.getenv("AUTOPUBLISH_STORY_REUSE_INTERVAL_MINUTES") or AUTOPUBLISH_STORY_REUSE_INTERVAL_MINUTES
    try:
        return max(30, int(val))
    except (ValueError, TypeError):
        return 120


def get_autopublish_reel_every_5() -> bool:
    """Se True, gera e publica um Reel automaticamente sempre que houver 5 posts (últimos 5 diferentes)."""
    val = get_runtime_override("AUTOPUBLISH_REEL_EVERY_5") or os.getenv("AUTOPUBLISH_REEL_EVERY_5") or AUTOPUBLISH_REEL_EVERY_5
    return val.lower() in ("true", "1", "yes", "on")


def get_autopublish_reel_allow_reused_posts() -> bool:
    """Se True, o Reel automático pode usar posts já usados em Reels anteriores."""
    val = get_runtime_override("AUTOPUBLISH_REEL_ALLOW_REUSED_POSTS") or os.getenv("AUTOPUBLISH_REEL_ALLOW_REUSED_POSTS") or AUTOPUBLISH_REEL_ALLOW_REUSED_POSTS
    return val.lower() in ("true", "1", "yes", "on")


def get_autopublish_reel_reuse_schedule_enabled() -> bool:
    """Se True, gera um Reel com posts já usados em Reels a cada X minutos (intervalo definido)."""
    val = get_runtime_override("AUTOPUBLISH_REEL_REUSE_SCHEDULE") or os.getenv("AUTOPUBLISH_REEL_REUSE_SCHEDULE") or AUTOPUBLISH_REEL_REUSE_SCHEDULE
    return val.lower() in ("true", "1", "yes", "on")


def get_autopublish_reel_reuse_interval_minutes() -> int:
    """Intervalo em minutos para o Reel agendado com posts já usados."""
    val = get_runtime_override("AUTOPUBLISH_REEL_REUSE_INTERVAL_MINUTES") or os.getenv("AUTOPUBLISH_REEL_REUSE_INTERVAL_MINUTES") or AUTOPUBLISH_REEL_REUSE_INTERVAL_MINUTES
    try:
        return max(30, int(float(val)))
    except (ValueError, TypeError):
        return 120


def get_autopublish_comment_autoreply() -> bool:
    """Se True, executa autoresposta a comentários em cada verificação do autopublish."""
    val = get_runtime_override("AUTOPUBLISH_COMMENT_AUTOREPLY") or os.getenv("AUTOPUBLISH_COMMENT_AUTOREPLY") or AUTOPUBLISH_COMMENT_AUTOREPLY
    return val.lower() in ("true", "1", "yes", "on")


# --- Ambiente (dev/prod) ---
ENV: str = _optional("ENV", "dev")
