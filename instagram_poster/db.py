"""
Base de dados interna (SQLite) para os posts do Instagram.
Substitui o Google Sheets como fonte de dados: agendamento, estado de publicação,
prompts de imagem e legendas ficam guardados localmente em posts.db.
"""
import logging
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _PROJECT_ROOT / "posts.db"

_COLUMNS = (
    "date", "time", "image_text", "caption", "gemini_prompt",
    "status", "published", "image_url", "image_prompt",
    "post_type", "slide2_text",
)

_TRUTHY = ("yes", "y", "1", "true")


@contextmanager
def _connect() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Cria a tabela de posts se ainda não existir. Chamado automaticamente ao importar o módulo."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL DEFAULT '',
                time TEXT NOT NULL DEFAULT '',
                image_text TEXT NOT NULL DEFAULT '',
                caption TEXT NOT NULL DEFAULT '',
                gemini_prompt TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '',
                published TEXT NOT NULL DEFAULT '',
                image_url TEXT NOT NULL DEFAULT '',
                image_prompt TEXT NOT NULL DEFAULT '',
                post_type TEXT NOT NULL DEFAULT 'single',
                slide2_text TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_date ON posts(date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status)")


init_db()


def _row_to_record(row: sqlite3.Row) -> dict[str, Any]:
    rec = {k: row[k] for k in _COLUMNS}
    rec["row_index"] = row["id"]
    return rec


def _parse_date(s: str) -> Optional[date]:
    """Parse de vários formatos de data: YYYY-MM-DD, DD/MM/YYYY, etc."""
    if not s:
        return None
    s = s.strip()
    if len(s) >= 10 and "-" in s[:5]:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    formats = ["%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d"]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            try:
                parts = s.split("/")
                if len(parts) == 3:
                    padded = f"{int(parts[0]):02d}/{int(parts[1]):02d}/{int(parts[2]):04d}"
                    return datetime.strptime(padded, "%d/%m/%Y").date()
            except Exception:
                continue
    return None


def _parse_time(s: str) -> Optional[time]:
    """Parse HH:MM ou HH:MM:SS."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None


def _is_true(s: str) -> bool:
    return (s or "").strip().lower() in _TRUTHY


def get_next_ready_post(today: Optional[date] = None, now: Optional[time] = None) -> Optional[dict[str, Any]]:
    """
    Devolve o próximo post pronto a publicar:
    status="ready", published vazio, date <= today (e opcionalmente time <= now).
    Ordenação: date, time.
    """
    today = today or date.today()
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM posts WHERE lower(status) = 'ready'").fetchall()

    candidates = []
    for row in rows:
        rec = _row_to_record(row)
        if _is_true(rec["published"]):
            continue
        d = _parse_date(rec["date"])
        if d is None or d > today:
            continue
        if d == today and now is not None:
            t = _parse_time(rec["time"])
            if t is not None and t > now:
                continue
        candidates.append((d, _parse_time(rec["time"]) or time(0, 0), rec))

    if not candidates:
        logger.info(
            "get_next_ready_post: 0 candidatos (critérios: date<=%s, status=ready, published vazio)", today
        )
        return None
    candidates.sort(key=lambda x: (x[0], x[1]))
    chosen = candidates[0][2]
    logger.info(
        "get_next_ready_post: %s candidato(s), próximo: id %s (%s %s)",
        len(candidates), chosen.get("row_index"), chosen.get("date", ""), chosen.get("time", ""),
    )
    return chosen


def get_upcoming_posts(n: int = 14, from_date: Optional[date] = None) -> list[dict[str, Any]]:
    """
    Devolve os próximos n posts a partir de from_date (default: hoje), ordenados por date e time.
    Inclui publicados e não publicados (para exibir na UI).
    """
    from_date = from_date or date.today()
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM posts").fetchall()

    candidates = []
    for row in rows:
        rec = _row_to_record(row)
        d = _parse_date(rec["date"])
        if d is None:
            continue
        is_published = _is_true(rec["published"])
        # Mostrar tudo de hoje em diante, mais os anteriores não publicados.
        if d < from_date and is_published:
            continue
        t = _parse_time(rec["time"]) or time(0, 0)
        candidates.append((d, t, rec))

    candidates.sort(key=lambda x: (x[0], x[1]))
    return [rec for _, _, rec in candidates[:n]]


def mark_published(row_index: int) -> None:
    """Marca o post como publicado: status='posted', published='yes'."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE posts SET status = 'posted', published = 'yes', updated_at = datetime('now') WHERE id = ?",
            (row_index,),
        )
        if cur.rowcount == 0:
            raise ValueError(f"Post não encontrado: {row_index}")
    logger.info("BD atualizada: post %s -> status=posted, published=yes", row_index)


