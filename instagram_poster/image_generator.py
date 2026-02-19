"""
Geração de imagens a partir de prompt (multi-provedor) e upload para Cloudinary.
O provedor activo é definido por IMAGE_PROVIDER no .env (gemini, openai, pollinations).
Após gerar a imagem, sobrepõe o texto da quote (Image Text) automaticamente.

Para evitar que o modelo de imagem (FLUX) renderize texto na imagem, o texto da
quote nunca é incluído no prompt enviado ao AI. Em vez disso, a quote é convertida
numa descrição visual via LLM e o texto é sobreposto depois via Pillow.
"""
import io
import logging
import re
import textwrap
from typing import Optional

import requests

from instagram_poster.config import (
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_URL,
    get_image_provider,
    get_pollinations_api_key,
)
from instagram_poster.providers import get_provider

logger = logging.getLogger(__name__)

_SCENE_SYSTEM_PROMPT = (
    "You are a visual scene describer for image generation. "
    "Given a quote or phrase, describe a concrete image scene that matches its mood and theme. "
    "Include: setting/environment, color palette, mood/emotion, and visual elements. "
    "CRITICAL RULES:\n"
    "- NEVER include any text, letters, typography, or words in the description.\n"
    "- NEVER repeat or paraphrase the quote itself.\n"
    "- Only describe visual elements (scenery, objects, lighting, colors).\n"
    "- Keep the output under 80 words.\n"
    "- Output ONLY the image generation prompt, nothing else."
)

_GENERIC_FALLBACK_PROMPT = (
    "Beautiful square 1080x1080 image. Calm minimalist composition, "
    "soft gradient colors blending from warm peach to cool lavender, "
    "peaceful atmosphere with gentle light. Nature-inspired abstract background. "
    "No text, no letters, no words, no watermarks."
)

_TEXT_RENDER_PATTERNS = [
    re.compile(r"(?i)(?:the\s+image\s+must\s+)?display\s+this\s+text\s+clearly[^.;]*[.;]?"),
    re.compile(r"(?i)must\s+display\s+this\s+text[^.;]*[.;]?"),
    re.compile(r"(?i)like\s+a\s+motivational[^.;]*quote\s+card[^.;]*[.;]?"),
    re.compile(r"(?i)only\s+the\s+given\s+text\s+must\s+appear[^.;]*[.;]?"),
    re.compile(r"(?i)readable\s+typography[^.;]*[.;]?"),
    re.compile(r"(?i)as\s+the\s+main\s+content[^.;]*[.;]?"),
    re.compile(r"(?i)do\s+not\s+add\s+extra\s+sentences[^.;]*[.;]?"),
]


def _quote_to_scene_prompt(quote_text: str) -> str:
    """Converte uma quote numa descrição puramente visual via Pollinations text API."""
    api_key = get_pollinations_api_key()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": "openai",
        "messages": [
            {"role": "system", "content": _SCENE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Convert this quote into a visual scene prompt for image generation "
                    f"(remember: describe ONLY visual elements, NO text in the image):\n"
                    f'"{quote_text}"'
                ),
            },
        ],
    }

    try:
        resp = requests.post(
            "https://gen.pollinations.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        scene = resp.json()["choices"][0]["message"]["content"].strip()
        if len(scene) < 15:
            raise ValueError("Resposta LLM demasiado curta")
        no_text_suffix = " No text, no letters, no words in the image."
        if "no text" not in scene.lower():
            scene += no_text_suffix
        logger.info("Quote convertida em cena visual: %s", scene[:120])
        return scene
    except Exception as exc:
        logger.warning("Falha ao converter quote via LLM (%s); a usar fallback genérico.", exc)
        return _GENERIC_FALLBACK_PROMPT


def _sanitize_prompt(prompt: str, quote_text: str) -> str:
    """Remove texto literal da quote e instruções de renderização de texto do prompt."""
    clean = prompt

    if quote_text and quote_text.strip():
        qt = quote_text.strip()
        for variant in [f'"{qt}"', f"'{qt}'", qt]:
            clean = clean.replace(variant, "")

    for pattern in _TEXT_RENDER_PATTERNS:
        clean = pattern.sub("", clean)

    clean = re.sub(r'Theme\s+inspired\s+by:\s*["\']*\s*["\']*\s*\.?', "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s{2,}", " ", clean).strip()

    no_text_instr = "Do NOT include any text, letters, words, or watermarks in the image."
    if "do not include any text" not in clean.lower():
        clean = clean.rstrip(".") + ". " + no_text_instr

    return clean


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
    "Beautiful square 1080x1080 image. Calm minimalist composition, "
    "soft gradient colors, peaceful atmosphere with gentle light. "
    "Nature-inspired abstract background. "
    "Do NOT include any text, letters, words, or watermarks in the image."
)


def _has_embedded_quote(prompt: str, quote_text: str) -> bool:
    """Verifica se o prompt contém o texto literal da quote (ou parte substancial)."""
    if not quote_text or not quote_text.strip():
        return False
    qt = quote_text.strip().lower()
    pl = prompt.lower()
    if qt in pl:
        return True
    words = qt.split()
    if len(words) >= 5:
        half = len(words) // 2
        chunk = " ".join(words[:half])
        if chunk in pl:
            return True
    return False


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

    has_overlay = bool(quote_text and quote_text.strip())

    if has_overlay:
        if use_full_prompt:
            candidate = prompt.strip()
            if _has_embedded_quote(candidate, quote_text):
                sanitized = _sanitize_prompt(candidate, quote_text)
                if len(sanitized.split()) < 8:
                    logger.info("Prompt sanitizado ficou curto; a converter quote via LLM.")
                    final_prompt = _quote_to_scene_prompt(quote_text)
                else:
                    final_prompt = sanitized
            else:
                final_prompt = candidate
                no_text = "Do NOT include any text, letters, words, or watermarks in the image."
                if "do not include any text" not in final_prompt.lower():
                    final_prompt = final_prompt.rstrip(".") + ". " + no_text
        else:
            logger.info("Sem Gemini_Prompt; a converter quote via LLM.")
            final_prompt = _quote_to_scene_prompt(quote_text)
    else:
        text = prompt.strip()
        final_prompt = text if use_full_prompt else _QUOTE_CARD_PROMPT

    logger.info("Prompt final para imagem: %s", final_prompt[:150])
    image_bytes = generate_image_from_prompt(final_prompt)

    if has_overlay:
        logger.info("A sobrepor quote na imagem: '%s'", quote_text[:60])
        image_bytes = overlay_quote_on_image(image_bytes, quote_text)

    return upload_image_to_cloudinary(image_bytes, public_id_prefix=public_id_prefix)
