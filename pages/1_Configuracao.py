"""
Configuração dos acessos: Google Sheets, Instagram, geração de imagens, Cloudinary.
Ao carregar JSON ou verificar, as variáveis são atualizadas no .env.
"""
import json
import os
import re
from pathlib import Path
import streamlit as st

from instagram_poster.auth import require_auth, render_auth_sidebar
from instagram_poster import config
from instagram_poster.config import get_media_backend, get_media_base_url
from instagram_poster.env_utils import (
    update_env_from_oauth_client_json,
    update_env_vars,
)
from instagram_poster.providers import AVAILABLE_PROVIDERS
from instagram_poster.sheets_client import get_all_rows_with_image_text, update_gemini_prompt
from instagram_poster.verification import (
    check_instagram_api_status,
    verify_all_connections,
    verify_cloudinary,
    verify_image_provider,
    verify_google_sheets,
    verify_instagram,
)

# URLs de ajuda
GOOGLE_OAUTH_SETUP = "https://console.cloud.google.com/apis/credentials"
INSTAGRAM_DEV_DASHBOARD = "https://developers.facebook.com/apps/"
GEMINI_API_KEY_URL = "https://aistudio.google.com/apikey"
CLOUDINARY_DASHBOARD = "https://console.cloudinary.com/"

# Raiz do projeto (onde fica google_oauth_client.json)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _init_config_session():
    if "config_sheet_id" not in st.session_state:
        st.session_state.config_sheet_id = config.get_ig_sheet_id() or ""
    if "config_google_oauth_client_id" not in st.session_state:
        st.session_state.config_google_oauth_client_id = config.get_google_oauth_client_id() or ""
    if "config_google_oauth_client_secret" not in st.session_state:
        st.session_state.config_google_oauth_client_secret = config.get_google_oauth_client_secret() or ""
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
    if "config_huggingface_token" not in st.session_state:
        st.session_state.config_huggingface_token = config.get_huggingface_token() or ""
    if "config_firefly_client_id" not in st.session_state:
        st.session_state.config_firefly_client_id = config.get_firefly_client_id() or ""
    if "config_firefly_client_secret" not in st.session_state:
        st.session_state.config_firefly_client_secret = config.get_firefly_client_secret() or ""
    if "config_image_provider" not in st.session_state:
        st.session_state.config_image_provider = config.get_image_provider() or "gemini"
    if "config_content_extra_prompt" not in st.session_state:
        st.session_state.config_content_extra_prompt = config.get_content_extra_prompt() or ""
    if "config_content_system_override" not in st.session_state:
        override_content = config.get_content_system_prompt_override()
        st.session_state.config_content_system_override = override_content if override_content else ""
    if "config_cloudinary_url" not in st.session_state:
        st.session_state.config_cloudinary_url = config.get_cloudinary_url() or ""
    if "config_media_backend" not in st.session_state:
        st.session_state.config_media_backend = get_media_backend()
    if "config_media_root" not in st.session_state:
        raw = config.get_runtime_override("MEDIA_ROOT") or os.getenv("MEDIA_ROOT") or config.MEDIA_ROOT
        st.session_state.config_media_root = (raw or "/srv/instagram_media").strip()
    if "config_media_base_url" not in st.session_state:
        st.session_state.config_media_base_url = get_media_base_url()


def _extract_sheet_id(value: str) -> str:
    """Extrai o ID do Sheet de uma URL ou devolve o valor se já for só o ID."""
    if not value or not value.strip():
        return ""
    v = value.strip()
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", v)
    if m:
        return m.group(1)
    return v


def _apply_config_from_session():
    sheet_id = _extract_sheet_id(st.session_state.get("config_sheet_id", ""))
    config.set_runtime_override("IG_SHEET_ID", sheet_id)
    config.set_runtime_override("GOOGLE_OAUTH_CLIENT_ID", st.session_state.get("config_google_oauth_client_id", ""))
    config.set_runtime_override("GOOGLE_OAUTH_CLIENT_SECRET", st.session_state.get("config_google_oauth_client_secret", ""))
    config.set_runtime_override("IG_BUSINESS_ID", st.session_state.get("config_ig_business_id", ""))
    config.set_runtime_override("IG_ACCESS_TOKEN", st.session_state.get("config_ig_access_token", ""))
    config.set_runtime_override("GEMINI_API_KEY", st.session_state.get("config_gemini_api_key", ""))
    config.set_runtime_override("OPENAI_API_KEY", st.session_state.get("config_openai_api_key", ""))
    config.set_runtime_override("POLLINATIONS_API_KEY", st.session_state.get("config_pollinations_api_key", ""))
    config.set_runtime_override("HUGGINGFACE_TOKEN", st.session_state.get("config_huggingface_token", ""))
    config.set_runtime_override("FIREFLY_CLIENT_ID", st.session_state.get("config_firefly_client_id", ""))
    config.set_runtime_override("FIREFLY_CLIENT_SECRET", st.session_state.get("config_firefly_client_secret", ""))
    config.set_runtime_override("IMAGE_PROVIDER", st.session_state.get("config_image_provider", "gemini"))
    config.set_runtime_override("CONTENT_GENERATION_EXTRA_PROMPT", st.session_state.get("config_content_extra_prompt", ""))
    config.set_runtime_override("CLOUDINARY_URL", st.session_state.get("config_cloudinary_url", ""))
    config.set_runtime_override("MEDIA_BACKEND", st.session_state.get("config_media_backend", "cloudinary"))
    config.set_runtime_override("MEDIA_ROOT", st.session_state.get("config_media_root", "/srv/instagram_media"))
    config.set_runtime_override("MEDIA_BASE_URL", st.session_state.get("config_media_base_url", "https://magnific1.ddns.net"))