def update_image_url(row_index: int, image_url: str) -> None:
    """Escreve o URL da imagem no post row_index."""
    if not (image_url or "").strip():
        return
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE posts SET image_url = ?, updated_at = datetime('now') WHERE id = ?",
            (image_url.strip(), row_index),
        )
        if cur.rowcount == 0:
            raise ValueError(f"Post não encontrado: {row_index}")
    logger.info("ImageURL atualizado: post %s", row_index)


def get_row_by_index(row_index: int) -> Optional[dict[str, Any]]:
    """Obtém os dados de um post específico pelo id."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (row_index,)).fetchone()
    return _row_to_record(row) if row else None


def get_all_rows_with_image_text() -> list[dict[str, Any]]:
    """Devolve todos os posts que têm image_text preenchido (para gerar gemini_prompt)."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM posts WHERE trim(image_text) != '' ORDER BY id").fetchall()
    return [_row_to_record(r) for r in rows]


def update_gemini_prompt(row_index: int, prompt: str) -> None:
    """Escreve o prompt no campo gemini_prompt do post row_index."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE posts SET gemini_prompt = ?, updated_at = datetime('now') WHERE id = ?",
            (prompt, row_index),
        )
        if cur.rowcount == 0:
            raise ValueError(f"Post não encontrado: {row_index}")
    logger.info("Gemini_Prompt atualizado: post %s", row_index)


def append_rows(rows: list[dict[str, Any]]) -> int:
    """Adiciona posts à base de dados. Cada item é um dict com chaves de _COLUMNS (em falta ficam vazias)."""
    if not rows:
        return 0
    with _connect() as conn:
        for r in rows:
            values = [str(r.get(c, "") or "") for c in _COLUMNS]
            conn.execute(
                f"INSERT INTO posts ({', '.join(_COLUMNS)}) VALUES ({', '.join('?' for _ in _COLUMNS)})",
                values,
            )
    logger.info("Adicionados %d posts à base de dados", len(rows))
    return len(rows)


def get_last_date() -> Optional[str]:
    """Devolve a data (string) do último post da BD, ou None se vazia."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT date FROM posts WHERE trim(date) != '' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return row["date"] if row else None


def get_published_rows_missing_image_url() -> list[dict[str, Any]]:
    """Devolve posts com published=yes mas image_url vazio."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM posts WHERE lower(published) IN ('yes','y','1','true') AND trim(image_url) = ''"
        ).fetchall()
    return [_row_to_record(r) for r in rows]


def get_published_posts_with_image() -> list[dict[str, Any]]:
    """Devolve todos os posts já publicados com image_url preenchido, mais recente primeiro."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM posts WHERE lower(published) IN ('yes','y','1','true') AND trim(image_url) != ''"
        ).fetchall()
    result = [_row_to_record(r) for r in rows]

    def sort_key(r):
        d = _parse_date(r.get("date") or "")
        t = _parse_time(r.get("time") or "")
        return (d or date.min, t or time(0, 0))

    result.sort(key=sort_key, reverse=True)
    return result


def get_last_published_posts(n: int = 5) -> list[dict[str, Any]]:
    """Devolve os últimos N posts publicados com image_url preenchido."""
    return get_published_posts_with_image()[:n]


def get_all_rows_with_image_url() -> list[dict[str, Any]]:
    """Devolve todos os posts (publicados ou não) que têm image_url preenchido."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM posts WHERE trim(image_url) != '' ORDER BY id").fetchall()
    return [_row_to_record(r) for r in rows]


def get_all_posts() -> list[dict[str, Any]]:
    """Devolve todos os posts, ordenados por data/hora (para gestão/edição completa)."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM posts").fetchall()
    result = [_row_to_record(r) for r in rows]

    def sort_key(r):
        d = _parse_date(r.get("date") or "")
        t = _parse_time(r.get("time") or "")
        return (d or date.min, t or time(0, 0))

    result.sort(key=sort_key)
    return result


def update_post(row_index: int, fields: dict[str, Any]) -> None:
    """Atualiza campos (de _COLUMNS) de um post existente."""
    updates = {k: v for k, v in fields.items() if k in _COLUMNS}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [row_index]
    with _connect() as conn:
        cur = conn.execute(
            f"UPDATE posts SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            values,
        )
        if cur.rowcount == 0:
            raise ValueError(f"Post não encontrado: {row_index}")
    logger.info("Post atualizado: %s (%s)", row_index, ", ".join(updates.keys()))


def delete_post(row_index: int) -> None:
    """Remove definitivamente um post da base de dados."""
    with _connect() as conn:
        cur = conn.execute("DELETE FROM posts WHERE id = ?", (row_index,))
        if cur.rowcount == 0:
            raise ValueError(f"Post não encontrado: {row_index}")
    logger.info("Post removido: %s", row_index)
