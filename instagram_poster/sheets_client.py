"""
Cliente para o Google Sheets.
Autenticação via OAuth (abre o browser na primeira vez e guarda o token).
Estrutura oficial das colunas:
  1. Date, 2. Time, 3. Image Text, 4. Caption, 5. Gemini_Prompt,
  6. Status, 7. Published, 8. ImageURL, 9. Image Prompt
"""
import json
import logging
import os
from pathlib import Path

# Permitir HTTP para localhost (necessário para o redirecionamento manual em servidores)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Trigger reload: 2026-05-12 14:33
from datetime import date, datetime, time
from typing import Any, Optional

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from instagram_poster.config import (
    SHEET_TAB_NAME,
    get_google_oauth_client_id,
    get_google_oauth_client_secret,
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
# Colunas opcionais para carrossel (2 slides). Se ausentes do Sheet, o post é tratado como "single".
COL_POST_TYPE = "Post Type"
COL_SLIDE2_TEXT = "Slide2 Text"

# Ficheiros OAuth (na raiz do projeto)
_OAUTH_CLIENT_JSON = _PROJECT_ROOT / "google_oauth_client.json"
_OAUTH_AUTHORIZED_JSON = _PROJECT_ROOT / "google_oauth_authorized.json"


def _get_client() -> gspread.Client:
    """Cria cliente gspread autenticado via OAuth (fluxo do browser)."""
    creds = _get_oauth_credentials()
    return gspread.authorize(creds)


def _get_oauth_credentials(force: bool = False) -> Credentials:
    creds: Optional[Credentials] = None
    if not force and _OAUTH_AUTHORIZED_JSON.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(_OAUTH_AUTHORIZED_JSON), SCOPES)
        except Exception as exc:
            logger.warning("Token OAuth inválido, será ignorado: %s", exc)
            creds = None

    if not force and creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _OAUTH_AUTHORIZED_JSON.write_text(creds.to_json())
            return creds
        except Exception as exc:
            logger.warning("Falha ao renovar token do Google: %s", exc)
            creds = None

    if not force and creds and creds.valid:
        return creds

    # Se chegamos aqui, precisamos de novo login
    flow = get_google_auth_flow()
    try:
        creds = flow.run_local_server(port=0, prompt="consent", timeout_seconds=300)
    except Exception as exc:
        logger.error("Erro ao abrir browser para OAuth: %s", exc)
        raise RuntimeError(
            "Não foi possível abrir o browser para autorização. "
            "Usa o botão 'Gerar Link Manual' na página de Configuração."
        ) from exc

    try:
        _OAUTH_AUTHORIZED_JSON.write_text(creds.to_json())
    except Exception as exc:
        logger.warning("Não foi possível guardar o token OAuth: %s", exc)
    return creds


def get_google_auth_flow() -> InstalledAppFlow:
    client_config = _load_oauth_client_config()
    try:
        return InstalledAppFlow.from_client_config(client_config, SCOPES)
    except Exception as exc:
        raise ValueError(
            "OAuth do Google inválido. Confirma o client_id/client_secret na Configuração."
        ) from exc


def get_google_auth_url(port: int = 8090) -> tuple[str, str, str]:
    """Gera o URL de autorização e os dados necessários para validação (state, verifier)."""
    flow = get_google_auth_flow()
    flow.redirect_uri = f"http://localhost:{port}/"
    url, state = flow.authorization_url(prompt="consent", access_type="offline")
    # Capturamos o code_verifier gerado automaticamente pelo flow
    return url, state, flow.code_verifier


def fetch_google_token_from_url(response_url: str, state: str, code_verifier: str = None, port: int = 8090) -> bool:
    """Consome o URL de redirecionamento para obter o token final."""
    try:
        flow = get_google_auth_flow()
        flow.redirect_uri = f"http://localhost:{port}/"
        
        # Restaurar o code_verifier se fornecido (essencial para evitar invalid_grant)
        if code_verifier:
            flow.code_verifier = code_verifier
            
        # OAuthlib exige que o state seja o mesmo da geração
        # Corrigir HTTPS se necessário (oauthlib é picuinhas com localhost)
        # Já definido no topo do ficheiro, mas reforçamos aqui
        
        flow.fetch_token(authorization_response=response_url)
        creds = flow.credentials
        
        if creds:
            if _OAUTH_AUTHORIZED_JSON.exists():
                _OAUTH_AUTHORIZED_JSON.unlink()
            _OAUTH_AUTHORIZED_JSON.write_text(creds.to_json())
            return True
        return False
    except Exception as e:
        logger.error("Erro ao processar URL de retorno: %s", e)
        raise e


