"""
Cliente para a Instagram Graph API oficial.
Publicação de imagens via endpoints /media e /media_publish.
Documentação: https://developers.facebook.com/docs/instagram-api/guides/content-publishing/
"""
import logging
from typing import Optional

import requests

from instagram_poster.config import IG_GRAPH_API_VERSION, IG_ACCESS_TOKEN, get_ig_business_id

logger = logging.getLogger(__name__)

BASE_URL = "https://graph.facebook.com"


def _url(path: str) -> str:
    return f"{BASE_URL}/{IG_GRAPH_API_VERSION}{path}"


def _check_config() -> None:
    if not get_ig_business_id():
        raise ValueError("Defina IG_BUSINESS_ID ou IG_BUSINESS_ACCOUNT_ID no .env")
    if not IG_ACCESS_TOKEN:
        raise ValueError("Defina IG_ACCESS_TOKEN no .env")


def create_media(image_url: str, caption: str) -> str:
    """
    Cria um content container para uma imagem.
    POST /{ig-business-id}/media com image_url e caption.
    A imagem deve estar num servidor público (URL acessível pelo Instagram).
    Devolve o creation_id (container ID) para usar em publish_media.
    """
    _check_config()
    ig_id = get_ig_business_id()
    url = _url(f"/{ig_id}/media")
    params = {
        "image_url": image_url,
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN,
    }
    logger.info("A criar media container para image_url=%s", image_url[:80] + "..." if len(image_url) > 80 else image_url)
    resp = requests.post(url, params=params, timeout=30)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        logger.error("create_media falhou: status=%s body=%s", resp.status_code, resp.text)
        raise
    data = resp.json()
    creation_id = data.get("id")
    if not creation_id:
        logger.error("Resposta sem 'id': %s", data)
        raise ValueError("Resposta da API sem container ID")
    return creation_id


def publish_media(creation_id: str) -> str:
    """
    Publica o container criado por create_media.
    POST /{ig-business-id}/media_publish com creation_id.
    Devolve o id do post publicado (media ID).
    """
    _check_config()
    ig_id = get_ig_business_id()
    url = _url(f"/{ig_id}/media_publish")
    params = {
        "creation_id": creation_id,
        "access_token": IG_ACCESS_TOKEN,
    }
    logger.info("A publicar media container %s", creation_id)
    resp = requests.post(url, params=params, timeout=30)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        logger.error("publish_media falhou: status=%s body=%s", resp.status_code, resp.text)
        raise
    data = resp.json()
    media_id = data.get("id")
    if not media_id:
        logger.error("Resposta sem 'id': %s", data)
        raise ValueError("Resposta da API sem media ID")
    return media_id
