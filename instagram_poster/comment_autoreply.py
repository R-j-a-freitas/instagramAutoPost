"""
Autoresposta a comentários nos posts do Instagram.
Responde com emoji de agradecimento (ex.: 🙏) aos comentários que ainda não têm resposta nossa.
GARANTIA: Uma única resposta por comentário — ficheiro JSON com lock, limite por execução, filtro de replies.
Processa apenas comentários novos (posteriores à última verificação). Espera pela resposta da API antes de avançar.
Nota: A API do Instagram não permite dar like em comentários.
"""
import json
import logging
import re
import time as _time
from datetime import datetime, timezone
from pathlib import Path

from instagram_poster.ig_client import get_comments, get_media_ids, get_my_id, reply_to_comment

logger = logging.getLogger(__name__)

_REPLIED_FILE = Path(__file__).resolve().parent.parent / ".comment_autoreply_replied.json"
_LAST_RUN_FILE = Path(__file__).resolve().parent.parent / ".comment_autoreply_last_run.json"
_REPLIED_DIR_OLD = Path(__file__).resolve().parent.parent / ".comment_autoreply_replied"
_DEFAULT_MESSAGE = "🙏"
_MAX_REPLIES_PER_RUN = 5  # Limite absoluto por execução — protecção contra bugs
_DEFAULT_DELAY_SECONDS = 3.0  # Espera entre respostas (aumentado para evitar rate limit)
_OUR_ID_CACHE: str | None = None


def _get_our_id() -> str:
    """Obtém o nosso user ID para comparação com from.id. Com cache."""
    global _OUR_ID_CACHE
    if _OUR_ID_CACHE is not None:
        return _OUR_ID_CACHE
    try:
        _OUR_ID_CACHE = get_my_id()
        return _OUR_ID_CACHE
    except Exception:
        from instagram_poster.config import get_ig_business_id
        _OUR_ID_CACHE = str(get_ig_business_id())
        return _OUR_ID_CACHE


