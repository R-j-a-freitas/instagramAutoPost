"""
Geração de Reels a partir dos últimos N posts publicados.
Cria vídeo slideshow 1080x1920 (9:16), opcionalmente com áudio, e upload para Cloudinary.
"""
import io
import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

import numpy as np
import requests

from instagram_poster.config import (
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_URL,
    get_pollinations_api_key,
)

logger = logging.getLogger(__name__)

_ASSETS_MUSIC = Path(__file__).resolve().parent.parent / "assets" / "music"
_MUSIC_FOLDER = _ASSETS_MUSIC / "MUSIC"


def get_available_music_tracks() -> list[dict[str, Any]]:
    """Lê assets/music/metadata.json e devolve lista de faixas em assets/music/MUSIC/ (com file existente)."""
    meta_path = _ASSETS_MUSIC / "metadata.json"
    if not meta_path.exists():
        return []
    try:
        with open(meta_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    tracks = data.get("tracks", [])
    result = []
    for t in tracks:
        if not isinstance(t, dict) or "file" not in t:
            continue
        path = _MUSIC_FOLDER / t["file"]
        if path.exists():
            result.append({
                "file": t["file"],
                "path": str(path),
                "name": t.get("name", t["file"]),
                "duration_s": t.get("duration_s", 0),
            })
    return result


def generate_caption_for_posts(posts: list[dict[str, Any]]) -> str:
    """
    Gera uma caption que resume os posts (via Pollinations). Se falhar, devolve texto fallback.
    """
    if not posts:
        return "Resumo dos nossos últimos posts. #keepcalm"
    quotes = [str(p.get("image_text") or "").strip() for p in posts if p.get("image_text")]
    if not quotes:
        return "Resumo dos nossos últimos posts. #keepcalm"
    api_key = get_pollinations_api_key()
    if not api_key:
        return "Resumo dos nossos últimos posts. #keepcalmnbepositive"
    prompt = (
        f"Write a short Instagram caption (2-4 sentences) that summarizes these quotes as one theme: "
        f"{' | '.join(quotes[:5])}. Tone: calm, positive. End with 1-2 hashtags like #keepcalmnbepositive."
    )
    try:
        resp = requests.post(
            "https://gen.pollinations.ai/v1/chat/completions",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            json={"model": "openai", "messages": [{"role": "user", "content": prompt}]},
            timeout=30,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        return text or "Resumo dos nossos últimos posts. #keepcalmnbepositive"
    except Exception as e:
        logger.warning("Caption IA falhou: %s", e)
        return "Resumo dos nossos últimos posts. #keepcalmnbepositive"


def _download_image(url: str) -> bytes:
    """Descarrega uma imagem a partir de um URL público."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content


def _image_to_vertical_frame(image_bytes: bytes) -> np.ndarray:
    """
    Converte imagem quadrada (ex.: 1080x1080) em frame vertical 1080x1920 para Reel:
    fundo desfocado da própria imagem e imagem centrada. Devolve array RGB (H, W, 3) para MoviePy.
    """
    from PIL import Image, ImageFilter

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    if w < 100 or h < 100:
        raise ValueError("Imagem demasiado pequena para Reel")
    sw, sh = 1080, 1920
    bg = img.resize((sw, sh), Image.Resampling.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=25))
    box_size = min(1080, w, h)
    square = img.resize((box_size, box_size), Image.Resampling.LANCZOS)
    x = (sw - square.width) // 2
    y = (sh - square.height) // 2
    bg.paste(square, (x, y))
    return np.array(bg)


def create_reel_video(
    posts: list[dict[str, Any]],
    duration_per_slide: float = 4.0,
    transition: str = "crossfade",
    audio_path: Optional[str] = None,
    audio_volume: float = 0.3,
) -> bytes:
    """
    Cria vídeo Reel (MP4 1080x1920) a partir dos posts (cada um com image_url).
    Se audio_path for fornecido, mistura o áudio (loop se necessário, fade out 2s).
    Devolve os bytes do ficheiro MP4.
    """
    from moviepy import AudioFileClip, ImageClip, concatenate_audioclips, concatenate_videoclips, vfx, afx

    if not posts:
        raise ValueError("Lista de posts vazia")

    clips = []
    for post in posts:
        url = (post.get("image_url") or "").strip()
        if not url:
            logger.warning("Post sem image_url, a ignorar")
            continue
        image_bytes = _download_image(url)
        frame = _image_to_vertical_frame(image_bytes)
        clip = ImageClip(frame, duration=duration_per_slide)
        clip = clip.with_effects([vfx.FadeIn(0.5), vfx.FadeOut(0.5)])
        clips.append(clip)

    if not clips:
        raise ValueError("Nenhuma imagem válida nos posts")

    video = concatenate_videoclips(clips, method="compose")

    if audio_path:
        audio = AudioFileClip(audio_path)
        audio = audio.with_effects([afx.MultiplyVolume(audio_volume)])
        if audio.duration < video.duration:
            loops = int(video.duration / audio.duration) + 1
            audio = concatenate_audioclips([audio] * loops)
        audio = audio.subclipped(0, video.duration)
        audio = audio.with_effects([afx.AudioFadeOut(2.0)])
        video = video.with_audio(audio)

    # Remover os primeiros 2 segundos (evitar ecrã preto no início)
    TRIM_START_SEC = 2.0
    if video.duration > TRIM_START_SEC:
        video = video.subclipped(TRIM_START_SEC, video.duration)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        video.write_videofile(
            tmp_path,
            fps=30,
            codec="libx264",
            audio_codec="aac" if audio_path else None,
            logger=None,
        )
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def upload_video_to_cloudinary(video_bytes: bytes) -> str:
    """Faz upload do vídeo para Cloudinary (resource_type=video) e devolve o secure_url."""
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
            "Configura o Cloudinary no .env para upload de vídeo."
        )

    import time
    public_id = f"ig_reel_{int(time.time())}"
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
        tmp_path = tmp.name
    try:
        result = cloudinary.uploader.upload_large(
            tmp_path,
            resource_type="video",
            public_id=public_id,
            overwrite=True,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    url = result.get("secure_url") or result.get("url")
    if not url:
        raise ValueError("Cloudinary não devolveu URL do vídeo.")
    logger.info("Vídeo carregado no Cloudinary: %s", url[:80])
    return url
