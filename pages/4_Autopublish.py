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
    get_autopublish_comment_autoreply,
    get_autopublish_enabled,
    get_autopublish_interval,
    get_autopublish_reel_every_5,
    get_autopublish_reel_reuse_interval_minutes,
    get_autopublish_reel_reuse_schedule_enabled,
    get_autopublish_story_reuse_interval_minutes,
    get_autopublish_story_reuse_schedule_enabled,
    get_autopublish_story_with_music,
    get_autopublish_story_with_post,
)
from instagram_poster.env_utils import update_env_vars

_ap_running = autopublish.is_running()
_ap_enabled = get_autopublish_enabled()
_ap_interval = get_autopublish_interval()
_ap_story = get_autopublish_story_with_post()
_ap_story_music = get_autopublish_story_with_music()
_ap_story_reuse = get_autopublish_story_reuse_schedule_enabled()
_ap_story_reuse_interval = get_autopublish_story_reuse_interval_minutes()
_ap_reel = get_autopublish_reel_every_5()
_ap_reel_reuse = get_autopublish_reel_reuse_schedule_enabled()
_ap_reel_reuse_interval = get_autopublish_reel_reuse_interval_minutes()
_ap_comment_autoreply = get_autopublish_comment_autoreply()

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
ap_story_music = st.toggle(
    "Adicionar musica nas Stories (video com audio da pasta MUSIC)",
    value=_ap_story_music,
    key="ap_menu_story_music",
    help="Gera um video (ate 60s, maximo da API) com a imagem + musica e publica como Story. Requer moviepy.",
)
st.caption(
    "**Duas fontes de Stories:** (1) Story com cada post — 1 Story por cada post publicado; "
    "(2) Story reuse — 1 Story a cada X horas com imagem de um post aleatorio. "
    "Se ambas estiverem activas, o total de Stories e a soma das duas."
)
col_story_reuse_toggle, col_story_reuse_time, col_story_reuse_unit = st.columns([2, 1, 0.5])
with col_story_reuse_toggle:
    ap_story_reuse = st.toggle(
        "Criar Stories com posts já usados a cada",
        value=_ap_story_reuse,
        key="ap_menu_story_reuse",
        help="Publica uma Story com a imagem do ultimo post publicado no intervalo definido ao lado.",
    )
with col_story_reuse_time:
    ap_story_reuse_interval_hours = st.number_input(
        "horas",
        min_value=0.5,
        max_value=168.0,
        value=round(_ap_story_reuse_interval / 60, 1),
        step=0.5,
        key="ap_menu_story_reuse_interval",
        label_visibility="collapsed",
    )
with col_story_reuse_unit:
    st.caption("h")
ap_reel = st.toggle(
    "Publicar Reel automaticamente a cada 5 posts nunca usados em Reels",
    value=_ap_reel,
    key="ap_menu_reel",
    help="Critério: 5 posts já publicados no Sheet (com ImageURL) que ainda não tenham sido usados em nenhum Reel (registo em assets/reels_used_rows.json). Gera e publica um Reel (8s/slide, fade, áudio da pasta MUSIC). Não significa «5 posts novos desde o último Reel».",
)
col_reuse_toggle, col_reuse_time, col_reuse_unit = st.columns([2, 1, 0.5])
with col_reuse_toggle:
    ap_reel_reuse = st.toggle(
        "Criar Reels com posts já usados a cada",
        value=_ap_reel_reuse,
        key="ap_menu_reel_reuse",
        help="Gera e publica um Reel com os ultimos 5 posts (podem ser ja usados em Reels) no intervalo definido ao lado.",
    )
with col_reuse_time:
    ap_reel_reuse_interval_hours = st.number_input(
        "horas",
        min_value=0.5,
        max_value=168.0,
        value=round(_ap_reel_reuse_interval / 60, 1),
        step=0.5,
        key="ap_menu_reel_reuse_interval",
        label_visibility="collapsed",
    )
with col_reuse_unit:
    st.caption("h")
