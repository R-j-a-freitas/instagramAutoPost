"""
Cliente para o Google Sheets.
Usa uma service account para ler e editar o Sheet via Google Sheets API.
Colunas esperadas: Date, Time, Image Text, Caption, Hashtags, Status, Published, ImageURL.
"""
import logging
from datetime import date, datetime, time
from typing import Any, Optional

import gspread
from google.oauth2.service_account import Credentials

from instagram_poster.config import IG_SHEET_ID, SHEET_TAB_NAME, get_google_credentials_path

logger = logging.getLogger(__name__)

# Scopes necessários para ler e editar Sheets
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Nomes de colunas esperados no Sheet (permite variação de maiúsculas/minúsculas)
COL_DATE = "Date"
COL_TIME = "Time"
COL_IMAGE_TEXT = "Image Text"
COL_CAPTION = "Caption"
COL_HASHTAGS = "Hashtags"
COL_STATUS = "Status"
COL_PUBLISHED = "Published"
COL_IMAGE_URL = "ImageURL"


def _get_client() -> gspread.Client:
    """Cria cliente gspread autenticado com a service account."""
    path = get_google_credentials_path()
    if not path:
        raise ValueError(
            "Defina GOOGLE_SERVICE_ACCOUNT_JSON (ou GOOGLE_CREDENTIALS_PATH) no .env com o caminho do ficheiro JSON da service account."
        )
    creds = Credentials.from_service_account_file(path, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_sheet():
    """Abre o workbook e a aba configurados."""
    gc = _get_client()
    wb = gc.open_by_key(IG_SHEET_ID)
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
        "hashtags": get(COL_HASHTAGS),
        "status": get(COL_STATUS),
        "published": get(COL_PUBLISHED),
        "image_url": get(COL_IMAGE_URL),
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
    sheet = _get_sheet()
    all_rows = sheet.get_all_values()
    if not all_rows:
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
        if d == today and now is not None:
            t = _parse_time(rec["time"])
            if t is not None and t > now:
                continue
        candidates.append((d, _parse_time(rec["time"]) or time(0, 0), rec))

    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][2]


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


def get_row_by_index(row_index: int) -> Optional[dict[str, Any]]:
    """Obtém os dados de uma linha específica do sheet (row_index 1-based, 2 = primeira linha de dados)."""
    sheet = _get_sheet()
    all_rows = sheet.get_all_values()
    if not all_rows or row_index < 2 or row_index > len(all_rows):
        return None
    col = _parse_header_row(all_rows[0])
    return _row_to_record(all_rows[row_index - 1], col, sheet_row_index=row_index)
