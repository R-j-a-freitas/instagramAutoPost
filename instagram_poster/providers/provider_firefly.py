"""Provedor de imagens: Adobe Firefly."""
import logging
import time
from typing import Optional

import requests

from instagram_poster.config import get_firefly_client_id, get_firefly_client_secret

logger = logging.getLogger(__name__)

_TOKEN_CACHE: Optional[dict] = None
_TOKEN_EXPIRES_AT: float = 0


def _get_access_token() -> str:
    """
    Obtém um access token do Adobe IMS usando client credentials.
    Cacheia o token até expirar (reutiliza se ainda válido).
    """
    global _TOKEN_CACHE, _TOKEN_EXPIRES_AT

    client_id = get_firefly_client_id()
    client_secret = get_firefly_client_secret()
    if not client_id or not client_secret:
        raise ValueError(
            "FIREFLY_CLIENT_ID e FIREFLY_CLIENT_SECRET não definidos. "
            "Obtém credenciais em https://developer.adobe.com/console"
        )

    # Reutilizar token se ainda válido (com margem de 60s)
    if _TOKEN_CACHE and time.time() < (_TOKEN_EXPIRES_AT - 60):
        return _TOKEN_CACHE["access_token"]

    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "openid,AdobeID,session,additional_info,read_organizations,firefly_api,ff_apis",
    }

    try:
        resp = requests.post(
            "https://ims-na1.adobelogin.com/ims/token/v3",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        token_data = resp.json()
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 3600)
        if not access_token:
            raise ValueError("Adobe IMS não devolveu access_token")
        _TOKEN_CACHE = token_data
        _TOKEN_EXPIRES_AT = time.time() + expires_in
        logger.info("Token Adobe Firefly obtido (expira em %ds)", expires_in)
        return access_token
    except requests.HTTPError as e:
        logger.error("Erro ao obter token Adobe: status=%s body=%s", e.response.status_code, e.response.text[:200])
        raise ValueError(f"Falha na autenticação Adobe Firefly: {e}") from e


class FireflyProvider:
    def generate(self, prompt: str) -> bytes:
        """
        Gera uma imagem usando Adobe Firefly API.
        Tamanho: 1024x1024 (square) para Instagram.
        """
        access_token = _get_access_token()
        client_id = get_firefly_client_id()

        # Tamanho 1024x1024 (square) para Instagram posts
        data = {
            "prompt": prompt,
            "size": {"width": 1024, "height": 1024},
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": client_id,
            "Authorization": f"Bearer {access_token}",
        }

        try:
            resp = requests.post(
                "https://firefly-api.adobe.io/v3/images/generate",
                json=data,
                headers=headers,
                timeout=60,
            )
            resp.raise_for_status()
            result = resp.json()
            # A resposta tem output[0].image.base64 ou output[0].image.url
            outputs = result.get("output", [])
            if not outputs:
                raise ValueError("Firefly não devolveu nenhuma imagem")
            image_data = outputs[0].get("image", {})
            # Preferir URL se disponível (mais eficiente)
            if image_data.get("url"):
                image_url = image_data["url"]
                logger.info("Firefly gerou imagem, a descarregar de %s...", image_url[:80])
                img_resp = requests.get(image_url, timeout=60)
                img_resp.raise_for_status()
                return img_resp.content
            # Fallback: base64
            if image_data.get("base64"):
                import base64
                return base64.b64decode(image_data["base64"])
            raise ValueError("Firefly devolveu resposta sem URL nem base64")
        except requests.HTTPError as e:
            error_text = e.response.text[:500] if e.response else str(e)
            logger.error("Erro na API Firefly: status=%s body=%s", e.response.status_code if e.response else "N/A", error_text)
            raise ValueError(f"Falha ao gerar imagem com Firefly: {error_text}") from e