st.set_page_config(page_title="Configuração | Instagram Auto Post", page_icon="⚙️", layout="wide")
require_auth()
with st.sidebar:
    render_auth_sidebar()
_init_config_session()
_apply_config_from_session()

nav1, nav2, _ = st.columns([1, 1, 4])
with nav1:
    if st.button("← Início", key="nav_home_cfg"):
        st.switch_page("app.py")
with nav2:
    if st.button("📸 Posts", key="nav_posts_cfg"):
        st.switch_page("pages/2_Posts.py")

st.title("Configuração")
st.caption("Liga cada serviço com um clique — autentica no site do provedor e a app recebe o acesso automaticamente.")


def _mask_key(key: str) -> str:
    if not key or len(key) < 10:
        return "---"
    return f"{key[:4]}...{key[-4:]}"


# Resumo de estado no topo
with st.container():
    st.markdown("#### Credenciais activas")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _sheet = config.get_ig_sheet_id()
        if _sheet:
            st.success(f"Sheets\n\n`...{_sheet[-8:]}`")
        else:
            st.error("Sheets\n\nnão configurado")
    with c2:
        _ig = config.get_ig_business_id()
        _tk = config.get_ig_access_token()
        if _ig and _tk:
            st.success(f"Instagram\n\nID `...{_ig[-6:]}`")
        else:
            st.error("Instagram\n\nnão configurado")
    with c3:
        _prov = config.get_image_provider()
        _prov_label = AVAILABLE_PROVIDERS.get(_prov, _prov)
        if _prov == "pollinations":
            _pk = config.get_pollinations_api_key()
            if _pk:
                st.success(f"Imagens\n\n{_prov_label}\n`{_mask_key(_pk)}`")
            else:
                st.success(f"Imagens\n\n**{_prov_label}**\n(sem key)")
        elif _prov == "gemini":
            _gk = config.get_gemini_api_key()
            if _gk:
                st.success(f"Imagens\n\n{_prov_label}\n`{_mask_key(_gk)}`")
            else:
                st.error(f"Imagens\n\n{_prov_label}\nAPI key em falta")
        elif _prov == "openai":
            _ok = config.get_openai_api_key()
            if _ok:
                st.success(f"Imagens\n\n{_prov_label}\n`{_mask_key(_ok)}`")
            else:
                st.error(f"Imagens\n\n{_prov_label}\nAPI key em falta")
    with c4:
        if get_media_backend() == "local_http":
            st.success(f"Media\n\nlocal HTTP\n`{get_media_base_url()}`")
        else:
            _cn = config.CLOUDINARY_CLOUD_NAME
            _cu = config.get_cloudinary_url()
            if (_cu and _cu.strip().startswith("cloudinary://")) or _cn:
                st.success(f"Cloudinary\n\n`{_cn or 'via URL'}`")
            else:
                st.error("Cloudinary\n\nnão configurado")

    # Botão para verificar todas as ligações
    if st.button("🔍 Verificar todas as ligações", type="primary", key="verify_all_cfg"):
        _apply_config_from_session()
        with st.spinner("A verificar ligações..."):
            results = verify_all_connections()
        all_ok = all(ok for _, ok, _ in results)
        if all_ok:
            st.success("Todas as ligações OK.")
        else:
            st.warning("Algumas ligações falharam. Ver detalhes abaixo.")
        with st.expander("Resultado da verificação", expanded=not all_ok):
            for name, ok, msg in results:
                if ok:
                    st.success(f"**{name}:** {msg}")
                else:
                    st.error(f"**{name}:** {msg}")
    st.divider()

# ========== 1. GOOGLE SHEETS ==========
st.subheader("1. Google Sheets")
st.caption("Autentica via OAuth: guardas o Client ID + Secret ou fazes upload do JSON, clicas em «Verificar e aceitar» e o browser trata do resto.")

_oauth_client_exists = (_PROJECT_ROOT / "google_oauth_client.json").exists()
_oauth_token_path = _PROJECT_ROOT / "google_oauth_authorized.json"
_oauth_token_exists = _oauth_token_path.exists()
_has_inline_client = bool(
    (st.session_state.config_google_oauth_client_id or "").strip()
    and (st.session_state.config_google_oauth_client_secret or "").strip()
)
_client_config_available = _oauth_client_exists or _has_inline_client

with st.container():
    col_oauth_id, col_oauth_secret = st.columns(2)
    with col_oauth_id:
        st.text_input(
            "Google OAuth Client ID",
            value=st.session_state.config_google_oauth_client_id,
            key="config_google_oauth_client_id",
            placeholder="ex.: 1234567890-abc.apps.googleusercontent.com",
        )
    with col_oauth_secret:
        st.text_input(
            "Google OAuth Client Secret",
            value=st.session_state.config_google_oauth_client_secret,
            key="config_google_oauth_client_secret",
            type="password",
            placeholder="Client secret",
        )
    if st.button("Guardar OAuth Client ID/Secret", key="save_google_oauth_creds"):
        cid = (st.session_state.get("config_google_oauth_client_id") or "").strip()
        csec = (st.session_state.get("config_google_oauth_client_secret") or "").strip()
        if not cid or not csec:
            st.error("Preenche ambos os campos antes de guardar.")
        else:
            update_env_vars({
                "GOOGLE_OAUTH_CLIENT_ID": cid,
                "GOOGLE_OAUTH_CLIENT_SECRET": csec,
            })
            config.set_runtime_override("GOOGLE_OAUTH_CLIENT_ID", cid)
            config.set_runtime_override("GOOGLE_OAUTH_CLIENT_SECRET", csec)
            st.success("Credenciais guardadas. Agora clica em «Verificar e aceitar» para autorizar no browser.")

