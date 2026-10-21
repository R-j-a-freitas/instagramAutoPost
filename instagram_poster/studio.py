"""
Estúdio de vídeo: ponte entre a app e as ferramentas de vídeo instaladas no servidor (~/video).

- publish_reel(): publica um MP4 como Reel, com capa explícita (frame escolhido) e legenda.
- make_parallax_clips(): clips de 5 s com movimento 2.5D a partir de prompts (imagem Pollinations
  flux ~0,002 $ + recorte por profundidade + HyperFrames), via ~/video/tools/make_parallax_clips.py.
- storyline_*(): montagem com o FireRed-OpenStoryline (serviço video-storyline em 127.0.0.1:7861).
Os resultados são também copiados para a pasta partilhada Video/saida.
"""
import json
import logging
import os
import re
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

HOME = Path.home()
VIDEO_OUT = Path("/DATA/shares/workspace/Video/saida")
CLIPS_ROOT = HOME / "video/storyline_media/media"
PARALLAX_SCRIPT = HOME / "video/tools/make_parallax_clips.py"
STORYLINE_DIR = HOME / "video/repos/OpenStoryline"
STORYLINE_PY = HOME / "video/envs/openstoryline/bin/python"
STORYLINE_BRIDGE = STORYLINE_DIR / ".claude/skills/openstoryline-use/scripts/bridge_openstoryline.py"
STORYLINE_URL = "http://127.0.0.1:7861"
CONTROL_URL = "http://127.0.0.1:8092/video/api"
COST_PER_IMAGE_USD = 0.002  # flux.1-schnell na Pollinations


def slugify(text: str, n: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:n].rstrip("-") or "video")


def save_output(video_bytes: bytes, name: str) -> Path:
    """Guarda o vídeo em Video/saida (descarregável em /video/files/saida/) e devolve o caminho."""
    VIDEO_OUT.mkdir(parents=True, exist_ok=True)
    path = VIDEO_OUT / f"{datetime.now():%Y%m%d-%H%M}_{slugify(name)}.mp4"
    path.write_bytes(video_bytes)
    return path


def cover_from_video(video_bytes: bytes, offset_ms: int) -> bytes:
    from instagram_poster.quote_reel import cover_from_video as _cover
    return _cover(video_bytes, offset_ms)


def publish_reel(video_bytes: bytes, caption: str, cover_offset_ms: int = 3500) -> str:
    """Publica como Reel com capa no frame cover_offset_ms. Devolve o media_id."""
    from instagram_poster import ig_client
    from instagram_poster.image_generator import upload_image_bytes
    from instagram_poster.reel_generator import upload_video_bytes

    video_url = upload_video_bytes(video_bytes, public_id_prefix="ig_studio_reel")
    cover_url = None
    try:
        cover_url = upload_image_bytes(cover_from_video(video_bytes, cover_offset_ms), public_id_prefix="ig_studio_cover")
    except Exception as e:
        logger.warning("Estúdio: capa não gerada (%s)", e)
    creation_id = ig_client.create_reel(video_url=video_url, caption=caption, thumb_offset_ms=cover_offset_ms,
                                        cover_url=cover_url)
    return ig_client.publish_media(creation_id, max_wait=240)


def video_duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


# --- Clips 2.5D -----------------------------------------------------------------------------------

def clip_sets() -> list[Path]:
    """Pastas de clips já gerados (mais recentes primeiro)."""
    if not CLIPS_ROOT.is_dir():
        return []
    sets = [p for p in CLIPS_ROOT.iterdir() if p.is_dir() and any(p.glob("clip_*.mp4"))]
    return sorted(sets, key=lambda p: p.stat().st_mtime, reverse=True)


