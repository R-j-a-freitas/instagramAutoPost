"""
Vídeo IA: geração de vídeos a partir de prompts usando Pollinations.
Permite escolher um post do Sheets, gerar o vídeo, escolher música e publicar no Instagram.
"""
import tempfile
import streamlit as st
import requests
import io
import time
import sys
import importlib
from pathlib import Path
from urllib.parse import quote

# Forçar reload do reel_generator para evitar ImportError de cache
if 'instagram_poster.reel_generator' in sys.modules:
    importlib.reload(sys.modules['instagram_poster.reel_generator'])

from instagram_poster.config import (
    get_pollinations_api_key,
    get_media_root,
    get_video_provider,
    get_nvidia_video_model,
)
from instagram_poster.sheets_client import get_upcoming_posts, get_row_by_index
from instagram_poster.providers.provider_pollinations import PollinationsProvider
from instagram_poster.providers.provider_nvidia import NVIDIAProvider
from instagram_poster.reel_generator import (
    get_available_music_tracks,
    upload_video_bytes,
    mark_posts_used_in_reel,
    mix_video_with_audio,
    repeat_video
)
from instagram_poster import autopublish, ig_client
from instagram_poster.auth import require_auth, render_auth_sidebar

st.set_page_config(page_title="Vídeo IA | Instagram Auto Post", page_icon="🎬", layout="wide")
require_auth()
with st.sidebar:
    render_auth_sidebar()

# Navegação
nav1, nav2, nav3, nav4, nav5, nav6, nav7, _ = st.columns([1, 1, 1, 1, 1, 1, 1, 1])
with nav1:
    if st.button("← Inicio", key="nav_home_vid"):
        st.switch_page("app.py")
with nav2:
    if st.button("⚙️ Configuracao", key="nav_cfg_vid"):
        st.switch_page("pages/1_Configuracao.py")
with nav3:
    if st.button("📸 Posts", key="nav_posts_vid"):
        st.switch_page("pages/2_Posts.py")
with nav4:
    if st.button("✏️ Conteudo", key="nav_content_vid"):
        st.switch_page("pages/3_Conteudo.py")
with nav5:
    if st.button("🔄 Autopublish", key="nav_ap_vid"):
        st.switch_page("pages/4_Autopublish.py")
with nav6:
    if st.button("📱 Stories", key="nav_stories_vid"):
        st.switch_page("pages/5_Stories.py")
with nav7:
    if st.button("🎬 Reels", key="nav_reels_vid"):
        st.switch_page("pages/4_Reels.py")

video_provider = get_video_provider()
provider_label = "NVIDIA NIM" if video_provider == "nvidia" else "Pollinations"

st.title(f"Vídeo IA ({provider_label})")
st.caption(f"Gera um vídeo a partir da descrição de um post do Google Sheets usando {provider_label}.")

# --- Secção 1: Seleção de post ---
st.subheader("1. Escolher post do Sheets")
try:
    upcoming = get_upcoming_posts(n=20)
except Exception as e:
    st.error(f"Erro ao ler o Sheet: {e}")
    upcoming = []

if not upcoming:
    st.warning("Nenhum post planeado no Sheet.")
    st.stop()

# Criar opções para o selectbox
options = {f"Linha {p['row_index']} - {p['date']} {p['time']} | {p['image_text'][:40]}...": p for p in upcoming}
selected_label = st.selectbox("Selecionar post", list(options.keys()))
selected_post = options[selected_label]

# Detectar mudança de post e atualizar estados
current_idx = selected_post.get("row_index")
if "last_selected_row_idx" not in st.session_state:
    st.session_state.last_selected_row_idx = None

if st.session_state.last_selected_row_idx != current_idx:
    new_p = selected_post.get('gemini_prompt') or ""
    st.session_state.video_ia_prompt = new_p
    st.session_state["vid_prompt_area"] = new_p # Atualizar widget diretamente
    st.session_state.last_selected_row_idx = current_idx
    st.session_state.video_ia_bytes = None # Resetar vídeo anterior ao mudar post

st.info(f"**Prompt de Imagem (usado para o vídeo):** {selected_post.get('gemini_prompt') or 'Vazio'}")

st.divider()

# --- Secção 2: Geração do Vídeo ---
st.subheader("2. Gerar Vídeo")

if video_provider == "pollinations":
    col_model, col_ratio, col_dur = st.columns(3)
    with col_model:
        vid_model = st.selectbox("Modelo", ["grok-video", "grok-video-pro", "seedance", "veo", "wan"], index=0, 
                                 help="grok-video/pro (~6s fixo), seedance (~2s), veo (8s), wan (até 10s).")
    with col_ratio:
        vid_ratio = st.selectbox("Proporção", ["9:16", "16:9", "1:1"], index=0)
    with col_dur:
        # Limites reais baseados na API atual do Pollinations
        max_d = 10
        default_d = 6
        if vid_model == "wan":
            max_d = 10
        elif vid_model == "veo":
            max_d = 8
            default_d = 8
        elif vid_model == "seedance":
            max_d = 2
            default_d = 2
        elif vid_model == "grok-video":
            max_d = 6
            default_d = 6
        elif vid_model == "grok-video-pro":
            max_d = 30
            default_d = 30
        
        vid_duration = st.slider("Duração (seg)", 1, max_d, default_d)
        st.caption(f"Nota: {vid_model} tem limite de {max_d}s.")
