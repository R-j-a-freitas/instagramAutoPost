"""
Cliente para o Google Sheets.
Acede ao Sheet via gspread.oauth() (OAuth pessoal) ou Service Account.
Estrutura oficial das colunas:
  1. Date, 2. Time, 3. Image Text, 4. Caption, 5. Gemini_Prompt,
  6. Status, 7. Published, 8. ImageURL, 9. Image Prompt
"""
import logging
from pathlib import Path
from datetime import date, datetime, time
from typing import Any, Optional

import gspread
from google.oauth2.service_account import Credentials as ServiceAccountCredentials

from instagram_poster.config import (
    SHEET_TAB_NAME,
    get_google_credentials_dict,
    get_google_credentials_path,
    get_ig_sheet_id,
)

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

COL_DATE = "Date"
COL_TIME = "Time"
COL_IMAGE_TEXT = "Image Text"
COL_CAPTION = "Caption"
COL_GEMINI_PROMPT = "Gemini_Prompt"
COL_STATUS = "Status"
COL_PUBLISHED = "Published"
COL_IMAGE_URL = "ImageURL"
COL_IMAGE_PROMPT = "Image Prompt"

# Ficheiros OAuth (na raiz do projeto)
_OAUTH_CLIENT_JSON = _PROJECT_ROOT / "google_oauth_client.json"
_OAUTH_AUTHORIZED_JSON = _PROJECT_ROOT / "google_oauth_authorized.json"


