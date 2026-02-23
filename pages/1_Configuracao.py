"""
Configuração dos acessos: Google Sheets, Instagram, geração de imagens, Cloudinary.
Ao carregar JSON ou verificar, as variáveis são atualizadas no .env.
"""
import json
import os
import re
from pathlib import Path
import streamlit as st

from instagram_poster import config
from instagram_poster.env_utils import (
    update_env_from_oauth_client_json,
    update_env_from_service_account_json,
    update_env_vars,
)
from instagram_poster.providers import AVAILABLE_PROVIDERS
from instagram_poster.sheets_client import get_all_rows_with_image_text, update_gemini_prompt
from instagram_poster.verification import (
    check_instagram_api_status,
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


st.set_page_config(page_title="Configuração | Instagram Auto Post", page_icon="⚙️", layout="wide")
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
        _cn = config.CLOUDINARY_CLOUD_NAME
        _cu = config.get_cloudinary_url()
        if (_cu and _cu.strip().startswith("cloudinary://")) or _cn:
            st.success(f"Cloudinary\n\n`{_cn or 'via URL'}`")
        else:
            st.error("Cloudinary\n\nnão configurado")
    st.divider()

# ========== 1. GOOGLE SHEETS ==========
st.subheader("1. Google Sheets")

# Verificar estado atual
_oauth_client_exists = (_PROJECT_ROOT / "google_oauth_client.json").exists()
_oauth_token_exists = (_PROJECT_ROOT / "google_oauth_authorized.json").exists()

if _oauth_client_exists and _oauth_token_exists:
    st.success("Google Sheets: autorizado (token guardado)")
elif _oauth_client_exists:
    st.info("JSON OAuth carregado. Clica **Verificar e aceitar** para autorizar no browser (abre uma vez).")
elif config.get_google_credentials_dict() is not None or config.get_google_credentials_path():
    st.info("Service Account configurada.")
else:
    st.warning("Faz upload do JSON do Google abaixo.")

st.markdown("**Upload JSON do Google**")
st.caption(
    "Descarrega do [Google Cloud Console](" + GOOGLE_OAUTH_SETUP + ") → "
    "Credenciais → OAuth 2.0 Client ID (Computador) → Descarregar JSON. "
    "Ou usa Service Account."
)
uploaded = st.file_uploader("Ficheiro JSON", type=["json"], key="upload_google_json", label_visibility="collapsed")
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
        is_service_account = "client_email" in data and "token_uri" in data

        if is_oauth_client:
            dest = _PROJECT_ROOT / "google_oauth_client.json"
            dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
            update_env_from_oauth_client_json(data)
            st.success("JSON OAuth carregado. Clica **Verificar e aceitar** abaixo — o browser abrirá para autorizares.")
            st.rerun()
        elif is_service_account:
            secrets_dir = _PROJECT_ROOT / "secrets"
            secrets_dir.mkdir(exist_ok=True)
            sa_path = secrets_dir / "google_service_account.json"
            sa_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            update_env_from_service_account_json(str(sa_path.resolve()))
            config.set_google_credentials_dict(data)
            st.success(f"Service Account carregada: {data.get('client_email', '')}")
        else:
            st.error(
                "JSON não reconhecido. Deve ser **OAuth Client** (tem client_id) "
                "ou **Service Account** (tem client_email)."
            )
    except json.JSONDecodeError as e:
        st.error(f"JSON inválido: {e}")

st.text_input(
    "ID do Google Sheet",
    value=st.session_state.config_sheet_id,
    key="config_sheet_id",
    placeholder="URL ou ID (ex.: 1UBdukuHNvpfdcyBxKIQAt5pRIKFrGLYI6tZdYhfYCig)",
)
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
        if _oauth_client_exists and not _oauth_token_exists:
            st.info("Na primeira vez, o browser deve abrir para autorizares. Se não abriu, verifica a consola/terminal.")

st.divider()

# ========== 2. INSTAGRAM ==========
st.subheader("2. Instagram Graph API")
st.caption("Publicação no Instagram. Liga com a tua conta ou cola token manualmente.")

try:
    from instagram_poster.oauth_instagram import get_auth_url, has_oauth_token, clear_oauth_token
    ig_oauth_available = get_auth_url(state="instagram") is not None
except Exception:
    ig_oauth_available = False

col_ig1, col_ig2 = st.columns(2)
with col_ig1:
    if ig_oauth_available:
        if has_oauth_token():
            st.success("✅ Instagram ligado (OAuth)")
            if st.button("Desligar Instagram", key="disconnect_ig"):
                clear_oauth_token()
                st.rerun()
        else:
            auth_url = get_auth_url(state="instagram")
            if auth_url:
                st.link_button("🔗 Ligar com Instagram", auth_url, type="primary", use_container_width=True)
                st.caption("Serás redirecionado para o Instagram para autorizar.")
    else:
        st.info("Para OAuth: adiciona INSTAGRAM_APP_ID e INSTAGRAM_APP_SECRET ao .env")
        st.caption(f"[Criar app Instagram]({INSTAGRAM_DEV_DASHBOARD}) → Adicionar produto Instagram → Configurar OAuth redirect: http://localhost:8501/")

with col_ig2:
    st.markdown("**Ou: credenciais manuais**")
    st.text_input(
        "Instagram Business ID",
        value=st.session_state.config_ig_business_id,
        key="config_ig_business_id",
        placeholder="ID da conta de negócios",
        label_visibility="collapsed",
    )
    st.text_input(
        "Access Token",
        value=st.session_state.config_ig_access_token,
        key="config_ig_access_token",
        type="password",
        placeholder="Token de acesso (long-lived)",
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
        ok, msg = verify_instagram()
        if ok:
            st.success(msg)
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

# ========== 4. CLOUDINARY ==========
st.subheader("4. Cloudinary")
st.caption("Upload de imagens geradas. Configura no .env (CLOUDINARY_URL) ou introduz directamente abaixo.")
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

# ========== 5. GERAÇÃO DE CONTEÚDO ==========
st.subheader("5. Geração de conteúdo")
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

# ========== 6. PREENCHER PROMPT DE IMAGEM NO SHEET ==========
st.subheader("6. Preencher Gemini_Prompt no Sheet")
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

# ========== 7. AUTOPUBLISH ==========
st.subheader("7. Publicacao automatica")
st.caption("Publica posts automaticamente na hora agendada no Sheet. Funciona com a app aberta ou via Task Scheduler.")

from instagram_poster import autopublish
from instagram_poster.config import (
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
        help="Publica uma Story com a imagem do ultimo post publicado no intervalo definido ao lado.",
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
        help="Gera e publica um Reel com os ultimos 5 posts (podem ser ja usados em Reels) no intervalo definido ao lado.",
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

# Guardar alteracoes no .env
ap_story_reuse_interval = max(30, int(ap_story_reuse_interval_hours * 60))
ap_reel_reuse_interval = max(30, int(ap_reel_reuse_interval_hours * 60))
if (ap_enabled != _ap_enabled or ap_interval != _ap_interval or ap_story != _ap_story or ap_story_music != _ap_story_music or ap_story_reuse != _ap_story_reuse or ap_story_reuse_interval != _ap_story_reuse_interval
        or ap_reel != _ap_reel or ap_reel_reuse != _ap_reel_reuse or ap_reel_reuse_interval != _ap_reel_reuse_interval):
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

# Estado e estatisticas
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