if _oauth_token_exists:
    st.success("Google Sheets: autorizado (token guardado)")
    if st.button("Desligar e renovar autorização", key="disconnect_google"):
        if _oauth_token_path.exists():
            _oauth_token_path.unlink()
        st.rerun()
    st.caption("Se aparecer «invalid_grant», clica acima para desligar e depois em «Verificar e aceitar» para reautorizar.")
else:
    with st.expander("📋 Como autorizar", expanded=not _client_config_available):
        st.markdown(
            """
1. **Preenche o ID do Sheet** e o **OAuth Client ID + Secret** (ou faz upload do JSON).
2. Clica em **«Verificar e aceitar — Google Sheets»**.
3. O browser abre — escolhe a conta Google e autoriza.
4. Volta aqui: o token fica guardado para os próximos acessos.
            """
        )
    if not _client_config_available:
        st.warning("Falta definir o OAuth Client ID/Secret ou carregar o JSON.")
    else:
        st.info("Clica em «Verificar e aceitar» para abrir o browser e aprovar o acesso ao Google Sheets.")

st.markdown("**Upload opcional do JSON OAuth**")
st.caption(
    "Descarrega do [Google Cloud Console](" + GOOGLE_OAUTH_SETUP + ") → "
    "Credenciais → OAuth 2.0 Client ID (Computador) → Descarregar JSON. "
    "(Opcional se já preencheste ID e Secret acima.)"
)
uploaded = st.file_uploader("Ficheiro JSON OAuth", type=["json"], key="upload_google_json", label_visibility="collapsed")
if uploaded is not None:
    try:
        data = json.load(uploaded)
        is_oauth_client = False
        for key in ("web", "installed"):
            if key in data:
                c = data[key]
                if (c.get("client_id") or "").strip() and (c.get("client_secret") or "").strip():
                    is_oauth_client = True
                    break
        if is_oauth_client:
            dest = _PROJECT_ROOT / "google_oauth_client.json"
            dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
            update_env_from_oauth_client_json(data)
            st.success("✅ JSON OAuth guardado. A página vai recarregar — clica em «Verificar e aceitar» para abrir o browser.")
            st.rerun()
        else:
            st.error("JSON não reconhecido. Precisas de um ficheiro OAuth Client (com client_id e client_secret).")
    except json.JSONDecodeError as e:
        st.error(f"JSON inválido: {e}")

st.text_input(
    "ID do Google Sheet",
    value=st.session_state.config_sheet_id,
    key="config_sheet_id",
    placeholder="URL ou ID (ex.: 1UBdukuHNvpfdcyBxKIQAt5pRIKFrGLYI6tZdYhfYCig)",
)
st.caption("Preenche o ID do Sheet antes de clicar em Verificar e aceitar.")
if st.button("Verificar e aceitar — Google Sheets", key="verify_sheets"):
    _apply_config_from_session()
    sheet_id = _extract_sheet_id(st.session_state.get("config_sheet_id", ""))
    if sheet_id:
        update_env_vars({"IG_SHEET_ID": sheet_id})
    ok, msg = verify_google_sheets()
    if ok:
        st.success(msg)
    else:
        st.error(msg)
        if "invalid_grant" in (msg or "").lower():
            st.warning("Token expirado ou revogado. Clica em «Desligar e renovar autorização» acima e depois em «Verificar e aceitar» para reautorizar no browser.")
        elif _client_config_available:
            st.info("Na primeira vez, o browser deve abrir para autorizares. Se não abriu, verifica a consola/terminal.")

st.divider()

# ========== 2. INSTAGRAM ==========
st.subheader("2. Instagram Graph API")
st.caption("Publicação no Instagram. Liga com a tua conta ou cola token manualmente.")

with st.expander("📌 Como renovar o token (erro invalid_grant / token expirado)", expanded=False):
    st.markdown("""
**Erro «invalid_grant: Token has been expired or revoked»?**

1. **Forma simples:** Clica no botão **«Ligar com Instagram»** (ou **«Renovar token»** se já estiveres ligado).
2. Serás redirecionado para o Instagram — inicia sessão e autoriza a app.
3. Volta à app — o novo token é guardado automaticamente.

**Alternativa (token manual):** Gera um token no [Meta Developers](https://developers.facebook.com/) → tua app → Instagram → Generate access tokens. Cola o token no campo «Access Token» abaixo e clica em «Verificar e aceitar».
    """)

with st.expander("⚠️ Erro «Invalid platform app» ao clicar em Ligar/Renovar", expanded=True):
    try:
        from instagram_poster.oauth_instagram import get_redirect_uri
        _redirect_uri = get_redirect_uri()
    except Exception:
        _redirect_uri = "http://localhost:8502/"
    st.markdown(f"""
**O que significa:** A app Meta/Instagram não reconhece a configuração. Corrige no [Meta for Developers](https://developers.facebook.com/):

1. **Produto correcto:** A app deve ter **«Instagram API with Instagram Login»** (não só «Instagram Graph API»).  
   → Apps → tua app → Adicionar produto → **Instagram** → escolhe «API with Instagram Login».

2. **Redirect URI exacto:** Em **Instagram** → **Configuração da API** → **Valid OAuth Redirect URIs**, adiciona:
   ```
   {_redirect_uri}
   ```
   (Deve coincidir exactamente, incluindo a barra final `/`.)

3. **Porta:** Se a app corre em **8502** (run.bat), define no `.env`:
   ```
   OAUTH_REDIRECT_BASE=http://localhost:8502
   ```

4. **App ID:** Usa o **Instagram App ID** da secção Instagram (não o App ID geral).

5. **Testadores:** Em modo Development, adiciona a tua conta Instagram como **Instagram Tester** em Roles → Testers.
    """)