ap_comment_autoreply = st.toggle(
    "Autoresposta a comentários em cada verificação",
    value=_ap_comment_autoreply,
    key="ap_menu_comment_autoreply",
    help="Em cada ciclo do autopublish, responde aos comentários nos teus posts com 🙏 (emoji de agradecimento).",
)

# Guardar alteracoes no .env
ap_story_reuse_interval = max(30, int(ap_story_reuse_interval_hours * 60))
ap_reel_reuse_interval = max(30, int(ap_reel_reuse_interval_hours * 60))
if (ap_enabled != _ap_enabled or ap_interval != _ap_interval or ap_story != _ap_story or ap_story_music != _ap_story_music or ap_story_reuse != _ap_story_reuse or ap_story_reuse_interval != _ap_story_reuse_interval
        or ap_reel != _ap_reel or ap_reel_reuse != _ap_reel_reuse or ap_reel_reuse_interval != _ap_reel_reuse_interval
        or ap_comment_autoreply != _ap_comment_autoreply):
    update_env_vars({
        "AUTOPUBLISH_ENABLED": "true" if ap_enabled else "false",
        "AUTOPUBLISH_INTERVAL_MINUTES": str(ap_interval),
        "AUTOPUBLISH_STORY_WITH_POST": "true" if ap_story else "false",
        "AUTOPUBLISH_STORY_WITH_MUSIC": "true" if ap_story_music else "false",
        "AUTOPUBLISH_STORY_REUSE_SCHEDULE": "true" if ap_story_reuse else "false",
        "AUTOPUBLISH_STORY_REUSE_INTERVAL_MINUTES": str(ap_story_reuse_interval),
        "AUTOPUBLISH_REEL_EVERY_5": "true" if ap_reel else "false",
        "AUTOPUBLISH_REEL_REUSE_SCHEDULE": "true" if ap_reel_reuse else "false",
        "AUTOPUBLISH_REEL_REUSE_INTERVAL_MINUTES": str(ap_reel_reuse_interval),
    })
    config.set_runtime_override("AUTOPUBLISH_ENABLED", "true" if ap_enabled else "false")
    config.set_runtime_override("AUTOPUBLISH_INTERVAL_MINUTES", str(ap_interval))
    config.set_runtime_override("AUTOPUBLISH_STORY_WITH_POST", "true" if ap_story else "false")
    config.set_runtime_override("AUTOPUBLISH_STORY_WITH_MUSIC", "true" if ap_story_music else "false")
    config.set_runtime_override("AUTOPUBLISH_STORY_REUSE_SCHEDULE", "true" if ap_story_reuse else "false")
    config.set_runtime_override("AUTOPUBLISH_STORY_REUSE_INTERVAL_MINUTES", str(ap_story_reuse_interval))
    config.set_runtime_override("AUTOPUBLISH_REEL_EVERY_5", "true" if ap_reel else "false")
    config.set_runtime_override("AUTOPUBLISH_REEL_REUSE_SCHEDULE", "true" if ap_reel_reuse else "false")
    config.set_runtime_override("AUTOPUBLISH_REEL_REUSE_INTERVAL_MINUTES", str(ap_reel_reuse_interval))
    config.set_runtime_override("AUTOPUBLISH_COMMENT_AUTOREPLY", "true" if ap_comment_autoreply else "false")

# Se autopublish esta activado mas o thread nao corre, arrancar automaticamente (evita "bloqueado")
if ap_enabled and not _ap_running:
    autopublish.start_background_loop(interval_minutes=ap_interval)
    st.rerun()

