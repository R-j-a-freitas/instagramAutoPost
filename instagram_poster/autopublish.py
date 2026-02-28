"""
Motor de publicacao automatica.
- run_once(): verifica e publica o proximo post pronto (usado pelo CLI e pelo thread).
- start_background_loop() / stop_background_loop(): thread de background dentro do Streamlit.
- try_publish_auto_reel(): gera e publica um Reel quando ha 5 posts (8s/slide, fade, audio MUSIC).
"""
import json
import logging
import os
import random
import threading
import time as _time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LOG_FILE = _PROJECT_ROOT / ".autopublish_log.json"
_STOPPED_FILE = _PROJECT_ROOT / ".autopublish_stopped"
_REEL_LOCK_FILE = _PROJECT_ROOT / ".autopublish_reel.lock"
_STORY_REUSE_LOCK_FILE = _PROJECT_ROOT / ".autopublish_story_reuse.lock"
_MEDIA_LOCK_STALE_SEC = 120  # lock com mais de 2 min é considerado órfão


@contextmanager
def _file_lock(lock_path: Path) -> Generator[bool, None, None]:
    """
    Lock entre processos. Se outro processo tiver o lock activo, devolve False.
    """
    acquired = False
    fd = None
    try:
        if lock_path.exists():
            mtime = lock_path.stat().st_mtime
            if _time.time() - mtime < _MEDIA_LOCK_STALE_SEC:
                yield False
                return
            try:
                lock_path.unlink()
            except OSError:
                yield False
                return
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            yield False
            return
        acquired = True
        yield True
    finally:
        if acquired and fd is not None:
            try:
                os.close(fd)
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass


_REEL_MARK_USED_RETRIES = 3
_REEL_MARK_USED_RETRY_DELAY_SEC = 2

_lock = threading.Lock()
_stop_event = threading.Event()
_thread: Optional[threading.Thread] = None

_log: list[dict[str, Any]] = []
_last_log_file_mtime: float = 0.0  # mtime do ficheiro na última carga; permite recarregar quando outro processo (ex. Task Scheduler) grava
_last_check: Optional[datetime] = None
_started_at: Optional[datetime] = None
_total_published: int = 0
_total_errors: int = 0
_last_reel_row_indices: Optional[frozenset] = None
_last_reel_at: Optional[datetime] = None  # último Reel (auto ou reuse) — usado para intervalo de reuse
_last_story_reuse_at: Optional[datetime] = None  # última Story (com post ou reuse)
_current_interval_minutes: Optional[int] = None


def _serialize_log_entry(e: dict[str, Any]) -> dict[str, Any]:
    out = dict(e)
    if "timestamp" in out and hasattr(out["timestamp"], "isoformat"):
        out["timestamp"] = out["timestamp"].isoformat()
    return out


def _deserialize_log_entry(e: dict[str, Any]) -> dict[str, Any]:
    out = dict(e)
    if "timestamp" in out and isinstance(out["timestamp"], str):
        try:
            out["timestamp"] = datetime.fromisoformat(out["timestamp"])
        except (ValueError, TypeError):
            pass
    return out


