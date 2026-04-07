"""
Autoresposta a comentários nos posts do Instagram.
Responde com emoji de agradecimento (ex.: 🙏) aos comentários que ainda não têm resposta nossa.
GARANTIA: Uma única resposta por comentário — ficheiro JSON com lock, limite por execução, filtro de replies.
Nota: A API do Instagram não permite dar like em comentários.
"""
import fcntl
import json
import logging
import re
import time as _time
from datetime import datetime, timezone
from pathlib import Path

from instagram_poster.ig_client import get_comments, get_media_ids, get_my_id, reply_to_comment

logger = logging.getLogger(__name__)

_REPLIED_FILE = Path(__file__).resolve().parent.parent / ".comment_autoreply_replied.json"
_LOCK_FILE = Path(__file__).resolve().parent.parent / ".comment_autoreply.lock"
_LAST_RUN_FILE = Path(__file__).resolve().parent.parent / ".comment_autoreply_last_run.json"
_DEFAULT_MESSAGE = "🙏"
_MAX_REPLIES_PER_RUN = 15
_ID_CACHE: dict[str, str] = {}


def _get_all_my_ids() -> set[str]:
    """Obtém todos os IDs possíveis para o nosso utilizador (Scoped e Business)."""
    global _ID_CACHE
    ids = set()
    try:
        if "sid" not in _ID_CACHE:
            sid = get_my_id()
            if sid: _ID_CACHE["sid"] = str(sid)
        if _ID_CACHE.get("sid"): ids.add(_ID_CACHE["sid"])
    except Exception:
        pass
    
    try:
        from instagram_poster.config import get_ig_business_id
        if "bid" not in _ID_CACHE:
            bid = get_ig_business_id()
            if bid: _ID_CACHE["bid"] = str(bid)
        if _ID_CACHE.get("bid"): ids.add(_ID_CACHE["bid"])
    except Exception:
        pass
    return ids


def _load_replied_ids_set() -> set[str]:
    if not _REPLIED_FILE.exists():
        return set()
    try:
        txt = _REPLIED_FILE.read_text(encoding="utf-8").strip()
        if not txt: return set()
        data = json.loads(txt)
        ids_raw = data if isinstance(data, list) else data.get("ids", []) if isinstance(data, dict) else []
        return {re.sub(r"\D", "", str(x)) for x in (ids_raw or []) if x}
    except Exception:
        return set()


def _save_replied_ids(ids: set[str]):
    try:
        _REPLIED_FILE.parent.mkdir(parents=True, exist_ok=True)
        _REPLIED_FILE.write_text(json.dumps(list(ids)), encoding="utf-8")
    except Exception:
        pass


def _we_already_replied_to_comment(comment: dict) -> bool:
    if not isinstance(comment, dict): return True
    cid = re.sub(r"\D", "", str(comment.get("id", "")))
    if not cid: return True
    
    # 1. Check local file (memória persistente)
    if cid in _load_replied_ids_set():
        return True
    
    # 2. Check API replies (qualquer resposta existente bloqueia nova autoreply)
    replies_obj = comment.get("replies") or {}
    reply_list = replies_obj.get("data") or [] if isinstance(replies_obj, dict) else []
    
    if reply_list:
        # Se já existir qualquer resposta (nossa ou de outros), não duplicamos a autoreply.
        logger.info("Comentário %s já tem respostas no Instagram. A transitar para skip.", cid)
        return True
    
    return False


def run_autoreply(
    message: str = "🙏",
    max_media: int = 10,
    delay_seconds: float = 2.0,
) -> dict:
    # Lock global para evitar que UI e Background corram ao mesmo tempo
    lock_fd = open(_LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return {"replied": 0, "skipped": 0, "errors": ["Outra instância da autoresposta já está a correr."], "log": ["Ocupado."], "replied_items": [], "media_count": 0, "comments_total": 0}

    try:
        return _run_autoreply_impl(message, max_media, delay_seconds)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def _run_autoreply_impl(message: str, max_media: int, delay_seconds: float) -> dict:
    replied_count = 0
    skipped_count = 0
    errors: list[str] = []
    log: list[str] = []
    replied_items: list[dict[str, str]] = []
    
    try:
        media_ids_raw = get_media_ids(limit=max_media)
        media_ids = [str(m) for m in (media_ids_raw or []) if m]
        log.append(f"Verificando {len(media_ids)} post(s).")
    except Exception as e:
        return {"replied": 0, "skipped": 0, "errors": [str(e)], "log": [f"Erro: {e}"], "replied_items": [], "media_count": 0, "comments_total": 0}

    processed_ids: set[str] = set()
    replied_ids = _load_replied_ids_set()

    for media_id in media_ids:
        if replied_count >= 15: break
        try:
            comments = get_comments(media_id)
        except Exception: continue

        for comment in (comments or []):
            if replied_count >= 15: break
            cid_raw = comment.get("id")
            cid = re.sub(r"\D", "", str(cid_raw or ""))
            if not cid or cid in processed_ids: continue
            processed_ids.add(cid)

            # Filtros
            if bool(comment.get("parent_id") or comment.get("parent")): continue
            
            # Check if it is from us
            author_id = str((comment.get("from") or {}).get("id") or "")
            if author_id in _get_all_my_ids(): 
                skipped_count += 1
                continue
            
            # Check if we already replied (File + API)
            if cid in replied_ids or _we_already_replied_to_comment(comment):
                if cid not in replied_ids:
                    replied_ids.add(cid)
                    _save_replied_ids(replied_ids)
                skipped_count += 1
                continue
            
            # Respond
            try:
                reply_to_comment(cid_raw, message)
                replied_count += 1
                replied_ids.add(cid)
                _save_replied_ids(replied_ids)
                replied_items.append({"username": str(comment.get("username", "?")), "comment_id": cid})
                log.append(f"  ✓ Respondido: @{comment.get('username')}")
                if delay_seconds > 0: _time.sleep(delay_seconds)
            except Exception as e:
                errors.append(f"Erro no comentário {cid}: {e}")

    return {
        "replied": replied_count,
        "skipped": skipped_count,
        "errors": errors,
        "log": log or ["Nenhum comentário novo."],
        "replied_items": replied_items,
        "media_count": len(media_ids),
        "comments_total": len(processed_ids),
    }


def get_replied_count() -> int:
    return len(_load_replied_ids_set())


def reset_replied_ids() -> int:
    count = get_replied_count()
    _save_replied_ids(set())
    return count
