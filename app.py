"""
Instagram Auto Post – Página inicial.
Configura os acessos e gere os posts (usa os botões abaixo ou o menu lateral).
"""
import streamlit as st
from instagram_poster import config  # noqa: F401 — carrega .env e patch IPv4
from instagram_poster.config import get_autopublish_enabled, get_autopublish_interval

st.set_page_config(page_title="Instagram Auto Post", page_icon="📸", layout="wide")

# Arrancar autopublish automaticamente (uma vez por sessao Streamlit)
if "autopublish_started" not in st.session_state:
    st.session_state.autopublish_started = False
if get_autopublish_enabled() and not st.session_state.autopublish_started:
    from instagram_poster.autopublish import start_background_loop, is_running
    if not is_running():
        start_background_loop(interval_minutes=get_autopublish_interval())
    st.session_state.autopublish_started = True

# Callback OAuth Instagram (se configurado)
_params = st.query_params
if "code" in _params and "state" in _params:
    _state = _params.get("state", "")
    _code = _params.get("code", "")
    if _state == "instagram" and _code:
        try:
            from instagram_poster.oauth_instagram import exchange_code_for_token
            exchange_code_for_token(_code)
            st.session_state.oauth_success = "Instagram ligado com sucesso."
        except Exception as e:
            st.session_state.oauth_error = f"Instagram: {e}"
    st.query_params.clear()
    st.switch_page("pages/1_Configuracao.py")
if "error" in _params:
    st.session_state.oauth_error = _params.get("error_description", _params.get("error", "Autorização cancelada."))
    st.query_params.clear()
    st.switch_page("pages/1_Configuracao.py")

st.title("Instagram Auto Post")
st.caption("Publicação via Instagram Graph API + Google Sheet")

st.markdown("### Acesso rapido")
col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)
with col1:
    if st.button("⚙️ Configuracao", use_container_width=True):
        st.switch_page("pages/1_Configuracao.py")
with col2:
    if st.button("📸 Gestao de Posts", use_container_width=True):
        st.switch_page("pages/2_Posts.py")
with col3:
    if st.button("✏️ Criar Conteudo", use_container_width=True):
        st.switch_page("pages/3_Conteudo.py")
with col4:
    if st.button("🔄 Autopublish – Historico", use_container_width=True):
        st.switch_page("pages/4_Autopublish.py")
with col5:
    if st.button("📱 Stories", use_container_width=True):
        st.switch_page("pages/5_Stories.py")
with col6:
    if st.button("🎬 Reels", use_container_width=True):
        st.switch_page("pages/4_Reels.py")
with col7:
    if st.button("🎵 YouTube Áudio", use_container_width=True):
        st.switch_page("pages/6_YouTube_Audio.py")
with col8:
    if st.button("🖱️ Auto Click", use_container_width=True):
        st.switch_page("pages/7_AutoClick.py")

st.markdown("""
### Como usar

1. **Configuracao** -- Faz upload do JSON do Google (OAuth Client), preenche o ID do Sheet,
   credenciais Instagram e provedor de imagens.

2. **Criar Conteudo** -- Gera novos posts com IA (quotes, captions, prompts de imagem) e adiciona ao Sheet.

3. **Posts** -- Ve os proximos posts planeados e publica manualmente com "Post next" ou "Post selected row".

4. **Autopublish – Historico** -- Ve os posts publicados automaticamente, erros e eventos. Activa o autopublish e o intervalo na Configuracao; podes tambem configurar o Windows Task Scheduler para publicar sem o browser aberto.

5. **Stories** -- Monitoriza as Stories publicadas e usa o botao para publicar uma Story a partir de um post aleatorio (entre os ja publicados no feed).

6. **Reels** -- Gera um video slideshow (9:16) a partir dos ultimos posts publicados, com opcao de musica (upload ou biblioteca ambient), e publica no Instagram.

7. **YouTube Áudio** -- Cola o link de um vídeo do YouTube e descarrega o áudio em MP3; podes guardar na pasta de música dos Reels.

8. **Auto Click** -- Automatiza cliques numa página do browser (ex.: Instagram). Arranca o browser, autentica manualmente, define até 5 coordenadas na grelha e inicia ciclos de cliques com refresh. Útil para tarefas repetitivas como seguir utilizadores ou interagir com conteúdo.
""")