def _load_log_from_file() -> None:
    """Carrega o log do ficheiro para memória e restaura timestamps da última Story/Reel."""
    global _log, _total_published, _total_errors, _last_reel_at, _last_story_reuse_at, _last_log_file_mtime
    if not _LOG_FILE.exists():
        return
    try:
        data = json.loads(_LOG_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            loaded = [_deserialize_log_entry(e) for e in data]
            with _lock:
                _log[:] = loaded[-100:]
                _last_log_file_mtime = _LOG_FILE.stat().st_mtime
                _total_published = sum(1 for x in _log if x.get("type") == "publish" and x.get("success") is True)
                _total_errors = sum(1 for x in _log if x.get("type") == "error" and x.get("success") is False)
                _last_reel_at = None
                _last_story_reuse_at = None
                for e in reversed(_log):
                    ts = e.get("timestamp")
                    if ts and hasattr(ts, "year") and e.get("type") == "reel":
                        _last_reel_at = ts
                        break
                for e in reversed(_log):
                    ts = e.get("timestamp")
                    if ts and hasattr(ts, "year") and e.get("type") == "story":
                        _last_story_reuse_at = ts
                        break
    except Exception as e:
        logger.warning("Não foi possível carregar log do autopublish: %s", e)


def _save_log_to_file() -> None:
    """Persiste o log em ficheiro para sobreviver à navegação e reinícios."""
    global _last_log_file_mtime
    try:
        with _lock:
            data = [_serialize_log_entry(e) for e in _log]
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LOG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
        if _LOG_FILE.exists():
            _last_log_file_mtime = _LOG_FILE.stat().st_mtime
    except Exception as e:
        logger.warning("Não foi possível gravar log do autopublish: %s", e)


def trim_old_check_entries(max_age_hours: int = 48) -> int:
    """Remove entradas 'check' com mais de max_age_hours. Devolve número removido."""
    global _log
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    with _lock:
        kept = []
        removed = 0
        for e in _log:
            if e.get("type") == "check":
                ts = e.get("timestamp")
                if ts and hasattr(ts, "year") and ts < cutoff:
                    removed += 1
                    continue
            kept.append(e)
        _log[:] = kept
    if removed:
        try:
            _save_log_to_file()
        except Exception:
            pass
    return removed


def clear_check_entries() -> int:
    """Remove todas as entradas de tipo 'check' do log. Devolve o número removido."""
    global _log
    with _lock:
        before = len(_log)
        _log[:] = [e for e in _log if e.get("type") != "check"]
        removed = before - len(_log)
    if removed:
        try:
            _save_log_to_file()
        except Exception:
            pass
    return removed


def clear_error_entries() -> int:
    """Remove todas as entradas de tipo 'error' do log. Devolve o número removido."""
    global _log, _total_errors
    with _lock:
        before = len(_log)
        _log[:] = [e for e in _log if e.get("type") != "error"]
        removed = before - len(_log)
        _total_errors = sum(1 for e in _log if e.get("type") == "error" and e.get("success") is False)
    if removed:
        try:
            _save_log_to_file()
        except Exception:
            pass
    return removed


def ensure_log_loaded_for_cli() -> None:
    """
    Carrega o log do ficheiro se _log estiver vazio.
    Obrigatório chamar no CLI antes de run_once() para não sobrescrever entradas existentes
    (posts, reels, stories) com um log vazio.
    """
    with _lock:
        if _log:
            return
    if _LOG_FILE.exists():
        _load_log_from_file()


def get_log() -> list[dict[str, Any]]:
    need_load = False
    with _lock:
        if _LOG_FILE.exists():
            mtime = _LOG_FILE.stat().st_mtime
            if not _log or mtime > _last_log_file_mtime:
                need_load = True
    if need_load:
        _load_log_from_file()
    trim_old_check_entries(max_age_hours=48)
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
            "total_comments": sum(1 for e in _log if e.get("type") == "comment"),
            "effective_interval_minutes": _current_interval_minutes,
        }


def get_effective_interval_minutes() -> Optional[int]:
    """Intervalo em minutos com que o thread foi iniciado (ou None se não estiver a correr)."""
    with _lock:
        return _current_interval_minutes


def is_running() -> bool:
    with _lock:
        return _thread is not None and _thread.is_alive()


