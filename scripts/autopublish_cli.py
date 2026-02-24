"""
Script autonomo de autopublish — corre sem Streamlit.
Pensado para ser executado pelo Windows Task Scheduler via run_autopublish.bat.

Uso: py scripts/autopublish_cli.py
Exit codes: 0 = publicado ou nada a publicar, 1 = erro
"""
import sys
import os
import logging

# Garantir que o directorio raiz do projecto esta no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from instagram_poster import config  # noqa: F401 — carrega .env e patch IPv4
from instagram_poster.autopublish import run_once

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("autopublish_cli")


def main():
    logger.info("Autopublish CLI: a verificar posts prontos...")
    try:
        result = run_once()
        if result is True:
            logger.info("Autopublish CLI: post publicado com sucesso.")
        elif result is False:
            logger.error("Autopublish CLI: falha ao publicar.")
            sys.exit(1)
        else:
            logger.info("Autopublish CLI: nenhum post pronto agora.")
    except Exception:
        logger.exception("Autopublish CLI: erro inesperado")
        sys.exit(1)

    try:
        if config.get_autopublish_comment_autoreply():
            from instagram_poster.comment_autoreply import run_autoreply
            r = run_autoreply(message="🙏", max_media=5, delay_seconds=1.0)
            if r.get("replied", 0) > 0:
                logger.info("Autopublish CLI: autoresposta a %d comentário(s)", r["replied"])
    except Exception:
        logger.exception("Autopublish CLI: erro na autoresposta a comentários")


if __name__ == "__main__":
    main()
