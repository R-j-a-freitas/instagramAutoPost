"""
Instagram Auto Post – Página inicial.
Configura os acessos e gere os posts (usa os botões abaixo ou o menu lateral).
"""
import streamlit as st
from instagram_poster import config  # noqa: F401 — carrega .env e patch IPv4

st.set_page_config(page_title="Instagram Auto Post", page_icon="📸", layout="wide")

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

st.markdown("### Acesso rápido")
col1, col2, _ = st.columns([1, 1, 2])
with col1:
    if st.button("⚙️ Configuração", use_container_width=True):
        st.switch_page("pages/1_Configuracao.py")
with col2:
    if st.button("📸 Gestão de Posts", use_container_width=True):
        st.switch_page("pages/2_Posts.py")

st.markdown("""
### Como usar

1. **Configuração** – Faz upload do JSON do Google (OAuth Client), preenche o ID do Sheet,
   credenciais Instagram e API Key do Gemini. Na primeira verificação do Google Sheets,
   o browser abre para autorizares (uma única vez).

2. **Posts** – Vê os próximos posts planeados e publica com "Post next" ou "Post selected row".
""")