def make_parallax_clips(name: str, prompts: list[str], timeout: int = 1800) -> Path:
    """Gera um clip 2.5D por prompt numa pasta nova em CLIPS_ROOT e devolve a pasta."""
    out = CLIPS_ROOT / f"{datetime.now():%Y%m%d-%H%M}_{slugify(name, 30)}"
    out.mkdir(parents=True, exist_ok=True)
    py = shutil.which("python3") or "/usr/bin/python3"
    r = subprocess.run([py, str(PARALLAX_SCRIPT), str(out), *prompts], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0 and not any(out.glob("clip_*.mp4")):
        raise RuntimeError((r.stderr or r.stdout)[-600:])
    imgs = out / "imagens"  # imagens originais à parte, para a montagem só ver clips
    imgs.mkdir(exist_ok=True)
    for img in out.glob("img_*.jpg"):
        img.replace(imgs / img.name)
    return out


def simple_montage(clips: list[Path], audio_path: Optional[str] = None, xfade: float = 0.6,
                   audio_volume: float = 0.8) -> bytes:
    """Montagem rápida e grátis: junta os clips com dissolves (ffmpeg xfade) e música livre."""
    import tempfile
    if not clips:
        raise ValueError("Sem clips")
    ffmpeg = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
    durs = [video_duration(c) for c in clips]
    cmd = [ffmpeg, "-y", "-v", "error"]
    for c in clips:
        cmd += ["-i", str(c)]
    parts, last, offset = [], "[0:v]", 0.0
    for i in range(1, len(clips)):
        offset += durs[i - 1] - xfade
        out = f"[v{i}]"
        parts.append(f"{last}[{i}:v]xfade=transition=fade:duration={xfade}:offset={offset:.3f}{out}")
        last = out
    total = sum(durs) - xfade * (len(clips) - 1)
    vf = ";".join(parts) + (";" if parts else "") + f"{last}format=yuv420p[v]"
    if audio_path:
        cmd += ["-i", audio_path]
        a = len(clips)
        vf += (f";[{a}:a]silenceremove=start_periods=1:start_threshold=-45dB,atrim=0:{total:.3f},asetpts=PTS-STARTPTS,"
               f"volume={audio_volume},afade=t=in:st=0:d=0.5,afade=t=out:st={max(total - 1.5, 0):.3f}:d=1.5[a]")
    with tempfile.TemporaryDirectory(prefix="studio_montage_") as td:
        out_path = Path(td, "montage.mp4")
        cmd += ["-filter_complex", vf, "-map", "[v]"] + (["-map", "[a]", "-c:a", "aac", "-b:a", "128k"] if audio_path else [])
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "30", "-t", f"{total:.3f}",
                "-movflags", "+faststart", str(out_path)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if r.returncode != 0 or not out_path.exists():
            raise RuntimeError(f"ffmpeg falhou: {r.stderr[-500:]}")
        return out_path.read_bytes()


# --- Montagem com o OpenStoryline ------------------------------------------------------------------

def _http(method: str, url: str, timeout: float = 30):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def storyline_running() -> bool:
    try:
        urllib.request.urlopen(STORYLINE_URL + "/", timeout=3)
        return True
    except Exception:
        return False


def storyline_start(wait: int = 180) -> bool:
    """Liga o serviço video-storyline pela API de controlo da página /video/ e espera que responda."""
    if storyline_running():
        return True
    try:
        _http("POST", f"{CONTROL_URL}/storyline/start")
    except Exception as e:
        logger.warning("Estúdio: não consegui ligar o OpenStoryline pela API de controlo (%s)", e)
    end = time.time() + wait
    while time.time() < end:
        if storyline_running():
            return True
        time.sleep(3)
    return False


def storyline_edit(clips_dir: Path, request: str, timeout: int = 1500, session_id: Optional[str] = None) -> dict:
    """Envia os clips da pasta e o pedido ao OpenStoryline; devolve {session_id, video, log}.
    Com session_id continua a mesma sessão (pedidos de alteração sobre o vídeo anterior)."""
    import requests

    if not storyline_start():
        raise RuntimeError("O OpenStoryline não arrancou (serviço video-storyline).")
    if not session_id:
        session_id = _http("POST", f"{STORYLINE_URL}/api/sessions")["session_id"]
        files = [("files", (p.name, open(p, "rb"), "video/mp4")) for p in sorted(clips_dir.glob("clip_*.mp4"))]
        try:
            r = requests.post(f"{STORYLINE_URL}/api/sessions/{session_id}/media", files=files, timeout=300)
            r.raise_for_status()
        finally:
            for _, (_, fh, _) in files:
                fh.close()
    started = time.time()
    # O agente apresenta um plano e pede confirmação antes de montar; aqui não há ninguém para responder.
    request = request.rstrip() + "\n\nDo not ask for confirmation: execute the full plan now and render the final video."
    r = subprocess.run([str(STORYLINE_PY), str(STORYLINE_BRIDGE), "--base-url", STORYLINE_URL, "--session-id", session_id,
                        "--lang", "en", "--timeout", str(timeout), "--prompt", request],
                       capture_output=True, text=True, timeout=timeout + 60, cwd=STORYLINE_DIR)
    video = latest_storyline_video(session_id, since=started, log=r.stdout or "")
    return {"session_id": session_id, "video": video, "log": (r.stdout or "")[-4000:] + (r.stderr or "")[-2000:],
            "returncode": r.returncode}


def latest_storyline_video(session_id: str, since: float = 0, log: str = "") -> Optional[Path]:
    """O vídeo final: o caminho indicado na resposta do agente, ou o MP4 mais recente da sessão
    em .storyline/.server_cache/<sessão>/render_video_*/ (ou outputs/)."""
    for m in re.findall(r"(/[^\s)\]\"']+\.mp4)", log or ""):
        if Path(m).is_file():
            return Path(m)
    roots = [STORYLINE_DIR / ".storyline" / ".server_cache" / session_id, STORYLINE_DIR / "outputs"]
    cands = [p for r in roots if r.is_dir() for p in r.rglob("output_*.mp4") if p.stat().st_mtime >= since - 5]
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None