# Botão para forçar gravação no .env (útil para Task Scheduler)
if st.button("Guardar configuração no .env", key="ap_force_save", help="Grava os toggles no .env para o Task Scheduler usar. Faz isto após alterar opções."):
    update_env_vars({
        "AUTOPUBLISH_ENABLED": "true" if ap_enabled else "false",
        "AUTOPUBLISH_INTERVAL_MINUTES": str(ap_interval),
        "AUTOPUBLISH_STORY_WITH_POST": "true" if ap_story else "false",
        "AUTOPUBLISH_STORY_WITH_MUSIC": "true" if ap_story_music else "false",
        "AUTOPUBLISH_STORY_REUSE_SCHEDULE": "true" if ap_story_reuse else "false",
        "AUTOPUBLISH_STORY_REUSE_INTERVAL_MINUTES": str(ap_story_reuse_interval),
        "AUTOPUBLISH_REEL_EVERY_5": "true" if ap_reel else "false",
        "AUTOPUBLISH_REEL_REUSE_SCHEDULE": "true" if ap_reel_reuse else "false",
        "AUTOPUBLISH_REEL_REUSE_INTERVAL_MINUTES": str(ap_reel_reuse_interval),
        "AUTOPUBLISH_COMMENT_AUTOREPLY": "true" if ap_comment_autoreply else "false",
    })
    st.success("Configuração guardada no .env.")
    st.rerun()

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
    effective = autopublish.get_effective_interval_minutes()
    interval_display = effective if effective is not None else _ap_interval
    st.success(f"Autopublish activo (intervalo efectivo: {interval_display} min)")
    if effective is not None and effective != _ap_interval:
        st.caption("O slider foi alterado; para usar o novo intervalo, para e volta a iniciar.")
    reel_status = "**Reel auto:** activo (a cada 5 posts)" if ap_reel else "**Reel auto:** inactivo"
    st.caption(reel_status)
elif ap_enabled:
    st.info("Autopublish configurado mas nao iniciado. Clica 'Iniciar autopublish' acima.")
    reel_status = "Reel auto: activo" if ap_reel else "Reel auto: inactivo"
    st.caption(reel_status)
else:
    st.warning("Autopublish desactivado. Activa o interruptor acima.")

# Metricas (get_log primeiro para recarregar do ficheiro se outro processo gravou)
_ = autopublish.get_log()
stats = autopublish.get_stats()
last_check = autopublish.get_last_check()

col_s1, col_s2, col_s3, col_s4, col_s5, col_s6 = st.columns(6)
with col_s1:
    st.metric("Posts publicados", stats["total_published"])
with col_s2:
    st.metric("Stories", stats.get("total_stories", 0), help="Stories publicadas automaticamente ou manualmente.")
with col_s3:
    st.metric("Reels auto", stats.get("total_reels", 0), help="Numero de Reels publicados automaticamente. Activa/desactiva no interruptor «Publicar Reel automaticamente a cada 5 posts» acima.")
with col_s4:
    st.metric("Erros", stats["total_errors"])
with col_s5:
    st.metric("Verificacoes", stats["total_checks"])
