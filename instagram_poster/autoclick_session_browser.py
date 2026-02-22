"""
Browser de sessão: abre o Chromium na URL indicada e mantém-se aberto para o utilizador
autenticar e navegar. Outro processo (ciclo de cliques) liga-se via CDP à mesma janela.

Usa o mesmo padrão do autoclick_preview_script (p.chromium.launch) que funciona no Windows,
com args adicionais para CDP (--remote-debugging-port).

Uso: python -m instagram_poster.autoclick_session_browser <url>
"""
import socket
import subprocess
import sys
import time
from pathlib import Path

_CDP_PORT_DEFAULT = 9222
_CDP_PORT_RANGE = list(range(9222, 9232))
_PORT_FILE = Path(__file__).resolve().parent.parent / ".autoclick_session_port.txt"


def _kill_process_on_port(port: int) -> bool:
    """Mata processos que usem a porta (Windows)."""
    if sys.platform != "win32":
        return False
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return False
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
                            time.sleep(0.3)
                            return True
                    except (ValueError, subprocess.TimeoutExpired):
                        pass
    except Exception:
        pass
    return False


def _kill_all_cdp_ports() -> None:
    """Mata processos nas portas CDP (9222-9231)."""
    for port in _CDP_PORT_RANGE:
        _kill_process_on_port(port)
    time.sleep(0.5)


def _is_port_free(port: int) -> bool:
    """Verifica se a porta está livre."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def _find_free_cdp_port() -> int:
    """Encontra a primeira porta livre no intervalo CDP."""
    _kill_all_cdp_ports()
    for port in _CDP_PORT_RANGE:
        for _ in range(3):
            if _is_port_free(port):
                return port
            _kill_process_on_port(port)
            time.sleep(0.5)
    return _CDP_PORT_DEFAULT


def main():
    if len(sys.argv) < 2:
        print("Uso: python -m instagram_poster.autoclick_session_browser <url>", file=sys.stderr)
        sys.exit(1)
    url = sys.argv[1].strip()
    if not url:
        print("URL obrigatória.", file=sys.stderr)
        sys.exit(1)

    if _PORT_FILE.exists():
        try:
            _PORT_FILE.unlink()
        except Exception:
            pass

    cdp_port = _find_free_cdp_port()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright não instalado. Executa: pip install playwright "
            "e python -m playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        with sync_playwright() as p:
            # Mesmo padrão do autoclick_preview_script (launch simples que funciona no Windows)
            # + args CDP para o ciclo de cliques se ligar
            browser = p.chromium.launch(
                headless=False,
                args=[
                    f"--remote-debugging-port={cdp_port}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-session-crashed-bubble",
                ],
            )
            try:
                # Escrever o ficheiro da porta logo após o launch — CDP fica disponível imediatamente.
                # Assim a UI passa a verde e o botão Iniciar fica ativo sem esperar pelo goto.
                _PORT_FILE.write_text(str(cdp_port), encoding="utf-8")
                page = browser.new_page()
                page.goto(url, timeout=60000)
                if cdp_port != _CDP_PORT_DEFAULT:
                    print(f"CDP na porta {cdp_port} (9222 ocupada).", file=sys.stderr, flush=True)
                # Manter vivo como no preview: while browser.is_connected()
                while True:
                    try:
                        if not browser.is_connected():
                            break
                    except Exception:
                        break
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                if _PORT_FILE.exists():
                    try:
                        _PORT_FILE.unlink()
                    except Exception:
                        pass
                try:
                    browser.close()
                except Exception:
                    pass
    except Exception as e:
        print(f"Erro ao abrir o browser: {e}", file=sys.stderr)
        if _PORT_FILE.exists():
            try:
                _PORT_FILE.unlink()
            except Exception:
                pass
        sys.exit(1)


if __name__ == "__main__":
    main()
