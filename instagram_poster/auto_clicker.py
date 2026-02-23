"""
Auto-click em posição (x, y) ou em várias posições numa página.
- Preview: abre o browser num subprocess para ver a página e clicar para guardar coordenadas (mais fiável no Windows).
- Modo único: clica (x, y) a cada N segundos.
- Modo 5 Seguir: clica em 5 posições em sequência, faz refresh, espera carregar, repete.
"""
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_preview_process: Optional[subprocess.Popen] = None
_run_process: Optional[subprocess.Popen] = None
_last_error: Optional[str] = None

_COORDS_FILE = Path(__file__).resolve().parent.parent / ".autoclick_last_click.txt"
_POSITIONS_FILE = Path(__file__).resolve().parent.parent / ".autoclick_positions.json"
_RUN_POSITIONS_FILE = Path(__file__).resolve().parent.parent / ".autoclick_run_positions.json"
_SESSION_PORT_FILE = Path(__file__).resolve().parent.parent / ".autoclick_session_port.txt"

_session_process: Optional[subprocess.Popen] = None


def save_positions(positions: List[Tuple[int, int]]) -> None:
    """Guarda a lista de posições (x, y) em ficheiro para usar como referência nas próximas sessões."""
    if not positions:
        if _POSITIONS_FILE.exists():
            _POSITIONS_FILE.unlink()
        return
    import json
    data = [{"x": x, "y": y} for x, y in positions]
    _POSITIONS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_positions() -> List[Tuple[int, int]]:
    """Carrega a lista de posições guardada (referência). Devolve lista vazia se não existir ficheiro."""
    if not _POSITIONS_FILE.exists():
        return []
    try:
        import json
        data = json.loads(_POSITIONS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        out = []
        for item in data:
            if isinstance(item, dict) and "x" in item and "y" in item:
                out.append((int(item["x"]), int(item["y"])))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                out.append((int(item[0]), int(item[1])))
        return out[:10]
    except Exception:
        return []


def is_running() -> bool:
    with _lock:
        if _run_process is not None and _run_process.poll() is None:
            return True
        return False


def is_preview_running() -> bool:
    with _lock:
        if _preview_process is None:
            return False
        ret = _preview_process.poll()
        return ret is None


def is_session_browser_running() -> bool:
    """True se o browser de sessão (para autenticar e navegar) estiver em execução."""
    global _session_process
    with _lock:
        if _session_process is None:
            return False
        if _session_process.poll() is not None:
            _session_process = None
            return False
        return True


def get_session_port() -> Optional[int]:
    """Porta CDP do browser de sessão, ou None se não estiver a correr."""
    if not is_session_browser_running() or not _SESSION_PORT_FILE.exists():
        return None
    try:
        return int(_SESSION_PORT_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def start_session_browser(url: str) -> None:
    """Abre o browser na URL e mantém-se aberto para o utilizador autenticar e navegar.
    
    USA autoclick_session_browser (launch simples) — NÃO o autoclick_preview_script --session
    (launch_persistent_context), que no Windows não expõe o CDP de forma fiável.
    """
    global _session_process, _last_error
    with _lock:
        if _session_process is not None and _session_process.poll() is None:
            return
        _last_error = None
        _session_process = None
    _kill_all_cdp_ports()
    try:
        project_root = _COORDS_FILE.parent
        env = os.environ.copy()
        env.setdefault("NODE_OPTIONS", "--no-deprecation")
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "instagram_poster.autoclick_session_browser",  # <-- módulo dedicado, usa launch() simples
                url.strip(),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            cwd=str(project_root),
            env=env,
        )
        with _lock:
            _session_process = proc

        def _collect_session_stderr():
            global _session_process, _last_error
            try:
                proc.wait()
                with _lock:
                    if _session_process is proc:
                        _session_process = None
                    if proc.returncode not in (0, None) and proc.stderr:
                        err = proc.stderr.read().decode("utf-8", errors="replace").strip()
                        if err and not _is_epipe_or_connection_err(err):
                            _last_error = err
            except Exception:
                pass
        threading.Thread(target=_collect_session_stderr, daemon=True).start()
        logger.info("Browser de sessão iniciado: url=%s", url)
    except FileNotFoundError:
        with _lock:
            _last_error = "Python ou módulo não encontrado. Verifica o ambiente."
    except Exception as e:
        with _lock:
            _last_error = str(e)
        logger.exception("Session browser start failed")


def _kill_process_on_port(port: int) -> None:
    """Liberta a porta matando processos que a usem (Windows)."""
    if sys.platform != "win32":
        return
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line.upper():
                parts = line.split()
                if parts:
                    try:
                        pid = int(parts[-1])
                        if pid > 0:
                            subprocess.run(
                                ["taskkill", "/F", "/PID", str(pid), "/T"],
                                capture_output=True,
                                timeout=3,
                            )
                    except (ValueError, subprocess.TimeoutExpired):
                        pass
    except Exception:
        pass


def _kill_all_cdp_ports() -> None:
    """Mata todos os processos nas portas CDP (9222-9231)."""
    for port in range(9222, 9232):
        _kill_process_on_port(port)
    time.sleep(0.5)


def stop_session_browser() -> None:
    """Fecha o browser de sessão."""
    global _session_process
    with _lock:
        proc = _session_process
        _session_process = None
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
        except Exception as e:
            logger.warning("Erro ao terminar browser de sessão: %s", e)
        _kill_all_cdp_ports()
        if _SESSION_PORT_FILE.exists():
            try:
                _SESSION_PORT_FILE.unlink()
            except Exception:
                pass
        logger.info("Browser de sessão fechado.")


def get_last_error() -> Optional[str]:
    with _lock:
        return _last_error


def read_last_click() -> Optional[Tuple[int, int]]:
    """Lê as últimas coordenadas guardadas (clique na janela de preview). Devolve (x, y) ou None."""
    if not _COORDS_FILE.exists():
        return None
    try:
        text = _COORDS_FILE.read_text(encoding="utf-8").strip()
        parts = text.split(",")
        if len(parts) == 2:
            return int(parts[0].strip()), int(parts[1].strip())
    except Exception:
        pass
    return None


def start_preview(url: str) -> None:
    """Abre o browser num subprocess para ver a página; move o rato e clica para guardar coordenadas."""
    global _preview_process, _last_error
    with _lock:
        if _preview_process is not None and _preview_process.poll() is None:
            return
        _last_error = None
        _preview_process = None
    try:
        project_root = _COORDS_FILE.parent
        env = os.environ.copy()
        env.setdefault("NODE_OPTIONS", "--no-deprecation")
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "instagram_poster.autoclick_preview_script",
                url.strip(),
                str(_COORDS_FILE.resolve()),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            cwd=str(project_root),
            env=env,
        )
        with _lock:
            _preview_process = proc
        logger.info("Preview browser started (subprocess): url=%s", url)

        def _collect_preview_stderr():
            global _preview_process, _last_error
            try:
                proc.wait()
                with _lock:
                    if _preview_process is proc:
                        _preview_process = None
                    if proc.returncode != 0 and proc.stderr:
                        err = proc.stderr.read().decode("utf-8", errors="replace").strip()
                        if err and not _is_epipe_or_connection_err(err):
                            _last_error = err or f"Preview saiu com código {proc.returncode}"
            except Exception:
                pass
        threading.Thread(target=_collect_preview_stderr, daemon=True).start()
    except FileNotFoundError:
        with _lock:
            _last_error = "Python ou módulo não encontrado. Verifica que estás no ambiente correto."
    except Exception as e:
        with _lock:
            _last_error = str(e)
        logger.exception("Preview subprocess failed")


