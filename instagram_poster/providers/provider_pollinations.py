"""Provedor de imagens: Pollinations.ai (gen.pollinations.ai)."""
import logging
from urllib.parse import quote

import requests

from instagram_poster.config import get_pollinations_api_key

logger = logging.getLogger(__name__)

_BASE_URL = "https://gen.pollinations.ai/image/{prompt}"
_DEFAULT_PARAMS = {
    "width": "1080",
    "height": "1080",
    "model": "flux",
    "nologo": "true",
    "enhance": "false",
}


class PollinationsProvider:
    def generate(self, prompt: str) -> bytes:
        api_key = get_pollinations_api_key()

        encoded_prompt = quote(prompt, safe="")
        url = _BASE_URL.format(prompt=encoded_prompt)
        params = _DEFAULT_PARAMS.copy()

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        logger.info("Pollinations: a gerar imagem (modelo flux)...")
        resp = requests.get(url, params=params, headers=headers, timeout=90)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type and len(resp.content) < 1000:
            raise ValueError(
                f"Pollinations não devolveu uma imagem (content-type: {content_type})"
            )

        logger.info("Pollinations: imagem gerada (%d bytes)", len(resp.content))
        return resp.content
