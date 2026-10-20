"""
Reel de uma frase: vídeo vertical nativo 1080x1920, 8 s, com zoom lento sobre uma imagem gerada
já em 9:16 e a frase a entrar palavra a palavra (modelo HyperFrames em assets/hyperframes/quote_reel;
se o HyperFrames falhar, plano B em ffmpeg com a frase fixa desde o primeiro frame). A capa do Reel
é o momento COVER_OFFSET_MS, com a frase completa.

Substitui os Reels "slideshow" (5 imagens quadradas x 8 s, fundo desfocado), cujo tempo médio
de visualização era ~3 s. Usa o mesmo estilo de texto dos posts do feed (fonte e caixa da marca).

Música: só faixas de uso livre em assets/music/LIVRE/ (música com direitos de autor colada no
vídeo leva o Instagram a silenciar ou limitar o Reel). Sem faixas, o Reel sai sem som.
"""
import io
import json
import logging
import os
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
                      audio_volume: float = 0.8) -> bytes:
    """Gera o MP4 (H.264/AAC, 1080x1920, 30 fps) e devolve os bytes.
    Motor principal: modelo HyperFrames (palavras a entrar uma a uma); plano B: ffmpeg (texto fixo)."""
    quote = (post.get("image_text") or "").strip()
    if not quote:
        raise ValueError("Post sem image_text")
    if audio_path is None:
        tracks = free_music_tracks()
        audio_path = str(random.choice(tracks)) if tracks else None
    background = _vertical_background(post)
    try:
        return _render_hyperframes(quote, background, audio_path, audio_volume)
    except Exception as e:
        logger.warning("Quote reel: HyperFrames falhou (%s); a usar o modelo ffmpeg", e)
        return _render_ffmpeg(quote, background, duration, audio_path, audio_volume)


# Modelo animado (assets/hyperframes/quote_reel) e o CLI do HyperFrames instalado com o Herk Edit Kit.
HYPERFRAMES_TEMPLATE = _PROJECT_ROOT / "assets" / "hyperframes" / "quote_reel"
HYPERFRAMES_BIN = os.environ.get(
    "HYPERFRAMES_BIN", str(Path.home() / "video/repos/HerkEditKit/node_modules/.bin/hyperframes"))
HYPERFRAMES_DURATION = 8.0  # fixo no modelo (data-duration)
COVER_OFFSET_MS = 3500  # capa do Reel: frase completa, linha e @ já visíveis


def _render_hyperframes(quote: str, background: bytes, audio_path: Optional[str], audio_volume: float) -> bytes:
    if not Path(HYPERFRAMES_BIN).exists():
        raise FileNotFoundError(f"HyperFrames não encontrado em {HYPERFRAMES_BIN}")
    with tempfile.TemporaryDirectory(prefix="quote_reel_hf_") as td:
        proj = Path(td, "proj")
        shutil.copytree(HYPERFRAMES_TEMPLATE, proj)
        (proj / "bg.jpg").write_bytes(background)
        vars_file = Path(td, "vars.json")
        vars_file.write_text(json.dumps({"quote": quote, "handle": HANDLE}, ensure_ascii=False), encoding="utf-8")
        silent = Path(td, "silent.mp4")
        r = subprocess.run([HYPERFRAMES_BIN, "render", "--variables-file", str(vars_file), "--output", str(silent),
                            "--quiet", "--strict"], cwd=proj, capture_output=True, text=True, timeout=600)
        if r.returncode != 0 or not silent.exists():
            raise RuntimeError(f"hyperframes render falhou: {(r.stderr or r.stdout)[-500:]}")
        if not audio_path:
            logger.warning("Quote reel sem som: põe faixas de uso livre em %s", FREE_MUSIC_DIR)
            return silent.read_bytes()
        out = Path(td, "reel.mp4")
        d = HYPERFRAMES_DURATION
        ffmpeg = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
        r = subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(silent), "-i", audio_path, "-filter_complex",
                            f"[1:a]silenceremove=start_periods=1:start_threshold=-45dB,atrim=0:{d},asetpts=PTS-STARTPTS,volume={audio_volume},"
                            f"afade=t=in:st=0:d=0.4,afade=t=out:st={d - 1.2}:d=1.2[a]",
                            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                            "-t", str(d), "-movflags", "+faststart", str(out)],
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0 or not out.exists():
            raise RuntimeError(f"ffmpeg (áudio) falhou: {r.stderr[-500:]}")
        return out.read_bytes()


def _render_ffmpeg(quote: str, background: bytes, duration: float, audio_path: Optional[str],
                   audio_volume: float) -> bytes:
    """Modelo simples (plano B): texto fixo desde o primeiro frame e zoom lento."""
    ffmpeg = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
    frames = int(round(duration * FPS))
    with tempfile.TemporaryDirectory(prefix="quote_reel_") as td:
        bg, ov, out = Path(td, "bg.jpg"), Path(td, "ov.png"), Path(td, "reel.mp4")
        bg.write_bytes(background)
        ov.write_bytes(_text_overlay(quote))
        # Zoom lento 1.00 -> 1.06 sobre uma versão 2x da imagem (evita o tremer do zoompan).
        vf = (f"[0:v]scale={2 * W}:{2 * H}:force_original_aspect_ratio=increase,crop={2 * W}:{2 * H},"
              f"zoompan=z='1+0.06*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS}[bg];"
              f"[bg][1:v]overlay=0:0,format=yuv420p[v]")
        cmd = [ffmpeg, "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-i", str(bg), "-i", str(ov)]
        if audio_path:
            cmd += ["-i", audio_path]
            vf += (f";[2:a]silenceremove=start_periods=1:start_threshold=-45dB,atrim=0:{duration},asetpts=PTS-STARTPTS,volume={audio_volume},"
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