def stop_preview() -> None:
    """Termina o processo do browser de preview (fecha a janela)."""
    global _preview_process
    with _lock:
        proc = _preview_process
        _preview_process = None
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
        except Exception as e:
            logger.warning("Erro ao terminar preview: %s", e)
        logger.info("Preview browser terminado.")


def _is_epipe_or_connection_err(err: str) -> bool:
    """Ignora EPIPE e erros de ligação ao fechar o browser (esperado)."""
    s = err.lower()
    return "epipe" in s or "broken pipe" in s or "target closed" in s


def _wait_run_process(proc: subprocess.Popen) -> None:
    """Thread que espera pelo processo do ciclo e regista erro em stderr."""
    global _last_error, _run_process
    try:
        proc.wait()
        with _lock:
            if _run_process is proc:
                _run_process = None
        if proc.returncode != 0 and proc.stderr:
            err = proc.stderr.read().decode("utf-8", errors="replace").strip()
            if err and not _is_epipe_or_connection_err(err):
                with _lock:
                    _last_error = err
    except Exception as e:
        logger.warning("wait run process: %s", e)
        with _lock:
            if _run_process is proc:
                _run_process = None


def start(
    url: str,
    x: int,
    y: int,
    interval_seconds: float,
    max_clicks: Optional[int] = None,
    positions: Optional[List[Tuple[int, int]]] = None,
    max_rounds: Optional[int] = None,
) -> None:
    """
    Inicia o ciclo de cliques em SUBPROCESS (evita EPIPE no terminal do Streamlit).
    - Se positions tiver 2+ posições: modo "5 Seguir + refresh". max_rounds=0 ou None = infinito.
    - Caso contrário: clica em (x, y) a cada interval_seconds. max_clicks=None = infinito.
    """
    global _run_process, _last_error
    use_multi = positions and len(positions) >= 2
    pos_list = positions if use_multi else [(x, y)]
    max_r = (max_rounds if max_rounds is not None else 0) if use_multi else (max_clicks if max_clicks is not None else 0)

    with _lock:
        if _run_process is not None and _run_process.poll() is None:
            return
        _last_error = None
        _run_process = None

    import json
    try:
        data = [{"x": px, "y": py} for px, py in pos_list]
        _RUN_POSITIONS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        with _lock:
            _last_error = f"Erro a guardar posições: {e}"
        return

    session_port = get_session_port()
    use_cdp = use_multi and (session_port is not None)
    if use_multi and session_port is None:
        with _lock:
            _last_error = (
                "Browser de sessão não está disponível (porta CDP). Clica primeiro em «Arrancar browser», "
                "espera que a janela abra e autentica; depois usa «Iniciar»."
            )
        return

    try:
        project_root = _RUN_POSITIONS_FILE.parent
        if use_cdp:
            cmd = [
                sys.executable,
                "-m",
                "instagram_poster.autoclick_run_script",
                "--cdp",
                str(session_port),
                str(_RUN_POSITIONS_FILE.resolve()),
                str(interval_seconds),
                str(max_r),
            ]
        else:
            cmd = [
                sys.executable,
                "-m",
                "instagram_poster.autoclick_run_script",
                url.strip(),
                str(_RUN_POSITIONS_FILE.resolve()),
                str(interval_seconds),
                str(max_r),
            ]
        env = os.environ.copy()
        env.setdefault("NODE_OPTIONS", "--no-deprecation")
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            cwd=str(project_root),
            env=env,
        )
        with _lock:
            _run_process = proc
        watcher = threading.Thread(target=_wait_run_process, args=(proc,), daemon=True)
        watcher.start()
        logger.info(
            "Auto-clicker started (subprocess, %s): interval=%ss, positions=%s, max=%s",
            "CDP" if use_cdp else "URL", interval_seconds, len(pos_list), max_r,
        )
    except FileNotFoundError:
        with _lock:
            _last_error = "Python ou módulo não encontrado. Verifica o ambiente."
    except Exception as e:
        with _lock:
            _last_error = str(e)
        logger.exception("Auto-clicker subprocess start failed")


def stop() -> None:
    """Termina o subprocess do ciclo de cliques."""
    global _run_process
    with _lock:
        proc = _run_process
        _run_process = None
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
        except Exception as e:
            logger.warning("Erro ao terminar processo: %s", e)
        logger.info("Auto-clicker subprocess terminado.")
    logger.info("Auto-clicker stop requested")

