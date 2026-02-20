"""
Historico e controlo do Autopublish.
Menu para activar autopublish, Story automatica, iniciar/parar e historico.
"""
import streamlit as st

st.set_page_config(page_title="Autopublish | Instagram Auto Post", page_icon="🔄", layout="wide")

# Navegacao
nav1, nav2, nav3, nav4, nav5, _ = st.columns([1, 1, 1, 1, 1, 2])
with nav1:
    if st.button("← Inicio", key="nav_home_ap"):
        st.switch_page("app.py")
with nav2:
    if st.button("⚙️ Configuracao", key="nav_cfg_ap"):
        st.switch_page("pages/1_Configuracao.py")
with nav3:
    if st.button("📸 Posts", key="nav_posts_ap"):
        st.switch_page("pages/2_Posts.py")
with nav4:
    if st.button("✏️ Conteudo", key="nav_content_ap"):
        st.switch_page("pages/3_Conteudo.py")
with nav5:
    if st.button("📱 Stories", key="nav_stories_ap"):
        st.switch_page("pages/5_Stories.py")

st.title("Autopublish – Historico")
st.caption("Publicacao automatica na hora agendada no Sheet. Configura e controla aqui.")

from instagram_poster import autopublish, config
from instagram_poster.config import (
    get_autopublish_enabled,
    get_autopublish_interval,
    get_autopublish_reel_every_5,
    get_autopublish_story_with_post,
)
from instagram_poster.env_utils import update_env_vars

_ap_running = autopublish.is_running()
_ap_enabled = get_autopublish_enabled()
_ap_interval = get_autopublish_interval()
_ap_story = get_autopublish_story_with_post()
_ap_reel = get_autopublish_reel_every_5()

# ========== Menu Autopublish ==========
st.subheader("Menu Autopublish")
ap_enabled = st.toggle(
    "Activar autopublish",
    value=_ap_enabled,
    key="ap_menu_enabled",
    help="Quando activo, a app verifica de X em X minutos se ha posts prontos e publica.",
)
ap_interval = st.slider(
    "Intervalo de verificacao (minutos)",
    min_value=1, max_value=60, value=_ap_interval,
    key="ap_menu_interval",
    help="A cada N minutos, verifica se ha posts prontos e publica automaticamente.",
)
ap_story = st.toggle(
    "Publicar Story automaticamente com cada post",
    value=_ap_story,
    key="ap_menu_story",
    help="Quando um post e publicado (feed), publica tambem uma Story com a mesma imagem em formato vertical.",
)
ap_reel = st.toggle(
    "Publicar Reel automaticamente a cada 5 posts",
    value=_ap_reel,
    key="ap_menu_reel",
    help="Quando ha 5 ou mais posts publicados, gera e publica um Reel com os ultimos 5 (8s/slide, fade, audio da pasta MUSIC).",
)

# Guardar alteracoes no .env
if ap_enabled != _ap_enabled or ap_interval != _ap_interval or ap_story != _ap_story or ap_reel != _ap_reel:
    update_env_vars({
        "AUTOPUBLISH_ENABLED": "true" if ap_enabled else "false",
        "AUTOPUBLISH_INTERVAL_MINUTES": str(ap_interval),
        "AUTOPUBLISH_STORY_WITH_POST": "true" if ap_story else "false",
        "AUTOPUBLISH_REEL_EVERY_5": "true" if ap_reel else "false",
    })
    config.set_runtime_override("AUTOPUBLISH_ENABLED", "true" if ap_enabled else "false")
    config.set_runtime_override("AUTOPUBLISH_INTERVAL_MINUTES", str(ap_interval))
    config.set_runtime_override("AUTOPUBLISH_STORY_WITH_POST", "true" if ap_story else "false")
    config.set_runtime_override("AUTOPUBLISH_REEL_EVERY_5", "true" if ap_reel else "false")

# Botoes iniciar / parar
col_btn1, col_btn2, _ = st.columns([1, 1, 2])
with col_btn1:
    if _ap_running:
        if st.button("Parar autopublish", key="ap_menu_stop"):
            autopublish.stop_background_loop()
            st.rerun()
    else:
        start_btn = st.button("Iniciar autopublish", type="primary", key="ap_menu_start", disabled=not ap_enabled)
        if start_btn:
            autopublish.start_background_loop(interval_minutes=ap_interval)
            st.rerun()
        if not ap_enabled:
            st.caption("Activa o interruptor «Activar autopublish» para poder iniciar.")
with col_btn2:
    if st.button("Ir para Configuracao", key="go_config_ap"):
        st.switch_page("pages/1_Configuracao.py")

