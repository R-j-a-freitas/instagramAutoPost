"""
Motor de publicacao automatica.
- run_once(): verifica e publica o proximo post pronto (usado pelo CLI e pelo thread).
- start_background_loop() / stop_background_loop(): thread de background dentro do Streamlit.
- try_publish_auto_reel(): gera e publica um Reel quando ha 5 posts (8s/slide, fade, audio MUSIC).
"""
import logging
import random
import threading
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_stop_event = threading.Event()
_thread: Optional[threading.Thread] = None

_log: list[dict[str, Any]] = []
_last_check: Optional[datetime] = None
_started_at: Optional[datetime] = None
_total_published: int = 0
_total_errors: int = 0
_last_reel_row_indices: Optional[frozenset] = None


def get_log() -> list[dict[str, Any]]:
    with _lock:
        return list(_log)


def get_last_check() -> Optional[datetime]:
    with _lock:
        return _last_check


def get_stats() -> dict[str, Any]:
    with _lock:
        return {
            "started_at": _started_at,
            "total_published": _total_published,
            "total_errors": _total_errors,
            "total_checks": sum(1 for e in _log if e.get("type") == "check"),
            "total_stories": sum(1 for e in _log if e.get("type") == "story"),
            "total_reels": sum(1 for e in _log if e.get("type") == "reel"),
        }


def is_running() -> bool:
    with _lock:
        return _thread is not None and _thread.is_alive()


def _add_log_entry(
    success: Optional[bool],
    message: str,
    entry_type: str = "info",
    post_data: Optional[dict[str, Any]] = None,
    media_id: Optional[str] = None,
):
    global _total_published, _total_errors
    with _lock:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(),
            "success": success,
            "message": message,
            "type": entry_type,
            "media_id": media_id,
        }
        if post_data:
            entry["row"] = post_data.get("row_index")
            entry["date"] = post_data.get("date", "")
            entry["time"] = post_data.get("time", "")
            entry["quote"] = post_data.get("image_text", "")
        _log.append(entry)
        if entry_type == "publish" and success is True:
            _total_published += 1
        elif entry_type == "error" and success is False:
            _total_errors += 1
        if len(_log) > 100:
            _log.pop(0)


def log_story_published(post_data: dict[str, Any], media_id: Optional[str] = None) -> None:
    """Regista uma Story publicada no histórico (para monitorização)."""
    _add_log_entry(
        True,
        "Story publicada",
        entry_type="story",
        post_data=post_data,
        media_id=media_id,
    )


def run_once() -> Optional[bool]:
    """
    Verifica se ha post pronto agora e publica.
    Retorna True (publicado), False (erro), None (nada a publicar).
    """
    global _last_check
    with _lock:
        _last_check = datetime.now()

    now = datetime.now()
    try:
        from instagram_poster.scheduler import run_publish_next
        success, msg, media_id, post_data = run_publish_next(today=now.date(), now=now.time())
    except Exception as e:
        logger.exception("Autopublish: erro inesperado")
        _add_log_entry(False, f"Erro: {e}", entry_type="error")
        return False

    if not success and "Nenhum post pronto" in msg:
        logger.debug("Autopublish: nada a publicar agora")
        _add_log_entry(None, "Verificado — nenhum post pronto", entry_type="check")
        return None

    if success:
        quote_preview = ""
        if post_data:
            quote_preview = (post_data.get("image_text") or "")[:50]
        logger.info("Autopublish: post publicado — %s", msg)
        _add_log_entry(
            True,
            f"Publicado: \"{quote_preview}...\"" if len(quote_preview) >= 50 else f"Publicado: \"{quote_preview}\"",
            entry_type="publish",
            post_data=post_data,
            media_id=media_id,
        )
    else:
        logger.warning("Autopublish: falha — %s", msg)
        _add_log_entry(False, msg, entry_type="error", post_data=post_data)

    return success


