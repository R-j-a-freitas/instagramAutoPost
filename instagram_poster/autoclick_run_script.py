"""
Script standalone para executar o ciclo de cliques (grelha 5 posições + refresh).
Modo sessão: --cdp <porta> → liga ao browser já aberto (onde o utilizador autenticou).
Uso com sessão: python -m instagram_poster.autoclick_run_script --cdp <porta> <path_positions.json> <interval_sec> <max_rounds>
Uso sem sessão (legado): python -m instagram_poster.autoclick_run_script <url> <path_positions.json> <interval_sec> <max_rounds>
  max_rounds=0 = infinito.
"""
import json
import sys
import time
from pathlib import Path


def _load_positions(positions_path: Path):
    if not positions_path.exists():
        print(f"Ficheiro de posições não encontrado: {positions_path}", file=sys.stderr)
        sys.exit(1)
    try:
        data = json.loads(positions_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            data = []
        positions = []
        for item in data:
            if isinstance(item, dict) and "x" in item and "y" in item:
                positions.append((int(item["x"]), int(item["y"])))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                positions.append((int(item[0]), int(item[1])))
        return positions
    except Exception as e:
        print(f"Erro a ler posições: {e}", file=sys.stderr)
        sys.exit(1)


def _is_connection_error(e: Exception) -> bool:
    """Deteta EPIPE, broken pipe e erros de ligação ao browser."""
    s = str(e).lower()
    return "epipe" in s or "broken pipe" in s or "connection" in s or "target closed" in s


def _run_click_loop(page, positions, interval_seconds: float, max_rounds: int) -> None:
    round_num = 0
    while True:
        if max_rounds > 0 and round_num >= max_rounds:
            break
        for i, (px, py) in enumerate(positions):
            try:
                page.mouse.move(px, py)
                time.sleep(0.25)
                page.mouse.click(px, py)
            except Exception as e:
                if _is_connection_error(e):
                    return
                print(f"Click em ({px},{py}) falhou: {e}", file=sys.stderr)
            time.sleep(max(0.5, interval_seconds))
        round_num += 1
        if max_rounds > 0 and round_num >= max_rounds:
            break
        try:
            page.reload(wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception as e:
            if _is_connection_error(e):
                return
            print(f"Reload/wait: {e}", file=sys.stderr)
        time.sleep(max(1, interval_seconds))


def main():
    use_cdp = len(sys.argv) >= 2 and sys.argv[1].strip() == "--cdp"
    if use_cdp and len(sys.argv) < 6:
        print(
            "Uso (sessão): python -m instagram_poster.autoclick_run_script --cdp <porta> <path_positions.json> <interval_sec> <max_rounds>",
            file=sys.stderr,
        )
        sys.exit(1)
    if not use_cdp and len(sys.argv) < 5:
        print(
            "Uso: python -m instagram_poster.autoclick_run_script <url> <path_positions.json> <interval_sec> <max_rounds>",
            file=sys.stderr,
        )
        sys.exit(1)

    if use_cdp:
        cdp_port = sys.argv[2].strip()
        try:
            port_num = int(cdp_port)
            cdp_url = f"http://127.0.0.1:{port_num}"
        except ValueError:
            cdp_url = cdp_port
        positions_path = Path(sys.argv[3]).resolve()
        try:
            interval_seconds = float(sys.argv[4])
        except ValueError:
            interval_seconds = 2.0
        try:
            max_rounds = int(sys.argv[5])
        except ValueError:
            max_rounds = 0
    else:
        url = sys.argv[1].strip()
        positions_path = Path(sys.argv[2]).resolve()
        try:
            interval_seconds = float(sys.argv[3])
        except ValueError:
            interval_seconds = 2.0
        try:
            max_rounds = int(sys.argv[4])
        except ValueError:
            max_rounds = 0

    positions = _load_positions(positions_path)
    if len(positions) < 1:
        print("É necessária pelo menos 1 posição.", file=sys.stderr)
        sys.exit(1)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright não instalado. Executa: pip install playwright e python -m playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        with sync_playwright() as p:
            if use_cdp:
                browser = p.chromium.connect_over_cdp(cdp_url)
                try:
                    if not browser.contexts:
                        print("Browser de sessão sem contextos.", file=sys.stderr)
                        sys.exit(1)
                    context = browser.contexts[0]
                    if not context.pages:
                        print("Browser de sessão sem páginas abertas.", file=sys.stderr)
                        sys.exit(1)
                    page = context.pages[0]
                    _run_click_loop(page, positions, interval_seconds, max_rounds)
                finally:
                    pass
            else:
                browser = p.chromium.launch(headless=False)
                try:
                    context = browser.new_context()
                    page = context.new_page()
                    page.goto(url, timeout=60000)
                    _run_click_loop(page, positions, interval_seconds, max_rounds)
                finally:
                    browser.close()
    except Exception as e:
        if _is_connection_error(e):
            sys.exit(0)
        raise


if __name__ == "__main__":
    main()
