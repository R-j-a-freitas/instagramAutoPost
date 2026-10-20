"""
Reel de uma frase: vídeo vertical nativo 1080x1920, ~8 s, com a frase do post legível desde o
primeiro frame (é também a capa) e um zoom lento sobre uma imagem gerada já em 9:16.

Substitui os Reels "slideshow" (5 imagens quadradas x 8 s, fundo desfocado), cujo tempo médio
de visualização era ~3 s. Usa o mesmo estilo de texto dos posts do feed (fonte e caixa da marca).

Música: só faixas de uso livre em assets/music/LIVRE/ (música com direitos de autor colada no
vídeo leva o Instagram a silenciar ou limitar o Reel). Sem faixas, o Reel sai sem som.
"""
import io
import json
import logging
import random
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_USED_FILE = _PROJECT_ROOT / "assets" / "quote_reels_used.json"
_MEDIA_FILE = _PROJECT_ROOT / "assets" / "quote_reels_media.json"
FREE_MUSIC_DIR = _PROJECT_ROOT / "assets" / "music" / "LIVRE"
W, H = 1080, 1920
FPS = 30
HANDLE = "@keepcalmnbepositive"


def get_used_row_indices() -> set[int]:
    try:
        return {int(x) for x in json.loads(_USED_FILE.read_text(encoding="utf-8"))}
    except (OSError, ValueError, TypeError):
        return set()


def mark_used(row_index: int, media_id: Optional[str] = None) -> None:
    used = get_used_row_indices() | {int(row_index)}
    _USED_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _USED_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(sorted(used)), encoding="utf-8")
    tmp.replace(_USED_FILE)
    if media_id:  # para o relatório semanal distinguir estes Reels dos slideshows antigos
        ids = get_quote_reel_media_ids() | {str(media_id)}
        tmp = _MEDIA_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(sorted(ids)), encoding="utf-8")
        tmp.replace(_MEDIA_FILE)


def get_quote_reel_media_ids() -> set[str]:
    try:
        return {str(x) for x in json.loads(_MEDIA_FILE.read_text(encoding="utf-8"))}
    except (OSError, ValueError, TypeError):
        return set()


def free_music_tracks() -> list[Path]:
    if not FREE_MUSIC_DIR.is_dir():
        return []
    return sorted(p for p in FREE_MUSIC_DIR.iterdir() if p.suffix.lower() in (".mp3", ".m4a", ".wav"))