with col_s6:
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
    story_entries = [e for e in ap_log if e.get("type") == "story"]
    comment_entries = [e for e in ap_log if e.get("type") == "comment"]
    error_entries = [e for e in ap_log if e.get("type") == "error"]
    check_entries = [e for e in ap_log if e.get("type") == "check"]
    other_entries = [e for e in ap_log if e.get("type") not in ("publish", "error", "check", "reel", "story", "comment")]

    if check_entries:
        with st.expander(f"Verificações ({len(check_entries)})", expanded=True):
            st.caption("Cada verificação corresponde a um ciclo do intervalo definido. Mais recentes em primeiro.")
            col_cap, col_btn = st.columns([3, 1])
            with col_btn:
                if st.button("Limpar verificações", key="ap_clear_checks"):
                    autopublish.clear_check_entries()
                    st.rerun()
            with st.container(height=320):
                for entry in reversed(check_entries):
                    ts = entry["timestamp"].strftime("%H:%M:%S")
                    msg = entry.get("message", "")
                    st.text(f"[{ts}] {msg}")

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

    _ORIGEM_LABELS = {"reuse": "Reuse", "com_post": "Com post", "aleatorio": "Aleatório", "manual": "Manual"}

    with st.expander(f"Stories postadas ({len(story_entries)})", expanded=bool(story_entries)):
        st.caption("Stories publicadas automaticamente com cada post ou manualmente na página Stories.")
        if story_entries:
            for entry in reversed(story_entries):
                ts = entry["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                quote = entry.get("quote", "")
                post_date = entry.get("date", "")
                post_time = entry.get("time", "")
                row = entry.get("row", "")
                mid = entry.get("media_id", "")
                origem = _ORIGEM_LABELS.get(entry.get("story_source", ""), "—")
                schedule_info = f"{post_date} {post_time}".strip()

                col_p1, col_p2 = st.columns([3, 1])
                with col_p1:
                    st.markdown(f"**\"{quote}\"**" if quote else "*(sem quote)*")
                with col_p2:
                    st.caption(f"Story: {ts}")
                detail_parts = [f"Origem: {origem}"]
                if schedule_info:
                    detail_parts.append(f"Post: {schedule_info}")
                if row:
                    detail_parts.append(f"Linha: {row}")
                if mid:
                    detail_parts.append(f"Media ID: `{mid}`")
                if detail_parts:
                    st.caption(" | ".join(detail_parts))
                st.divider()
        else:
            st.caption("Nenhuma Story registada.")

    with st.expander(f"Comentarios respondidos ({len(comment_entries)})", expanded=bool(comment_entries)):
        st.caption("Comentarios respondidos automaticamente com emoji de agradecimento (ex.: 🙏) em cada verificacao.")
        if comment_entries:
            for entry in reversed(comment_entries):
                ts = entry["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                username = entry.get("comment_username", "?")
                text_preview = entry.get("comment_text", "")
                msg = entry.get("message", "")
                cid = entry.get("comment_id", "")

                col_c1, col_c2 = st.columns([3, 1])
                with col_c1:
                    st.markdown(f"**@{username}** «{text_preview}...»")
                with col_c2:
                    st.caption(f"Respondido: {ts}")
                if cid:
                    st.caption(f"Comment ID: `{cid}`")
                st.divider()
        else:
            st.caption("Nenhum comentario respondido ainda.")

    with st.expander(f"Erros ({len(error_entries)})"):
        if st.button("Limpar erros", key="ap_clear_errors", disabled=not error_entries):
            autopublish.clear_error_entries()
            st.rerun()
        if error_entries:
            has_token_error = any(
                "invalid_grant" in (e.get("message") or "").lower()
                or ("token" in (e.get("message") or "").lower() and "expired" in (e.get("message") or "").lower())
                for e in error_entries
            )
            if has_token_error:
                if st.button("🔗 Ir renovar token (Configuração)", type="primary", key="ap_go_renew_token"):
                    st.switch_page("pages/1_Configuracao.py")
                st.caption("Token expirado ou revogado. Clica acima para ir à Configuração e renovar.")
            has_moviepy_error = any(
                "moviepy" in (e.get("message") or "").lower() for e in error_entries
            )
            if has_moviepy_error:
                if st.button("Instalar dependências agora", type="primary", key="ap_install_moviepy"):
                    import subprocess
                    import sys
                    with st.spinner("A instalar (pode demorar alguns minutos)..."):
                        try:
                            result = subprocess.run(
                                [sys.executable, "-m", "pip", "install", "moviepy", "imageio-ffmpeg"],
                                capture_output=True,
                                text=True,
                                timeout=600,
                            )
                        except subprocess.TimeoutExpired:
                            st.error("Instalação demorou demasiado. Tenta no terminal: pip install moviepy imageio-ffmpeg")
                            result = None
                    if result is not None:
                        if result.returncode == 0:
                            st.success("Instalado. Recarrega a página (F5 ou botão do browser).")
                        else:
                            st.error(f"Falha: {result.stderr or result.stdout or 'Erro desconhecido'}")
                st.caption("Recarrega a página após instalar.")
            for entry in reversed(error_entries):
                ts = entry["timestamp"].strftime("%H:%M:%S")
                st.error(f"[{ts}] {entry['message']}")
        else:
            st.caption("Nenhum erro registado.")

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
