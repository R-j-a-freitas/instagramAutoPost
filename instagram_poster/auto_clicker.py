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
_stop_event = threading.Event()
_thread: Optional[threading.Thread] = None
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
        if _thread is not None and _thread.is_alive():
            return True
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
            env=os.environ.copy(),
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
                        if err:
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
        if _thread is not None and _thread.is_alive():
            return
        _last_error = None
        _preview_process = None
    try:
        project_root = _COORDS_FILE.parent
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
                        if err:
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
            if err:
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
    Inicia o ciclo de cliques.
    - Se positions tiver 2+ posições: modo "5 Seguir + refresh" em SUBPROCESS (janela visível).
      max_rounds=0 ou None = infinito.
    - Caso contrário: clica em (x, y) a cada interval_seconds em thread. max_clicks=None = infinito.
    """
    global _thread, _run_process, _last_error
    use_multi = positions and len(positions) >= 2
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        if _run_process is not None and _run_process.poll() is None:
            return
        _last_error = None
        _run_process = None

    if use_multi:
        import json
        try:
            data = [{"x": px, "y": py} for px, py in positions]
            _RUN_POSITIONS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            with _lock:
                _last_error = f"Erro a guardar posições: {e}"
            return
        session_port = get_session_port()
        if session_port is None:
            with _lock:
                _last_error = (
                    "Browser de sessão não está disponível (porta CDP). Clica primeiro em «Arrancar browser», "
                    "espera que a janela abra e autentica; depois usa «Iniciar»."
                )
            return
        try:
            project_root = _RUN_POSITIONS_FILE.parent
            cmd = [
                sys.executable,
                "-m",
                "instagram_poster.autoclick_run_script",
                "--cdp",
                str(session_port),
                str(_RUN_POSITIONS_FILE.resolve()),
                str(interval_seconds),
                str(max_rounds if max_rounds is not None else 0),
            ]
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                cwd=str(project_root),
            )
            with _lock:
                _run_process = proc
            watcher = threading.Thread(target=_wait_run_process, args=(proc,), daemon=True)
            watcher.start()
            logger.info(
                "Auto-clicker started (subprocess, CDP): interval=%ss, positions=%s, max_rounds=%s",
                interval_seconds, len(positions), max_rounds,
            )
        except FileNotFoundError:
            with _lock:
                _last_error = "Python ou módulo não encontrado. Verifica o ambiente."
        except Exception as e:
            with _lock:
                _last_error = str(e)
            logger.exception("Auto-clicker subprocess start failed")
        return

    _stop_event.clear()
    with _lock:
        _thread = threading.Thread(
            target=_run_loop,
            args=(url, x, y, interval_seconds, max_clicks, positions, max_rounds),
            daemon=True,
        )
        _thread.start()
    logger.info(
        "Auto-clicker started (thread): url=%s, interval=%ss, max_rounds=%s",
        url, interval_seconds, max_rounds,
    )


def stop() -> None:
    """Marca para parar; termina o subprocess ou a thread do ciclo."""
    global _run_process
    _stop_event.set()
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


def _run_loop(
    url: str,
    x: int,
    y: int,
    interval_seconds: float,
    max_clicks: Optional[int] = None,
    positions: Optional[List[Tuple[int, int]]] = None,
    max_rounds: Optional[int] = None,
) -> None:
    global _last_error
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        with _lock:
            _last_error = "Playwright não instalado. Executa: pip install playwright e python -m playwright install chromium"
        return
    use_multi = positions and len(positions) >= 2
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            try:
                context = browser.new_context()
                page = context.new_page()
                page.goto(url, timeout=60000)
                if use_multi:
                    _run_loop_multi(page, positions, interval_seconds, max_rounds)
                else:
                    _run_loop_single(page, x, y, interval_seconds, max_clicks)
            finally:
                browser.close()
    except Exception as e:
        logger.exception("Auto-clicker error")
        with _lock:
            _last_error = str(e)


def _run_loop_single(
    page,
    x: int,
    y: int,
    interval_seconds: float,
    max_clicks: Optional[int] = None,
) -> None:
    count = 0
    while not _stop_event.is_set():
        if max_clicks is not None and count >= max_clicks:
            break
        if _stop_event.wait(timeout=interval_seconds):
            break
        if max_clicks is not None and count >= max_clicks:
            break
        try:
            page.mouse.click(x, y)
            count += 1
        except Exception as e:
            logger.warning("Click at (%s, %s) failed: %s", x, y, e)


def _run_loop_multi(
    page,
    positions: List[Tuple[int, int]],
    interval_seconds: float,
    max_rounds: Optional[int] = None,
) -> None:
    """Clica em cada posição (cursor move-se visivelmente), refresh, espera carregar, repete max_rounds vezes (0 = infinito)."""
    round_num = 0
    while not _stop_event.is_set():
        if max_rounds is not None and max_rounds > 0 and round_num >= max_rounds:
            break
        for i, (px, py) in enumerate(positions):
            if _stop_event.is_set():
                return
            try:
                page.mouse.move(px, py)
                time.sleep(0.25)
                page.mouse.click(px, py)
                logger.info("Ronda %s — Click %s/%s em (%s, %s)", round_num + 1, i + 1, len(positions), px, py)
            except Exception as e:
                logger.warning("Click at (%s, %s) failed: %s", px, py, e)
            if _stop_event.wait(timeout=max(0.5, interval_seconds)):
                return
        round_num += 1
        if _stop_event.is_set():
            return
        try:
            page.reload(wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception as e:
            logger.warning("Reload/wait failed: %s", e)
        if _stop_event.wait(timeout=max(1, interval_seconds)):
            return