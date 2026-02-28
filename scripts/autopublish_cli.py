"""
Script autonomo de autopublish — corre sem Streamlit.
Pensado para ser executado pelo Windows Task Scheduler via run_autopublish.bat.

Uso: py scripts/autopublish_cli.py
Exit codes: 0 = publicado ou nada a publicar, 1 = erro
"""
import sys
import os
import logging
from pathlib import Path

# Garantir que o directorio raiz do projecto esta no path
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

# Recarregar .env antes de importar config (garante valores actualizados)
_env_path = _project_root / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path, override=True)

from instagram_poster import config  # noqa: F401 — carrega .env e patch IPv4
from instagram_poster.autopublish import ensure_log_loaded_for_cli, run_once, try_publish_auto_reel, try_publish_reel_reuse_scheduled, try_publish_story_reuse_scheduled

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("autopublish_cli")


def main():
    # Carregar log existente para não sobrescrever (Reels, Stories, etc.) ao gravar
    ensure_log_loaded_for_cli()

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

    # Reels automáticos (igual ao thread do Streamlit)
    try:
        if config.get_autopublish_reel_every_5():
            if try_publish_auto_reel():
                logger.info("Autopublish CLI: Reel publicado (5 posts).")
    except Exception:
        logger.exception("Autopublish CLI: erro no Reel automático")
    try:
        if try_publish_reel_reuse_scheduled():
            logger.info("Autopublish CLI: Reel reuse agendado publicado.")
    except Exception:
        logger.exception("Autopublish CLI: erro no Reel reuse")
    try:
        if try_publish_story_reuse_scheduled():
            logger.info("Autopublish CLI: Story reuse agendada publicada.")
    except Exception:
        logger.exception("Autopublish CLI: erro na Story reuse")

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
