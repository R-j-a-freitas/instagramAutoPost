"""
Descarregar áudio de um vídeo do YouTube em MP3 (via yt-dlp).
Usa FFmpeg incluído no projeto (imageio-ffmpeg). O ficheiro pode ser guardado na pasta de música dos Reels.
"""
import os
import re
import shutil
import tempfile
from pathlib import Path

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

import streamlit as st

from instagram_poster.auth import require_auth, render_auth_sidebar

st.set_page_config(page_title="YouTube Áudio | Instagram Auto Post", page_icon="🎵", layout="wide")
require_auth()
with st.sidebar:
    render_auth_sidebar()

# Navegação
nav1, nav2, nav3, nav4, nav5, nav6, nav7, _ = st.columns([1, 1, 1, 1, 1, 1, 1, 2])
with nav1:
    if st.button("← Inicio", key="nav_home_yt"):
        st.switch_page("app.py")
with nav2:
    if st.button("⚙️ Configuracao", key="nav_cfg_yt"):
        st.switch_page("pages/1_Configuracao.py")
with nav3:
    if st.button("📸 Posts", key="nav_posts_yt"):
        st.switch_page("pages/2_Posts.py")
with nav4:
    if st.button("✏️ Conteudo", key="nav_content_yt"):
        st.switch_page("pages/3_Conteudo.py")
with nav5:
    if st.button("🔄 Autopublish", key="nav_ap_yt"):
        st.switch_page("pages/4_Autopublish.py")
with nav6:
    if st.button("📱 Stories", key="nav_stories_yt"):
        st.switch_page("pages/5_Stories.py")
with nav7:
    if st.button("🎬 Reels", key="nav_reels_yt"):
        st.switch_page("pages/4_Reels.py")

st.title("YouTube → Áudio MP3")
st.caption("Descarrega apenas o stream de áudio (sem vídeo) e converte para MP3 (192 kbps) — mais rápido. Usa yt-dlp e FFmpeg (imageio-ffmpeg).")

missing = []
if imageio_ffmpeg is None:
    missing.append("imageio-ffmpeg")
if yt_dlp is None:
    missing.append("yt-dlp")
if missing:
    st.error(
        f"**{' e '.join(missing)}** não encontrado(s). Instala com: `pip install {' '.join(missing)}`"
    )
    if st.button("Instalar dependências agora", type="primary", key="yt_install_deps"):
        import subprocess
        import sys
        with st.spinner("A instalar (pode demorar alguns minutos)..."):
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "imageio-ffmpeg", "yt-dlp"],
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
            except subprocess.TimeoutExpired:
                st.error("Instalação demorou demasiado. Tenta no terminal: pip install imageio-ffmpeg yt-dlp")
                result = None
        if result is not None:
            if result.returncode == 0:
                st.success("Instalado. Recarrega a página (F5 ou botão do browser).")
            else:
                st.error(f"Falha: {result.stderr or result.stdout or 'Erro desconhecido'}")

# Estado para o ficheiro descarregado
if "yt_audio_path" not in st.session_state:
    st.session_state.yt_audio_path = None
if "yt_audio_filename" not in st.session_state:
    st.session_state.yt_audio_filename = None