try:
    from instagram_poster.oauth_instagram import get_auth_url, has_oauth_token, clear_oauth_token
    ig_oauth_available = get_auth_url(state="instagram") is not None
except Exception:
    ig_oauth_available = False

col_ig1, col_ig2 = st.columns(2)
with col_ig1:
    if ig_oauth_available:
        auth_url = get_auth_url(state="instagram")
        if has_oauth_token():
            st.success("✅ Instagram ligado (OAuth)")
            if auth_url:
                st.link_button("🔗 Renovar token", auth_url, type="secondary", use_container_width=True)
                st.caption("Clica para renovar o token (reautorizar no Instagram). Resolve o erro «invalid_grant».")
            if st.button("Desligar Instagram", key="disconnect_ig"):
                clear_oauth_token()
                st.rerun()
        else:
            if auth_url:
                st.link_button("🔗 Ligar com Instagram", auth_url, type="primary", use_container_width=True)
                st.caption("Serás redirecionado para o Instagram para autorizar. **Usa este botão para renovar o token** se aparecer «invalid_grant».")
    else:
        st.info("Para OAuth: adiciona INSTAGRAM_APP_ID e INSTAGRAM_APP_SECRET ao .env")
        try:
            from instagram_poster.oauth_instagram import get_redirect_uri as _get_ru
            _ru = _get_ru()
        except Exception:
            _ru = "http://localhost:8502/"
        st.caption(f"[Criar app Instagram]({INSTAGRAM_DEV_DASHBOARD}) → Adicionar produto «Instagram API with Instagram Login» → Valid OAuth Redirect URIs: {_ru}")

with col_ig2:
    st.markdown("**Ou: credenciais manuais**")
    with st.expander("📍 Onde ver o ID e o token?", expanded=True):
        st.markdown("""
**No [Meta for Developers](https://developers.facebook.com/):**

1. **Instagram Business ID**  
   Apps → tua app → **Instagram** → **Configuração da API** → secção «1. Generate access tokens».  
   O ID aparece ao lado do nome da conta (ex.: `keepcalmnbepositive` → ID: `17841449097041089`).

2. **Access Token**  
   Na mesma secção, clica em **«Generate token»** ao lado da tua conta.  
   Autoriza e copia o token que aparece. Cola no campo «Access Token» abaixo.
        """)
    st.text_input(
        "Instagram Business ID",
        value=st.session_state.config_ig_business_id,
        key="config_ig_business_id",
        placeholder="ID da conta de negócios (ex.: 17841449097041089)",
        label_visibility="collapsed",
    )
    st.text_input(
        "Access Token",
        value=st.session_state.config_ig_access_token,
        key="config_ig_access_token",
        type="password",
        placeholder="Token (Generate token no Meta Developers)",
        label_visibility="collapsed",
    )

col_verify_ig, col_monitor_ig = st.columns(2)
with col_verify_ig:
    if st.button("Verificar e aceitar — Instagram", key="verify_ig"):
        _apply_config_from_session()
        ig_id = st.session_state.get("config_ig_business_id", "")
        ig_token = st.session_state.get("config_ig_access_token", "")
        if ig_id:
            update_env_vars({"IG_BUSINESS_ID": ig_id})
        if ig_token:
            update_env_vars({"IG_ACCESS_TOKEN": ig_token})
            try:
                from instagram_poster.oauth_instagram import TOKEN_FILE
                if TOKEN_FILE.exists():
                    TOKEN_FILE.unlink()
            except Exception:
                pass
        ok, msg = verify_instagram()
        if ok:
            st.success(msg)
            st.caption("Se usas Task Scheduler ou autopublish em background, reinicia a app para aplicar o novo token.")
        else:
            st.error(msg)
with col_monitor_ig:
    if st.button("Verificar estado da API / rate limits", key="check_ig_api", help="Faz um request de teste e mostra código de erro, headers X-App-Usage, etc. para ver se a API está bloqueada ou no limite."):
        _apply_config_from_session()
        st.session_state["ig_api_status_result"] = check_instagram_api_status()
        st.rerun()
    st.caption("Códigos 4, 17, 32, 613 = rate limit. Headers X-App-Usage com 100% = no limite.")

if st.session_state.get("ig_api_status_result") is not None:
    res = st.session_state["ig_api_status_result"]
    with st.expander("Resultado: estado da API Instagram", expanded=True):
        if res.get("ok"):
            st.success("A API respondeu normalmente. Podes ver os headers de uso em baixo.")
        else:
            st.warning("A API devolveu erro ou está em rate limit. Ver detalhes em baixo.")
        for line in res.get("summary") or []:
            st.write(line)
        st.markdown("**Código HTTP:** " + (str(res.get("status_code")) if res.get("status_code") is not None else "—"))
        if res.get("error_code") is not None:
            st.markdown("**Código de erro da API:** " + str(res["error_code"]))
        if res.get("error_message"):
            st.markdown("**Mensagem:** " + str(res["error_message"]))
        if res.get("usage_headers"):
            st.markdown("**Headers de uso (Meta):**")
            st.code("\n".join(f"{k}: {v}" for k, v in res["usage_headers"].items()), language=None)
        if res.get("body") is not None:
            st.markdown("**Resposta (corpo):**")
            if isinstance(res["body"], dict):
                st.json(res["body"])
            else:
                st.code(str(res["body"]), language=None)
    if st.button("Ocultar resultado da API", key="clear_ig_api_result"):
        st.session_state["ig_api_status_result"] = None
        st.rerun()

