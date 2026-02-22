"""
Auto Click: grelha com 5 posições de clique, ciclo com refresh e número de ciclos configurável.
"""
import streamlit as st

from instagram_poster import auto_clicker

st.set_page_config(page_title="Auto Click | Instagram Auto Post", page_icon="🖱️", layout="wide")


@st.fragment(run_every=2)
def _poll_run_finished():
    """Quando os ciclos terminam, atualiza a página para mostrar «Parado» e ativar Iniciar."""
    if st.session_state.get("autoclick_was_running") and not auto_clicker.is_running():
        st.session_state["autoclick_was_running"] = False
        st.rerun()

# Navegação
nav1, nav2, nav3, _ = st.columns([1, 1, 1, 3])
with nav1:
    if st.button("← Inicio", key="nav_home_ac"):
        st.switch_page("app.py")
with nav2:
    if st.button("⚙️ Configuracao", key="nav_cfg_ac"):
        st.switch_page("pages/1_Configuracao.py")
with nav3:
    if st.button("📸 Posts", key="nav_posts_ac"):
        st.switch_page("pages/2_Posts.py")

st.title("Auto Click")
st.caption("Passo 1: Arranca o browser e autentica/navega até à página. Passo 2: Inicia os ciclos de cliques nas coordenadas definidas.")

st.info("Na primeira utilização, instala o browser Chromium: `python -m playwright install chromium`")

running = auto_clicker.is_running()
preview_running = auto_clicker.is_preview_running()
session_running = auto_clicker.is_session_browser_running()
session_ready = session_running and (auto_clicker.get_session_port() is not None)  # porta CDP disponível
last_error = auto_clicker.get_last_error()
if last_error:
    st.error(last_error)

# Inicializar grelha a partir de posições guardadas (uma vez)
if "autoclick_grid_init" not in st.session_state:
    st.session_state["autoclick_grid_init"] = True
    saved = auto_clicker.load_positions()
    for i in range(1, 6):
        if i <= len(saved):
            x, y = saved[i - 1]
            st.session_state[f"autoclick_g{i}_x"] = x
            st.session_state[f"autoclick_g{i}_y"] = y
        else:
            st.session_state[f"autoclick_g{i}_x"] = 0
            st.session_state[f"autoclick_g{i}_y"] = 0

# Aplicar atualizações pendentes à grelha ANTES de instanciar os widgets (evita StreamlitAPIException)
if "autoclick_pending_load" in st.session_state:
    for i, (sx, sy) in enumerate(st.session_state["autoclick_pending_load"][:5], start=1):
        st.session_state[f"autoclick_g{i}_x"] = sx
        st.session_state[f"autoclick_g{i}_y"] = sy
    del st.session_state["autoclick_pending_load"]
if "autoclick_pending_use" in st.session_state:
    slot, lx, ly = st.session_state["autoclick_pending_use"]
    st.session_state[f"autoclick_g{slot}_x"] = lx
    st.session_state[f"autoclick_g{slot}_y"] = ly
    del st.session_state["autoclick_pending_use"]

# --- Passo 1: Arrancar browser e autenticar ---
st.subheader("1. Arrancar browser e autenticar")
st.caption("Abre o browser na URL. Autentica (ex.: login no Instagram) e navega até à página onde queres os cliques. Só depois clica em **Iniciar** (secção abaixo).")
url = st.text_input(
    "URL inicial",
    value=st.session_state.get("autoclick_url", "https://www.instagram.com/"),
    placeholder="https://...",
    key="autoclick_url",
    disabled=running,
)
col_session, col_session_help, _ = st.columns([1, 2, 2])
with col_session:
    if session_running:
        if st.button("Fechar browser (sessão)", key="autoclick_stop_session", disabled=running):
            auto_clicker.stop_session_browser()
            st.rerun()
    else:
        if st.button("Arrancar browser", type="primary", key="autoclick_start_session", disabled=running or not (url and url.strip())):
            if url and url.strip():
                auto_clicker.start_session_browser(url.strip())
                st.rerun()
with col_session_help:
    if session_ready:
        st.success("Browser aberto. Autentica e navega até à página desejada. Depois usa **Iniciar** na secção «Intervalo e ciclos».")
        st.caption("Se não vires a janela do Chromium, verifica a **barra de tarefas** ou atrás de outras janelas. Se tiver fechado, atualiza a página — o aviso «Browser aberto» desaparece quando o browser fecha.")
    elif session_running:
        st.warning("Browser a arrancar… Aguarda alguns segundos. Se a janela já abriu, clica em **Atualizar** para ativar o botão Iniciar.")
        if st.button("Atualizar", key="autoclick_refresh_session", disabled=running):
            st.rerun()
    else:
        st.caption("Clica em **Arrancar browser**, faz login se necessário e vai à página onde queres os cliques.")

# --- Ajuda para coordenadas (preview opcional) ---
st.subheader("Ajuda para coordenadas (opcional)")
st.caption("Para descobrir X e Y de cada posição, podes abrir um browser de preview e clicar para guardar coordenadas.")
col_open, col_preview_help, _ = st.columns([1, 2, 2])
with col_open:
    preview_clicked = st.button(
        "Abrir browser para ver coordenadas",
        key="autoclick_open_preview",
        disabled=running,
        help="Abre uma janela do browser com overlay de coordenadas para obter X e Y de cada posição.",
    )
    if preview_clicked:
        if url and url.strip():
            auto_clicker.start_preview(url.strip())
            st.rerun()
        else:
            st.warning("Indica um URL em «URL inicial» antes de abrir o browser para coordenadas.")
            st.rerun()
