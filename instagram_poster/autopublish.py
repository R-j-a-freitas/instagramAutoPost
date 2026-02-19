"""
Motor de publicacao automatica.
- run_once(): verifica e publica o proximo post pronto (usado pelo CLI e pelo thread).
- start_background_loop() / stop_background_loop(): thread de background dentro do Streamlit.
"""
import logging
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
        if success is True:
            _total_published += 1
        elif success is False:
            _total_errors += 1
        if len(_log) > 100:
            _log.pop(0)


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
