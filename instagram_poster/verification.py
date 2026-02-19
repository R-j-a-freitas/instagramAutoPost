"""
Funções de verificação/teste para validar a configuração de cada serviço.
"""
import io
import base64
from typing import Tuple

import requests

from instagram_poster.config import (
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_URL,
    IG_GRAPH_API_VERSION,
    get_gemini_api_key,
    get_ig_access_token,
    get_ig_business_id,
    get_image_provider,
    get_openai_api_key,
)
from instagram_poster.providers import AVAILABLE_PROVIDERS


def verify_google_sheets() -> Tuple[bool, str]:
    """Verifica se a ligação ao Google Sheet funciona (lê 1 linha)."""
    try:
        from instagram_poster.sheets_client import get_upcoming_posts
        _ = get_upcoming_posts(n=1, from_date=None)
        return True, "Google Sheets: ligação OK."
    except Exception as e:
        return False, f"Google Sheets: {e}"


def verify_instagram() -> Tuple[bool, str]:
    """Verifica se o token e IG Business ID são válidos (chamada à API)."""
    ig_id = get_ig_business_id()
    token = get_ig_access_token()
    if not ig_id or not token:
        return False, "Instagram: preenche IG_BUSINESS_ID e IG_ACCESS_TOKEN."
    url = f"https://graph.instagram.com/{IG_GRAPH_API_VERSION}/{ig_id}"
    params = {"fields": "id,username", "access_token": token}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        username = data.get("username", "?")
        return True, f"Instagram: OK (@{username})"
    except requests.HTTPError as e:
        try:
            err = e.response.json()
            msg = err.get("error", {}).get("message", str(e))
        except Exception:
            msg = str(e)
        return False, f"Instagram: {msg}"
    except Exception as e:
        return False, f"Instagram: {e}"


def _verify_gemini() -> Tuple[bool, str]:
    api_key = get_gemini_api_key()
    if not api_key:
        return False, "Gemini: preenche GEMINI_API_KEY."
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        last_err = ""
        for model in ("gemini-2.0-flash", "gemini-2.0-flash-lite"):
            try:
                client.models.generate_content(model=model, contents="Say OK.")
                return True, f"Gemini: OK ({model})"
            except Exception as exc:
                last_err = str(exc)[:120]
                if "429" in last_err or "RESOURCE_EXHAUSTED" in last_err:
                    return False, "Gemini: quota excedida (429). Aguarda reset ou faz upgrade."
                continue
        return False, f"Gemini: {last_err}"
    except Exception as e:
        return False, f"Gemini: {e}"


def _verify_openai() -> Tuple[bool, str]:
    api_key = get_openai_api_key()
    if not api_key:
        return False, "OpenAI: preenche OPENAI_API_KEY."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        client.models.list()
        return True, "OpenAI: OK (DALL-E 3)"
    except ImportError:
        return False, "OpenAI: instala o pacote — pip install openai"
    except Exception as e:
        msg = str(e)[:120]
        if "401" in msg or "invalid" in msg.lower():
            return False, "OpenAI: API key inválida."
        return False, f"OpenAI: {msg}"


def _verify_pollinations() -> Tuple[bool, str]:
    from instagram_poster.config import get_pollinations_api_key
    api_key = get_pollinations_api_key()
    try:
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        resp = requests.get(
            "https://gen.pollinations.ai/image/test%20image?width=64&height=64&model=flux&nologo=true",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if "image" in ct or len(resp.content) > 1000:
            key_info = " (com API key)" if api_key else " (sem key)"
            return True, f"Pollinations: OK{key_info}"
        return False, f"Pollinations: resposta inesperada (content-type: {ct})"
    except Exception as e:
        return False, f"Pollinations: {e}"


def verify_image_provider() -> Tuple[bool, str]:
    """Verifica o provedor de imagens activo (IMAGE_PROVIDER no .env)."""
    provider = get_image_provider()
    label = AVAILABLE_PROVIDERS.get(provider, provider)
    if provider == "gemini":
        return _verify_gemini()
    if provider == "openai":
        return _verify_openai()
    if provider == "pollinations":
        return _verify_pollinations()
    return False, f"Provedor desconhecido: {provider}"


# Alias para compatibilidade
verify_gemini = verify_image_provider


def verify_cloudinary() -> Tuple[bool, str]:
    """Verifica se o Cloudinary está configurado e aceita upload (teste com 1x1 pixel)."""
    if CLOUDINARY_URL and CLOUDINARY_URL.strip().startswith("cloudinary://"):
        pass
    elif CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
        pass
    else:
        return False, "Cloudinary: define CLOUDINARY_URL no .env ou as variáveis separadas."
    try:
        import cloudinary
        import cloudinary.uploader
        if CLOUDINARY_URL and CLOUDINARY_URL.strip().startswith("cloudinary://"):
            cloudinary.config(cloudinary_url=CLOUDINARY_URL)
        else:
            cloudinary.config(
                cloud_name=CLOUDINARY_CLOUD_NAME,
                api_key=CLOUDINARY_API_KEY,
                api_secret=CLOUDINARY_API_SECRET,
                secure=True,
            )
        tiny_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        result = cloudinary.uploader.upload(
            io.BytesIO(tiny_png),
            public_id="ig_test_verify",
            overwrite=True,
        )
        url = result.get("secure_url") or result.get("url")
        if url:
            return True, "Cloudinary: OK"
        return True, "Cloudinary: OK"
    except Exception as e:
        return False, f"Cloudinary: {e}"
