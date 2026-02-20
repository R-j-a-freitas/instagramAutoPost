"""
Configuração dos acessos: Google Sheets, Instagram, geração de imagens, Cloudinary.
Ao carregar JSON ou verificar, as variáveis são atualizadas no .env.
"""
import json
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
    if "config_image_provider" not in st.session_state:
        st.session_state.config_image_provider = config.get_image_provider() or "gemini"


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
    config.set_runtime_override("IMAGE_PROVIDER", st.session_state.get("config_image_provider", "gemini"))


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
        _cu = config.CLOUDINARY_URL
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

st.divider()

# ========== 3. GERAÇÃO DE IMAGENS ==========
st.subheader("3. Geração de imagens")
st.caption("Escolhe o provedor para gerar imagens a partir do prompt. Pollinations é grátis e não precisa de API key.")

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

if st.button("Verificar — Geração de imagens", key="verify_image_provider"):
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
    update_env_vars(env_updates)
    ok, msg = verify_image_provider()
    if ok:
        st.success(msg)
    else:
        st.error(msg)

st.divider()

# ========== 4. CLOUDINARY ==========
st.subheader("4. Cloudinary")
st.caption("Upload de imagens geradas. Configura no .env (CLOUDINARY_URL) ou no dashboard.")
st.link_button("☁️ Dashboard Cloudinary", CLOUDINARY_DASHBOARD, use_container_width=True)
if st.button("Verificar — Cloudinary", key="verify_cloudinary"):
    ok, msg = verify_cloudinary()
    if ok:
        st.success(msg)
    else:
        st.error(msg)

st.divider()

# ========== 5. PREENCHER PROMPT DE IMAGEM NO SHEET ==========
st.subheader("5. Preencher Gemini_Prompt no Sheet")
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

# ========== 6. AUTOPUBLISH ==========
st.subheader("6. Publicacao automatica")
st.caption("Publica posts automaticamente na hora agendada no Sheet. Funciona com a app aberta ou via Task Scheduler.")

from instagram_poster import autopublish
from instagram_poster.config import (
    get_autopublish_enabled,
    get_autopublish_interval,
    get_autopublish_reel_every_5,
    get_autopublish_story_with_post,
)

_ap_running = autopublish.is_running()
_ap_enabled = get_autopublish_enabled()
_ap_interval = get_autopublish_interval()
_ap_story = get_autopublish_story_with_post()
_ap_reel = get_autopublish_reel_every_5()

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
ap_reel = st.toggle(
    "Publicar Reel automaticamente a cada 5 posts",
    value=_ap_reel,
    key="config_autopublish_reel",
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
    if error_entries:
        with st.expander(f"Erros ({len(error_entries)})"):
            for entry in reversed(error_entries):
                ts = entry["timestamp"].strftime("%H:%M:%S")
                st.error(f"[{ts}] {entry['message']}")

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