def try_publish_auto_reel() -> bool:
    """
    Se houver pelo menos 5 posts publicados e o conjunto dos últimos 5 for diferente do último
    Reel gerado, gera um Reel (8s/slide, fade, áudio aleatório da pasta MUSIC, caption que resume
    os posts) e publica no Instagram. Retorna True se publicou, False caso contrário.
    """
    global _last_reel_row_indices
    try:
        from instagram_poster.reel_generator import (
            create_reel_video,
            generate_caption_for_posts,
            get_available_music_tracks,
            upload_video_to_cloudinary,
        )
        from instagram_poster.sheets_client import get_last_published_posts
        from instagram_poster import ig_client
    except Exception as e:
        logger.warning("Autopublish Reel: import falhou: %s", e)
        return False

    posts = get_last_published_posts(n=5)
    if len(posts) < 5:
        return False
    current_indices = frozenset(p.get("row_index") for p in posts if p.get("row_index") is not None)
    if len(current_indices) < 5:
        return False
    with _lock:
        if _last_reel_row_indices == current_indices:
            return False

    # Áudio aleatório da pasta MUSIC
    tracks = get_available_music_tracks()
    audio_path: Optional[str] = None
    if tracks:
        audio_path = random.choice(tracks)["path"]
    caption = generate_caption_for_posts(posts)

    try:
        video_bytes = create_reel_video(
            posts=posts,
            duration_per_slide=8.0,
            transition="fade",
            audio_path=audio_path,
            audio_volume=0.3,
        )
        video_url = upload_video_to_cloudinary(video_bytes)
        creation_id = ig_client.create_reel(video_url=video_url, caption=caption)
        media_id = ig_client.publish_media(creation_id, max_wait=180)
        with _lock:
            _last_reel_row_indices = current_indices
        _add_log_entry(
            True,
            f"Reel publicado (5 posts, 8s/slide): \"{caption[:50]}...\"",
            entry_type="reel",
            media_id=media_id,
        )
        logger.info("Autopublish: Reel publicado, media_id=%s", media_id)
        return True
    except Exception as e:
        logger.exception("Autopublish Reel: falha")
        _add_log_entry(False, f"Reel automático falhou: {e}", entry_type="error")
        return False


def _loop(interval_minutes: int):
    """Loop interno do thread de background."""
    logger.info("Autopublish: thread iniciado (intervalo=%dmin)", interval_minutes)
    interval_secs = interval_minutes * 60
    while not _stop_event.is_set():
        try:
            result = run_once()
            if result is True:
                # Publicou — verificar imediatamente se ha mais posts prontos
                continue
        except Exception:
            logger.exception("Autopublish: erro no loop")
        try:
            from instagram_poster.config import get_autopublish_reel_every_5
            if get_autopublish_reel_every_5():
                try_publish_auto_reel()
        except Exception:
            logger.exception("Autopublish: erro ao tentar Reel automático")
        _stop_event.wait(timeout=interval_secs)
    logger.info("Autopublish: thread parado")


def start_background_loop(interval_minutes: int = 5) -> bool:
    """Inicia o thread de background. Retorna True se iniciou, False se ja estava a correr."""
    global _thread, _started_at
    with _lock:
        if _thread is not None and _thread.is_alive():
            return False
        _stop_event.clear()
        _started_at = datetime.now()
        _thread = threading.Thread(
            target=_loop,
            args=(interval_minutes,),
            daemon=True,
            name="autopublish",
        )
        _thread.start()
    _add_log_entry(None, f"Autopublish iniciado (cada {interval_minutes} min)", entry_type="start")
    return True


def stop_background_loop() -> bool:
    """Para o thread de background. Retorna True se parou, False se nao estava a correr."""
    global _thread, _started_at
    with _lock:
        if _thread is None or not _thread.is_alive():
            return False
    _stop_event.set()
    _thread.join(timeout=10)
    with _lock:
        _thread = None
        _started_at = None
    _add_log_entry(None, "Autopublish parado", entry_type="stop")
    return True
