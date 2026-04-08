"""
Autoresposta a comentários nos posts do Instagram.
Suporta mensagens estáticas e IA (Pollinations) para respostas personalizadas.
GARANTIA: Uma única resposta por comentário — ficheiro JSON com lock, limite por execução, filtro de replies.
"""
import fcntl
import json
import logging
import re
import time as _time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from instagram_poster.ig_client import (
    get_comments,
    get_media_ids,
    get_my_id,
    reply_to_comment,
    get_media_caption,
)
from instagram_poster.text_generator import generate_text

logger = logging.getLogger(__name__)

_REPLIED_FILE = Path(__file__).resolve().parent.parent / ".comment_autoreply_replied.json"
_LOCK_FILE = Path(__file__).resolve().parent.parent / ".comment_autoreply.lock"
_ID_CACHE: dict[str, str] = {}

# Prompt de sistema para garantir o tom do canal @keepcalmnbepositive
_AI_REPLY_SYSTEM_PROMPT = """
You are @keepcalmnbepositive on Instagram. Your tone is calm, encouraging, and kind.
Niche: personal development, mindset, self-compassion, slow growth.
Goal: Respond to user comments in a friendly and professional way, always starting with their @username.
The response MUST ALWAYS be in ENGLISH, even if the user comments in another language.
Maximum 2 short sentences. Be authentic and genuinely helpful or appreciative. 
No toxic positivity. No hashtags.
"""


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
    
    if cid in _load_replied_ids_set():
        return True
    
    replies_obj = comment.get("replies") or {}
    reply_list = replies_obj.get("data") or [] if isinstance(replies_obj, dict) else []
    
    if reply_list:
        logger.info("Comentário %s já tem respostas no Instagram. Skip.", cid)
        return True
    
    return False


def _generate_ai_reply(username: str, comment_text: str, post_caption: str) -> str:
    """Gera uma resposta via IA (Pollinations) baseada no comentário e contexto do post."""
    user_prompt = (
        f"Context (Original Post Caption): \"{post_caption}\"\n"
        f"User @{username} commented: \"{comment_text}\"\n\n"
        f"Generate a kind and brief reply starting with @{username}:"
    )
    try:
        reply = generate_text(_AI_REPLY_SYSTEM_PROMPT, user_prompt)
        reply = reply.strip()
        # Garantir que começa com @username se o AI se esqueceu
        if not reply.startswith(f"@{username}"):
            reply = f"@{username} {reply}"
        # Truncar se for demasiado longo para a API (300 chars é o limite do params, mas vamos ser seguros)
        return reply[:280]
    except Exception as e:
        logger.warning("Falha ao gerar resposta IA para @%s: %s", username, e)
        return f"@{username} 🙏"


def run_autoreply(
    message: str = "🙏",
    max_media: int = 10,
    delay_seconds: float = 2.0,
    use_ai: bool = False,
) -> dict:
    lock_fd = open(_LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return {"replied": 0, "skipped": 0, "errors": ["Outra instância a correr."], "log": ["Ocupado."], "replied_items": [], "media_count": 0, "comments_total": 0}

    try:
        return _run_autoreply_impl(message, max_media, delay_seconds, use_ai)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def _run_autoreply_impl(message: str, max_media: int, delay_seconds: float, use_ai: bool) -> dict:
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
    my_ids = _get_all_my_ids()

    for media_id in media_ids:
        if replied_count >= 15: break
        
        post_caption = ""
        if use_ai:
            post_caption = get_media_caption(media_id)

        try:
            comments = get_comments(media_id)
        except Exception: continue

        for comment in (comments or []):
            if replied_count >= 15: break
            cid_raw = comment.get("id")
            cid = re.sub(r"\D", "", str(cid_raw or ""))
            if not cid or cid in processed_ids: continue
            processed_ids.add(cid)

            if bool(comment.get("parent_id") or comment.get("parent")): continue
            
            author_id = str((comment.get("from") or {}).get("id") or "")
            if author_id in my_ids: 
                skipped_count += 1
                continue
            
            if cid in replied_ids or _we_already_replied_to_comment(comment):
                if cid not in replied_ids:
                    replied_ids.add(cid)
                    _save_replied_ids(replied_ids)
                skipped_count += 1
                continue
            
            # Preparar resposta
            username = comment.get("username") or (comment.get("from") or {}).get("username") or "?"
            username = str(username)
            comment_text = str(comment.get("text") or "")
            
            if use_ai:
                final_msg = _generate_ai_reply(username, comment_text, post_caption)
            else:
                # Comportamento padrão: @username + emoji/msg
                final_msg = f"@{username} {message}" if not message.startswith("@") else message

            try:
                reply_to_comment(cid_raw, final_msg)
                replied_count += 1
                replied_ids.add(cid)
                _save_replied_ids(replied_ids)
                replied_items.append({"username": username, "comment_id": cid, "message": final_msg})
                log.append(f"  ✓ @{username}: {final_msg[:30]}...")
                if delay_seconds > 0: _time.sleep(delay_seconds)
            except Exception as e:
                errors.append(f"Erro @{username}: {e}")

    return {
        "replied": replied_count,
        "skipped": skipped_count,
        "errors": errors,
        "log": log or ["Nada novo."],
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