def _load_last_run_timestamp() -> datetime | None:
    """Carrega o timestamp da última verificação (início da última execução)."""
    if not _LAST_RUN_FILE.exists():
        return None
    try:
        data = json.loads(_LAST_RUN_FILE.read_text(encoding="utf-8"))
        ts_str = data.get("last_run") if isinstance(data, dict) else None
        if not ts_str:
            return None
        s = str(ts_str).replace("Z", "+00:00").replace("+0000", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception as e:
        logger.warning("Não foi possível carregar last_run: %s", e)
        return None


def _save_last_run_timestamp(dt: datetime) -> None:
    """Guarda o timestamp do início desta execução."""
    try:
        _LAST_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LAST_RUN_FILE.write_text(json.dumps({"last_run": dt.isoformat()}, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning("Não foi possível gravar last_run: %s", e)


def _parse_comment_timestamp(comment: dict) -> datetime | None:
    """Extrai e parseia o timestamp do comentário (formato ISO da API)."""
    ts = comment.get("timestamp")
    if not ts:
        return None
    try:
        s = str(ts).replace("Z", "+00:00").replace("+0000", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _normalize_comment_id(comment_id: str) -> str:
    """Extrai apenas dígitos — IDs do IG são numéricos. Evita variantes como '123' vs '123.0'."""
    return re.sub(r"\D", "", str(comment_id)) or str(comment_id).strip()


def _load_replied_ids() -> set[str]:
    """Carrega o conjunto de IDs já respondidos."""
    if not _REPLIED_FILE.exists():
        return set()
    try:
        data = json.loads(_REPLIED_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {_normalize_comment_id(x) for x in data if x}
        if isinstance(data, dict):
            ids = data.get("ids") or data.get("replied") or []
            return {_normalize_comment_id(x) for x in ids if x}
        return set()
    except Exception as e:
        logger.warning("Não foi possível carregar ficheiro de respondidos: %s", e)
        return set()


def _comment_is_from_us(comment: dict) -> bool:
    """Nunca responder aos nossos próprios comentários ou replies."""
    from_info = comment.get("from") or {}
    author_id = from_info.get("id") if isinstance(from_info, dict) else None
    if author_id is None:
        return False
    return str(author_id) == _get_our_id()


def _we_already_replied(comment: dict) -> bool:
    """Verifica se já respondemos (ficheiro ou replies na API)."""
    comment_id = comment.get("id")
    if not comment_id:
        return True
    cid = _normalize_comment_id(comment_id)
    if cid in _load_replied_ids():
        return True
    replies = comment.get("replies") or {}
    reply_list = replies.get("data") if isinstance(replies, dict) else []
    our_id = _get_our_id()
    for r in reply_list:
        from_info = r.get("from") or {}
        aid = from_info.get("id") if isinstance(from_info, dict) else None
        if aid is not None and str(aid) == our_id:
            return True
    return False


def _is_reply_not_top_level(comment: dict) -> bool:
    """Se tiver parent_id ou for resposta, não processar — só top-level."""
    return bool(comment.get("parent_id") or comment.get("parent") or comment.get("reply_to"))


def _migrate_from_dir_format() -> None:
    """Migra do antigo formato baseado em diretório para o novo ficheiro JSON."""
    if not _REPLIED_DIR_OLD.exists() or not _REPLIED_DIR_OLD.is_dir():
        return
    try:
        import shutil
        old_ids = []
        for f in _REPLIED_DIR_OLD.iterdir():
            if f.is_file():
                cid = _normalize_comment_id(f.name)
                if cid:
                    old_ids.append(cid)
        if old_ids:
            current = _load_replied_ids()
            current.update(old_ids)
            _REPLIED_FILE.write_text(json.dumps(list(current)), encoding="utf-8")
        shutil.rmtree(str(_REPLIED_DIR_OLD), ignore_errors=True)
        logger.info(f"Migrados {len(old_ids)} comentários do formato diretório.")
    except Exception as e:
        logger.warning("Falha a migrar o diretório antigo de respostas: %s", e)


def _try_claim_replied_id(comment_id: str) -> bool:
    """Verifica e guarda um ID de comentário. Retorna False se já estiver guardado."""
    current = _load_replied_ids()
    cid = _normalize_comment_id(comment_id)
    if not cid or cid in current:
        return False
    current.add(cid)
    try:
        _REPLIED_FILE.parent.mkdir(parents=True, exist_ok=True)
        _REPLIED_FILE.write_text(json.dumps(list(current)), encoding="utf-8")
        return True
    except Exception as e:
        logger.error("Falha a reclamar o ID de resposta %s: %s", cid, e)
        return False


def _remove_replied_id(comment_id: str) -> None:
    """Remove um ID guardado em memória caso ocorra erro ao responder via API."""
    current = _load_replied_ids()
    cid = _normalize_comment_id(comment_id)
    if cid in current:
        current.remove(cid)
        try:
            _REPLIED_FILE.write_text(json.dumps(list(current)), encoding="utf-8")
        except Exception as e:
            logger.error("Falha a remover o ID de resposta %s: %s", cid, e)


def run_autoreply(
    message: str = _DEFAULT_MESSAGE,
    max_media: int = 10,
    delay_seconds: float = _DEFAULT_DELAY_SECONDS,
) -> dict:
    """
    Responde aos comentários novos que ainda não têm resposta.
    - Processa apenas comentários posteriores à última verificação.
    - Espera pela resposta da API antes de avançar para o próximo.
    - Pausa configurável entre respostas (default 3s).
    Máximo _MAX_REPLIES_PER_RUN respostas por execução.
    """
    _migrate_from_dir_format()
    run_start = datetime.now(timezone.utc)
    last_run = _load_last_run_timestamp()

    replied_count = 0
    skipped_count = 0
    errors: list[str] = []
    log: list[str] = []
    replied_items: list[dict[str, str]] = []
    replied_to_this_run: set[str] = set()

    try:
        media_ids = get_media_ids(limit=max_media)
        log.append(f"Verificados {len(media_ids)} post(s).")
    except Exception as e:
        errors.append(f"Erro ao obter posts: {e}")
        return {"replied": 0, "skipped": 0, "errors": errors, "log": [f"Erro: {e}"], "replied_items": [], "media_count": 0, "comments_total": 0}

    comments_total = 0
    processed_ids: set[str] = set()

    for media_id in media_ids:
        if replied_count >= _MAX_REPLIES_PER_RUN:
            log.append(f"Limite de {_MAX_REPLIES_PER_RUN} respostas por execução atingido.")
            break
        try:
            comments = get_comments(media_id)
        except Exception as e:
            errors.append(f"Erro ao obter comentários do post {media_id}: {e}")
            log.append(f"Post {media_id}: erro — {e}")
            continue

        comments_total += len(comments)
        if comments:
            log.append(f"Post {media_id}: {len(comments)} comentário(s).")

        for comment in comments:
            if replied_count >= _MAX_REPLIES_PER_RUN:
                break
            if last_run is not None:
                comment_ts = _parse_comment_timestamp(comment)
                if comment_ts is not None and comment_ts <= last_run:
                    skipped_count += 1
                    log.append(f"  — Ignorado (anterior à última verificação): @{comment.get('username', '?')}")
                    continue
            comment_id_raw = comment.get("id")
            if not comment_id_raw:
                continue
            comment_id = _normalize_comment_id(str(comment_id_raw))
            if not comment_id:
                continue
            if comment_id in processed_ids:
                skipped_count += 1
                log.append(f"  — Ignorado (duplicado): @{comment.get('username', '?')}")
                continue
            processed_ids.add(comment_id)

            if _is_reply_not_top_level(comment):
                skipped_count += 1
                log.append(f"  — Ignorado (resposta, não top-level): @{comment.get('username', '?')}")
                continue
            if _comment_is_from_us(comment):
                skipped_count += 1
                log.append(f"  — Ignorado (comentário nosso): @{comment.get('username', '?')}")
                continue
            if _we_already_replied(comment):
                skipped_count += 1
                log.append(f"  — Ignorado (já respondido): @{comment.get('username', '?')}")
                continue
            if comment_id in replied_to_this_run:
                logger.error("ERRO: tentativa de responder ao mesmo comentário %s duas vezes nesta execução", comment_id)
                skipped_count += 1
                continue

            if not _try_claim_replied_id(comment_id):
                skipped_count += 1
                log.append(f"  — Ignorado (já reservado/respondido): @{comment.get('username', '?')}")
                continue
            replied_to_this_run.add(comment_id)

            username = comment.get("username", "?")
            text_preview = (comment.get("text") or "")[:40]
            try:
                reply_to_comment(comment_id_raw, message)
                replied_count += 1
                replied_items.append({"username": username, "text_preview": text_preview, "comment_id": comment_id})
                log.append(f"  ✓ Respondido: @{username} «{text_preview}...»")
                logger.info("Autoresposta enviada ao comentário %s", comment_id)
                if delay_seconds > 0:
                    _time.sleep(delay_seconds)
            except Exception as e:
                _remove_replied_id(comment_id)
                replied_to_this_run.discard(comment_id)
                errors.append(f"Erro ao responder ao comentário {comment_id}: {e}")
                log.append(f"  ✗ Erro @{username}: {e}")

    _save_last_run_timestamp(run_start)
    if not log:
        log.append("Nenhum comentário encontrado nos posts verificados.")

    return {
        "replied": replied_count,
        "skipped": skipped_count,
        "errors": errors,
        "log": log,
        "replied_items": replied_items,
        "media_count": len(media_ids),
        "comments_total": comments_total,
    }
