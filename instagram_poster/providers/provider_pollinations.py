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

    def generate_video(self, prompt: str, model: str = "grok-video", aspect_ratio: str = "9:16", duration: int = 4) -> bytes:
        """
        Gera um vídeo a partir de um prompt (MP4).
        Modelos sugeridos: 'grok-video' (grátis/integrado via airforce), 'seedance', 'veo' (pago), 'wan' (pago).
        """
        api_key = get_pollinations_api_key()
        if not api_key:
            raise ValueError("Pollinations: API Key necessária para gerar vídeo.")

        # Truncar prompt para evitar erro 400 por URL demasiado longa (limite seguro ~1000 chars)
        MAX_PROMPT_LEN = 1000
        if len(prompt) > MAX_PROMPT_LEN:
            prompt = prompt[:MAX_PROMPT_LEN].rsplit(" ", 1)[0]
            logger.info("Pollinations: prompt truncado para %d caracteres", len(prompt))

        encoded_prompt = quote(prompt, safe="")
        url = f"https://gen.pollinations.ai/video/{encoded_prompt}"
        
        # Parâmetros baseados na documentação e pesquisa:
        # grok-video (api.airforce) é a melhor aposta para uso grátis/estável.
        params = {
            "model": model,
            "nologo": "true",
            "aspectRatio": aspect_ratio,
            "duration": str(duration),
            "audio": "false"  # Desactivar áudio para acelerar/evitar falhas
        }
        
        headers = {"Authorization": f"Bearer {api_key}"}

        logger.info("Pollinations: a gerar vídeo (modelo %s, %s)...", model, aspect_ratio)
        resp = requests.get(url, params=params, headers=headers, timeout=300)
        
        if not resp.ok:
            try:
                error_data = resp.json()
                msg = error_data.get("error", {}).get("message", resp.text)
            except Exception:
                msg = resp.text
            # Se der 400, pode ser o modelo. Logar URL (sem key) para debug.
            logger.error("Pollinations video error %d: %s. URL base: %s", resp.status_code, msg, url)
            raise ValueError(f"Pollinations Video Error {resp.status_code}: {msg}")

        content_type = resp.headers.get("content-type", "")
        if "video" not in content_type and len(resp.content) < 1000:
            raise ValueError(
                f"Pollinations não devolveu um vídeo (content-type: {content_type}, bytes: {len(resp.content)})"
            )

        logger.info("Pollinations: vídeo gerado (%d bytes)", len(resp.content))
        return resp.content
