"""
Gestão de posts no Instagram: ver próximos posts e publicar.
Inclui verificação das ligações antes de publicar.
"""
import streamlit as st
from datetime import date, datetime

from instagram_poster.auth import require_auth, render_auth_sidebar
from instagram_poster import config
from instagram_poster.config import get_media_backend, get_media_base_url
from instagram_poster.providers import AVAILABLE_PROVIDERS
from instagram_poster.scheduler import run_publish_next, run_publish_row
from instagram_poster.sheets_client import get_upcoming_posts
from instagram_poster.verification import verify_all_connections

if "last_publish_result" not in st.session_state:
    st.session_state.last_publish_result = None


def _init_config_session():
    if "config_sheet_id" not in st.session_state:
        st.session_state.config_sheet_id = config.get_ig_sheet_id() or ""
    if "config_ig_business_id" not in st.session_state:
        st.session_state.config_ig_business_id = config.get_ig_business_id() or ""
    if "config_ig_access_token" not in st.session_state:
        st.session_state.config_ig_access_token = config.get_ig_access_token() or ""
    if "config_gemini_api_key" not in st.session_state:
        st.session_state.config_gemini_api_key = config.get_gemini_api_key() or ""
    if "config_openai_api_key" not in st.session_state:
        st.session_state.config_openai_api_key = config.get_openai_api_key() or ""
    if "config_pollinations_api_key" not in st.session_state:
        st.session_state.config_pollinations_api_key = config.get_pollinations_api_key() or ""
    # Sempre sincronizar o provedor a partir da config/.env para não usar valor antigo da session
    st.session_state.config_image_provider = config.get_image_provider() or "gemini"


def _apply_config_from_session():
    config.set_runtime_override("IG_SHEET_ID", st.session_state.get("config_sheet_id", ""))
    config.set_runtime_override("IG_BUSINESS_ID", st.session_state.get("config_ig_business_id", ""))
    config.set_runtime_override("IG_ACCESS_TOKEN", st.session_state.get("config_ig_access_token", ""))
    config.set_runtime_override("GEMINI_API_KEY", st.session_state.get("config_gemini_api_key", ""))
    config.set_runtime_override("OPENAI_API_KEY", st.session_state.get("config_openai_api_key", ""))
    config.set_runtime_override("POLLINATIONS_API_KEY", st.session_state.get("config_pollinations_api_key", ""))
    config.set_runtime_override("IMAGE_PROVIDER", st.session_state.get("config_image_provider", "gemini"))


def _mask_key(key: str) -> str:
    """Mascara uma API key mostrando apenas os primeiros e últimos caracteres."""
    if not key or len(key) < 10:
        return "---"
    return f"{key[:4]}...{key[-4:]}"


def _render_status_sidebar():
    """Renderiza o painel de estado dos serviços na sidebar."""
    st.sidebar.markdown("### Estado dos serviços")

    # Google Sheets
    sheet_id = config.get_ig_sheet_id()
    if sheet_id:
        st.sidebar.success(f"Sheets: `...{sheet_id[-8:]}`")
    else:
        st.sidebar.error("Sheets: não configurado")

    # Instagram
    ig_id = config.get_ig_business_id()
    ig_token = config.get_ig_access_token()
    if ig_id and ig_token:
        st.sidebar.success(f"Instagram: ID `...{ig_id[-6:]}`")
    else:
        st.sidebar.error("Instagram: não configurado")

    # Provedor de imagens
    provider_key = config.get_image_provider()
    provider_label = AVAILABLE_PROVIDERS.get(provider_key, provider_key)
    if provider_key == "pollinations":
        poll_key = config.get_pollinations_api_key()
        if poll_key:
            st.sidebar.success(f"Imagens: **{provider_label}** (`{_mask_key(poll_key)}`)")
        else:
            st.sidebar.success(f"Imagens: **{provider_label}** (sem key)")
    elif provider_key == "gemini":
        gemini_key = config.get_gemini_api_key()
        if gemini_key:
            st.sidebar.success(f"Imagens: **{provider_label}** (`{_mask_key(gemini_key)}`)")
        else:
            st.sidebar.error(f"Imagens: {provider_label} — API key em falta")
    elif provider_key == "openai":
        openai_key = config.get_openai_api_key()
        if openai_key:
            st.sidebar.success(f"Imagens: **{provider_label}** (`{_mask_key(openai_key)}`)")
        else:
            st.sidebar.error(f"Imagens: {provider_label} — API key em falta")
    else:
        st.sidebar.warning(f"Imagens: provedor desconhecido ({provider_key})")

    # Media (Cloudinary ou local HTTP)
    if get_media_backend() == "local_http":
        st.sidebar.success(f"Media: local HTTP ({get_media_base_url()})")
    else:
        cloud_name = config.CLOUDINARY_CLOUD_NAME
        cloud_url = config.CLOUDINARY_URL
        if (cloud_url and cloud_url.strip().startswith("cloudinary://")) or cloud_name:
            st.sidebar.success(f"Cloudinary: `{cloud_name or 'via URL'}`")
        else:
            st.sidebar.error("Cloudinary: não configurado")

    # Autopublish
    from instagram_poster import autopublish
    if autopublish.is_running():
        interval = config.get_autopublish_interval()
        st.sidebar.success(f"Autopublish: activo (cada {interval} min)")
        last_check = autopublish.get_last_check()
        if last_check:
            st.sidebar.caption(f"Ultima verificacao: {last_check.strftime('%H:%M:%S')}")
        ap_log = autopublish.get_log()
        last_pub = next((e for e in reversed(ap_log) if e["success"] is True), None)
        if last_pub:
            st.sidebar.caption(f"Ultimo post: {last_pub['timestamp'].strftime('%H:%M:%S')} — {last_pub['message'][:40]}")
    elif config.get_autopublish_enabled():
        st.sidebar.warning("Autopublish: configurado mas parado")
    else:
        st.sidebar.info("Autopublish: desactivado")

    st.sidebar.markdown("---")


