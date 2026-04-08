"""
Autoresposta a comentários nos posts do Instagram.
Responde com emoji de agradecimento aos comentários que ainda não têm resposta.
"""
import streamlit as st

from instagram_poster.auth import require_auth, render_auth_sidebar

st.set_page_config(page_title="Comentários | Instagram Auto Post", page_icon="💬", layout="wide")
require_auth()
with st.sidebar:
    render_auth_sidebar()

# Navegação
nav1, nav2, nav3, nav4, nav5, nav6, _ = st.columns([1, 1, 1, 1, 1, 1, 2])
with nav1:
    if st.button("← Inicio", key="nav_home_cmt"):
        st.switch_page("app.py")
with nav2:
    if st.button("⚙️ Configuracao", key="nav_cfg_cmt"):
        st.switch_page("pages/1_Configuracao.py")
with nav3:
    if st.button("📸 Posts", key="nav_posts_cmt"):
        st.switch_page("pages/2_Posts.py")
with nav4:
    if st.button("🔄 Autopublish", key="nav_ap_cmt"):
        st.switch_page("pages/4_Autopublish.py")
with nav5:
    if st.button("📱 Stories", key="nav_stories_cmt"):
        st.switch_page("pages/5_Stories.py")
with nav6:
    if st.button("🎬 Reels", key="nav_reels_cmt"):
        st.switch_page("pages/4_Reels.py")

st.title("Autoresposta a comentários")
st.caption(
    "Responde automaticamente aos comentários nos teus posts com uma mensagem de agradecimento. "
    "A API do Instagram não permite dar like em comentários."
)

from instagram_poster.comment_autoreply import run_autoreply, get_replied_count, reset_replied_ids

st.subheader("Configuração")
use_ai = st.toggle("Usar IA para as respostas (Pollinations)", value=False, help="Se ativo, ignora a mensagem abaixo e usa IA para gerar uma resposta personalizada Mentionando o utilizador.")
msg = st.text_input(
    "Mensagem de agradecimento (fallback/estática)",
    value="🙏",
    max_chars=300,
    help="Emoji ou texto a enviar como resposta se a IA estiver desligada.",
    disabled=use_ai
)
max_media = st.slider("Número de posts a verificar", min_value=5, max_value=25, value=10)
delay = st.number_input("Pausa entre respostas (segundos)", min_value=0.0, max_value=10.0, value=2.0, step=0.5)

if st.button("Executar autoresposta agora", type="primary", key="run_autoreply"):
    try:
        with st.spinner("A processar comentários..."):
            result = run_autoreply(message=msg or "🙏", max_media=max_media, delay_seconds=delay, use_ai=use_ai)
        for item in result.get("replied_items", []):
            from instagram_poster import autopublish
            autopublish.log_comment_reply(
                username=item.get("username", "?"),
                text_preview=item.get("text_preview", ""),
                comment_id=item.get("comment_id", ""),
            )
        st.success(
            f"Concluído: {result['replied']} resposta(s) enviada(s), {result['skipped']} comentário(s) já respondido(s). "
            f"Verificados {result.get('media_count', 0)} post(s), {result.get('comments_total', 0)} comentário(s) no total."
        )
        if result.get("errors"):
            for err in result["errors"]:
                st.error(err)
        if result.get("log"):
            with st.expander("Log detalhado", expanded=True):
                for line in result["log"]:
                    st.text(line)
    except Exception as e:
        st.error(f"Erro: {e}")
        st.info(
            "Verifica se a conta Instagram está ligada na Configuração e se a app tem a permissão "
            "instagram_business_manage_comments (gerir comentários)."
        )

st.divider()

col_info1, col_info2 = st.columns(2)
with col_info1:
    replied_count = get_replied_count()
    st.metric("Comentários já respondidos (cache)", replied_count)
with col_info2:
    if st.button("🗑️ Limpar cache de respondidos", key="reset_replied"):
        removed = reset_replied_ids()
        st.success(f"{removed} ID(s) removido(s). Na próxima execução, todos os comentários serão verificados novamente.")
        st.rerun()

st.caption(
    "**Uma resposta por comentário:** cada comentário recebe no máximo uma resposta. "
    "Os IDs são guardados em ficheiro e verificados na API para evitar duplicados. "
    "Se limpares o cache, o sistema volta a verificar todos os comentários mas só responde aos que ainda não têm resposta na API."
)
