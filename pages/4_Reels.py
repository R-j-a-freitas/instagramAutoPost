"""
Reels: geração de vídeo slideshow a partir dos últimos posts publicados.
Opções de áudio: sem música, upload de ficheiro, ou biblioteca ambient.
"""
import tempfile
import streamlit as st
import requests

from instagram_poster.config import get_pollinations_api_key
from instagram_poster.reel_generator import (
    create_reel_video,
    get_available_music_tracks,
    get_posts_for_reel,
    mark_posts_used_in_reel,
    upload_video_bytes,
)
from instagram_poster import autopublish, ig_client

st.set_page_config(page_title="Reels | Instagram Auto Post", page_icon="🎬", layout="wide")

# Navegação
nav1, nav2, nav3, nav4, nav5, nav6, _ = st.columns([1, 1, 1, 1, 1, 1, 2])
with nav1:
    if st.button("← Inicio", key="nav_home_reel"):
        st.switch_page("app.py")
with nav2:
    if st.button("⚙️ Configuracao", key="nav_cfg_reel"):
        st.switch_page("pages/1_Configuracao.py")
with nav3:
    if st.button("📸 Posts", key="nav_posts_reel"):
        st.switch_page("pages/2_Posts.py")
with nav4:
    if st.button("✏️ Conteudo", key="nav_content_reel"):
        st.switch_page("pages/3_Conteudo.py")
with nav5:
    if st.button("🔄 Autopublish", key="nav_ap_reel"):
        st.switch_page("pages/4_Autopublish.py")
with nav6:
    if st.button("📱 Stories", key="nav_stories_reel"):
        st.switch_page("pages/5_Stories.py")

st.title("Reels")
st.caption("Gera um vídeo slideshow (9:16) a partir dos últimos posts publicados e publica no Instagram.")

# --- Secção 1: Seleção de posts ---
st.subheader("1. Posts para o Reel")
allow_reuse = st.checkbox(
    "Incluir posts já usados em Reels anteriores",
    value=False,
    key="reel_allow_reuse",
    help="Por defeito só são mostrados posts que ainda não foram usados em nenhum Reel.",
)
n_posts = st.slider("Número de posts a incluir", min_value=1, max_value=10, value=5, key="reel_n_posts")

try:
    all_posts = get_posts_for_reel(n=10, allow_reuse=allow_reuse)
except Exception as e:
    st.error(f"Erro ao ler o Sheet: {e}")
    all_posts = []

posts_to_use = []
if not all_posts:
    st.warning("Nenhum post publicado com imagem no Sheet. Publica posts primeiro ou preenche ImageURL nas linhas publicadas (página Stories).")
else:
    if not allow_reuse and len(all_posts) < 10:
        st.info(f"Há {len(all_posts)} post(s) publicados ainda não usados em Reels. Reduz o número de slides ou activa «Incluir posts já usados em Reels anteriores».")
    posts_display = all_posts[: min(n_posts, len(all_posts))]
    selected = []
    cols = st.columns(min(5, len(posts_display)))
    for i, post in enumerate(posts_display):
        with cols[i % 5]:
            url = (post.get("image_url") or "").strip()
            quote = (post.get("image_text") or "")[:50]
            date = post.get("date", "")
            if url:
                st.image(url, use_container_width=True, caption=f"{date} | {quote}...")
            st.caption(f"Linha {post.get('row_index')}")
            include = st.checkbox("Incluir", key=f"reel_inc_{i}", value=True)
            selected.append(include)
    posts_to_use = [p for p, inc in zip(posts_display, selected) if inc]
    st.caption(f"A usar {len(posts_to_use)} post(s) selecionado(s) de {len(posts_display)} mostrado(s).")

st.divider()

# --- Secção 2: Configuração do vídeo ---
st.subheader("2. Configuração do vídeo")
col_dur, col_trans = st.columns(2)
with col_dur:
    duration_per_slide = st.slider("Duração por slide (seg)", min_value=2, max_value=8, value=4, key="reel_duration")
with col_trans:
    transition = st.selectbox("Transição", ["Fade", "Crossfade"], key="reel_transition")

st.divider()

# --- Secção 3: Áudio ---
st.subheader("3. Áudio")
audio_option = st.radio(
    "Áudio",
    ["Sem música", "Upload ficheiro", "Biblioteca ambient"],
    key="reel_audio_option",
)
audio_volume = st.slider("Volume do áudio (%)", 0, 100, 30, key="reel_vol") / 100.0
audio_path = None

