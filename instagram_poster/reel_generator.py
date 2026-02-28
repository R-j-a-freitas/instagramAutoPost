"""
Geração de Reels a partir dos últimos N posts publicados.
Cria vídeo slideshow 1080x1920 (9:16), opcionalmente com áudio, e upload para Cloudinary ou local.
"""
import io
import json
import logging
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import numpy as np
import requests

from instagram_poster.config import (
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
    CLOUDINARY_CLOUD_NAME,
    get_cloudinary_url,
    get_media_backend,
    get_media_base_url,
    get_media_root,
    get_pollinations_api_key,
)

logger = logging.getLogger(__name__)

_ASSETS_MUSIC = Path(__file__).resolve().parent.parent / "assets" / "music"
_MUSIC_FOLDER = _ASSETS_MUSIC / "MUSIC"
_ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets"
_REELS_USED_ROWS_FILE = _ASSETS_ROOT / "reels_used_rows.json"


def get_reel_used_row_indices() -> set[int]:
    """Lê assets/reels_used_rows.json e devolve o conjunto de row_index já usados em Reels."""
    if not _REELS_USED_ROWS_FILE.exists():
        return set()
    try:
        with open(_REELS_USED_ROWS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return set()
    if not isinstance(data, list):
        return set()
    return set(int(x) for x in data if isinstance(x, (int, float)))


def mark_posts_used_in_reel(row_indices: list[int]) -> None:
    """Regista os row_index como usados em Reels (persiste em assets/reels_used_rows.json)."""
    if not row_indices:
        return
    current = get_reel_used_row_indices()
    current.update(row_indices)
    _ASSETS_ROOT.mkdir(parents=True, exist_ok=True)
    payload = sorted(current)
    try:
        with open(_REELS_USED_ROWS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=0)
        logger.info("Reels: %d linha(s) marcadas como usadas em Reel (total: %d)", len(row_indices), len(payload))
    except OSError as e:
        logger.warning("Não foi possível gravar reels_used_rows.json: %s", e)


def get_posts_for_reel(n: int, allow_reuse: bool = False) -> list[dict[str, Any]]:
    """
    Devolve até n posts publicados elegíveis para Reel.
    Se allow_reuse for False, exclui posts cujo row_index já foi usado em algum Reel.
    """
    from instagram_poster.sheets_client import get_last_published_posts
    all_posts = get_last_published_posts(n=30)
    if not all_posts:
        return []
    if allow_reuse:
        return all_posts[:n]
    used = get_reel_used_row_indices()
    eligible = [p for p in all_posts if (p.get("row_index") or 0) not in used]
    return eligible[:n]


def _scan_music_folder() -> list[dict[str, Any]]:
    """Varre assets/music/MUSIC/ e devolve uma entrada por ficheiro .mp3 existente."""
    if not _MUSIC_FOLDER.exists():
        logger.warning("Pasta de música não encontrada: %s", _MUSIC_FOLDER)
        return []
    result = []
    for path in sorted(_MUSIC_FOLDER.glob("*.mp3")):
        name = path.stem
        result.append({
            "file": path.name,
            "path": str(path),
            "name": name,
            "duration_s": 0,
        })
    return result


def _load_metadata_overrides() -> dict[str, dict[str, Any]]:
    """Carrega metadata.json e devolve um dict filename -> {name?, duration_s?} para enriquecer as faixas."""
    meta_path = _ASSETS_MUSIC / "metadata.json"
    if not meta_path.exists():
        return {}
    try:
        with open(meta_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("metadata.json não usado: %s", e)
        return {}
    overrides = {}
    for t in data.get("tracks", []):
        if isinstance(t, dict) and t.get("file"):
            overrides[t["file"]] = t
    return overrides


def _rebuild_metadata_json(tracks: list[dict[str, Any]]) -> None:
    """Reescreve assets/music/metadata.json para reflectir a lista actual de faixas (ficheiros na pasta)."""
    _ASSETS_MUSIC.mkdir(parents=True, exist_ok=True)
    meta_path = _ASSETS_MUSIC / "metadata.json"
    payload = {
        "tracks": [
            {"file": t["file"], "name": t["name"], "duration_s": t.get("duration_s", 0)}
            for t in tracks
        ]
    }
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info("metadata.json actualizado com %d faixa(s) em %s", len(tracks), meta_path)
    except OSError as e:
        logger.warning("Não foi possível escrever metadata.json: %s", e)


def get_available_music_tracks(rebuild_json: bool = True) -> list[dict[str, Any]]:
    """
    Devolve as faixas de música disponíveis em assets/music/MUSIC/.
    A lista é construída a partir dos ficheiros .mp3 existentes na pasta. Se rebuild_json for True
    (default), o metadata.json é reconstruído para reflectir as músicas actuais (útil no autopost e ao criar Reel).
    """
    tracks = _scan_music_folder()
    overrides = _load_metadata_overrides()
    for t in tracks:
        if t["file"] in overrides:
            o = overrides[t["file"]]
            if o.get("name"):
                t["name"] = o["name"]
            if "duration_s" in o:
                t["duration_s"] = o["duration_s"]
    if rebuild_json and tracks:
        _rebuild_metadata_json(tracks)
    logger.info("Encontradas %d faixa(s) de música em %s", len(tracks), _MUSIC_FOLDER)
    return tracks


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
    try:
        from moviepy import AudioFileClip, ImageClip, concatenate_audioclips, concatenate_videoclips, vfx, afx
    except ImportError as e:
        raise ImportError(
            "moviepy não encontrado. Instala com: pip install moviepy imageio-ffmpeg"
        ) from e

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


def upload_video_bytes(video_bytes: bytes, public_id_prefix: str = "ig_reel") -> str:
    """
    Se MEDIA_BACKEND=="cloudinary": usa Cloudinary como hoje.
    Se MEDIA_BACKEND=="local_http": grava em MEDIA_ROOT e devolve MEDIA_BASE_URL/<filename>.mp4
    """
    if get_media_backend() == "local_http":
        return _upload_video_to_local(video_bytes, public_id_prefix)
    return _upload_video_to_cloudinary(video_bytes, public_id_prefix)


def _upload_video_to_local(video_bytes: bytes, public_id_prefix: str) -> str:
    """Grava vídeo em MEDIA_ROOT e devolve URL público."""
    filename = f"{public_id_prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}.mp4"
    try:
        path = get_media_root() / filename
        path.write_bytes(video_bytes)
    except OSError as e:
        raise ValueError(
            f"MEDIA_ROOT não gravável: {get_media_root()}. Verifica permissões. Erro: {e}"
        ) from e
    url = f"{get_media_base_url()}/{filename}"
    logger.info("Vídeo gravado localmente: %s", url[:80])
    return url


def _upload_video_to_cloudinary(video_bytes: bytes, public_id_prefix: str = "ig_reel") -> str:
    """Faz upload do vídeo para Cloudinary (resource_type=video) e devolve o secure_url."""
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
            "Configura o Cloudinary no .env para upload de vídeo."
        )

    public_id = f"{public_id_prefix}_{int(time.time())}"
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