st.divider()

# ========== 3. GERAÇÃO DE IMAGENS ==========
st.subheader("3. Geração de imagens")
st.caption("Escolhe o provedor para gerar imagens a partir do prompt. Provedores com tier gratuito (uso/créditos limitados): Pollinations, Gemini, Hugging Face.")

_provider_keys = list(AVAILABLE_PROVIDERS.keys())
_provider_labels = list(AVAILABLE_PROVIDERS.values())
_current_provider = st.session_state.get("config_image_provider", "gemini")
_current_idx = _provider_keys.index(_current_provider) if _current_provider in _provider_keys else 0

selected_provider = st.selectbox(
    "Provedor de imagens",
    options=_provider_keys,
    format_func=lambda k: AVAILABLE_PROVIDERS[k],
    index=_current_idx,
    key="config_image_provider",
)

if selected_provider == "gemini":
    st.link_button("Obter API Key no Google AI Studio", GEMINI_API_KEY_URL, use_container_width=True)
    st.text_input(
        "Gemini API Key",
        value=st.session_state.config_gemini_api_key,
        key="config_gemini_api_key",
        type="password",
        placeholder="Cola a API Key aqui",
    )
elif selected_provider == "openai":
    st.link_button("Obter API Key na OpenAI", "https://platform.openai.com/api-keys", use_container_width=True)
    st.text_input(
        "OpenAI API Key",
        value=st.session_state.config_openai_api_key,
        key="config_openai_api_key",
        type="password",
        placeholder="sk-...",
    )
    st.caption("Usa DALL-E 3 (1024x1024). Custo: ~$0.04 por imagem.")
elif selected_provider == "pollinations":
    st.link_button("Obter API Key no Pollinations", "https://enter.pollinations.ai", use_container_width=True)
    st.text_input(
        "Pollinations API Key",
        value=st.session_state.config_pollinations_api_key,
        key="config_pollinations_api_key",
        type="password",
        placeholder="sk_...",
    )
    st.caption("Usa modelo FLUX via gen.pollinations.ai. Com API key: sem rate-limit. Sem key: funciona com limites.")
elif selected_provider == "huggingface":
    st.link_button("Obter token em Hugging Face", "https://huggingface.co/settings/tokens", use_container_width=True)
    st.text_input(
        "Hugging Face Access Token",
        value=st.session_state.config_huggingface_token,
        key="config_huggingface_token",
        type="password",
        placeholder="hf_...",
    )
    st.caption("Inference API com FLUX.1-schnell (free tier com créditos limitados; ao esgotar, surge 402 — compra créditos ou PRO em huggingface.co). Token em huggingface.co/settings/tokens.")
elif selected_provider == "firefly":
    st.link_button("Obter credenciais no Adobe Developer Console", "https://developer.adobe.com/console", use_container_width=True)
    st.text_input(
        "Firefly Client ID",
        value=st.session_state.config_firefly_client_id,
        key="config_firefly_client_id",
        type="password",
        placeholder="Client ID",
    )
    st.text_input(
        "Firefly Client Secret",
        value=st.session_state.config_firefly_client_secret,
        key="config_firefly_client_secret",
        type="password",
        placeholder="Client Secret",
    )
    st.caption("Adobe Firefly API. Cria um projeto no Adobe Developer Console e adiciona o produto Firefly Services para obter Client ID e Secret.")

# Persistir o provedor escolhido no .env assim que mudar (para Publicar usar o correto mesmo após F5)
_current_env_provider = (os.getenv("IMAGE_PROVIDER") or "gemini").strip()
if selected_provider != _current_env_provider:
    update_env_vars({"IMAGE_PROVIDER": selected_provider})

if st.button("Verificar e gravar a configuração escolhida", key="verify_image_provider"):
    _apply_config_from_session()
    env_updates = {"IMAGE_PROVIDER": selected_provider}
    if selected_provider == "gemini":
        gemini_key = st.session_state.get("config_gemini_api_key", "")
        if gemini_key:
            env_updates["GEMINI_API_KEY"] = gemini_key
    elif selected_provider == "openai":
        openai_key = st.session_state.get("config_openai_api_key", "")
        if openai_key:
            env_updates["OPENAI_API_KEY"] = openai_key
    elif selected_provider == "pollinations":
        poll_key = st.session_state.get("config_pollinations_api_key", "")
        if poll_key:
            env_updates["POLLINATIONS_API_KEY"] = poll_key
    elif selected_provider == "huggingface":
        hf_token = st.session_state.get("config_huggingface_token", "")
        if hf_token:
            env_updates["HUGGINGFACE_TOKEN"] = hf_token
    elif selected_provider == "firefly":
        firefly_id = st.session_state.get("config_firefly_client_id", "")
        firefly_secret = st.session_state.get("config_firefly_client_secret", "")
        if firefly_id:
            env_updates["FIREFLY_CLIENT_ID"] = firefly_id
        if firefly_secret:
            env_updates["FIREFLY_CLIENT_SECRET"] = firefly_secret
    update_env_vars(env_updates)
    ok, msg = verify_image_provider()
    if ok:
        st.success(msg)
    else:
        st.error(msg)

