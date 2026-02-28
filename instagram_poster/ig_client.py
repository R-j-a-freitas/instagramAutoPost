"""
Cliente para a Instagram Graph API oficial (via Instagram Login).
Publicação de imagens via endpoints /media e /media_publish.
Docs: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing/
"""
import logging
import time
from typing import Optional

import requests

from instagram_poster.config import IG_GRAPH_API_VERSION, get_ig_access_token, get_ig_business_id

logger = logging.getLogger(__name__)

BASE_URL = "https://graph.instagram.com"


def _url(path: str) -> str:
    return f"{BASE_URL}/{IG_GRAPH_API_VERSION}{path}"


def _check_config() -> None:
    if not get_ig_business_id():
        raise ValueError("Defina IG_BUSINESS_ID ou IG_BUSINESS_ACCOUNT_ID no .env")
    if not get_ig_access_token():
        raise ValueError("Defina IG_ACCESS_TOKEN no .env ou preenche na sidebar da app.")


def get_my_id() -> str:
    """
    Obtém o scoped user ID do utilizador autenticado (para comparação com from.id nas replies).
    GET /me?fields=id
    O from.id nas replies pode ser IGSID, diferente do Business Account ID.
    """
    _check_config()
    url = _url("/me")
    params = {"fields": "id", "access_token": get_ig_access_token()}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    user_id = data.get("id")
    if not user_id:
        raise ValueError("Resposta da API /me sem id")
    return str(user_id)


def create_media(image_url: str, caption: str) -> str:
    """
    Cria um content container para uma imagem (feed).
    POST /{ig-business-id}/media com image_url e caption.
    Devolve o creation_id (container ID) para usar em publish_media.
    """
    _check_config()
    ig_id = get_ig_business_id()
    url = _url(f"/{ig_id}/media")
    params = {
        "image_url": image_url,
        "caption": caption,
        "access_token": get_ig_access_token(),
    }
    logger.info("A criar media container para image_url=%s", image_url[:80] + "..." if len(image_url) > 80 else image_url)
    resp = requests.post(url, params=params, timeout=30)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        logger.error("create_media falhou: status=%s body=%s", resp.status_code, resp.text)
        raise
    data = resp.json()
    creation_id = data.get("id")
    if not creation_id:
        logger.error("Resposta sem 'id': %s", data)
        raise ValueError("Resposta da API sem container ID")
    return creation_id


def create_story(image_url: Optional[str] = None, video_url: Optional[str] = None) -> str:
    """
    Cria um content container para uma Story (imagem ou vídeo 9:16, ex.: 1080x1920).
    A API do Instagram aceita image_url (JPEG) ou video_url (MP4). A música só entra se estiver dentro do vídeo.
    POST com JSON body e Bearer token (evita problemas de encoding na query).
    """
    _check_config()
    if video_url and video_url.strip():
        media_url = video_url.strip()
        media_key = "video_url"
    elif image_url and image_url.strip():
        media_url = image_url.strip()
        media_key = "image_url"
    else:
        raise ValueError("É obrigatório indicar image_url ou video_url para criar uma Story.")
    ig_id = get_ig_business_id()
    url = _url(f"/{ig_id}/media")
    token = get_ig_access_token()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"media_type": "STORIES", media_key: media_url}
    logger.info("A criar Story container para %s=%s", media_key, media_url[:80] + "..." if len(media_url) > 80 else media_url)
    resp = requests.post(url, json=payload, headers=headers, timeout=60 if media_key == "video_url" else 30)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        body = (resp.text or "")[:500]
        logger.error("create_story falhou: status=%s body=%s", resp.status_code, body)
        try:
            err = resp.json().get("error", {})
            msg = (err.get("message") or "").lower()
            if "too many actions" in msg or err.get("code") == 9:
                raise ValueError(
                    "Limite de acções da API do Instagram excedido. "
                    "Publicaste demasiado em pouco tempo. Espera algumas horas antes de publicar Stories ou outros conteúdos."
                ) from e
            user_msg = err.get("error_user_msg") or err.get("message") or body
            raise ValueError(f"Instagram Story: {user_msg}") from e
        except ValueError:
            raise
        except Exception:
            raise ValueError(
                f"Instagram Story falhou (400). A imagem deve ser JPEG e estar num URL público. Resposta: {body}"
            ) from e
    data = resp.json()
    creation_id = data.get("id")
    if not creation_id:
        logger.error("Resposta sem 'id': %s", data)
        raise ValueError("Resposta da API sem container ID para Story")
    return creation_id


def create_reel(video_url: str, caption: str) -> str:
    """
    Cria um content container para um Reel (vídeo).
    POST /{ig-user-id}/media com media_type=REELS e video_url.
    Devolve o creation_id para usar em publish_media(creation_id, max_wait=180).
    """
    _check_config()
    ig_id = get_ig_business_id()
    url = _url(f"/{ig_id}/media")
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": get_ig_access_token(),
    }
    logger.info("A criar Reel container para video_url=%s", video_url[:80] + "..." if len(video_url) > 80 else video_url)
    resp = requests.post(url, params=params, timeout=30)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        logger.error("create_reel falhou: status=%s body=%s", resp.status_code, resp.text)
        raise
    data = resp.json()
    creation_id = data.get("id")
    if not creation_id:
        logger.error("Resposta sem 'id': %s", data)
        raise ValueError("Resposta da API sem container ID para Reel")
    return creation_id


