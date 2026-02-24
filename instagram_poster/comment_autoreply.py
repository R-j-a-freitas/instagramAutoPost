"""
Autoresposta a comentários nos posts do Instagram.
Responde com emoji de agradecimento (ex.: 🙏) aos comentários que ainda não têm resposta nossa.
Garante uma única resposta por comentário (ficheiros atómicos + verificação na API).
Nota: A API do Instagram não permite dar like em comentários.
"""
import json
import logging
from pathlib import Path

from instagram_poster.config import get_ig_business_id
from instagram_poster.ig_client import get_comments, get_media_ids, reply_to_comment

logger = logging.getLogger(__name__)

# Directorio com um ficheiro por comment_id — criação atómica evita race conditions
_REPLIED_DIR = Path(__file__).resolve().parent.parent / ".comment_autoreply_replied"
_OLD_REPLIED_FILE = Path(__file__).resolve().parent.parent / ".comment_autoreply_replied.json"
_DEFAULT_MESSAGE = "🙏"


def _migrate_old_replied_file() -> None:
    """Migra IDs do ficheiro JSON antigo para o novo formato (directorio de ficheiros)."""
    if not _OLD_REPLIED_FILE.exists():
        return
    try:
        data = json.loads(_OLD_REPLIED_FILE.read_text(encoding="utf-8"))
        ids = data if isinstance(data, list) else data.get("replied", []) if isinstance(data, dict) else []
        if not ids:
            return
        _REPLIED_DIR.mkdir(parents=True, exist_ok=True)
        for cid in ids:
            if cid:
                path = _replied_marker_path(str(cid))
                if not path.exists():
                    try:
                        path.open("x").close()
                    except OSError:
                        pass
        _OLD_REPLIED_FILE.rename(_OLD_REPLIED_FILE.with_suffix(".json.bak"))
        logger.info("Migrados %d comentários do ficheiro antigo para o novo formato.", len(ids))
    except Exception as e:
        logger.warning("Migração do ficheiro de comentários respondidos falhou: %s", e)


def _sanitize_comment_id(comment_id: str) -> str:
    """Sanitiza o comment_id para uso como nome de ficheiro (IDs do IG são numéricos)."""
    return str(comment_id).replace("/", "_").replace("\\", "_")


def _replied_marker_path(comment_id: str) -> Path:
    """Caminho do ficheiro marcador para um comment_id."""
    return _REPLIED_DIR / _sanitize_comment_id(comment_id)


def _try_claim_comment(comment_id: str) -> bool:
    """
    Tenta "reservar" o comentário para resposta (criação atómica).
    Devolve True se conseguirmos reservar (ninguém o fez antes), False se já estiver reservado.
    Funciona entre processos e reinícios — evita múltiplas respostas ao mesmo comentário.
    """
    path = _replied_marker_path(comment_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.open("x").close()  # Modo exclusivo: falha se já existir (FileExistsError)
        return True
    except FileExistsError:
        return False
    except OSError as e:
        logger.warning("Não foi possível criar marcador para comentário %s: %s", comment_id, e)
        return False


def _unclaim_comment(comment_id: str) -> None:
    """Remove o marcador (quando a resposta falhou, para permitir retry)."""
    try:
        p = _replied_marker_path(comment_id)
        if p.exists():
            p.unlink()
    except OSError as e:
        logger.warning("Não foi possível remover marcador do comentário %s: %s", comment_id, e)


def _we_already_replied(comment: dict) -> bool:
    """Verifica se já respondemos a este comentário (via replies na API ou ficheiro marcador)."""
    comment_id = comment.get("id")
    if not comment_id:
        return True
    # 1. Ficheiro marcador (persistente entre reinícios)
    if _replied_marker_path(comment_id).exists():
        return True
    # 2. Verificar na API se já temos resposta nossa (replies podem vir paginadas)
    replies = comment.get("replies") or {}
    reply_list = replies.get("data") if isinstance(replies, dict) else []
    if not reply_list:
        return False
    our_id = str(get_ig_business_id())
    for r in reply_list:
        from_info = r.get("from") or {}
        reply_author_id = from_info.get("id") if isinstance(from_info, dict) else None
        if reply_author_id is not None and str(reply_author_id) == our_id:
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

    _migrate_old_replied_file()

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
            # Reserva atómica: só um processo/thread consegue "ganhar" por comentário
            if not _try_claim_comment(comment_id):
                skipped_count += 1
                log.append(f"  — Ignorado (já reservado/respondido): @{username} «{text_preview}...»")
                continue
            try:
                reply_to_comment(comment_id, message)
                replied_count += 1
                log.append(f"  ✓ Respondido: @{username} «{text_preview}...»")
                logger.info("Autoresposta enviada ao comentário %s: %s", comment["id"], message)
                if delay_seconds > 0:
                    time.sleep(delay_seconds)
            except Exception as e:
                _unclaim_comment(comment_id)
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