def _sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos para nome de ficheiro Windows."""
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return re.sub(r"\s+", " ", name).strip() or "audio"


def _get_ffmpeg_location() -> str | None:
    """
    Caminho para o FFmpeg: pasta do projeto (com ffmpeg/ffprobe), imageio-ffmpeg
    ou FFmpeg do sistema (PATH).
    """
    root = Path(__file__).resolve().parent.parent

    # 1) Pasta do projeto (se tiver binários compatíveis)
    for subdir in ("tools/ffmpeg", "ffmpeg", "tools/ffmpeg/bin", "ffmpeg/bin"):
        folder = root / subdir.replace("/", os.sep)
        ff = folder / "ffmpeg"
        ff_exe = folder / "ffmpeg.exe"
        if ff.exists() or ff_exe.exists():
            return str(folder)

    # 2) imageio-ffmpeg (download automático)
    if imageio_ffmpeg is not None:
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return str(Path(exe).resolve())

    # 3) FFmpeg do sistema (PATH)
    import shutil
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return str(Path(sys_ffmpeg).parent)

    return None


def download_youtube_audio(url: str) -> tuple[str | None, str | None, str | None]:
    """
    Descarrega o áudio do YouTube em MP3.
    Devolve (caminho, nome_ficheiro, None) em sucesso ou (None, None, mensagem_erro) em falha.
    """
    if yt_dlp is None:
        return None, None, "yt-dlp não instalado. Executa: pip install yt-dlp"
    if not url or "youtube.com" not in url and "youtu.be" not in url:
        return None, None, "URL inválido. Usa um link do YouTube (youtube.com ou youtu.be)."
    ffmpeg_location = _get_ffmpeg_location()
    if not ffmpeg_location:
        return None, None, "FFmpeg não encontrado. Instala o pacote imageio-ffmpeg (pip install imageio-ffmpeg) ou coloca ffmpeg.exe em tools/ffmpeg/."
    with tempfile.TemporaryDirectory() as tmpdir:
        outtmpl = str(Path(tmpdir) / "%(title).100s.%(ext)s")
        # Apenas áudio: evita descarregar vídeo (muito mais rápido). M4A/WebM são streams só-áudio no YouTube.
        # Sem "best" no final para não fazer fallback para vídeo+áudio.
        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
            "outtmpl": outtmpl,
            "concurrent_fragment_downloads": 4,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "quiet": True,
        }
        ydl_opts["ffmpeg_location"] = ffmpeg_location
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
            if not info:
                return None, None, "O YouTube não devolveu informações do vídeo."
            title = info.get("title") or "audio"
            base = Path(tmpdir)
            mp3s = list(base.glob("*.mp3"))
            if not mp3s:
                return None, None, "O áudio não foi convertido para MP3 (verifica se o vídeo tem áudio)."
            mp3_path = mp3s[0]
            persistent = Path(tempfile.gettempdir()) / f"yt_audio_{mp3_path.name}"
            shutil.copy2(mp3_path, persistent)
            return str(persistent), _sanitize_filename(title) + ".mp3", None
        except Exception as e:
            err = str(e).strip() or e.__class__.__name__
            return None, None, err


st.subheader("Descarregar áudio")
url = st.text_input(
    "URL do vídeo do YouTube",
    placeholder="https://www.youtube.com/watch?v=... ou https://youtu.be/...",
    key="yt_url",
)
col_dl, col_sp = st.columns([1, 3])
with col_dl:
    do_download = st.button("🎵 Descarregar áudio (MP3)", type="primary", key="yt_dl_btn")

if do_download and url:
    with st.spinner("A descarregar áudio… (pode demorar)"):
        path, filename, err_msg = download_youtube_audio(url.strip())
    if path and filename:
        st.session_state.yt_audio_path = path
        st.session_state.yt_audio_filename = filename
        st.success(f"Áudio descarregado: **{filename}**")
    else:
        st.error("Não foi possível descarregar. " + (err_msg or "Verifica o URL."))
        st.session_state.yt_audio_path = None
        st.session_state.yt_audio_filename = None

# Botão para transferir o ficheiro e opção de guardar na pasta de música
if st.session_state.yt_audio_path and Path(st.session_state.yt_audio_path).exists():
    st.divider()
    st.subheader("Ficheiro descarregado")
    fp = Path(st.session_state.yt_audio_path)
    fname = st.session_state.yt_audio_filename or fp.name
    with open(fp, "rb") as f:
        st.download_button(
            "⬇️ Transferir MP3",
            data=f.read(),
            file_name=fname,
            mime="audio/mpeg",
            key="yt_download_btn",
        )
    # Guardar na pasta de música dos Reels
    music_folder = Path(__file__).resolve().parent.parent / "assets" / "music" / "MUSIC"
    if music_folder.exists():
        save_to_music = st.checkbox("Guardar na pasta de música dos Reels (assets/music/MUSIC/)", key="yt_save_music")
        if save_to_music and st.button("Guardar cópia na pasta MUSIC", key="yt_copy_music"):
            dest = music_folder / fname
            shutil.copy2(fp, dest)
            st.success(f"Cópia guardada em: **{dest}**")
            st.caption("Adiciona a faixa em assets/music/metadata.json para aparecer na página Reels.")
    else:
        st.caption("Pasta assets/music/MUSIC/ não encontrada; não é possível guardar aqui.")

st.divider()
st.caption("O descarregamento usa apenas streams de áudio (M4A/WebM), nunca o vídeo, para ser mais rápido. FFmpeg (imageio-ffmpeg) converte para MP3.")

# Documentação
_docs_path = Path(__file__).resolve().parent.parent / "docs" / "YouTube_Audio.md"
if _docs_path.exists():
    with st.expander("📖 Documentação — YouTube Áudio e FFmpeg"):
        st.markdown(_docs_path.read_text(encoding="utf-8"))
else:
    st.caption("Documentação em `docs/YouTube_Audio.md`.")