# Botão para gerar imagem de teste (comprovar que o provedor está a funcionar)
if "config_image_provider_last" not in st.session_state:
    st.session_state.config_image_provider_last = selected_provider
provider_changed = st.session_state.config_image_provider_last != selected_provider
if provider_changed:
    st.session_state.config_image_provider_last = selected_provider
    st.info("Provedor de imagens alterado. Gera uma imagem de teste para comprovar que está a funcionar.")

if st.button("Gerar imagem de teste", key="generate_test_image"):
    _apply_config_from_session()
    env_updates = {"IMAGE_PROVIDER": selected_provider}
    if selected_provider == "gemini":
        if st.session_state.get("config_gemini_api_key"):
            env_updates["GEMINI_API_KEY"] = st.session_state.config_gemini_api_key
    elif selected_provider == "openai":
        if st.session_state.get("config_openai_api_key"):
            env_updates["OPENAI_API_KEY"] = st.session_state.config_openai_api_key
    elif selected_provider == "pollinations":
        if st.session_state.get("config_pollinations_api_key"):
            env_updates["POLLINATIONS_API_KEY"] = st.session_state.config_pollinations_api_key
    elif selected_provider == "huggingface":
        if st.session_state.get("config_huggingface_token"):
            env_updates["HUGGINGFACE_TOKEN"] = st.session_state.config_huggingface_token
    elif selected_provider == "firefly":
        if st.session_state.get("config_firefly_client_id"):
            env_updates["FIREFLY_CLIENT_ID"] = st.session_state.config_firefly_client_id
        if st.session_state.get("config_firefly_client_secret"):
            env_updates["FIREFLY_CLIENT_SECRET"] = st.session_state.config_firefly_client_secret
    update_env_vars(env_updates)
    config.set_runtime_override("IMAGE_PROVIDER", selected_provider)
    try:
        from instagram_poster import image_generator
        with st.spinner("A gerar imagem de teste..."):
            test_prompt = "A serene landscape with a small house and trees, soft morning light, no text."
            image_bytes = image_generator.generate_image_from_prompt(test_prompt)
        if image_bytes:
            st.success("Imagem de teste gerada com sucesso.")
            st.image(image_bytes, caption="Imagem de teste", use_container_width=True)
        else:
            st.error("O provedor não devolveu dados.")
    except Exception as e:
        st.error(f"Erro ao gerar imagem de teste: {e}")

st.divider()

# ========== 4. BACKEND DE MEDIA ==========
st.subheader("4. Backend de media")
st.caption(
    "Escolhe onde guardar imagens e vídeos: Cloudinary (nuvem) ou servidor local (nginx). "
    "Com local_http, os ficheiros são gravados em disco e servidos via URL público. "
    "Ver INSTAGRAM_HTTP_MEDIA_SETUP.md para configuração nginx."
)
col_media1, col_media2 = st.columns(2)
with col_media1:
    media_backend = st.selectbox(
        "Backend de media",
        options=["cloudinary", "local_http"],
        index=0 if (st.session_state.get("config_media_backend", "cloudinary") == "cloudinary") else 1,
        format_func=lambda x: "Cloudinary (nuvem)" if x == "cloudinary" else "Local HTTP (servidor próprio)",
        key="config_media_backend",
    )
with col_media2:
    if media_backend == "local_http":
        st.text_input(
            "MEDIA_ROOT (directório local)",
            value=st.session_state.get("config_media_root", "/srv/instagram_media"),
            key="config_media_root",
            placeholder="/srv/instagram_media",
            help="Path onde as imagens/vídeos são gravados. Windows: ex. C:\\caminho\\instagram_media",
        )
        st.text_input(
            "MEDIA_BASE_URL (URL público)",
            value=st.session_state.get("config_media_base_url", "https://magnific1.ddns.net"),
            key="config_media_base_url",
            placeholder="https://magnific1.ddns.net",
            help="URL base servida pelo nginx. Deve ser DNS público (nunca localhost).",
        )
if st.button("Guardar — Backend de media", key="save_media_backend"):
    _apply_config_from_session()
    backend_val = st.session_state.get("config_media_backend", "cloudinary")
    root_val = (st.session_state.get("config_media_root") or "/srv/instagram_media").strip()
    url_val = (st.session_state.get("config_media_base_url") or "https://magnific1.ddns.net").strip().rstrip("/")
    update_env_vars({
        "MEDIA_BACKEND": backend_val,
        "MEDIA_ROOT": root_val,
        "MEDIA_BASE_URL": url_val,
    })
    config.set_runtime_override("MEDIA_BACKEND", backend_val)
    config.set_runtime_override("MEDIA_ROOT", root_val)
    config.set_runtime_override("MEDIA_BASE_URL", url_val)
    st.success("Backend de media guardado.")

st.divider()

# ========== 5. CLOUDINARY ==========
st.subheader("5. Cloudinary")
if media_backend == "local_http":
    st.info("Media: backend local (Cloudinary não necessário). Os campos abaixo aplicam-se apenas quando MEDIA_BACKEND=cloudinary.")
