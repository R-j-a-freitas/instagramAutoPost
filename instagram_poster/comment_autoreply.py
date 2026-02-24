"""
Autoresposta a comentários nos posts do Instagram.
Responde com emoji de agradecimento (ex.: 🙏) aos comentários que ainda não têm resposta nossa.
Garante uma única resposta por comentário (ficheiro local + verificação na API).
Nota: A API do Instagram não permite dar like em comentários.
"""
import json
import logging
from pathlib import Path

from instagram_poster.config import get_ig_business_id
from instagram_poster.ig_client import get_comments, get_media_ids, reply_to_comment

logger = logging.getLogger(__name__)

_REPLIED_FILE = Path(__file__).resolve().parent.parent / ".comment_autoreply_replied.json"
_DEFAULT_MESSAGE = "🙏"


def _load_replied_ids() -> set[str]:
    """Carrega os IDs de comentários a que já respondemos."""
    if not _REPLIED_FILE.exists():
        return set()
    try:
        data = json.loads(_REPLIED_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(data)
        if isinstance(data, dict) and "replied" in data:
            return set(data["replied"])
        return set()
    except Exception as e:
        logger.warning("Não foi possível carregar ficheiro de comentários respondidos: %s", e)
        return set()


def _save_replied_id(comment_id: str) -> None:
    """Adiciona um comment_id ao ficheiro de respondidos (evita duplicados em execuções paralelas)."""
    replied = _load_replied_ids()
    replied.add(comment_id)
    try:
        _REPLIED_FILE.parent.mkdir(parents=True, exist_ok=True)
        _REPLIED_FILE.write_text(json.dumps(list(replied), ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning("Não foi possível gravar ficheiro de comentários respondidos: %s", e)


def _remove_replied_id(comment_id: str) -> None:
    """Remove um comment_id do ficheiro (quando a resposta falhou, para permitir retry)."""
    replied = _load_replied_ids()
    replied.discard(comment_id)
    try:
        _REPLIED_FILE.write_text(json.dumps(list(replied), ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning("Não foi possível actualizar ficheiro de comentários respondidos: %s", e)


def _we_already_replied(comment: dict) -> bool:
    """Verifica se já respondemos a este comentário (via replies ou ficheiro)."""
    comment_id = comment.get("id")
    if not comment_id:
        return True
    if comment_id in _load_replied_ids():
        return True
    replies = comment.get("replies") or {}
    reply_list = replies.get("data") if isinstance(replies, dict) else []
    if not reply_list:
        return False
    our_id = get_ig_business_id()
    for r in reply_list:
        from_info = r.get("from") or {}
        reply_author_id = from_info.get("id") if isinstance(from_info, dict) else None
        if reply_author_id == our_id:
            return True
    return False


def run_autoreply(
    message: str = _DEFAULT_MESSAGE,
    max_media: int = 10,
    delay_seconds: float = 2.0,
) -> dict:
    """
    Percorre os posts recentes, obtém comentários e responde aos que ainda não têm resposta nossa.
    Devolve {"replied": N, "skipped": M, "errors": [...], "log": [...], "media_count": N, "comments_total": N}.
    """
    import time

    replied_count = 0
    skipped_count = 0
    errors: list[str] = []
    log: list[str] = []

    try:
        media_ids = get_media_ids(limit=max_media)
        log.append(f"Verificados {len(media_ids)} post(s).")
    except Exception as e:
        errors.append(f"Erro ao obter posts: {e}")
        return {"replied": 0, "skipped": 0, "errors": errors, "log": [f"Erro: {e}"], "media_count": 0, "comments_total": 0}

    comments_total = 0
    for media_id in media_ids:
        try:
            comments = get_comments(media_id)
        except Exception as e:
            errors.append(f"Erro ao obter comentários do post {media_id}: {e}")
            log.append(f"Post {media_id}: erro ao obter comentários — {e}")
            continue

        comments_total += len(comments)
        if comments:
            log.append(f"Post {media_id}: {len(comments)} comentário(s).")

        for comment in comments:
            username = comment.get("username", "?")
            text_preview = (comment.get("text") or "")[:40]
            if _we_already_replied(comment):
                skipped_count += 1
                log.append(f"  — Ignorado (já respondido): @{username} «{text_preview}...»")
                continue
            comment_id = comment["id"]
            _save_replied_id(comment_id)
            try:
                reply_to_comment(comment_id, message)
                replied_count += 1
                log.append(f"  ✓ Respondido: @{username} «{text_preview}...»")
                logger.info("Autoresposta enviada ao comentário %s: %s", comment["id"], message)
                if delay_seconds > 0:
                    time.sleep(delay_seconds)
            except Exception as e:
                _remove_replied_id(comment_id)
                errors.append(f"Erro ao responder ao comentário {comment_id}: {e}")
                log.append(f"  ✗ Erro ao responder @{username}: {e}")

    if not log:
        log.append("Nenhum comentário encontrado nos posts verificados.")

    return {
        "replied": replied_count,
        "skipped": skipped_count,
        "errors": errors,
        "log": log,
        "media_count": len(media_ids),
        "comments_total": comments_total,
    }
