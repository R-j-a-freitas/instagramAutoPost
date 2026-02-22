"""Provedor de imagens: Hugging Face Inference (FLUX, free tier) via SDK."""
import io
import logging

from instagram_poster.config import get_huggingface_token

logger = logging.getLogger(__name__)

_MODEL = "black-forest-labs/FLUX.1-schnell"


class HuggingFaceProvider:
    def generate(self, prompt: str) -> bytes:
        token = get_huggingface_token()
        if not token or not token.strip():
            raise ValueError(
                "HUGGINGFACE_TOKEN não definido. Obtém um token em https://huggingface.co/settings/tokens"
            )

        try:
            from huggingface_hub import InferenceClient
        except ImportError:
            raise ImportError("Instala o pacote huggingface_hub: pip install huggingface_hub") from None

        client = InferenceClient(api_key=token.strip())
        logger.info("Hugging Face: a gerar imagem (FLUX.1-schnell)...")

        try:
            image = client.text_to_image(
                prompt,
                model=_MODEL,
            )
        except Exception as e:
            err_msg = str(e).strip() or e.__class__.__name__
            if "404" in err_msg or "not found" in err_msg.lower():
                raise ValueError(
                    "Hugging Face: modelo ou endpoint não encontrado. Verifica que o token tem permissão 'Inference' e que o modelo está disponível."
                ) from e
            if "503" in err_msg or "loading" in err_msg.lower():
                raise ValueError("Hugging Face: modelo temporariamente a carregar. Tenta novamente em instantes.") from e
            raise ValueError(f"Hugging Face: {err_msg}") from e

        if image is None:
            raise ValueError("Hugging Face não devolveu imagem.")

        if isinstance(image, bytes):
            return image
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        out = buf.getvalue()
        logger.info("Hugging Face: imagem gerada (%d bytes)", len(out))
        return out