# Estado
if _ap_running:
    st.success(f"Autopublish activo (cada {_ap_interval} min)")
    reel_status = "**Reel auto:** activo (a cada 5 posts)" if ap_reel else "**Reel auto:** inactivo"
    st.caption(reel_status)
elif ap_enabled:
    st.info("Autopublish configurado mas nao iniciado. Clica 'Iniciar autopublish' acima.")
    reel_status = "Reel auto: activo" if ap_reel else "Reel auto: inactivo"
    st.caption(reel_status)
else:
    st.warning("Autopublish desactivado. Activa o interruptor acima.")

# Metricas
stats = autopublish.get_stats()
last_check = autopublish.get_last_check()

col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
with col_s1:
    st.metric("Posts publicados", stats["total_published"])
with col_s2:
    st.metric("Reels auto", stats.get("total_reels", 0), help="Numero de Reels publicados automaticamente. Activa/desactiva no interruptor «Publicar Reel automaticamente a cada 5 posts» acima.")
with col_s3:
    st.metric("Erros", stats["total_errors"])
with col_s4:
    st.metric("Verificacoes", stats["total_checks"])
with col_s5:
    if last_check:
        st.metric("Ultima verificacao", last_check.strftime("%H:%M:%S"))
    elif stats.get("started_at"):
        st.metric("Iniciado em", stats["started_at"].strftime("%H:%M:%S"))
    else:
        st.metric("Ultima verificacao", "—")

st.divider()

# Historico detalhado
ap_log = autopublish.get_log()
if ap_log:
    published_entries = [e for e in ap_log if e.get("type") == "publish"]
    reel_entries = [e for e in ap_log if e.get("type") == "reel"]
    error_entries = [e for e in ap_log if e.get("type") == "error"]
    other_entries = [e for e in ap_log if e.get("type") not in ("publish", "error", "check", "reel")]

    if reel_entries:
        with st.expander(f"Reels publicados automaticamente ({len(reel_entries)})", expanded=True):
            st.caption("Reels gerados com 5 posts, 8s/slide, transicao fade e audio aleatorio da pasta MUSIC.")
            for entry in reversed(reel_entries):
                ts = entry["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                msg = entry.get("message", "")
                mid = entry.get("media_id", "")
                st.markdown(f"**{msg}**")
                st.caption(f"Publicado: {ts}" + (f" | Media ID: `{mid}`" if mid else ""))
                st.divider()

    if published_entries:
        with st.expander(f"Posts publicados ({len(published_entries)})", expanded=True):
            for entry in reversed(published_entries):
                ts = entry["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                quote = entry.get("quote", "")
                post_date = entry.get("date", "")
                post_time = entry.get("time", "")
                row = entry.get("row", "")
                mid = entry.get("media_id", "")
                schedule_info = f"{post_date} {post_time}".strip()

                col_p1, col_p2 = st.columns([3, 1])
                with col_p1:
                    st.markdown(f"**\"{quote}\"**" if quote else "*(sem quote)*")
                with col_p2:
                    st.caption(f"Publicado: {ts}")
                detail_parts = []
                if schedule_info:
                    detail_parts.append(f"Agendado: {schedule_info}")
                if row:
                    detail_parts.append(f"Linha: {row}")
                if mid:
                    detail_parts.append(f"Media ID: `{mid}`")
                if detail_parts:
                    st.caption(" | ".join(detail_parts))
                st.divider()

    if error_entries:
        with st.expander(f"Erros ({len(error_entries)})"):
            for entry in reversed(error_entries):
                ts = entry["timestamp"].strftime("%H:%M:%S")
                st.error(f"[{ts}] {entry['message']}")

    if other_entries:
        with st.expander(f"Eventos do sistema ({len(other_entries)})"):
            for entry in reversed(other_entries):
                ts = entry["timestamp"].strftime("%H:%M:%S")
                st.info(f"[{ts}] {entry['message']}")
else:
    st.caption("Nenhuma actividade registada.")

# Link para Task Scheduler
with st.expander("Configurar Windows Task Scheduler (publicar sem browser)"):
    st.markdown("""
**Para publicar automaticamente mesmo sem a app aberta:**

1. Abre o **Agendador de Tarefas** do Windows (`taskschd.msc`)
2. Clica **Criar Tarefa Basica**
3. Nome: `InstagramAutoPost`
4. Trigger: **Diariamente**, repetir a cada **5 minutos** (ou o intervalo que preferires)
5. Acao: **Iniciar um programa**
   - Programa: o caminho completo para `run_autopublish.bat`
   - Iniciar em: a pasta do projecto
6. Marca "Executar mesmo que o utilizador nao esteja ligado"

O script `run_autopublish.bat` verifica uma vez se ha posts prontos e publica.
    """)
