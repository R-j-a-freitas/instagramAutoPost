"""
Funções de verificação/teste para validar a configuração de cada serviço.
"""
import io
import base64
from typing import Any, Dict, List, Optional, Tuple

import requests

from instagram_poster.config import (
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
    CLOUDINARY_CLOUD_NAME,
    get_cloudinary_url,
    get_media_backend,
    get_media_root,
    IG_GRAPH_API_VERSION,
    get_gemini_api_key,
    get_ig_access_token,
    get_ig_business_id,
    get_image_provider,
    get_openai_api_key,
)
from instagram_poster.providers import AVAILABLE_PROVIDERS

# Códigos de erro da Meta/Instagram que indicam rate limit
RATE_LIMIT_ERROR_CODES = (4, 17, 32, 613)
RATE_LIMIT_LABELS = {
    4: "rate limit da app",
    17: "rate limit do utilizador",
    32: "rate limit de páginas",
    613: "rate limit customizado",
}
# Headers de uso da Meta (valor em percentagem; 100 = no limite)
USAGE_HEADERS = ("X-App-Usage", "X-Ad-Account-Usage", "X-Page-Usage")


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


def check_instagram_api_status() -> Dict[str, Any]:
    """
    Faz um request de teste à Instagram/Facebook Graph API e devolve estado, headers de uso
    e interpretação de rate limits (códigos 4, 17, 32, 613 e headers X-App-Usage, etc.).
    Útil para monitorizar se a API está bloqueada ou perto do limite.
    """
    result: Dict[str, Any] = {
        "ok": False,
        "status_code": None,
        "error_code": None,
        "error_message": None,
        "body": None,
        "usage_headers": {},
        "summary": [],
    }
    ig_id = get_ig_business_id()
    token = get_ig_access_token()
    if not ig_id or not token:
        result["summary"].append("Preenche IG_BUSINESS_ID e IG_ACCESS_TOKEN.")
        return result
    url = f"https://graph.instagram.com/{IG_GRAPH_API_VERSION}/{ig_id}"
    params = {"fields": "id,username", "access_token": token}
    try:
        resp = requests.get(url, params=params, timeout=15)
        result["status_code"] = resp.status_code
        for name in USAGE_HEADERS:
            val = resp.headers.get(name)
            if val is not None:
                result["usage_headers"][name] = val
        try:
            result["body"] = resp.json()
        except Exception:
            result["body"] = resp.text or "(vazio)"
        if not resp.ok:
            err = result["body"]
            if isinstance(err, dict) and "error" in err:
                err_info = err["error"]
                result["error_code"] = err_info.get("code")
                result["error_message"] = err_info.get("message", "")
                code = result["error_code"]
                if code in RATE_LIMIT_ERROR_CODES:
                    result["summary"].append(
                        f"Rate limit ativo: código {code} — {RATE_LIMIT_LABELS.get(code, 'limite da API')}."
                    )
                else:
                    result["summary"].append(f"Erro da API: código {code}. {result['error_message']}")
            else:
                result["summary"].append(f"HTTP {resp.status_code}. Resposta: {result['body']}")
            return result
        result["ok"] = True
        result["summary"].append("Request OK — a API respondeu normalmente.")
        for hname, hval in result["usage_headers"].items():
            try:
                raw = str(hval).strip()
                parts = [p.strip() for p in raw.split(",")]
                pcts: List[Optional[int]] = []
                for part in parts:
                    p = part.replace("%", "").strip()
                    if p.isdigit():
                        pcts.append(int(p))
                    else:
                        pcts.append(None)
                if pcts:
                    max_pct = max((x for x in pcts if x is not None), default=None)
                    if max_pct is not None and max_pct >= 100:
                        result["summary"].append(f"{hname}: {raw} — no limite (100%).")
                    elif max_pct is not None:
                        result["summary"].append(f"{hname}: {raw}")
                else:
                    result["summary"].append(f"{hname}: {raw}")
            except Exception:
                result["summary"].append(f"{hname}: {hval}")
        return result
    except requests.RequestException as e:
        result["summary"].append(f"Falha de rede: {e}")
        return result
    except Exception as e:
        result["summary"].append(str(e))
        return result


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


def _verify_huggingface() -> Tuple[bool, str]:
    from instagram_poster.config import get_huggingface_token
    token = get_huggingface_token()
    if not token or not token.strip():
        return False, "Hugging Face: preenche HUGGINGFACE_TOKEN (huggingface.co/settings/tokens)."
    try:
        from huggingface_hub import InferenceClient
        client = InferenceClient(api_key=token.strip())
        image = client.text_to_image("a red circle", model="black-forest-labs/FLUX.1-schnell")
        if image is not None:
            return True, "Hugging Face: OK"
        return False, "Hugging Face: não devolveu imagem."
    except Exception as e:
        msg = str(e).strip() or e.__class__.__name__
        if "401" in msg or "unauthorized" in msg.lower() or "token" in msg.lower():
            return False, "Hugging Face: token inválido ou expirado."
        if "503" in msg or "loading" in msg.lower():
            return False, "Hugging Face: modelo temporariamente a carregar. Tenta novamente em instantes."
        return False, f"Hugging Face: {msg[:200]}"


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
    if provider == "huggingface":
        return _verify_huggingface()
    if provider == "firefly":
        from instagram_poster.config import get_firefly_client_id, get_firefly_client_secret
        if get_firefly_client_id() and get_firefly_client_secret():
            return True, "Firefly: credenciais definidas (testa ao gerar uma imagem)."
        return False, "Firefly: preenche FIREFLY_CLIENT_ID e FIREFLY_CLIENT_SECRET."
    return False, f"Provedor desconhecido: {provider}"


# Alias para compatibilidade
verify_gemini = verify_image_provider


def verify_cloudinary() -> Tuple[bool, str]:
    """Verifica se o Cloudinary está configurado e aceita upload (teste com 1x1 pixel)."""
    if get_media_backend() == "local_http":
        try:
            media_root = get_media_root()
            test_file = media_root / ".verify_write_test"
            test_file.write_bytes(b"ok")
            test_file.unlink()
            return True, "Media: backend local (MEDIA_ROOT gravavel)"
        except OSError as e:
            return False, f"Media local: MEDIA_ROOT nao gravavel: {e}"
    cloudinary_url = get_cloudinary_url()
    if cloudinary_url and cloudinary_url.strip().startswith("cloudinary://"):
        pass
    elif CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
        pass
    else:
        return False, "Cloudinary: define CLOUDINARY_URL no .env ou as variáveis separadas."
    try:
        import cloudinary
        import cloudinary.uploader
        if cloudinary_url and cloudinary_url.strip().startswith("cloudinary://"):
            cloudinary.config(cloudinary_url=cloudinary_url)
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


def verify_all_connections() -> List[Tuple[str, bool, str]]:
    """
    Executa todas as verificações de ligação e devolve lista de (nome, ok, mensagem).
    Ordem: Google Sheets, Instagram, Imagens, Media (Cloudinary ou local).
    """
    results: List[Tuple[str, bool, str]] = []
    results.append(("Google Sheets", *verify_google_sheets()))
    results.append(("Instagram", *verify_instagram()))
    results.append(("Imagens", *verify_image_provider()))
    results.append(("Media", *verify_cloudinary()))
    return results