def _wait_for_container(creation_id: str, max_wait: int = 120, interval: int = 3) -> str:
    """
    Polling do status do container até FINISHED.
    O Instagram processa o container de forma assíncrona — chamar
    media_publish antes de FINISHED resulta em erro 400.
    """
    elapsed = 0
    status = "UNKNOWN"
    while elapsed < max_wait:
        url = _url(f"/{creation_id}")
        params = {"fields": "status,status_code", "access_token": get_ig_access_token()}
        resp = requests.get(url, params=params, timeout=15)
        if not resp.ok:
            logger.warning("Erro ao verificar container %s: %s", creation_id, resp.text[:200])
            time.sleep(interval)
            elapsed += interval
            continue
        data = resp.json()
        status = data.get("status_code") or data.get("status", "")
        logger.info("Container %s: status=%s (elapsed=%ds)", creation_id, status, elapsed)
        if status == "FINISHED":
            return status
        if status == "ERROR":
            raise ValueError(f"Container falhou: {data}")
        time.sleep(interval)
        elapsed += interval
    logger.warning(
        "Container %s não ficou pronto em %ds (último status: %s)",
        creation_id,
        max_wait,
        status,
    )
    raise TimeoutError(
        f"Container {creation_id} não ficou pronto em {max_wait}s (último status: {status}). "
        "Para Reels pode ser necessário aumentar max_wait (ex.: 240s)."
    )


def publish_media(creation_id: str, max_wait: int = 120) -> str:
    """
    Publica o container criado por create_media ou create_reel.
    Espera até o container estar FINISHED antes de chamar media_publish.
    Default 120s para feed/Story; para Reels use max_wait=240 (processamento mais lento).
    """
    _check_config()
    ig_id = get_ig_business_id()

    _wait_for_container(creation_id, max_wait=max_wait)

    url = _url(f"/{ig_id}/media_publish")
    params = {
        "creation_id": creation_id,
        "access_token": get_ig_access_token(),
    }
    logger.info("A publicar media container %s", creation_id)
    resp = requests.post(url, params=params, timeout=30)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        body_preview = (resp.text or "")[:500]
        logger.error("publish_media falhou: status=%s body=%s", resp.status_code, body_preview)
        if resp.status_code == 400:
            try:
                err_data = resp.json()
                err = err_data.get("error", {}) or {}
                code = err.get("code")
                subcode = err.get("error_subcode")
                msg = (err.get("message") or "").lower()
                user_msg = err.get("error_user_msg") or err.get("error_user_title") or ""
                if code == 9 or subcode == 2207042 or "too many actions" in msg or "limite" in msg or "máximo" in msg:
                    raise ValueError(
                        "Limite de publicações da API do Instagram excedido. "
                        "Alcançaste o número máximo de publicações permitidas (por dia/hora). "
                        "Espera algumas horas ou até amanhã antes de publicar novamente."
                    ) from e
            except ValueError:
                raise
            except Exception:
                pass
            raise ValueError(
                f"Instagram API 400 Bad Request ao publicar contentor {creation_id}. "
                f"Resposta: {body_preview}. "
                "O contentor pode ainda não estar FINISHED (aumentar max_wait) ou ter expirado (criar novo)."
            ) from e
        raise
    data = resp.json()
    media_id = data.get("id")
    if not media_id:
        logger.error("Resposta sem 'id': %s", data)
        raise ValueError("Resposta da API sem media ID")
    return media_id


def get_media_ids(limit: int = 25) -> list[str]:
    """
    Obtém os IDs dos media (posts, reels) do utilizador.
    GET /{ig-user-id}/media
    Devolve lista de media IDs (máx. limit).
    """
    _check_config()
    ig_id = get_ig_business_id()
    url = _url(f"/{ig_id}/media")
    params = {"fields": "id", "access_token": get_ig_access_token(), "limit": min(limit, 50)}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    items = data.get("data") or []
    return [x["id"] for x in items if x.get("id")]


def get_comment_replies(comment_id: str) -> list[dict]:
    """
    Obtém as replies de um comentário específico (verificação final antes de responder).
    GET /{comment-id}?fields=replies{from}
    Usado para garantir que não respondemos duas vezes ao mesmo comentário.
    """
    _check_config()
    url = _url(f"/{comment_id}")
    params = {
        "fields": "replies.limit(100){id,from}",
        "access_token": get_ig_access_token(),
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    replies = data.get("replies") or {}
    return replies.get("data") or []


def get_comments(media_id: str) -> list[dict]:
    """
    Obtém os comentários de um media (apenas top-level).
    GET /{media-id}/comments?fields=id,text,username,timestamp,replies
    """
    _check_config()
    url = _url(f"/{media_id}/comments")
    params = {
        "fields": "id,text,username,timestamp,from,replies.limit(100){id,from}",
        "access_token": get_ig_access_token(),
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data") or []


def reply_to_comment(comment_id: str, message: str) -> str:
    """
    Responde a um comentário.
    POST /{comment-id}/replies?message=...
    Devolve o ID do comentário de resposta criado.
    Requer permissão instagram_business_manage_comments.
    """
    _check_config()
    url = _url(f"/{comment_id}/replies")
    params = {"message": message[:300], "access_token": get_ig_access_token()}
    resp = requests.post(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    reply_id = data.get("id")
    if not reply_id:
        raise ValueError("Resposta da API sem ID da reply")
    return reply_id
