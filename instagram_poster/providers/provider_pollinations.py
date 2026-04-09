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
        import time
        api_key = get_pollinations_api_key()

        encoded_prompt = quote(prompt, safe="")
        url = _BASE_URL.format(prompt=encoded_prompt)
        params = _DEFAULT_PARAMS.copy()

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info("Pollinations: a gerar imagem (modelo flux)... (tentativa %d/%d)", attempt + 1, max_retries)
                resp = requests.get(url, params=params, headers=headers, timeout=90)
                resp.raise_for_status()

                content_type = resp.headers.get("content-type", "")
                if "image" not in content_type and len(resp.content) < 1000:
                    raise ValueError(f"Pollinations não devolveu uma imagem (content-type: {content_type})")

                logger.info("Pollinations: imagem gerada (%d bytes)", len(resp.content))
                return resp.content

            except requests.exceptions.RequestException as e:
                status_code = getattr(e.response, "status_code", 500) if e is not None and hasattr(e, "response") else 500
                if attempt == max_retries - 1 or (400 <= status_code < 500 and status_code not in (429,)):
                    logger.error("Pollinations: falhou após %d tentativas (status %s): %s", max_retries, status_code, e)
                    raise
                logger.warning("Falha no Pollinations (status %s). A aguardar 5s...", status_code)
                time.sleep(5)
        
        raise RuntimeError("Falha inesperada no retry loop do Pollinations.")

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

        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info("Pollinations: a gerar vídeo (modelo %s, %s)... (tentativa %d/%d)", model, aspect_ratio, attempt + 1, max_retries)
                resp = requests.get(url, params=params, headers=headers, timeout=300)
                
                if not resp.ok:
                    try:
                        error_data = resp.json()
                        msg = error_data.get("error", {}).get("message", resp.text)
                    except Exception:
                        msg = resp.text
                    
                    status_code = resp.status_code
                    if attempt == max_retries - 1 or (400 <= status_code < 500 and status_code not in (429,)):
                        logger.error("Pollinations video error %d: %s. URL base: %s", status_code, msg, url)
                        raise ValueError(f"Pollinations Video Error {status_code}: {msg}")
                    
                    logger.warning("Falha no Pollinations Video (status %s). A aguardar 10s...", status_code)
                    import time
                    time.sleep(10)
                    continue
                
                break # Success
            except requests.exceptions.RequestException as e:
                status_code = getattr(e.response, "status_code", 500) if e is not None and hasattr(e, "response") else 500
                if attempt == max_retries - 1 or (400 <= status_code < 500 and status_code not in (429,)):
                    logger.error("Pollinations video request exception: %s", e)
                    raise
                logger.warning("Excepção no Pollinations Video (status %s). Aguardar 10s...", status_code)
                import time
                time.sleep(10)

        content_type = resp.headers.get("content-type", "")
        if "video" not in content_type and len(resp.content) < 1000:
            raise ValueError(
                f"Pollinations não devolveu um vídeo (content-type: {content_type}, bytes: {len(resp.content)})"
            )

        logger.info("Pollinations: vídeo gerado (%d bytes)", len(resp.content))
        return resp.content
