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


def create_media(image_url: str, caption: str) -> str:
    """
    Cria um content container para uma imagem.
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


def _wait_for_container(creation_id: str, max_wait: int = 60, interval: int = 3) -> str:
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
    raise TimeoutError(
        f"Container {creation_id} não ficou pronto em {max_wait}s (último status: {status})"
    )


def publish_media(creation_id: str) -> str:
    """
    Publica o container criado por create_media.
    Espera até o container estar FINISHED antes de chamar media_publish.
    """
    _check_config()
    ig_id = get_ig_business_id()

    _wait_for_container(creation_id)

    url = _url(f"/{ig_id}/media_publish")
    params = {
        "creation_id": creation_id,
        "access_token": get_ig_access_token(),
    }
    logger.info("A publicar media container %s", creation_id)
    resp = requests.post(url, params=params, timeout=30)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        logger.error("publish_media falhou: status=%s body=%s", resp.status_code, resp.text)
        raise
    data = resp.json()
    media_id = data.get("id")
    if not media_id:
        logger.error("Resposta sem 'id': %s", data)
        raise ValueError("Resposta da API sem media ID")
    return media_id
