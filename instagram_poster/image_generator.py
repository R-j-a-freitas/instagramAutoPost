"""
Geração de imagens a partir de prompt (multi-provedor) e upload para Cloudinary.
O provedor activo é definido por IMAGE_PROVIDER no .env (gemini, openai, pollinations, firefly).
Após gerar a imagem, sobrepõe o texto da quote (Image Text) automaticamente.

Para evitar que o modelo de imagem (FLUX) renderize texto na imagem, o texto da
quote nunca é incluído no prompt enviado ao AI. Em vez disso, a quote é convertida
numa descrição visual via LLM e o texto é sobreposto depois via Pillow.
"""
import io
import logging
import re
import tempfile
import textwrap
import time
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
import requests

from instagram_poster.config import (
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
    CLOUDINARY_CLOUD_NAME,
    get_cloudinary_url,
    get_image_provider,
    get_media_backend,
    get_media_base_url,
    get_media_root,
)
from instagram_poster.providers import get_provider
from instagram_poster.text_generator import generate_text

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


def _normalize_to_feed_size(image_bytes: bytes) -> bytes:
    """
    Garante que a imagem tem exatamente 1080x1080px (resolução ideal para o feed do Instagram).
    Se a imagem for mais pequena ou não quadrada, é redimensionada mantendo as proporções
    e centrada sobre um fundo desfocado da própria imagem (mesmo estilo das Stories).
    """
    from PIL import Image, ImageFilter

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    target = 1080

    # Se já estiver no tamanho certo, não faz nada (mas normaliza sempre para JPEG:
    # a API do Instagram só aceita JPEG para imagens; PNG causa 400 Bad Request)
    if w == target and h == target:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        return buf.getvalue()

    # Fundo: imagem esticada para 1080x1080 e desfocada
    bg = img.resize((target, target), Image.Resampling.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=20))

    # Imagem central: caber dentro de 1080x1080 mantendo proporção
    scale = min(target / w, target / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    center_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    x = (target - new_w) // 2
    y = (target - new_h) // 2
    bg.paste(center_img, (x, y))

    buf = io.BytesIO()
    bg.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _load_text_font(size: int):
    """Tenta carregar uma fonte truetype legível; devolve (font, tamanho_efectivo)."""
    from PIL import ImageFont

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
            return ImageFont.truetype(fp, size), size
        except (OSError, IOError):
            continue
    return ImageFont.load_default(), 20


def overlay_quote_on_image(image_bytes: bytes, quote_text: str) -> bytes:
    """
    Normaliza a imagem para 1080x1080 (feed Instagram) e sobrepõe o texto da quote centrado.
    Usa Pillow para renderizar tipografia legível com sombra.
    """
    from PIL import Image, ImageDraw

    # Normalizar para 1080x1080 antes de qualquer sobreposição
    image_bytes = _normalize_to_feed_size(image_bytes)

    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h = img.size

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font, target_font_size = _load_text_font(max(28, int(h * 0.05)))

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
    result.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def render_explanation_card(image_bytes: bytes, explanation_text: str) -> bytes:
    """
    Cria o 2º slide de um carrossel: a mesma imagem-base do slide 1, mas com um fundo
    mais desfocado/escurecido (para dar contraste a um parágrafo mais longo) e o texto
    de explicação do dia (Slide2 Text) sobreposto, centrado verticalmente.
    """
    from PIL import Image, ImageDraw, ImageFilter

    image_bytes = _normalize_to_feed_size(image_bytes)
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size

    bg = img.filter(ImageFilter.GaussianBlur(radius=35)).convert("RGBA")
    dark = Image.new("RGBA", (w, h), (0, 0, 0, 110))
    bg = Image.alpha_composite(bg, dark)
    draw = ImageDraw.Draw(bg)

    font, target_font_size = _load_text_font(max(24, int(h * 0.034)))

    max_text_width = int(w * 0.78)
    chars_per_line = max(18, int(max_text_width / (target_font_size * 0.55)))
    lines = textwrap.wrap(explanation_text.strip(), width=chars_per_line)
    if not lines:
        buf = io.BytesIO()
        bg.convert("RGB").save(buf, format="JPEG", quality=95)
        return buf.getvalue()

    line_spacing = int(target_font_size * 0.55)
    line_heights = []
    line_widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    total_text_height = sum(line_heights) + line_spacing * (len(lines) - 1)
    y_cursor = (h - total_text_height) // 2

    for i, line in enumerate(lines):
        lw = line_widths[i]
        x = (w - lw) // 2
        draw.text((x + 2, y_cursor + 2), line, font=font, fill=(0, 0, 0, 160))
        draw.text((x, y_cursor), line, font=font, fill=(255, 255, 255, 245))
        y_cursor += line_heights[i] + line_spacing

    buf = io.BytesIO()
    bg.convert("RGB").save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def upload_image_bytes(image_bytes: bytes, public_id_prefix: str = "ig_post") -> str:
    """
    Decide o backend com base em get_media_backend():
    - cloudinary: upload para Cloudinary (comportamento actual)
    - local_http: grava em MEDIA_ROOT e devolve MEDIA_BASE_URL/<filename>
    """
    if get_media_backend() == "local_http":
        return _upload_image_to_local(image_bytes, public_id_prefix)
    return _upload_image_to_cloudinary(image_bytes, public_id_prefix)


def _upload_image_to_local(image_bytes: bytes, public_id_prefix: str) -> str:
    """Grava imagem em MEDIA_ROOT e devolve URL público."""
    # Tudo o que passa por aqui já foi normalizado para JPEG (a API do Instagram
    # só aceita JPEG para imagens; PNG causa 400 Bad Request).
    filename = f"{public_id_prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}.jpg"
    try:
        path = get_media_root() / filename
        path.write_bytes(image_bytes)
    except OSError as e:
        raise ValueError(
            f"MEDIA_ROOT não gravável: {get_media_root()}. Verifica permissões. Erro: {e}"
        ) from e
    url = f"{get_media_base_url()}/{filename}"
    logger.info("Imagem gravada localmente: %s", url)
    return url


def _upload_image_to_cloudinary(image_bytes: bytes, public_id_prefix: str = "ig_post") -> str:
    """
    Faz upload dos bytes da imagem para Cloudinary e devolve o URL público.
    """
    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError:
        raise ImportError("Instala o pacote cloudinary: pip install cloudinary") from None

    cloudinary_url = get_cloudinary_url()
    if cloudinary_url and cloudinary_url.strip().startswith("cloudinary://"):
        cloudinary.config(cloudinary_url=cloudinary_url)
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


def _download_image(url: str) -> bytes:
    """Descarrega uma imagem a partir de um URL público."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content


def _image_to_story_frame(image_bytes: bytes) -> bytes:
    """
    Converte uma imagem quadrada (ex.: 1080x1080) num frame vertical 1080x1920
    para Instagram Story: fundo desfocado da própria imagem e imagem centrada.
    A API do Instagram só aceita JPEG para imagens; PNG causa 400 Bad Request.
    """
    from PIL import Image, ImageFilter

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    if w < 100 or h < 100:
        raise ValueError("Imagem demasiado pequena para converter em Story")
    sw, sh = 1080, 1920
    # Fundo: imagem esticada para 1080x1920 e desfocada
    bg = img.resize((sw, sh), Image.Resampling.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=25))
    # Imagem central: largura total 1080px (enche o ecrã da story de lado a lado)
    target_w = 1080
    target_h = int(h * (target_w / w))
    center_img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    x = (sw - target_w) // 2
    y = (sh - target_h) // 2
    bg.paste(center_img, (x, y))
    buf = io.BytesIO()
    bg.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def get_story_image_url_from_feed_image(feed_image_url: str) -> str:
    """
    A partir do URL da imagem do post (feed), gera uma imagem 1080x1920 para
    Story (fundo desfocado + imagem centrada) e faz upload para Cloudinary.
    Devolve o URL público para usar em create_story.
    """
    if not (feed_image_url or "").strip():
        raise ValueError("URL da imagem do post está vazio.")
    logger.info("A gerar imagem Story a partir do post: %s", feed_image_url[:80])
    image_bytes = _download_image(feed_image_url.strip())
    # Normalizar para 1080x1080 antes de converter em frame de Story
    image_bytes = _normalize_to_feed_size(image_bytes)
    story_bytes = _image_to_story_frame(image_bytes)
    return upload_image_bytes(story_bytes, public_id_prefix="ig_story")


def _image_to_vertical_frame_np(image_bytes: bytes) -> np.ndarray:
    """
    Converte imagem em frame vertical 1080x1920 (array RGB para MoviePy).
    Reutiliza a lógica de _image_to_story_frame mas devolve numpy array.
    """
    from PIL import Image, ImageFilter

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    if w < 100 or h < 100:
        raise ValueError("Imagem demasiado pequena para Story")
    sw, sh = 1080, 1920
    bg = img.resize((sw, sh), Image.Resampling.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=25))
    # Imagem central: largura total 1080px (enche o ecrã de lado a lado)
    target_w = 1080
    target_h = int(h * (target_w / w))
    center_img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    x = (sw - target_w) // 2
    y = (sh - target_h) // 2
    bg.paste(center_img, (x, y))
    return np.array(bg)


def get_story_video_url_from_feed_image(
    feed_image_url: str,
    audio_path: Optional[str] = None,
    duration_seconds: float = 10.0,
) -> str:
    """
    Gera um vídeo curto (5-15s) com a imagem do post + áudio opcional para Story.
    Faz upload para Cloudinary e devolve o URL para create_story(video_url=...).
    A música só entra se estiver dentro do vídeo (a API do Instagram não suporta sticker de música).
    """
    if not (feed_image_url or "").strip():
        raise ValueError("URL da imagem do post está vazio.")
    try:
        from moviepy import AudioFileClip, ImageClip, concatenate_audioclips, afx
    except ImportError as e:
        raise ImportError(
            "moviepy não encontrado. Instala com: pip install moviepy imageio-ffmpeg"
        ) from e

    from instagram_poster.reel_generator import upload_video_bytes

    logger.info("A gerar vídeo Story com música a partir do post: %s", feed_image_url[:80])
    image_bytes = _download_image(feed_image_url.strip())
    # Normalizar para 1080x1080 antes de converter em frame de Story
    image_bytes = _normalize_to_feed_size(image_bytes)
    frame = _image_to_vertical_frame_np(image_bytes)
    # Instagram Story: máximo 59s para garantir aceitação
    clip = ImageClip(frame, duration=min(59.0, max(1.0, duration_seconds)))

    if audio_path and Path(audio_path).exists():
        audio = AudioFileClip(audio_path)
        audio = audio.with_effects([afx.MultiplyVolume(0.3)])
        if audio.duration < clip.duration:
            loops = int(clip.duration / audio.duration) + 1
            audio = concatenate_audioclips([audio] * loops)
        audio = audio.subclipped(0, clip.duration)
        audio = audio.with_effects([afx.AudioFadeOut(1.0)])
        clip = clip.with_audio(audio)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        clip.write_videofile(
            tmp_path,
            fps=30,
            codec="libx264",
            audio_codec="aac" if audio_path else None,
            logger=None,
        )
        with open(tmp_path, "rb") as f:
            video_bytes = f.read()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return upload_video_bytes(video_bytes, public_id_prefix="ig_story")


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


def _resolve_final_prompt(prompt: str, quote_text: Optional[str], use_full_prompt: bool) -> str:
    """Resolve o prompt final de imagem a partir do Gemini_Prompt/Image Text, sem texto literal da quote."""
    has_overlay = bool(quote_text and quote_text.strip())

    if has_overlay:
        if use_full_prompt:
            candidate = prompt.strip()
            if _has_embedded_quote(candidate, quote_text):
                sanitized = _sanitize_prompt(candidate, quote_text)
                if len(sanitized.split()) < 8:
                    logger.info("Prompt sanitizado ficou curto; a converter quote via LLM.")
                    return _quote_to_scene_prompt(quote_text)
                return sanitized
            final_prompt = candidate
            no_text = "Do NOT include any text, letters, words, or watermarks in the image."
            if "do not include any text" not in final_prompt.lower():
                final_prompt = final_prompt.rstrip(".") + ". " + no_text
            return final_prompt
        logger.info("Sem Gemini_Prompt; a converter quote via LLM.")
        return _quote_to_scene_prompt(quote_text)

    text = prompt.strip()
    return text if use_full_prompt else _QUOTE_CARD_PROMPT


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
    final_prompt = _resolve_final_prompt(prompt, quote_text, use_full_prompt)

    logger.info("Prompt final para imagem: %s", final_prompt[:150])
    image_bytes = generate_image_from_prompt(final_prompt)

    if has_overlay:
        logger.info("A sobrepor quote na imagem: '%s'", quote_text[:60])
        image_bytes = overlay_quote_on_image(image_bytes, quote_text)

    return upload_image_bytes(image_bytes, public_id_prefix=public_id_prefix)


def get_carousel_slides_from_prompt(
    prompt: str,
    quote_text: str,
    explanation_text: str,
    use_full_prompt: bool = True,
    public_id_prefix: str = "ig_post",
) -> tuple[str, str]:
    """
    Gera um carrossel de 2 slides a partir de UMA única imagem AI (evita gerar/pagar a
    imagem duas vezes e garante coerência visual entre os slides):
    - Slide 1: a imagem AI com a quote (Image Text) sobreposta — igual ao post normal.
    - Slide 2: a mesma imagem-base, com fundo mais desfocado/escurecido, com o texto de
      explicação do dia (Slide2 Text) sobreposto.
    Devolve (slide1_url, slide2_url).
    """
    if not (prompt or "").strip():
        raise ValueError("O prompt está vazio; não é possível gerar a imagem.")
    if not (explanation_text or "").strip():
        raise ValueError("Slide2 Text está vazio; não é possível gerar o 2º slide do carrossel.")

    final_prompt = _resolve_final_prompt(prompt, quote_text, use_full_prompt)
    logger.info("Prompt final para carrossel: %s", final_prompt[:150])
    base_image_bytes = generate_image_from_prompt(final_prompt)

    slide1_bytes = overlay_quote_on_image(base_image_bytes, quote_text) if quote_text.strip() else _normalize_to_feed_size(base_image_bytes)
    slide2_bytes = render_explanation_card(base_image_bytes, explanation_text)

    slide1_url = upload_image_bytes(slide1_bytes, public_id_prefix=f"{public_id_prefix}_s1")
    slide2_url = upload_image_bytes(slide2_bytes, public_id_prefix=f"{public_id_prefix}_s2")
    return slide1_url, slide2_url
