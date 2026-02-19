"""
Geração de imagens a partir de prompt (multi-provedor) e upload para Cloudinary.
O provedor activo é definido por IMAGE_PROVIDER no .env (gemini, openai, pollinations).
Após gerar a imagem, sobrepõe o texto da quote (Image Text) automaticamente.
"""
import io
import logging
import textwrap
from typing import Optional

from instagram_poster.config import (
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_URL,
    get_image_provider,
)
from instagram_poster.providers import get_provider

logger = logging.getLogger(__name__)


def generate_image_from_prompt(prompt: str) -> bytes:
    """
    Gera uma imagem usando o provedor activo (config IMAGE_PROVIDER).
    Devolve os bytes da imagem.
    """
    provider_name = get_image_provider()
    provider = get_provider(provider_name)
    logger.info("A gerar imagem com provedor '%s'...", provider_name)
    return provider.generate(prompt)


def overlay_quote_on_image(image_bytes: bytes, quote_text: str) -> bytes:
    """
    Sobrepõe o texto da quote centrado na imagem.
    Usa Pillow para renderizar tipografia legível com sombra.
    """
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h = img.size

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Tentar carregar fonte — fallback para default
    target_font_size = max(28, int(h * 0.05))
    font = None
    font_paths = [
        "C:/Windows/Fonts/georgia.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/times.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for fp in font_paths:
        try:
            font = ImageFont.truetype(fp, target_font_size)
            break
        except (OSError, IOError):
            continue
    if font is None:
        font = ImageFont.load_default()
        target_font_size = 20

    # Quebrar texto em linhas que caibam (~80% da largura)
    max_text_width = int(w * 0.80)
    chars_per_line = max(15, int(max_text_width / (target_font_size * 0.55)))
    lines = textwrap.wrap(quote_text.strip(), width=chars_per_line)
    if not lines:
        return image_bytes

    # Calcular dimensões do bloco de texto
    line_spacing = int(target_font_size * 0.4)
    line_heights = []
    line_widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    total_text_height = sum(line_heights) + line_spacing * (len(lines) - 1)
    max_line_width = max(line_widths)

    # Fundo semi-transparente atrás do texto
    padding_x = int(w * 0.06)
    padding_y = int(h * 0.04)
    box_w = max_line_width + padding_x * 2
    box_h = total_text_height + padding_y * 2
    box_x = (w - box_w) // 2
    box_y = (h - box_h) // 2

    draw.rounded_rectangle(
        [box_x, box_y, box_x + box_w, box_y + box_h],
        radius=int(min(w, h) * 0.02),
        fill=(0, 0, 0, 120),
    )

    # Desenhar texto linha a linha, centrado
    y_cursor = box_y + padding_y
    for i, line in enumerate(lines):
        lw = line_widths[i]
        x = (w - lw) // 2

        # Sombra
        draw.text((x + 2, y_cursor + 2), line, font=font, fill=(0, 0, 0, 180))
        # Texto principal
        draw.text((x, y_cursor), line, font=font, fill=(255, 255, 255, 245))

        y_cursor += line_heights[i] + line_spacing

    result = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG", quality=95)
    return buf.getvalue()


def upload_image_to_cloudinary(image_bytes: bytes, public_id_prefix: str = "ig_post") -> str:
    """
    Faz upload dos bytes da imagem para Cloudinary e devolve o URL público.
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
            "Configura o Cloudinary no .env: "
            "CLOUDINARY_URL (formato: cloudinary://API_KEY:API_SECRET@CLOUD_NAME) "
            "ou CLOUDINARY_CLOUD_NAME + CLOUDINARY_API_KEY + CLOUDINARY_API_SECRET. "
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


_QUOTE_CARD_PROMPT = (
    "Create a beautiful square image for Instagram (1080x1080). "
    "Theme inspired by: \"{text}\". "
    "Style: calm, minimalist, positive atmosphere. Soft colors, gradient or nature background. "
    "Do NOT include any text, letters, words, or watermarks in the image. "
    "The image should be a clean visual background suitable for overlaying a quote."
)


def get_image_url_from_prompt(
    prompt: str,
    quote_text: Optional[str] = None,
    use_full_prompt: bool = True,
    public_id_prefix: str = "ig_post",
) -> str:
    """
    Gera uma imagem com o provedor activo, sobrepõe a quote, e devolve URL público (Cloudinary).

    - prompt: Gemini_Prompt (descritivo da cena) ou Image Text como fallback
    - quote_text: texto da quote a sobrepor na imagem (Image Text)
    - use_full_prompt=True: usa prompt directamente (coluna Gemini_Prompt)
    - use_full_prompt=False: envolve no template de fundo para quote card
    """
    if not (prompt or "").strip():
        raise ValueError("O prompt está vazio; não é possível gerar a imagem.")
    text = prompt.strip()
    final_prompt = text if use_full_prompt else _QUOTE_CARD_PROMPT.format(text=text)
    image_bytes = generate_image_from_prompt(final_prompt)

    if quote_text and quote_text.strip():
        logger.info("A sobrepor quote na imagem: '%s'", quote_text[:60])
        image_bytes = overlay_quote_on_image(image_bytes, quote_text)

    return upload_image_to_cloudinary(image_bytes, public_id_prefix=public_id_prefix)
