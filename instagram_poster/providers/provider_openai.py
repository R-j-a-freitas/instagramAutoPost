"""Provedor de imagens: OpenAI DALL-E 3."""
import logging

import requests as http_requests

from instagram_poster.config import get_openai_api_key

logger = logging.getLogger(__name__)


class OpenAIProvider:
    def generate(self, prompt: str) -> bytes:
        api_key = get_openai_api_key()
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY não definida. Obtém uma chave em https://platform.openai.com/api-keys"
            )
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("Instala o pacote openai: pip install openai") from None

        client = OpenAI(api_key=api_key)
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024",
            response_format="url",
        )
        image_url = response.data[0].url
        if not image_url:
            raise ValueError("DALL-E 3 não devolveu URL de imagem.")

        logger.info("DALL-E 3 gerou imagem, a descarregar...")
        resp = http_requests.get(image_url, timeout=60)
        resp.raise_for_status()
        return resp.content