st.set_page_config(page_title="Posts | Instagram Auto Post", page_icon="📸", layout="wide")
require_auth()
with st.sidebar:
    render_auth_sidebar()
_init_config_session()

nav1, nav2, _ = st.columns([1, 1, 4])
with nav1:
    if st.button("← Início", key="nav_home_posts"):
        st.switch_page("app.py")
with nav2:
    if st.button("⚙️ Configuração", key="nav_cfg_posts"):
        st.switch_page("pages/1_Configuracao.py")

_apply_config_from_session()

# Sidebar: status sempre visível
_render_status_sidebar()

if st.sidebar.button("Verificar todas as ligações"):
    _apply_config_from_session()
    results = verify_all_connections()
    all_ok = all(ok for _, ok, _ in results)
    for name, ok, msg in results:
        if ok:
            st.sidebar.success(f"{name}: {msg}")
        else:
            st.sidebar.error(f"{name}: {msg}")
    if all_ok:
        st.sidebar.success("Todas as ligações OK. Podes publicar.")

n_posts = st.sidebar.slider("N.º de posts a mostrar", min_value=7, max_value=21, value=14)

st.title("Gestão de posts")
st.caption("Próximos posts planeados e publicação no Instagram")

try:
    posts = get_upcoming_posts(n=n_posts, from_date=date.today())
except Exception as e:
    st.error(f"Erro ao ler o Google Sheet: {e}")
    st.info("Configura os acessos na página **Configuração** (menu lateral) primeiro.")
    st.stop()

if not posts:
    st.warning("Nenhum post encontrado a partir de hoje no Sheet.")
    st.stop()

st.subheader("Próximos posts")
table_data = []
for p in posts:
    caption_preview = (p.get("caption") or "")[:50] + ("..." if len(p.get("caption") or "") > 50 else "")
    gemini_preview = (p.get("gemini_prompt") or "")[:40] + ("..." if len(p.get("gemini_prompt") or "") > 40 else "")
    table_data.append({
        "Linha": p.get("row_index"),
        "Data": p.get("date", ""),
        "Hora": p.get("time", ""),
        "Image Text": (p.get("image_text") or "")[:40] + ("..." if len(p.get("image_text") or "") > 40 else ""),
        "Caption": caption_preview,
        "Gemini_Prompt": gemini_preview,
        "Status": p.get("status", ""),
        "Published": p.get("published", ""),
        "Image Prompt": (p.get("image_prompt") or "")[:30] + ("..." if len(p.get("image_prompt") or "") > 30 else ""),
    })
st.dataframe(table_data, use_container_width=True, hide_index=True)

st.subheader("Publicar")
row_options = [f"Linha {p['row_index']} — {p.get('date')} {p.get('time')} — {(p.get('image_text') or '')[:40]}..." for p in posts]
row_values = [p["row_index"] for p in posts]
selected_label = st.selectbox(
    "Escolhe a linha para publicar (Post selected row):",
    options=row_options,
    index=0,
)
selected_row_index = row_values[row_options.index(selected_label)] if selected_label else row_values[0]

col1, col2, _ = st.columns([1, 1, 2])
with col1:
    if st.button("Post next", type="primary"):
        success, message, media_id, _post = run_publish_next(today=date.today(), now=datetime.now().time())
        st.session_state.last_publish_result = (success, message, media_id)
        st.rerun()
with col2:
    if st.button("Post selected row"):
        success, message, media_id, _post = run_publish_row(selected_row_index)
        st.session_state.last_publish_result = (success, message, media_id)
        st.rerun()

if st.session_state.last_publish_result:
    success, message, media_id = st.session_state.last_publish_result
    if success:
        st.success(f"Última ação: {message}")
    else:
        st.error(f"Última ação: {message}")

with st.expander("Ver detalhes do post selecionado"):
    detail = next((p for p in posts if p["row_index"] == selected_row_index), None)
    if detail:
        st.write("**Image Text:**", detail.get("image_text") or "(vazio)")
        st.write("**Caption:**", detail.get("caption") or "(vazio)")
        st.write("**Gemini_Prompt:**", detail.get("gemini_prompt") or "(vazio)")
        st.write("**ImageURL:**", detail.get("image_url") or "(vazio)")
        st.write("**Image Prompt:**", detail.get("image_prompt") or "(vazio)")
        st.write("**Status:**", detail.get("status"), "| **Published:**", detail.get("published"))
