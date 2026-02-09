"""
Geração de imagens com Gemini (Nano Banana) a partir do texto do Sheet (Image Text).
As imagens são geradas em memória; para publicar no Instagram é necessário um URL público,
por isso fazemos upload para Cloudinary quando CLOUDINARY_URL está definido.
"""
import io
import logging
from typing import Optional

from instagram_poster.config import (
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_URL,
    GEMINI_API_KEY,
    GEMINI_IMAGE_MODEL,
)

logger = logging.getLogger(__name__)


def generate_image_from_prompt(prompt: str) -> bytes:
    """
    Gera uma imagem com o modelo Gemini Nano Banana (gemini-2.5-flash-image)
    a partir do texto (ex.: coluna Image Text do Sheet).
    Devolve os bytes da imagem (PNG).
    """
    if not GEMINI_API_KEY:
        raise ValueError(
            "Defina GEMINI_API_KEY no .env. Obtém uma chave em https://aistudio.google.com/apikey"
        )
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise ImportError(
            "Instala o pacote google-genai: pip install google-genai"
        ) from None

    client = genai.Client(api_key=GEMINI_API_KEY)
    # Pedir resposta com texto e imagem (Nano Banana devolve imagem com este modelo)
    try:
        config = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
        response = client.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=[prompt],
            config=config,
        )
    except (TypeError, AttributeError):
        # Fallback sem config se o SDK não suportar response_modalities
        response = client.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=[prompt],
        )
    # Aceder a parts: SDK pode expor response.parts ou response.candidates[0].content.parts
    parts = getattr(response, "parts", None) or (
        response.candidates[0].content.parts if response.candidates and response.candidates[0].content else []
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


def upload_image_to_cloudinary(image_bytes: bytes, public_id_prefix: str = "ig_post") -> str:
    """
    Faz upload dos bytes da imagem para Cloudinary e devolve o URL público.
    Configuração: usa CLOUDINARY_URL ou, em alternativa, as variáveis
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY e CLOUDINARY_API_SECRET.
    """
    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError:
        raise ImportError("Instala o pacote cloudinary: pip install cloudinary") from None

    if CLOUDINARY_URL and CLOUDINARY_URL.strip().startswith("cloudinary://"):
        cloudinary.config(cloudinary_url=CLOUDINARY_URL)
    elif CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET,
            secure=True,
        )
    else:
        raise ValueError(
            "Para publicar imagens geradas pela Gemini, configura o Cloudinary no .env: "
            "ou CLOUDINARY_URL (formato: cloudinary://API_KEY:API_SECRET@CLOUD_NAME) "
            "ou as variáveis CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY e CLOUDINARY_API_SECRET. "
            "Ou preenche a coluna ImageURL no Sheet com um link manual."
        )

    import time
    public_id = f"{public_id_prefix}_{int(time.time())}"
    result = cloudinary.uploader.upload(
        io.BytesIO(image_bytes),
        public_id=public_id,
        overwrite=True,
    )
    url = result.get("secure_url") or result.get("url")
    if not url:
        raise ValueError("Cloudinary não devolveu URL da imagem.")
    logger.info("Imagem carregada no Cloudinary: %s", url)
    return url


# Prompt base para quote cards (mindset, self-love, healing) em inglês
_QUOTE_CARD_PROMPT = (
    "Create a single square or 4:5 vertical image for Instagram. "
    "The image must display this text clearly and prominently as the main content, "
    "like a motivational or affirmation quote card: \"{text}\". "
    "Use a clean, modern design with readable typography. "
    "Style: minimalist, positive, soft colors or gradient background. "
    "Do not add extra sentences, only the given text must appear."
)


def get_image_url_from_sheet_description(image_text: str, public_id_prefix: str = "ig_post") -> str:
    """
    Gera uma imagem a partir de image_text (Gemini Nano Banana) e devolve um URL público
    (via upload para Cloudinary). Usado quando a linha do Sheet não tem ImageURL preenchido.
    O prompt orienta o modelo a criar um quote card com o texto bem visível.
    """
    if not (image_text or "").strip():
        raise ValueError("Image Text está vazio; não é possível gerar a imagem.")
    prompt = _QUOTE_CARD_PROMPT.format(text=image_text.strip())
    image_bytes = generate_image_from_prompt(prompt)
    return upload_image_to_cloudinary(image_bytes, public_id_prefix=public_id_prefix)
