"""
Arranque da app: liga o autopublish logo que o processo inicia e depois corre o Streamlit.

Antes, o autopublish só arrancava quando alguém abria (e autenticava) a página: depois de um
reinício do servidor ninguém publicava até lá (ex.: 19/10 15:43 → 20/10 20:47). Aqui a thread
arranca no mesmo processo do Streamlit, por isso a página (estado, registo, Parar/Iniciar) vê e
controla a mesma thread, e o app.py não arranca outra (is_running() já é True).

Respeita a decisão do utilizador: se o autopublish estiver desligado na configuração ou tiver
sido parado na página (.autopublish_stopped), não o liga.

Uso (run.sh): python3 start_app.py --server.port 8502
"""
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("start_app")

try:
    from instagram_poster import autopublish
    from instagram_poster.config import get_autopublish_enabled, get_autopublish_interval

    if not get_autopublish_enabled():
        log.info("Autopublish desligado na configuração; não arranca.")
    elif autopublish._STOPPED_FILE.exists():
        log.info("Autopublish foi parado na página (.autopublish_stopped); não arranca.")
    elif autopublish.start_background_loop(interval_minutes=get_autopublish_interval()):
        log.info("Autopublish iniciado no arranque (intervalo %s min).", get_autopublish_interval())
except Exception:  # nunca impedir a app de arrancar por causa do autopublish
    log.exception("Falha a iniciar o autopublish no arranque; a app arranca na mesma.")

from streamlit.web import cli as stcli  # noqa: E402

sys.argv = ["streamlit", "run", "app.py", *sys.argv[1:]]
sys.exit(stcli.main())
