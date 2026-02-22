"""
Script standalone para abrir o browser do Auto Click (preview para obter coordenadas X,Y).
É lançado em subprocess para o browser abrir de forma fiável (evita problemas com threads no Windows).
O browser de sessão (Arrancar browser) está em instagram_poster.autoclick_session_browser.
Uso: python -m instagram_poster.autoclick_preview_script <url> [caminho_ficheiro_coords]
"""
import sys
import time
from pathlib import Path


def main():
    args = [a.strip() for a in sys.argv[1:] if a.strip()]
    if len(args) < 1:
        print(
            "Uso: python -m instagram_poster.autoclick_preview_script <url> [caminho_ficheiro_coords]",
            file=sys.stderr,
        )
        sys.exit(1)
    url = args[0]
    if len(args) >= 2:
        coords_file = Path(args[1]).resolve()
    else:
        coords_file = Path(__file__).resolve().parent.parent / ".autoclick_last_click.txt"

    # Overlay que segue o rato; corre em cada documento (incl. após navegação) via add_init_script
    preview_script = """
    (function() {
      function inject() {
        if (!document.body) {
          document.addEventListener('DOMContentLoaded', inject);
          return;
        }
        if (document.getElementById('autoclick-coords-overlay')) return;
        var div = document.createElement('div');
        div.id = 'autoclick-coords-overlay';
        div.setAttribute('style', 'position:fixed;left:0;top:0;background:#1a1a1a;color:#ffeb3b;padding:12px 16px;font-family:monospace;font-size:22px;font-weight:bold;z-index:2147483647;border:4px solid #ffeb3b;border-radius:8px;pointer-events:none;box-shadow:0 4px 20px rgba(0,0,0,0.8);');
        div.textContent = 'X: 0  Y: 0  — Clica para guardar';
        document.body.appendChild(div);
        function updatePos(e) {
          var x = e.clientX, y = e.clientY;
          div.textContent = 'X: ' + x + '  Y: ' + y + '  — Clica para guardar';
          div.style.left = (x + 20) + 'px';
          div.style.top = (y + 15) + 'px';
        }
        document.addEventListener('mousemove', updatePos);
        document.addEventListener('click', function(e) {
          if (typeof window.reportCoords === 'function') {
            window.reportCoords(e.clientX, e.clientY);
          }
        });
      }
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', inject);
      } else {
        inject();
      }
    })();
    """

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Erro: playwright não instalado. Executa: pip install playwright "
            "e python -m playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            try:
                page = browser.new_page()
                page.expose_binding(
                    "reportCoords",
                    lambda source, x, y: coords_file.write_text(
                        f"{int(x)},{int(y)}\n", encoding="utf-8"
                    ),
                )
                # add_init_script faz o overlay ser injetado em TODA a navegação (cada nova página)
                page.add_init_script(preview_script)
                page.goto(url, timeout=60000)
                while browser.is_connected():
                    time.sleep(1)
            finally:
                try:
                    browser.close()
                except Exception:
                    pass
    except Exception as e:
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()