else:
    st.caption("Upload de imagens geradas. Apenas quando MEDIA_BACKEND=cloudinary. Com local_http, o Cloudinary não é usado.")
    st.link_button("☁️ Dashboard Cloudinary", CLOUDINARY_DASHBOARD, use_container_width=True)

    def _normalize_cloudinary_url(value: str) -> str:
        """Aceita CLOUDINARY_URL=cloudinary://... ou só cloudinary://..."""
        if not value or not value.strip():
            return ""
        v = value.strip()
        if "=" in v and v.startswith("CLOUDINARY_URL"):
            v = v.split("=", 1)[1].strip().strip('"').strip("'")
        return v

    st.text_input(
        "CLOUDINARY_URL (introdução directa)",
        value=st.session_state.config_cloudinary_url,
        key="config_cloudinary_url",
        type="password",
        placeholder="CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME",
        help="Cola a variável de ambiente completa (ex.: CLOUDINARY_URL=cloudinary://233159192196183:xxx@dvnpqhz9h) ou só o valor cloudinary://...",
    )
    if st.button("Verificar — Cloudinary", key="verify_cloudinary"):
        _apply_config_from_session()
        url_val = _normalize_cloudinary_url(st.session_state.get("config_cloudinary_url", ""))
        if url_val:
            config.set_runtime_override("CLOUDINARY_URL", url_val)
            update_env_vars({"CLOUDINARY_URL": url_val})
        ok, msg = verify_cloudinary()
        if ok:
            st.success(msg)
        else:
            st.error(msg)

st.divider()

# ========== 6. GERAÇÃO DE CONTEÚDO ==========
st.subheader("6. Geração de conteúdo")
st.caption("Personaliza o prompt usado na página Conteúdo para variar temas ao longo do tempo ou consoante o que está em moda.")
content_extra = st.text_area(
    "Instruções adicionais / Foco actual",
    value=st.session_state.config_content_extra_prompt,
    key="config_content_extra_prompt",
    height=100,
    placeholder="Ex.: Este mês priorizar limites e dizer não; evitar clichés de produtividade. Temas em moda: descanso, slow living.",
    help="Temas em moda ou foco desta época. Será enviado à IA em cada geração para variar o conteúdo.",
)
with st.expander("Prompt de sistema padrão (referência)", expanded=False):
    st.caption("Prompt base usado na geração de conteúdo. Apenas informativo; serve de referência para o personalizado abaixo.")
    st.text_area(
        "Prompt padrão",
        value=config.get_default_content_system_prompt(),
        height=320,
        disabled=True,
        label_visibility="collapsed",
        key="content_default_prompt_display",
    )
with st.expander("Prompt de sistema personalizado (avançado)"):
    st.caption("Substitui por completo o prompt de sistema da geração de conteúdo. Deixar vazio para usar o padrão.")
    content_system_override = st.text_area(
        "Prompt de sistema",
        value=st.session_state.config_content_system_override,
        key="config_content_system_override",
        height=200,
        label_visibility="collapsed",
        placeholder="Colar aqui o prompt completo se quiser substituir o padrão...",
    )
if st.button("Guardar — Geração de conteúdo", key="save_content_generation"):
    _apply_config_from_session()
    extra_val = (st.session_state.get("config_content_extra_prompt") or "").strip()
    update_env_vars({"CONTENT_GENERATION_EXTRA_PROMPT": extra_val})
    config.set_runtime_override("CONTENT_GENERATION_EXTRA_PROMPT", extra_val)
    override_val = (st.session_state.get("config_content_system_override") or "").strip()
    override_path = config.get_content_system_prompt_override_path()
    if override_val:
        override_path.parent.mkdir(parents=True, exist_ok=True)
        override_path.write_text(override_val, encoding="utf-8")
    elif override_path.exists():
        override_path.write_text("", encoding="utf-8")
    st.success("Configuração de geração de conteúdo guardada.")

st.divider()

# ========== 7. PREENCHER PROMPT DE IMAGEM NO SHEET ==========
st.subheader("7. Preencher Gemini_Prompt no Sheet")
st.caption(
    "Gera descrições visuais (sem texto) a partir da Image Text de cada linha, "
    "usando IA para converter a quote numa cena. A quote é sobreposta na imagem ao publicar."
)
if st.button("Preencher Gemini_Prompt no Sheet"):
    _apply_config_from_session()
    try:
        from instagram_poster.image_generator import _quote_to_scene_prompt

        rows = get_all_rows_with_image_text()
        if not rows:
            st.warning("Nenhuma linha com Image Text encontrada.")
        else:
            progress = st.progress(0, text="A converter quotes em descrições visuais...")
            total = len(rows)
            ok_count = 0
            for i, rec in enumerate(rows):
                image_text = (rec.get("image_text") or "").strip()
                if not image_text:
                    continue
                scene_prompt = _quote_to_scene_prompt(image_text)
                update_gemini_prompt(rec["row_index"], scene_prompt)
                ok_count += 1
                progress.progress((i + 1) / total, text=f"Linha {rec['row_index']}... ({i + 1}/{total})")
            progress.empty()
            st.success(f"Gemini_Prompt preenchido em {ok_count} linhas (descrição visual sem texto).")
            st.rerun()
    except Exception as e:
        st.error(f"Erro: {e}")
        st.info("Liga o Google Sheets primeiro.")

st.divider()

# ========== 8. AUTOPUBLISH ==========
st.subheader("8. Publicacao automatica")
st.caption("Publica posts automaticamente na hora agendada no Sheet. Funciona com a app aberta ou via Task Scheduler.")

from instagram_poster import autopublish
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