def authorize_google_sheets(port: int = 8090, url_callback=None) -> bool:
    """Força o fluxo de autorização do Google (inicia o servidor e aguarda)."""
    try:
        if _OAUTH_AUTHORIZED_JSON.exists():
            _OAUTH_AUTHORIZED_JSON.unlink()
        
        flow = get_google_auth_flow()
        flow.redirect_uri = f"http://localhost:{port}/"
        
        if url_callback:
            # Monkey-patch para capturar o URL exato que o servidor vai usar
            def custom_print_status(url):
                url_callback(url)
            flow._print_status = custom_print_status
            
        # Inicia o servidor no porto especificado. 
        # open_browser=False para evitar o erro de 'could not locate runnable browser'
        creds = flow.run_local_server(port=port, prompt="consent", timeout_seconds=300, open_browser=False)
        
        if creds:
            _OAUTH_AUTHORIZED_JSON.write_text(creds.to_json())
            return True
        return False
    except Exception as e:
        logger.error("Falha na autorização manual: %s", e)
        raise e


def _load_oauth_client_config() -> dict[str, Any]:
    if _OAUTH_CLIENT_JSON.exists():
        try:
            return json.loads(_OAUTH_CLIENT_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Ficheiro google_oauth_client.json inválido.") from exc

    client_id = get_google_oauth_client_id()
    client_secret = get_google_oauth_client_secret()
    if client_id and client_secret:
        return {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
    raise ValueError(
        "Configura as credenciais OAuth do Google (client ID/secret) na página Configuração antes de autorizar."
    )


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

    post_type = get(COL_POST_TYPE, "single").strip().lower() or "single"
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
        "post_type": post_type,
        "slide2_text": get(COL_SLIDE2_TEXT),
    }


def _parse_date(s: str) -> Optional[date]:
    """Parse various date formats like YYYY-MM-DD, DD/MM/YYYY, etc."""
    if not s:
        return None
    s = s.strip()
    # Try common ISO format first
    if len(s) >= 10 and "-" in s[:5]:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    
    # Try other formats
    formats = ["%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d"]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            try:
                # Handle cases like D/M/YYYY
                parts = s.split("/")
                if len(parts) == 3:
                   # Try to pad components
                   padded = f"{int(parts[0]):02d}/{int(parts[1]):02d}/{int(parts[2]):04d}"
                   return datetime.strptime(padded, "%d/%m/%Y").date()
            except:
                continue
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
        d_str = rec.get("date", "")
        d = _parse_date(d_str)
        if d is None:
            if d_str.strip():
                logger.warning("get_upcoming_posts: Falha ao interpretar data na linha %s: '%s'", i + 1, d_str)
            continue
            
        published_val = (rec.get("published") or "").strip().lower()
        is_published = published_val in ("yes", "y", "1", "true")
        
        # O critério pedido: mostrar tudo de hoje em diante, MAIS os anteriores não publicados.
        if d < from_date and is_published:
            # Pula se for antigo E já publicado.
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


def get_all_rows_with_image_url() -> list[dict[str, Any]]:
    """Devolve todas as linhas (publicadas ou não) que têm ImageURL preenchido."""
    sheet = _get_sheet()
    all_rows = sheet.get_all_values()
    if not all_rows:
        return []
    col = _parse_header_row(all_rows[0])
    if COL_IMAGE_URL not in col:
        return []
    result = []
    for i in range(1, len(all_rows)):
        rec = _row_to_record(all_rows[i], col, sheet_row_index=i + 1)
        if rec and (rec.get("image_url") or "").strip():
            result.append(rec)
    return result