def _vertical_background(post: dict[str, Any]) -> bytes:
    """Imagem 1080x1920 sem texto: gerada em 9:16 a partir do prompt do post (Pollinations);
    se não for possível, recorte vertical da imagem do post (que já tem a frase, por isso é o plano B)."""
    from PIL import Image

    from instagram_poster.config import get_image_provider
    from instagram_poster.image_generator import _download_image, _sanitize_prompt

    quote = (post.get("image_text") or "").strip()
    prompt = (post.get("gemini_prompt") or "").strip()
    if prompt and get_image_provider() == "pollinations":
        try:
            from instagram_poster.providers.provider_pollinations import PollinationsProvider
            return PollinationsProvider().generate(_sanitize_prompt(prompt, quote), width=W, height=H)
        except Exception as e:  # rede/créditos: segue para o plano B
            logger.warning("Quote reel: imagem 9:16 falhou (%s); a usar recorte da imagem do post", e)
    img = Image.open(io.BytesIO(_download_image(post["image_url"]))).convert("RGB")
    scale = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    left, top = (img.width - W) // 2, (img.height - H) // 2
    buf = io.BytesIO()
    img.crop((left, top, left + W, top + H)).save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _text_overlay(quote: str) -> bytes:
    """PNG transparente 1080x1920 com a frase (estilo da marca) e o @ da conta.
    A frase fica no terço central, fora das zonas tapadas pela interface dos Reels (fundo e lado direito)."""
    from PIL import Image, ImageDraw

    from instagram_poster.image_generator import (
        BRAND_BOX_FILL_COLOR, BRAND_TEXT_COLOR, BRAND_TEXT_SHADOW_COLOR, _load_text_font)

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    size = 76 if len(quote) <= 90 else 64
    font, size = _load_text_font(size)
    max_w = int(W * 0.78)
    # Quebra por largura real em píxeis (não por número de caracteres).
    words, lines, cur = quote.split(), [], ""
    for word in words:
        test = f"{cur} {word}".strip()
        if draw.textlength(test, font=font) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    gap = int(size * 0.32)
    heights = [draw.textbbox((0, 0), l, font=font)[3] - draw.textbbox((0, 0), l, font=font)[1] for l in lines]
    widths = [draw.textlength(l, font=font) for l in lines]
    block_h = sum(heights) + gap * (len(lines) - 1)
    pad_x, pad_y = 56, 52
    box_w, box_h = int(max(widths)) + 2 * pad_x, block_h + 2 * pad_y
    box_x, box_y = (W - box_w) // 2, int(H * 0.42) - box_h // 2
    draw.rounded_rectangle([box_x, box_y, box_x + box_w, box_y + box_h], radius=28, fill=BRAND_BOX_FILL_COLOR)
    y = box_y + pad_y
    for line, lw, lh in zip(lines, widths, heights):
        x = (W - lw) // 2
        draw.text((x + 3, y + 3), line, font=font, fill=BRAND_TEXT_SHADOW_COLOR)
        draw.text((x, y), line, font=font, fill=BRAND_TEXT_COLOR)
        y += lh + gap
    small, _ = _load_text_font(34)
    hw = draw.textlength(HANDLE, font=small)
    hy = box_y + box_h + 34
    draw.text(((W - hw) // 2 + 2, hy + 2), HANDLE, font=small, fill=BRAND_TEXT_SHADOW_COLOR)
    draw.text(((W - hw) // 2, hy), HANDLE, font=small, fill=(255, 255, 255, 220))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_quote_reel(post: dict[str, Any], duration: float = 8.0, audio_path: Optional[str] = None,
                      audio_volume: float = 0.35) -> bytes:
    """Gera o MP4 (H.264/AAC, 1080x1920, 30 fps) e devolve os bytes."""
    quote = (post.get("image_text") or "").strip()
    if not quote:
        raise ValueError("Post sem image_text")
    ffmpeg = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
    if audio_path is None:
        tracks = free_music_tracks()
        audio_path = str(random.choice(tracks)) if tracks else None
    frames = int(round(duration * FPS))
    with tempfile.TemporaryDirectory(prefix="quote_reel_") as td:
        bg, ov, out = Path(td, "bg.jpg"), Path(td, "ov.png"), Path(td, "reel.mp4")
        bg.write_bytes(_vertical_background(post))
        ov.write_bytes(_text_overlay(quote))
        # Zoom lento 1.00 -> 1.06 sobre uma versão 2x da imagem (evita o tremer do zoompan).
        vf = (f"[0:v]scale={2 * W}:{2 * H}:force_original_aspect_ratio=increase,crop={2 * W}:{2 * H},"
              f"zoompan=z='1+0.06*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS}[bg];"
              f"[bg][1:v]overlay=0:0,format=yuv420p[v]")
        cmd = [ffmpeg, "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-i", str(bg), "-i", str(ov)]
        if audio_path:
            cmd += ["-i", audio_path]
            vf += (f";[2:a]atrim=0:{duration},asetpts=PTS-STARTPTS,volume={audio_volume},"
                   f"afade=t=in:st=0:d=0.4,afade=t=out:st={duration - 1.2}:d=1.2[a]")
        cmd += ["-filter_complex", vf, "-map", "[v]"]
        cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", "128k"] if audio_path else []
        cmd += ["-frames:v", str(frames), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-r", str(FPS), "-movflags", "+faststart", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0 or not out.exists():
            raise RuntimeError(f"ffmpeg falhou: {r.stderr[-500:]}")
        if not audio_path:
            logger.warning("Quote reel sem som: põe faixas de uso livre em %s", FREE_MUSIC_DIR)
        return out.read_bytes()