else:
    # NVIDIA
    col_model, col_ratio = st.columns(2)
    with col_model:
        vid_model = st.text_input("Modelo NVIDIA NIM", value=get_nvidia_video_model(), disabled=True)
    with col_ratio:
        vid_ratio = st.selectbox("Proporção", ["9:16", "16:9", "1:1"], index=0)
    vid_duration = 5
    st.info("NVIDIA Cosmos 1.0 gera vídeos de aproximadamente 5 segundos.")

if "video_ia_prompt" not in st.session_state:
    st.session_state.video_ia_prompt = selected_post.get('gemini_prompt') or ""

if st.button("Gerar Prompt com IA ✨", help=f"Gera um prompt detalhado de {vid_duration}s para o modelo {vid_model}"):
    api_key = get_pollinations_api_key()
    if not api_key:
        st.warning("Configura POLLINATIONS_API_KEY na Configuração.")
    else:
        with st.spinner(f"A criar prompt para {vid_duration}s..."):
            try:
                post_text = selected_post.get("image_text") or ""
                caption = (selected_post.get("caption") or "")[:300]
                system_prompt = (
                    f"You are an expert in AI video prompts. Create a cinematic {vid_duration}s video prompt "
                    f"specifically optimized for the '{vid_model}' model. Return ONLY the prompt text."
                )
                user_msg = (
                    f"Post: {post_text}\n"
                    f"Theme: {caption}\n"
                    f"Requested Duration: {vid_duration} seconds.\n"
                    f"Requirement: Plan the visual sequence/scenes to fit exactly within {vid_duration}s. "
                    f"Include the text: '{post_text}'"
                )
                
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                
                data = {
                    "model": "openai",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_msg}
                    ]
                }
                
                try:
                    resp = requests.post("https://gen.pollinations.ai/v1/chat/completions", 
                                       headers=headers, json=data, timeout=60)
                    resp.raise_for_status()
                    new_prompt = resp.json()["choices"][0]["message"]["content"].strip()
                except Exception:
                    url = f"https://text.pollinations.ai/{quote(user_msg)}"
                    params = {"system": system_prompt, "model": "openai", "seed": int(time.time())}
                    resp = requests.get(url, params=params, headers=headers, timeout=60)
                    resp.raise_for_status()
                    new_prompt = resp.text.strip()
                
                st.session_state.video_ia_prompt = new_prompt
                st.session_state["vid_prompt_area"] = new_prompt 
                st.rerun()
            except requests.exceptions.HTTPError as he:
                if he.response.status_code == 502:
                    st.error("Servidor Pollinations instável (502). Tenta de novo.")
                else:
                    st.error(f"Erro API ({he.response.status_code})")
            except requests.exceptions.Timeout:
                st.error("Timeout na IA. Tenta de novo.")
            except Exception as e:
                st.error(f"Erro ao gerar prompt: {e}")

pollinations_prompt = st.text_area("Ajustar prompt para o Pollinations (opcional)", 
                                 value=st.session_state.video_ia_prompt, 
                                 height=120, 
                                 key="vid_prompt_area")

if "video_ia_bytes" not in st.session_state:
    st.session_state.video_ia_bytes = None

if st.button(f"Gerar Vídeo com {provider_label}", type="primary"):
    if video_provider == "pollinations":
        api_key = get_pollinations_api_key()
        if not api_key:
            st.warning("Configura POLLINATIONS_API_KEY na Configuração.")
        elif not pollinations_prompt:
            st.warning("O prompt não pode estar vazio.")
        else:
            with st.spinner(f"A gerar vídeo via {vid_model}..."):
                try:
                    provider = PollinationsProvider()
                    video_bytes = provider.generate_video(
                        pollinations_prompt, 
                        model=vid_model, 
                        aspect_ratio=vid_ratio, 
                        duration=vid_duration
                    )
                    st.session_state.video_ia_bytes = video_bytes
                    st.session_state.video_ia_row_index = selected_post.get("row_index")
                    st.success("Vídeo gerado com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao gerar vídeo: {e}")
                    if "400" in str(e):
                        st.info("Dica: Tenta reduzir a duração ou o detalhe do prompt.")
    else:
        # NVIDIA
        if not pollinations_prompt:
            st.warning("O prompt não pode estar vazio.")
        else:
            with st.spinner(f"A gerar vídeo via NVIDIA ({vid_model})..."):
                try:
                    provider = NVIDIAProvider()
                    video_bytes = provider.generate_video(
                        pollinations_prompt,
                        model=vid_model,
                        aspect_ratio=vid_ratio
                    )
                    st.session_state.video_ia_bytes = video_bytes
                    st.session_state.video_ia_row_index = selected_post.get("row_index")
                    st.success("Vídeo gerado com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao gerar vídeo com NVIDIA: {e}")