with col_preview_help:
    last_click = auto_clicker.read_last_click()
    if last_click:
        lx, ly = last_click
        slot = st.selectbox("Preencher posição", list(range(1, 6)), format_func=lambda i: f"Posição {i}", key="autoclick_slot")
        if st.button("Usar (X,Y) do browser para esta posição", key="autoclick_use_for_slot", disabled=running):
            st.session_state["autoclick_pending_use"] = (slot, lx, ly)
            st.rerun()
        st.caption(f"Último clique no browser: (**{lx}**, **{ly}**). Escolhe a posição e clica em «Usar».")
if preview_running:
    if st.button("Fechar browser de preview", key="autoclick_stop_preview", disabled=running):
        auto_clicker.stop_preview()
        st.rerun()
    st.caption("Browser aberto: move o rato e clica; as coordenadas aparecem. Depois usa «Usar para esta posição» na grelha.")

# --- 2. Grelha das 5 posições ---
st.subheader("2. Grelha das 5 posições de clique")
st.caption("Introduz X e Y (em pixels) para cada um dos 5 cliques. Podes abrir o browser acima para descobrir os valores e preencher com «Usar».")

for i in range(1, 6):
    c1, c2, c3 = st.columns([1, 1, 3])
    with c1:
        st.number_input(
            f"Posição {i} — X",
            min_value=0,
            value=st.session_state.get(f"autoclick_g{i}_x", 0),
            key=f"autoclick_g{i}_x",
            disabled=running,
        )
    with c2:
        st.number_input(
            f"Posição {i} — Y",
            min_value=0,
            value=st.session_state.get(f"autoclick_g{i}_y", 0),
            key=f"autoclick_g{i}_y",
            disabled=running,
        )

def _grid_positions():
    return [
        (st.session_state.get(f"autoclick_g{i}_x", 0), st.session_state.get(f"autoclick_g{i}_y", 0))
        for i in range(1, 6)
    ]

pos_list = _grid_positions()
col_save, col_load, _ = st.columns([1, 1, 2])
with col_save:
    if st.button("Guardar grelha como referência", key="autoclick_save_ref", disabled=running):
        auto_clicker.save_positions(pos_list)
        st.success("Grelha guardada.")
        st.rerun()
with col_load:
    if auto_clicker.load_positions() and st.button("Carregar posições guardadas", key="autoclick_load_ref", disabled=running):
        saved = auto_clicker.load_positions()
        st.session_state["autoclick_pending_load"] = [(sx, sy) for sx, sy in saved[:5]]
        st.rerun()

# --- 3. Intervalo e ciclos ---
st.subheader("3. Intervalo e número de ciclos")
st.caption("Cada ciclo = 5 cliques (nas posições da grelha) + refresh da página. **Iniciar** só está ativo com o browser de sessão aberto (passo 1).")

col_interval, col_cycles, _ = st.columns([1, 1, 2])
with col_interval:
    interval_sec = st.number_input(
        "Intervalo entre cliques (segundos)",
        min_value=0.5,
        value=2.0,
        step=0.5,
        key="autoclick_interval",
        disabled=running,
    )
with col_cycles:
    num_cycles = st.number_input(
        "Número de ciclos (rondas)",
        min_value=0,
        value=0,
        step=1,
        key="autoclick_num_cycles",
        help="0 = infinito (repetir até clicares em Parar).",
        disabled=running,
    )

col_btn1, col_btn2, col_btn_help = st.columns([1, 1, 2])
with col_btn1:
    max_rounds = int(num_cycles) if num_cycles and num_cycles > 0 else None
    # Iniciar só ativo quando o browser de sessão está pronto (porta CDP disponível)
    start_disabled = running or not session_ready or not (url and url.strip())
    if st.button("Iniciar", type="primary", key="autoclick_start", disabled=start_disabled):
        if url and url.strip():
            positions = _grid_positions()
            auto_clicker.start(
                url.strip(),
                positions[0][0],
                positions[0][1],
                float(interval_sec),
                max_clicks=None,
                positions=positions,
                max_rounds=max_rounds,
            )
            st.rerun()
with col_btn2:
    if st.button("Parar", key="autoclick_stop", disabled=not running):
        auto_clicker.stop()
        st.rerun()
with col_btn_help:
    if not session_ready and not running:
        st.warning("Arranca primeiro o browser (passo 1), autentica e navega até à página; depois podes clicar em **Iniciar**.")

if running:
    st.session_state["autoclick_was_running"] = True
    rc = st.session_state.get("autoclick_num_cycles", 0)
    cycles_info = f"{rc} ciclos" if rc and rc > 0 else "ciclos infinitos"
    st.success(f"A correr: 5 cliques por ciclo + refresh. {cycles_info}. O rato move-se no browser já aberto.")
else:
    st.session_state["autoclick_was_running"] = False
    st.caption("Parado.")

_poll_run_finished()
