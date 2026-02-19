"""Provedor de imagens: Google Gemini (Nano Banana)."""
import io
import logging

from instagram_poster.config import GEMINI_IMAGE_MODEL, get_gemini_api_key

logger = logging.getLogger(__name__)


class GeminiProvider:
    def generate(self, prompt: str) -> bytes:
        api_key = get_gemini_api_key()
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY não definida. Obtém uma chave em https://aistudio.google.com/apikey"
            )
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise ImportError("Instala o pacote google-genai: pip install google-genai") from None

        client = genai.Client(api_key=api_key)
        try:
            config = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
            response = client.models.generate_content(
                model=GEMINI_IMAGE_MODEL,
                contents=[prompt],
                config=config,
            )
        except (TypeError, AttributeError):
            response = client.models.generate_content(
                model=GEMINI_IMAGE_MODEL,
                contents=[prompt],
            )

        parts = getattr(response, "parts", None) or (
            response.candidates[0].content.parts
            if response.candidates and response.candidates[0].content
            else []
        )
        if not parts:
            raise ValueError("A API Gemini não devolveu nenhuma imagem.")

        for part in parts:
            if getattr(part, "inline_data", None) and getattr(part.inline_data, "data", None):
                return bytes(part.inline_data.data)
            if hasattr(part, "as_image") and callable(part.as_image):
                try:
                    img = part.as_image()
                    if img is not None:
                        buf = io.BytesIO()
                        img.save(buf, format="PNG")
                        return buf.getvalue()
                except Exception:
                    pass

        raise ValueError("Resposta da Gemini sem dados de imagem.")