# Toggle on/off
ap_enabled = st.toggle(
    "Activar autopublish",
    value=_ap_enabled,
    key="config_autopublish_enabled",
)
ap_interval = st.slider(
    "Intervalo de verificacao (minutos)",
    min_value=1, max_value=60, value=_ap_interval,
    key="config_autopublish_interval",
    help="A cada N minutos, verifica se ha posts prontos e publica automaticamente.",
)
ap_story = st.toggle(
    "Publicar Story automaticamente com cada post",
    value=_ap_story,
    key="config_autopublish_story",
    help="Quando um post e publicado (feed), publica tambem uma Story com a mesma imagem em formato vertical.",
)
ap_story_music = st.toggle(
    "Adicionar musica nas Stories (video com audio da pasta MUSIC)",
    value=_ap_story_music,
    key="config_autopublish_story_music",
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
        key="config_autopublish_story_reuse",
        help="Publica uma Story com a imagem de um post aleatório já publicado no intervalo definido ao lado.",
    )
with col_story_reuse_time:
    ap_story_reuse_interval_hours = st.number_input(
        "horas",
        min_value=0.5,
        max_value=168.0,
        value=round(_ap_story_reuse_interval / 60, 1),
        step=0.5,
        key="config_autopublish_story_reuse_interval",
        label_visibility="collapsed",
    )
with col_story_reuse_unit:
    st.caption("h")
ap_reel = st.toggle(
    "Publicar Reel automaticamente a cada 5 posts nunca usados em Reels",
    value=_ap_reel,
    key="config_autopublish_reel",
    help="Critério: 5 posts já publicados no Sheet (com ImageURL) que ainda não tenham sido usados em nenhum Reel (registo em assets/reels_used_rows.json). Gera e publica um Reel (8s/slide, fade, áudio da pasta MUSIC). Não significa «5 posts novos desde o último Reel».",
)
col_reuse_toggle, col_reuse_time, col_reuse_unit = st.columns([2, 1, 0.5])
with col_reuse_toggle:
    ap_reel_reuse = st.toggle(
        "Criar Reels com posts já usados a cada",
        value=_ap_reel_reuse,
        key="config_autopublish_reel_reuse",
        help="Gera e publica um Reel com 5 posts aleatórios já publicados (podem ser já usados em Reels) no intervalo definido ao lado.",
    )
with col_reuse_time:
    ap_reel_reuse_interval_hours = st.number_input(
        "horas",
        min_value=0.5,
        max_value=168.0,
        value=round(_ap_reel_reuse_interval / 60, 1),
        step=0.5,
        key="config_autopublish_reel_reuse_interval",
        label_visibility="collapsed",
    )
with col_reuse_unit:
    st.caption("h")
ap_comment_autoreply = st.toggle(
    "Autoresposta a comentários em cada verificação",
    value=_ap_comment_autoreply,
    key="config_autopublish_comment_autoreply",
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
        "AUTOPUBLISH_COMMENT_AUTOREPLY": "true" if ap_comment_autoreply else "false",
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

# Botoes iniciar/parar
col_ap1, col_ap2, _ = st.columns([1, 1, 2])
with col_ap1:
    if _ap_running:
        if st.button("Parar autopublish", key="stop_autopublish"):
            autopublish.stop_background_loop()
            st.rerun()
    else:
        if st.button("Iniciar autopublish", type="primary", key="start_autopublish", disabled=not ap_enabled):
            autopublish.start_background_loop(interval_minutes=ap_interval)
            st.rerun()

# Estado e estatisticas (get_log primeiro para recarregar do ficheiro se outro processo gravou)
_ = autopublish.get_log()
stats = autopublish.get_stats()
last_check = autopublish.get_last_check()

if _ap_running:
    st.success(f"Autopublish activo (cada {_ap_interval} min)")
elif ap_enabled:
    st.info("Autopublish configurado mas nao iniciado. Clica 'Iniciar' ou reinicia a app.")
else:
    st.warning("Autopublish desactivado.")

# Metricas resumo
col_s1, col_s2, col_s3, col_s4 = st.columns(4)
with col_s1:
    st.metric("Posts publicados", stats["total_published"])
with col_s2:
    st.metric("Erros", stats["total_errors"])
with col_s3:
    st.metric("Verificacoes", stats["total_checks"])
with col_s4:
    if last_check:
        st.metric("Ultima verificacao", last_check.strftime("%H:%M:%S"))
    elif stats["started_at"]:
        st.metric("Iniciado em", stats["started_at"].strftime("%H:%M:%S"))
    else:
        st.metric("Ultima verificacao", "—")

# Historico detalhado
ap_log = autopublish.get_log()
if ap_log:
    published_entries = [e for e in ap_log if e.get("type") == "publish"]
    error_entries = [e for e in ap_log if e.get("type") == "error"]
    other_entries = [e for e in ap_log if e.get("type") not in ("publish", "error", "check")]

    # Posts publicados
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

    # Erros
    with st.expander(f"Erros ({len(error_entries)})"):
        if st.button("Limpar erros", key="config_clear_errors", disabled=not error_entries):
            autopublish.clear_error_entries()
            st.rerun()
        if error_entries:
            for entry in reversed(error_entries):
                ts = entry["timestamp"].strftime("%H:%M:%S")
                st.error(f"[{ts}] {entry['message']}")
        else:
            st.caption("Nenhum erro registado.")

    # Eventos do sistema (start/stop)
    if other_entries:
        with st.expander(f"Eventos do sistema ({len(other_entries)})"):
            for entry in reversed(other_entries):
                ts = entry["timestamp"].strftime("%H:%M:%S")
                st.info(f"[{ts}] {entry['message']}")
else:
    st.caption("Nenhuma actividade registada.")

# Instrucoes Task Scheduler
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

st.caption("Os valores são guardados no .env ao carregar JSON ou ao verificar. Mantém tudo sincronizado.")