def _get_client() -> gspread.Client:
    """
    Cria cliente gspread autenticado.
    Prioridade:
      1) gspread.oauth() com google_oauth_client.json (abre browser na 1a vez, depois usa token guardado)
      2) Service Account em memória (upload na UI)
      3) Service Account em ficheiro (.env)
    """
    # 1. OAuth pessoal (ficheiro google_oauth_client.json na raiz)
    if _OAUTH_CLIENT_JSON.exists():
        try:
            gc = gspread.oauth(
                credentials_filename=str(_OAUTH_CLIENT_JSON),
                authorized_user_filename=str(_OAUTH_AUTHORIZED_JSON),
                scopes=SCOPES,
            )
            return gc
        except Exception as e:
            logger.warning("gspread.oauth() falhou: %s", e)
    # 2. Service Account em memória (upload na UI)
    creds_dict = get_google_credentials_dict()
    if creds_dict is not None:
        creds = ServiceAccountCredentials.from_service_account_info(creds_dict, scopes=SCOPES)
        return gspread.authorize(creds)
    # 3. Service Account em ficheiro
    path = get_google_credentials_path()
    if not path:
        raise ValueError(
            "Faz upload do JSON do Google na Configuração (OAuth Client ou Service Account)."
        )
    creds = ServiceAccountCredentials.from_service_account_file(path, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_sheet():
    """Abre o workbook e a aba configurados."""
    gc = _get_client()
    wb = gc.open_by_key(get_ig_sheet_id())
    return wb.worksheet(SHEET_TAB_NAME)


def _parse_header_row(header_values: list[str]) -> dict[str, int]:
    """Mapeia nome da coluna -> índice (0-based)."""
    mapping = {}
    for i, label in enumerate(header_values):
        key = (label or "").strip()
        if key:
            mapping[key] = i
    return mapping


def _row_to_record(row: list[Any], col: dict[str, int], sheet_row_index: int) -> Optional[dict[str, Any]]:
    """Converte uma linha do sheet num dicionário com as chaves esperadas. sheet_row_index é 1-based."""
    if not row:
        return None
    def get(key: str, default: str = "") -> str:
        idx = col.get(key, -1)
        if idx < 0 or idx >= len(row):
            return default
        v = row[idx]
        return str(v).strip() if v is not None else default

    return {
        "row_index": sheet_row_index,
        "date": get(COL_DATE),
        "time": get(COL_TIME),
        "image_text": get(COL_IMAGE_TEXT),
        "caption": get(COL_CAPTION),
        "gemini_prompt": get(COL_GEMINI_PROMPT),
        "status": get(COL_STATUS),
        "published": get(COL_PUBLISHED),
        "image_url": get(COL_IMAGE_URL),
        "image_prompt": get(COL_IMAGE_PROMPT),
    }


def _parse_date(s: str) -> Optional[date]:
    """Parse YYYY-MM-DD."""
    if not s:
        return None
    try:
        return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_time(s: str) -> Optional[time]:
    """Parse HH:MM ou HH:MM:SS."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            t = datetime.strptime(s, fmt).time()
            return t
        except ValueError:
            continue
    return None


def get_next_ready_post(today: Optional[date] = None, now: Optional[time] = None) -> Optional[dict[str, Any]]:
    """
    Devolve o próximo post pronto a publicar:
    Status = "ready", Published vazio, Date <= today (e opcionalmente Time <= now).
    Ordenação: Date, Time.
    """
    today = today or date.today()
    now_time = now
    sheet = _get_sheet()
    all_rows = sheet.get_all_values()
    if not all_rows:
        logger.info("get_next_ready_post: sheet vazio")
        return None
    col = _parse_header_row(all_rows[0])
    if COL_DATE not in col or COL_STATUS not in col or COL_PUBLISHED not in col:
        logger.warning("Sheet sem colunas Date/Status/Published. Header: %s", list(col.keys()))
        return None

    candidates = []
    for i in range(1, len(all_rows)):
        rec = _row_to_record(all_rows[i], col, sheet_row_index=i + 1)
        if not rec:
            continue
        if rec["status"].lower() != "ready":
            continue
        if (rec["published"] or "").strip().lower() in ("yes", "y", "1", "true"):
            continue
        d = _parse_date(rec["date"])
        if d is None:
            continue
        if d > today:
            continue
        if d == today and now_time is not None:
            t = _parse_time(rec["time"])
            if t is not None and t > now_time:
                continue
        candidates.append((d, _parse_time(rec["time"]) or time(0, 0), rec))

    if not candidates:
        logger.info(
            "get_next_ready_post: 0 candidatos (critérios: Date<=%s, Time<=%s, Status=ready, Published vazio)",
            today,
            now_time,
        )
        return None
    candidates.sort(key=lambda x: (x[0], x[1]))
    chosen = candidates[0][2]
    logger.info(
        "get_next_ready_post: %s candidato(s), próximo: linha %s (%s %s)",
        len(candidates),
        chosen.get("row_index"),
        chosen.get("date", ""),
        chosen.get("time", ""),
    )
    return chosen


def get_upcoming_posts(n: int = 14, from_date: Optional[date] = None) -> list[dict[str, Any]]:
    """
    Devolve os próximos n posts a partir de from_date (default: hoje),
    ordenados por Date e Time. Inclui publicados e não publicados (para exibir na UI).
    """
    from_date = from_date or date.today()
    sheet = _get_sheet()
    all_rows = sheet.get_all_values()
    if not all_rows:
        return []
    col = _parse_header_row(all_rows[0])
    if COL_DATE not in col:
        return []

    candidates = []
    for i in range(1, len(all_rows)):
        rec = _row_to_record(all_rows[i], col, sheet_row_index=i + 1)
        if not rec:
            continue
        d = _parse_date(rec["date"])
        if d is None or d < from_date:
            continue
        t = _parse_time(rec["time"]) or time(0, 0)
        candidates.append((d, t, rec))

    candidates.sort(key=lambda x: (x[0], x[1]))
    return [rec for _, _, rec in candidates[:n]]


def mark_published(row_index: int) -> None:
    """
    Escreve na linha row_index (1-based, linha do sheet): Published = "yes", Status = "posted".
    """
    sheet = _get_sheet()
    all_rows = sheet.get_all_values()
    if not all_rows or row_index < 2 or row_index > len(all_rows):
        raise ValueError(f"Linha inválida: {row_index}")
    col = _parse_header_row(all_rows[0])
    status_col = col.get(COL_STATUS)
    published_col = col.get(COL_PUBLISHED)
    if status_col is None or published_col is None:
        raise ValueError("Sheet sem colunas Status ou Published")
    # gspread: atualizar célula por (row, col) 1-based
    sheet.update_cell(row_index, status_col + 1, "posted")
    sheet.update_cell(row_index, published_col + 1, "yes")
    logger.info("Sheet atualizado: linha %s -> Status=posted, Published=yes", row_index)


def update_image_url(row_index: int, image_url: str) -> None:
    """Escreve o URL da imagem na coluna ImageURL da linha row_index (1-based)."""
    if not (image_url or "").strip():
        return
    sheet = _get_sheet()
    all_rows = sheet.get_all_values()
    if not all_rows or row_index < 2 or row_index > len(all_rows):
        raise ValueError(f"Linha inválida: {row_index}")
    col = _parse_header_row(all_rows[0])
    url_col = col.get(COL_IMAGE_URL)
    if url_col is None:
        raise ValueError("Sheet sem coluna ImageURL")
    sheet.update_cell(row_index, url_col + 1, image_url.strip())
    logger.info("ImageURL atualizado: linha %s", row_index)


def get_row_by_index(row_index: int) -> Optional[dict[str, Any]]:
    """Obtém os dados de uma linha específica do sheet (row_index 1-based, 2 = primeira linha de dados)."""
    sheet = _get_sheet()
    all_rows = sheet.get_all_values()
    if not all_rows or row_index < 2 or row_index > len(all_rows):
        return None
    col = _parse_header_row(all_rows[0])
    return _row_to_record(all_rows[row_index - 1], col, sheet_row_index=row_index)


def get_all_rows_with_image_text() -> list[dict[str, Any]]:
    """Devolve todas as linhas de dados que têm Image Text preenchido (para gerar Gemini_Prompt)."""
    sheet = _get_sheet()
    all_rows = sheet.get_all_values()
    if not all_rows:
        return []
    col = _parse_header_row(all_rows[0])
    if COL_IMAGE_TEXT not in col:
        return []
    result = []
    for i in range(1, len(all_rows)):
        rec = _row_to_record(all_rows[i], col, sheet_row_index=i + 1)
        if rec and (rec.get("image_text") or "").strip():
            result.append(rec)
    return result


def update_gemini_prompt(row_index: int, prompt: str) -> None:
    """Escreve o prompt na coluna Gemini_Prompt da linha row_index (1-based)."""
    sheet = _get_sheet()
    all_rows = sheet.get_all_values()
    if not all_rows or row_index < 2 or row_index > len(all_rows):
        raise ValueError(f"Linha inválida: {row_index}")
    col = _parse_header_row(all_rows[0])
    gemini_col = col.get(COL_GEMINI_PROMPT)
    if gemini_col is None:
        raise ValueError("Sheet sem coluna Gemini_Prompt")
    sheet.update_cell(row_index, gemini_col + 1, prompt)
    logger.info("Gemini_Prompt atualizado: linha %s", row_index)


def append_rows(rows: list[list[str]]) -> int:
    """Adiciona linhas ao final do Sheet. Retorna numero de linhas adicionadas."""
    sheet = _get_sheet()
    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    logger.info("Adicionadas %d linhas ao Sheet", len(rows))
    return len(rows)


def get_last_date() -> Optional[str]:
    """Devolve a data (string) da ultima linha do Sheet, ou None se vazio."""
    sheet = _get_sheet()
    all_rows = sheet.get_all_values()
    if not all_rows or len(all_rows) < 2:
        return None
    col = _parse_header_row(all_rows[0])
    date_idx = col.get(COL_DATE)
    if date_idx is None:
        return None
    for row in reversed(all_rows[1:]):
        if date_idx < len(row) and row[date_idx].strip():
            return row[date_idx].strip()
    return None


def get_published_rows_missing_image_url() -> list[dict[str, Any]]:
    """
    Devolve linhas com Published=yes mas ImageURL vazio.
    Útil para preencher ImageURL em publicações antigas (sem republicar no Instagram).
    """
    sheet = _get_sheet()
    all_rows = sheet.get_all_values()
    if not all_rows:
        return []
    col = _parse_header_row(all_rows[0])
    if COL_PUBLISHED not in col or COL_IMAGE_URL not in col:
        return []
    result = []
    for i in range(1, len(all_rows)):
        rec = _row_to_record(all_rows[i], col, sheet_row_index=i + 1)
        if not rec:
            continue
        if (rec.get("published") or "").strip().lower() not in ("yes", "y", "1", "true"):
            continue
        if (rec.get("image_url") or "").strip():
            continue
        result.append(rec)
    return result


def get_published_posts_with_image() -> list[dict[str, Any]]:
    """
    Devolve todos os posts já publicados que têm ImageURL preenchido.
    Ordenados por data (mais recente primeiro). Útil para escolher um post para Story.
    """
    sheet = _get_sheet()
    all_rows = sheet.get_all_values()
    if not all_rows:
        return []
    col = _parse_header_row(all_rows[0])
    if COL_PUBLISHED not in col or COL_IMAGE_URL not in col or COL_DATE not in col:
        return []
    result = []
    for i in range(1, len(all_rows)):
        rec = _row_to_record(all_rows[i], col, sheet_row_index=i + 1)
        if not rec:
            continue
        if (rec.get("published") or "").strip().lower() not in ("yes", "y", "1", "true"):
            continue
        if not (rec.get("image_url") or "").strip():
            continue
        result.append(rec)
    # Ordenar por data descendente (mais recente primeiro)
    def sort_key(r):
        d = _parse_date(r.get("date") or "")
        t = _parse_time(r.get("time") or "")
        return (d or date.min, t or time(0, 0))
    result.sort(key=sort_key, reverse=True)
    return result


def get_last_published_posts(n: int = 5) -> list[dict[str, Any]]:
    """
    Devolve os últimos N posts publicados com ImageURL preenchido, ordenados do mais recente para o mais antigo.
    """
    all_published = get_published_posts_with_image()
    return all_published[:n]