if audio_option == "Upload ficheiro":
    uploaded = st.file_uploader("Ficheiro MP3 ou WAV (max 10MB)", type=["mp3", "wav"], accept_multiple_files=False, key="reel_upload")
    if uploaded and uploaded.size < 10 * 1024 * 1024:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(uploaded.getvalue())
            audio_path = tmp.name
    elif uploaded:
        st.caption("Ficheiro demasiado grande (max 10MB).")
elif audio_option == "Biblioteca ambient":
    tracks = get_available_music_tracks()
    if not tracks:
        st.info("Nenhuma faixa na pasta assets/music. Coloca ficheiros MP3 e metadata.json (ver [Pixabay Music](https://pixabay.com/music/search/ambient/)).")
    else:
        track_options = {t["name"]: t["path"] for t in tracks}
        selected = st.selectbox("Faixa", list(track_options.keys()), key="reel_track")
        if selected:
            audio_path = track_options[selected]

st.divider()

# --- Secção 4: Caption ---
st.subheader("4. Caption do Reel")
# Usar chave diferente do widget para poder definir reel_caption ao gerar com IA (evita erro do Streamlit).
_caption_value = st.session_state.get("reel_caption") or st.session_state.get("reel_caption_ta", "")
reel_caption = st.text_area("Caption", value=_caption_value, height=100, key="reel_caption_ta")
if st.button("Gerar caption com IA", key="reel_gen_caption"):
    api_key = get_pollinations_api_key()
    if not api_key:
        st.warning("Configura POLLINATIONS_API_KEY na Configuração.")
    elif not posts_to_use:
        st.warning("Preenche posts primeiro.")
    else:
        quotes = [p.get("image_text", "") for p in posts_to_use if p.get("image_text")]
        prompt = f"Write a short Instagram caption (2-4 sentences) that summarizes these quotes as one theme: {' | '.join(quotes[:5])}. Tone: calm, positive. End with 1-2 hashtags like #keepcalmnbepositive."
        try:
            resp = requests.post(
                "https://gen.pollinations.ai/v1/chat/completions",
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                json={"model": "openai", "messages": [{"role": "user", "content": prompt}]},
                timeout=30,
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
            st.session_state["reel_caption"] = text
            st.rerun()
        except Exception as e:
            st.error(f"Erro: {e}")

st.divider()

# --- Secção 5: Gerar e publicar ---
st.subheader("5. Gerar e publicar")

if "reel_video_bytes" not in st.session_state:
    st.session_state.reel_video_bytes = None

if st.button("Gerar Reel", type="primary", key="reel_generate"):
    if not posts_to_use:
        st.error("Não há posts para usar. Garante que existem posts publicados com ImageURL no Sheet.")
    else:
        with st.spinner("A gerar vídeo (pode demorar 1-2 min)..."):
            try:
                video_bytes = create_reel_video(
                    posts=posts_to_use,
                    duration_per_slide=float(duration_per_slide),
                    transition=transition.lower(),
                    audio_path=audio_path,
                    audio_volume=audio_volume,
                )
                st.session_state.reel_video_bytes = video_bytes
                st.session_state.reel_posts_for_video = [p.get("row_index") for p in posts_to_use if p.get("row_index") is not None]
                st.success("Reel gerado. Visualiza em baixo e publica no Instagram quando quiseres.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao gerar Reel: {e}")

if st.session_state.reel_video_bytes:
    st.video(st.session_state.reel_video_bytes)
    if st.button("Publicar no Instagram", type="primary", key="reel_publish"):
        caption = (st.session_state.get("reel_caption_ta") or st.session_state.get("reel_caption") or "").strip() or "Reel gerado automaticamente."
        with st.spinner("Upload para Cloudinary e publicação no Instagram (pode demorar 1-3 min)..."):
            try:
                video_url = upload_video_bytes(st.session_state.reel_video_bytes)
                creation_id = ig_client.create_reel(video_url=video_url, caption=caption)
                media_id = ig_client.publish_media(creation_id, max_wait=180)
                mark_posts_used_in_reel(st.session_state.get("reel_posts_for_video", []))
                autopublish.log_reel_manual(caption, media_id)
                st.success(f"Reel publicado. Media ID: {media_id}")
                st.session_state.reel_video_bytes = None
                st.session_state.reel_posts_for_video = []
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao publicar: {e}")
