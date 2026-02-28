"""
Migra media do Cloudinary para o servidor local e actualiza o Sheet.

Uso:
  python scripts/migrate_cloudinary_to_local.py
  python scripts/migrate_cloudinary_to_local.py --dry-run

Pré-requisitos:
  - .env com MEDIA_BACKEND=local_http, MEDIA_ROOT, MEDIA_BASE_URL
  - Credenciais Google Sheets configuradas
"""
import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

# Adicionar raiz do projeto ao path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from instagram_poster.config import get_media_backend, get_media_base_url, get_media_root
from instagram_poster.sheets_client import get_all_rows_with_image_url, update_image_url

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

CLOUDINARY_DOMAINS = ("res.cloudinary.com", "cloudinary.com")


def _is_cloudinary_url(url: str) -> bool:
    """Verifica se o URL é do Cloudinary."""
    if not url or not url.strip():
        return False
    parsed = urlparse(url.strip())
    host = (parsed.netloc or "").lower()
    return any(d in host for d in CLOUDINARY_DOMAINS)


def _extract_filename_from_url(url: str, row_index: int, content_type: Optional[str]) -> str:
    """
    Extrai o nome do ficheiro do URL Cloudinary.
    Fallback: media_row{row_index}.{ext}
    """
    parsed = urlparse(url.strip())
    path = parsed.path or ""
    segments = [s for s in path.split("/") if s]
    if segments:
        last = segments[-1]
        # Cloudinary pode ter formato: v123/ig_post_xxx.jpg ou ig_post_xxx.jpg
        if "." in last and re.match(r"^[\w\-_.]+$", last):
            return last
    # Fallback por extensão
    ext = ".png"
    if content_type:
        if "jpeg" in content_type or "jpg" in content_type:
            ext = ".jpg"
        elif "mp4" in content_type or "video" in content_type:
            ext = ".mp4"
    elif "/video/" in url.lower():
        ext = ".mp4"
    elif ".mp4" in url.lower():
        ext = ".mp4"
    return f"media_row{row_index}{ext}"


def migrate(dry_run: bool = False) -> None:
    if get_media_backend() != "local_http":
        logger.error("Define MEDIA_BACKEND=local_http no .env antes de migrar.")
        sys.exit(1)

    media_root = get_media_root()
    base_url = get_media_base_url()

    rows = get_all_rows_with_image_url()
    cloudinary_rows = [(r, (r.get("image_url") or "").strip()) for r in rows if _is_cloudinary_url(r.get("image_url") or "")]

    if not cloudinary_rows:
        logger.info("Nenhuma linha com URL do Cloudinary encontrada.")
        return

    logger.info("Encontradas %d linhas com URLs do Cloudinary.", len(cloudinary_rows))

    for rec, url in cloudinary_rows:
        row_index = rec.get("row_index")
        if not row_index:
            continue

        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("Linha %s: falha no download: %s", row_index, e)
            continue

        content_type = resp.headers.get("content-type", "")
        filename = _extract_filename_from_url(url, row_index, content_type)

        # Evitar colisão: se já existir, usar sufixo com row_index
        stem = Path(filename).stem
        ext = Path(filename).suffix
        target_path = media_root / filename
        if target_path.exists() and not dry_run:
            filename = f"{stem}_row{row_index}{ext}"
            target_path = media_root / filename

        new_url = f"{base_url.rstrip('/')}/{filename}"

        if dry_run:
            logger.info("Linha %s: %s -> %s (dry-run, não gravado)", row_index, url[:60] + "...", new_url)
            continue

        try:
            target_path.write_bytes(resp.content)
        except OSError as e:
            logger.warning("Linha %s: falha ao gravar %s: %s", row_index, target_path, e)
            continue

        try:
            update_image_url(row_index, new_url)
            logger.info("Linha %s: %s -> %s", row_index, url[:50] + "...", new_url)
        except Exception as e:
            logger.warning("Linha %s: ficheiro gravado mas falha ao actualizar Sheet: %s", row_index, e)


def main():
    parser = argparse.ArgumentParser(description="Migra media do Cloudinary para servidor local.")
    parser.add_argument("--dry-run", action="store_true", help="Apenas listar, sem gravar nem actualizar")
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
