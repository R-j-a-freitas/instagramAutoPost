"""
OAuth para Instagram Graph API.
Permite ao utilizador autenticar com Instagram e obter o access token automaticamente.
Suporta Instagram API with Instagram Login (api.instagram.com/oauth).
"""
import json
import secrets
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import requests

# Ficheiro onde guardamos o token OAuth
TOKEN_FILE = Path(__file__).resolve().parent.parent / "instagram_oauth_token.json"

# Scopes para publicar conteúdo (Instagram Graph API)
SCOPES = ["instagram_basic", "instagram_content_publish"]


def get_redirect_uri() -> str:
    """URI de callback para o OAuth."""
    import os
    base = os.getenv("OAUTH_REDIRECT_BASE", "http://localhost:8501")
    return base.rstrip("/") + "/"


def get_app_credentials() -> Optional[tuple[str, str]]:
    """Obtém (client_id, client_secret) do .env."""
    import os
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    client_id = os.getenv("INSTAGRAM_APP_ID", "").strip() or os.getenv("FACEBOOK_APP_ID", "").strip()
    client_secret = os.getenv("INSTAGRAM_APP_SECRET", "").strip() or os.getenv("FACEBOOK_APP_SECRET", "").strip()
    if not client_id or not client_secret:
        return None
    return (client_id, client_secret)


def get_auth_url(state: Optional[str] = None) -> Optional[str]:
    """Gera a URL para o utilizador autorizar a app no Instagram."""
    creds = get_app_credentials()
    if not creds:
        return None
    client_id, _ = creds
    state_val = state or secrets.token_urlsafe(32)
    params = {
        "client_id": client_id,
        "redirect_uri": get_redirect_uri(),
        "response_type": "code",
        "scope": ",".join(SCOPES),
        "state": state_val,
    }
    return f"https://api.instagram.com/oauth/authorize?{urlencode(params)}"


def exchange_code_for_token(code: str) -> Optional[dict]:
    """
    Troca o código de autorização por access token.
    POST https://api.instagram.com/oauth/access_token
    Devolve dict com access_token, user_id; guarda em ficheiro.
    """
    creds = get_app_credentials()
    if not creds:
        return None
    client_id, client_secret = creds
    # Nota: Instagram pode acrescentar #_ ao redirect_uri; o code vem limpo
    code = (code or "").strip()
    if not code:
        return None
    resp = requests.post(
        "https://api.instagram.com/oauth/access_token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "redirect_uri": get_redirect_uri(),
            "code": code,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if not resp.ok:
        return None
    data = resp.json()
    access_token = data.get("access_token")
    user_id = data.get("user_id")
    if not access_token:
        return None
    # Trocar por long-lived token (60 dias)
    long_lived = _exchange_for_long_lived(access_token, client_secret)
    if long_lived:
        access_token = long_lived
    # Obter Instagram Business Account ID (para publicar)
    ig_business_id = _get_ig_business_id(access_token, user_id)
    result = {
        "access_token": access_token,
        "user_id": user_id,
        "ig_business_id": ig_business_id,
    }
    TOKEN_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _exchange_for_long_lived(short_token: str, client_secret: str) -> Optional[str]:
    """Troca short-lived token por long-lived (60 dias)."""
    resp = requests.get(
        "https://graph.instagram.com/access_token",
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": client_secret,
            "access_token": short_token,
        },
        timeout=30,
    )
    if not resp.ok:
        return short_token  # Usar o short-lived se falhar
    data = resp.json()
    return data.get("access_token", short_token)


def _get_ig_business_id(access_token: str, user_id: str) -> Optional[str]:
    """
    Obtém o Instagram Business Account ID.
    Para contas profissionais, o user_id do OAuth é o IG User ID.
    Para publicar usamos o mesmo ID em /{ig-user-id}/media.
    """
    # Com Instagram Login, o user_id devolvido é o IG User ID
    return user_id


def load_oauth_token() -> Optional[dict]:
    """Carrega o token OAuth guardado. Dict com access_token, ig_business_id."""
    if not TOKEN_FILE.exists():
        return None
    try:
        data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        if data.get("access_token"):
            return data
    except Exception:
        pass
    return None


def has_oauth_token() -> bool:
    """Verifica se existe token OAuth guardado."""
    return load_oauth_token() is not None


def clear_oauth_token() -> None:
    """Remove o ficheiro de token."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