def _add_log_entry(
    success: Optional[bool],
    message: str,
    entry_type: str = "info",
    post_data: Optional[dict[str, Any]] = None,
    media_id: Optional[str] = None,
    story_source: Optional[str] = None,
    comment_username: Optional[str] = None,
    comment_text: Optional[str] = None,
    comment_id: Optional[str] = None,
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
        if story_source is not None:
            entry["story_source"] = story_source
        if comment_username is not None:
            entry["comment_username"] = comment_username
        if comment_text is not None:
            entry["comment_text"] = comment_text
        if comment_id is not None:
            entry["comment_id"] = comment_id
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
    try:
        _save_log_to_file()
    except Exception:
        pass


def log_comment_reply(
    username: str,
    text_preview: str,
    comment_id: str,
) -> None:
    """Regista uma resposta a comentário no histórico."""
    _add_log_entry(
        True,
        f"Respondido: @{username} «{text_preview}...»",
        entry_type="comment",
        comment_username=username,
        comment_text=text_preview,
        comment_id=comment_id,
    )


def log_reel_manual(caption: str, media_id: str) -> None:
    """Regista um Reel publicado manualmente (página Reels) no histórico."""
    global _last_reel_at
    with _lock:
        _last_reel_at = datetime.now()
    cap = (caption or "").strip() or "Reel gerado automaticamente"
    msg = f"Reel publicado (manual): \"{cap[:50]}...\"" if len(cap) > 50 else f"Reel publicado (manual): \"{cap}\""
    _add_log_entry(True, msg, entry_type="reel", media_id=media_id)


def log_story_published(
    post_data: dict[str, Any],
    media_id: Optional[str] = None,
    source: str = "manual",
) -> None:
    """Regista uma Story publicada no histórico. source: 'reuse'|'com_post'|'aleatorio'|'manual'."""
    global _last_story_reuse_at
    with _lock:
        _last_story_reuse_at = datetime.now()
    _add_log_entry(
        True,
        "Story publicada",
        entry_type="story",
        post_data=post_data,
        media_id=media_id,
        story_source=source,
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
        ts = now.strftime("%H:%M:%S")
        date_str = now.date().isoformat()
        time_str = now.time().strftime("%H:%M") if now else ""
        logger.info("Autopublish: nada a publicar agora (hoje=%s, agora=%s)", date_str, time_str)
        # Detalhe da verificação (o ciclo já registou "Verificação às X (intervalo: N min)")
        _add_log_entry(
            None,
            f"Nenhum post pronto (hoje={date_str}, agora={time_str})",
            entry_type="check",
        )
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
    Se houver pelo menos 5 posts publicados que nunca foram usados em nenhum Reel,
    gera um Reel (8s/slide, fade, áudio aleatório da pasta MUSIC, caption que resume
    os posts) e publica no Instagram. Retorna True se publicou, False caso contrário.
    O Reel automático usa apenas posts nunca usados em Reels (allow_reuse=False).
    Usa lock entre processos para evitar duplicados.
    """
    global _last_reel_row_indices
    with _file_lock(_REEL_LOCK_FILE) as lock_ok:
        if not lock_ok:
            logger.info("Outro processo a publicar Reel; a ignorar para evitar duplicado.")
            return False
        return _try_publish_auto_reel_impl()


def _try_publish_auto_reel_impl() -> bool:
    """Implementação de try_publish_auto_reel (chamada dentro do lock)."""
    global _last_reel_row_indices
    try:
        from instagram_poster.reel_generator import (
            create_reel_video,
            generate_caption_for_posts,
            get_available_music_tracks,
            get_posts_for_reel,
            mark_posts_used_in_reel,
            upload_video_bytes,
        )
        from instagram_poster import ig_client
    except Exception as e:
        logger.warning("Autopublish Reel: import falhou: %s", e)
        return False

    # Apenas posts que nunca foram usados em Reels
    posts = get_posts_for_reel(n=5, allow_reuse=False)
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
        selected = random.choice(tracks)
        audio_path = selected["path"]
        logger.info("Reel automático: áudio escolhido: %s", selected.get("name", selected["file"]))
    else:
        logger.warning("Reel automático: nenhuma faixa de música encontrada, Reel será sem som")
    caption = generate_caption_for_posts(posts)

    try:
        video_bytes = create_reel_video(
            posts=posts,
            duration_per_slide=8.0,
            transition="fade",
            audio_path=audio_path,
            audio_volume=0.3,
        )
        video_url = upload_video_bytes(video_bytes)
        creation_id = ig_client.create_reel(video_url=video_url, caption=caption)
        media_id = ig_client.publish_media(creation_id, max_wait=240)
        row_indices = [p.get("row_index") for p in posts if p.get("row_index") is not None]
        last_err = None
        for attempt in range(1, _REEL_MARK_USED_RETRIES + 1):
            try:
                mark_posts_used_in_reel(row_indices)
                logger.info("Reel: posts marcados como usados (tentativa %s)", attempt)
                break
            except Exception as e:
                last_err = e
                logger.warning("Falha a marcar posts usados no Reel (tentativa %s/%s): %s", attempt, _REEL_MARK_USED_RETRIES, e)
                if attempt < _REEL_MARK_USED_RETRIES:
                    _time.sleep(_REEL_MARK_USED_RETRY_DELAY_SEC)
        else:
            msg = f"Reel publicado no Instagram mas falha a gravar posts usados em reels_used_rows.json após {_REEL_MARK_USED_RETRIES} tentativas. Atualiza manualmente assets/reels_used_rows.json com as linhas {row_indices} para evitar Reel duplicado. Erro: {last_err}"
            logger.error(msg)
            _add_log_entry(False, msg, entry_type="error")
        with _lock:
            _last_reel_row_indices = current_indices
            _last_reel_at = datetime.now()
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


def try_publish_reel_reuse_scheduled() -> bool:
    """
    Se estiver activo o agendamento de Reels com reutilização, e tiver passado o intervalo
    desde o último Reel (auto ou reuse), gera um Reel com 5 posts (podem ser já usados) e publica.
    Não marca os posts como usados (são reutilizados). Retorna True se publicou.
    Usa lock entre processos para evitar duplicados.
    """
    global _last_reel_at
    with _file_lock(_REEL_LOCK_FILE) as lock_ok:
        if not lock_ok:
            logger.info("Outro processo a publicar Reel; a ignorar para evitar duplicado.")
            return False
        return _try_publish_reel_reuse_impl()


def _try_publish_reel_reuse_impl() -> bool:
    """Implementação de try_publish_reel_reuse_scheduled (chamada dentro do lock)."""
    global _last_reel_at
    try:
        from instagram_poster.config import (
            get_autopublish_reel_reuse_interval_minutes,
            get_autopublish_reel_reuse_schedule_enabled,
        )
        from instagram_poster.reel_generator import (
            create_reel_video,
            generate_caption_for_posts,
            get_available_music_tracks,
            get_posts_for_reel,
            upload_video_bytes,
        )
        from instagram_poster import ig_client
    except Exception as e:
        logger.warning("Autopublish Reel reuse: import falhou: %s", e)
        return False

    if not get_autopublish_reel_reuse_schedule_enabled():
        return False

    interval_minutes = get_autopublish_reel_reuse_interval_minutes()
    now = datetime.now()
    with _lock:
        last = _last_reel_at
    if last is not None and (now - last).total_seconds() < interval_minutes * 60:
        return False

    posts = get_posts_for_reel(n=5, allow_reuse=True)
    if len(posts) < 5:
        return False

    tracks = get_available_music_tracks()
    audio_path: Optional[str] = None
    if tracks:
        selected = random.choice(tracks)
        audio_path = selected["path"]
        logger.info("Reel reuse agendado: áudio %s", selected.get("name", selected["file"]))
    else:
        logger.warning("Reel reuse agendado: nenhuma faixa de música")
    caption = generate_caption_for_posts(posts)

    try:
        video_bytes = create_reel_video(
            posts=posts,
            duration_per_slide=8.0,
            transition="fade",
            audio_path=audio_path,
            audio_volume=0.3,
        )
        video_url = upload_video_bytes(video_bytes)
        creation_id = ig_client.create_reel(video_url=video_url, caption=caption)
        media_id = ig_client.publish_media(creation_id, max_wait=240)
        with _lock:
            _last_reel_at = datetime.now()
        _add_log_entry(
            True,
            f"Reel (reuse agendado) publicado: \"{caption[:50]}...\"",
            entry_type="reel",
            media_id=media_id,
        )
        logger.info("Autopublish: Reel reuse agendado publicado, media_id=%s", media_id)
        return True
    except Exception as e:
        logger.exception("Autopublish Reel reuse: falha")
        _add_log_entry(False, f"Reel reuse agendado falhou: {e}", entry_type="error")
        return False


def try_publish_story_reuse_scheduled() -> bool:
    """
    Se estiver activo o agendamento de Stories com reutilização, e tiver passado o intervalo
    desde a última Story (reuse), publica uma Story usando a imagem do último post publicado.
    Retorna True se publicou. Usa lock entre processos para evitar duplicados.
    """
    global _last_story_reuse_at
    with _file_lock(_STORY_REUSE_LOCK_FILE) as lock_ok:
        if not lock_ok:
            logger.info("Outro processo a publicar Story reuse; a ignorar para evitar duplicado.")
            return False
        return _try_publish_story_reuse_impl()


def _try_publish_story_reuse_impl() -> bool:
    """Implementação de try_publish_story_reuse_scheduled (chamada dentro do lock)."""
    global _last_story_reuse_at
    try:
        from instagram_poster.config import (
            get_autopublish_story_reuse_interval_minutes,
            get_autopublish_story_reuse_schedule_enabled,
            get_autopublish_story_with_music,
        )
        from instagram_poster import image_generator, ig_client
        from instagram_poster.reel_generator import get_available_music_tracks
        from instagram_poster.sheets_client import get_published_posts_with_image
    except Exception as e:
        logger.warning("Autopublish Story reuse: import falhou: %s", e)
        return False

    if not get_autopublish_story_reuse_schedule_enabled():
        return False

    interval_minutes = get_autopublish_story_reuse_interval_minutes()
    now = datetime.now()
    with _lock:
        last = _last_story_reuse_at
    if last is None:
        last = now - timedelta(hours=25)
    if (now - last).total_seconds() < interval_minutes * 60:
        return False

    # Todos os posts publicados com imagem (não apenas os últimos 30); reuse usa o histórico todo
    posts = get_published_posts_with_image()
    if not posts:
        return False

    # Evitar reutilizar um post que já foi usado numa Story nas últimas 48 h (evita "cópias da mesma")
    cutoff = now - timedelta(hours=48)
    story_log = [e for e in get_log() if e.get("type") == "story"]
    recently_used_rows = set()
    for e in story_log:
        if e.get("row") is None:
            continue
        ts = e.get("timestamp")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                ts = now
        if (ts or now) >= cutoff:
            recently_used_rows.add(e.get("row"))
    recently_used_rows = frozenset(recently_used_rows)
    posts_available = [p for p in posts if p.get("row_index") not in recently_used_rows]
    if not posts_available:
        logger.info("Autopublish Story reuse: todos os posts recentes já usados em Story; a saltar para evitar duplicado.")
        return False
    post = random.choice(posts_available)
    image_url = (post.get("image_url") or "").strip()
    if not image_url:
        return False

    try:
        with_music = get_autopublish_story_with_music()
        tracks = get_available_music_tracks() if with_music else []
        audio_path = random.choice(tracks)["path"] if tracks else None
        if with_music and audio_path:
            story_url = image_generator.get_story_video_url_from_feed_image(
                image_url, audio_path=audio_path, duration_seconds=60.0
            )
            creation_id = ig_client.create_story(video_url=story_url)
        else:
            story_url = image_generator.get_story_image_url_from_feed_image(image_url)
            creation_id = ig_client.create_story(image_url=story_url)
        media_id = ig_client.publish_media(creation_id, max_wait=180)
        with _lock:
            _last_story_reuse_at = datetime.now()
        _add_log_entry(
            True,
            "Story (reuse agendado) publicada",
            entry_type="story",
            post_data=post,
            media_id=media_id,
            story_source="reuse",
        )
        logger.info("Autopublish: Story reuse agendada publicada, media_id=%s", media_id)
        return True
    except Exception as e:
        logger.exception("Autopublish Story reuse: falha")
        _add_log_entry(False, f"Story reuse agendada falhou: {e}", entry_type="error")
        return False


def _loop(interval_minutes: int):
    """Loop interno do thread de background."""
    logger.info("Autopublish: thread iniciado (intervalo=%dmin)", interval_minutes)
    interval_secs = interval_minutes * 60
    while not _stop_event.is_set():
        # Registar cada ciclo no log para o historico actualizar sempre no intervalo definido
        cycle_start = datetime.now()
        _add_log_entry(
            None,
            f"Verificação às {cycle_start.strftime('%H:%M:%S')} (intervalo: {interval_minutes} min)",
            entry_type="check",
        )
        try:
            result = run_once()
            # Não fazer continue aqui: o Sheet pode ainda nao ter atualizado (Published=yes),
            # e get_next_ready_post() na proxima iteracao devolveria o mesmo post, causando
            # publicacoes duplicadas. Publicar no maximo 1 post por ciclo e esperar o intervalo.
        except Exception:
            logger.exception("Autopublish: erro no loop")
        try:
            from instagram_poster.config import get_autopublish_reel_every_5
            if get_autopublish_reel_every_5():
                try_publish_auto_reel()
        except Exception:
            logger.exception("Autopublish: erro ao tentar Reel automático")
        try:
            try_publish_reel_reuse_scheduled()
        except Exception:
            logger.exception("Autopublish: erro ao tentar Reel reuse agendado")
        try:
            try_publish_story_reuse_scheduled()
        except Exception:
            logger.exception("Autopublish: erro ao tentar Story reuse agendada")
        try:
            from instagram_poster.config import get_autopublish_comment_autoreply
            if get_autopublish_comment_autoreply():
                from instagram_poster.comment_autoreply import run_autoreply
                result = run_autoreply(message="🙏", max_media=5, delay_seconds=1.0)
                for item in result.get("replied_items", []):
                    log_comment_reply(
                        username=item.get("username", "?"),
                        text_preview=item.get("text_preview", ""),
                        comment_id=item.get("comment_id", ""),
                    )
                if result.get("replied", 0) > 0:
                    logger.info("Autopublish: autoresposta a %d comentário(s)", result["replied"])
        except Exception:
            logger.exception("Autopublish: erro ao executar autoresposta a comentários")
        _stop_event.wait(timeout=interval_secs)
    logger.info("Autopublish: thread parado")


def start_background_loop(interval_minutes: int = 5) -> bool:
    """Inicia o thread de background. Retorna True se iniciou, False se ja estava a correr."""
    global _thread, _started_at, _current_interval_minutes, _log, _total_published, _total_errors
    user_had_stopped = _STOPPED_FILE.exists()
    with _lock:
        if _thread is not None and _thread.is_alive():
            return False
        _stop_event.clear()
        _started_at = datetime.now()
        _current_interval_minutes = interval_minutes
        if user_had_stopped:
            global _last_reel_at, _last_story_reuse_at
            _log.clear()
            _total_published = 0
            _total_errors = 0
            _last_reel_at = None
            _last_story_reuse_at = None
            try:
                _STOPPED_FILE.unlink(missing_ok=True)
                if _LOG_FILE.exists():
                    _LOG_FILE.unlink()
            except Exception:
                pass
    if not user_had_stopped:
        _load_log_from_file()
    with _lock:
        _thread = threading.Thread(
            target=_loop,
            args=(interval_minutes,),
            daemon=True,
            name="autopublish",
        )
        _thread.start()
    _add_log_entry(
        None,
        f"Autopublish iniciado — intervalo efectivo: {interval_minutes} min",
        entry_type="start",
    )
    return True


def stop_background_loop() -> bool:
    """Para o thread de background. Retorna True se parou, False se nao estava a correr."""
    global _thread, _started_at, _current_interval_minutes
    with _lock:
        if _thread is None or not _thread.is_alive():
            return False
    _stop_event.set()
    _thread.join(timeout=10)
    with _lock:
        _thread = None
        _started_at = None
        _current_interval_minutes = None
    _add_log_entry(None, "Autopublish parado", entry_type="stop")
    try:
        _STOPPED_FILE.touch()
    except Exception:
        pass
    return True