if st.session_state.video_ia_bytes:
    st.video(st.session_state.video_ia_bytes)
    
    # Opção de guardar localmente
    if st.button("Guardar Localmente"):
        try:
            filename = f"pollinations_video_{int(time.time())}.mp4"
            save_path = get_media_root() / filename
            save_path.write_bytes(st.session_state.video_ia_bytes)
            st.success(f"Vídeo guardado em: {save_path}")
        except Exception as e:
            st.error(f"Erro ao guardar: {e}")

st.divider()

# --- Secção 3: Publicação Manual ---
st.subheader("3. Publicação Manual (Instagram)")

if not st.session_state.video_ia_bytes:
    st.info("Gera um vídeo primeiro para habilitar a publicação.")
else:
    col_music, col_caption = st.columns(2)
    
    with col_music:
        st.write("**Música (Opcional)**")
        st.caption("Nota: A mistura de música com o vídeo gerado requer MoviePy.")
        
        audio_option = st.radio(
            "Opção de Áudio", 
            ["Sem música extra", "Biblioteca ambient", "Upload ficheiro"],
            key="vid_audio_option"
        )
        
        audio_path = None
        if audio_option == "Biblioteca ambient":
            tracks = get_available_music_tracks()
            if tracks:
                track_options = {t["name"]: t["path"] for t in tracks}
                sel_track = st.selectbox("Escolher faixa", list(track_options.keys()), key="vid_sel_track")
                audio_path = track_options[sel_track]
            else:
                st.warning("Nenhuma música encontrada na biblioteca.")
        elif audio_option == "Upload ficheiro":
            uploaded = st.file_uploader("Upload MP3", type=["mp3"], key="vid_audio_upload")
            if uploaded:
                # Usar session_state para persistir o path do ficheiro temporário
                if "vid_uploaded_audio_path" not in st.session_state or st.session_state.vid_uploaded_audio_name != uploaded.name:
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                        tmp.write(uploaded.getvalue())
                        st.session_state.vid_uploaded_audio_path = tmp.name
                        st.session_state.vid_uploaded_audio_name = uploaded.name
                audio_path = st.session_state.vid_uploaded_audio_path
        
        audio_volume = st.slider("Volume do Áudio (%)", 0, 100, 30, key="vid_audio_vol") / 100.0
        
        st.write("**Repetir Vídeo (Loop)**")
        vid_loops = st.number_input("Multiplicar vídeo N vezes", min_value=1, max_value=10, value=1, 
                                   key="vid_loops",
                                   help="Útil para vídeos curtos (ex: 6s x 3 = 18s).")

    with col_caption:
        st.write("**Caption**")
        caption_val = selected_post.get("caption") or ""
        video_caption = st.text_area("Caption para o Instagram", value=caption_val, height=150)

    if st.button("Publicar no Instagram como Reel", type="primary"):
        with st.spinner("A processar e publicar..."):
            try:
                final_video_bytes = st.session_state.video_ia_bytes
                row_idx = st.session_state.get("video_ia_row_index")
                
                # Se o utilizador quiser repetir o vídeo (loop)
                if vid_loops > 1:
                    orig_size = len(final_video_bytes)
                    st.info(f"A processar loop ({vid_loops}x)...")
                    final_video_bytes = repeat_video(final_video_bytes, vid_loops)
                    new_size = len(final_video_bytes)
                    st.info(f"Loop concluído: {orig_size//1024}KB -> {new_size//1024}KB")
                
                # Se tiver áudio extra, misturar agora
                if audio_path:
                    st.info(f"A misturar áudio: {Path(audio_path).name} (Volume: {int(audio_volume*100)}%)...")
                    final_video_bytes = mix_video_with_audio(final_video_bytes, audio_path, audio_volume=audio_volume)
                else:
                    st.info("A continuar sem música extra...")
                
                st.info("A fazer upload do vídeo final...")
                video_url = upload_video_bytes(final_video_bytes, public_id_prefix="ia_vid")
                
                st.info("A criar Reel no Instagram...")
                creation_id = ig_client.create_reel(video_url=video_url, caption=video_caption)
                media_id = ig_client.publish_media(creation_id, max_wait=300)
                
                # Atualizar Sheet e logs
                if row_idx:
                    from instagram_poster import sheets_client
                    sheets_client.update_image_url(row_idx, video_url)
                    sheets_client.mark_published(row_idx)
                    mark_posts_used_in_reel([row_idx])
                
                autopublish.log_reel_manual(video_caption, media_id)
                st.success(f"Vídeo publicado com sucesso! Media ID: {media_id}")
                st.balloons()
                
                # Opcional: não limpar os bytes para permitir ver o resultado ou repetir
                # st.session_state.video_ia_bytes = None
            except Exception as e:
                st.error(f"Erro ao publicar: {e}")
