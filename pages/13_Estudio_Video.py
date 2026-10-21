"""
Estúdio de vídeo: gerar vídeos com as ferramentas instaladas no servidor (~/video) e publicá-los como Reels.

- Reel de frase: modelo HyperFrames (palavras a entrar, paralaxe 2.5D, música livre). ~0,002 $ por vídeo.
- Clips 2.5D: um clip de 5 s com movimento de câmara por cada prompt (imagem flux + recorte por profundidade).
- Montagem: junta clips numa sequência — simples (ffmpeg, grátis, segundos) ou com o OpenStoryline (agente
  que escolhe a ordem, escreve legendas e escolhe música; minutos, alguns cêntimos de modelo de texto).
Todos os resultados ficam também em Video/saida (https://magnific1.ddns.net/video/files/saida/).
"""
import os
from pathlib import Path

import streamlit as st

from instagram_poster.auth import require_auth, render_auth_sidebar

st.set_page_config(page_title="Estúdio de vídeo | Instagram Auto Post", page_icon="🎬", layout="wide")
require_auth()
with st.sidebar:
    render_auth_sidebar()

from instagram_poster import studio  # noqa: E402
from instagram_poster.db import get_published_posts_with_image, get_upcoming_posts  # noqa: E402
from instagram_poster.quote_reel import (  # noqa: E402
    COVER_OFFSET_MS, cover_from_video, create_quote_reel, free_music_tracks, get_used_row_indices, mark_used)

st.title("Estúdio de vídeo")
st.caption("Vídeos feitos com as ferramentas do servidor, sem custos de geração de vídeo por IA. "
           "Os ficheiros ficam também em Video/saida.")

MUSIC = free_music_tracks()


def music_picker(key: str):
    opts = ["Aleatória (música livre)"] + [p.stem.replace("_", " ").title() for p in MUSIC] + ["Sem música"]
    choice = st.selectbox("Música", opts, key=key, help="Faixas em domínio público/CC0 (assets/music/LIVRE).")
    if choice == opts[0]:
        return None  # o gerador escolhe uma ao acaso
    if choice == opts[-1]:
        return ""
    return str(MUSIC[opts.index(choice) - 1])


def publish_block(key: str, video: bytes, caption: str, cover_ms: int, on_published=None):
    """Pré-visualização, capa, legenda e botão Publicar."""
    c1, c2 = st.columns([2, 1])
    with c1:
        st.video(video)
    with c2:
        cover_ms = st.slider("Capa (segundo do vídeo)", 0.0, max(0.5, studio_duration(video) - 0.2),
                             cover_ms / 1000, 0.1, key=f"{key}_cover") * 1000
        try:
            st.image(cover_from_video(video, int(cover_ms)), caption="Capa", width=200)
        except Exception as e:
            st.caption(f"Sem pré-visualização da capa: {e}")
    text = st.text_area("Legenda", caption, height=160, key=f"{key}_caption")
    st.download_button("Descarregar MP4", video, file_name=f"{key}.mp4", mime="video/mp4", key=f"{key}_dl")
    if st.button("Publicar como Reel", type="primary", key=f"{key}_pub"):
        if not text.strip():
            st.warning("Escreve uma legenda antes de publicar.")
            return
        with st.spinner("A enviar e a publicar no Instagram (pode levar 1–3 minutos)…"):
            try:
                media_id = studio.publish_reel(video, text.strip(), int(cover_ms))
                if on_published:
                    on_published(media_id)
                st.success(f"Publicado no Instagram (media_id {media_id}).")
            except Exception as e:
                st.error(f"Falhou a publicação: {e}")


def studio_duration(video: bytes) -> float:
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
        f.write(video)
        f.flush()
        return studio.video_duration(Path(f.name)) or 8.0


tab_quote, tab_clips, tab_mont = st.tabs(["🎞️ Reel de frase", "🌄 Clips 2.5D", "🎬 Montagem"])

# --- Reel de frase -----------------------------------------------------------------------------------
with tab_quote:
    st.markdown("Reel vertical de 8 s: imagem gerada, movimento 2.5D, frase a entrar palavra a palavra, música livre. "
                "**Custo ≈ 0,002 $** (uma imagem). Demora ~15–25 s.")
    source = st.radio("Frase", ["De um post", "Texto livre"], horizontal=True, key="q_source")
    used = get_used_row_indices()
    if source == "De um post":
        posts = {int(p["row_index"]): p for p in get_upcoming_posts(30) + get_published_posts_with_image()[:60]
                 if (p.get("image_text") or "").strip()}
        rows = list(posts)
        if not rows:
            st.info("Não há posts com frase na base de dados.")
            post = None
        else:
            r = st.selectbox("Post", rows, key="q_row", format_func=lambda i: f"{i} · {posts[i].get('date', '')} · "
                             f"{posts[i]['image_text'][:70]}{'  (já tem Reel)' if i in used else ''}")
            post = posts[r]
    else:
        quote = st.text_input("Frase (curta, até ~90 caracteres)", key="q_text", max_chars=140)
        scene = st.text_area("Descrição da imagem de fundo", key="q_scene",
                             placeholder="Ex.: a person watching the sunrise from a balcony, calm, warm light")
        post = {"image_text": quote, "gemini_prompt": scene, "image_url": "", "caption": quote,
                "row_index": None} if quote.strip() and scene.strip() else None
    c1, c2 = st.columns(2)
    with c1:
        audio = music_picker("q_music")
    with c2:
        parallax = st.checkbox("Movimento 2.5D (paralaxe)", value=True, key="q_parallax")
    if st.button("Gerar Reel de frase", disabled=post is None, key="q_go"):
        os.environ["QUOTE_REEL_PARALLAX"] = "true" if parallax else "false"
        with st.spinner("A gerar imagem, profundidade e animação…"):
            try:
                video = create_quote_reel(post, audio_path=audio)
                path = studio.save_output(video, f"reel-{post['image_text']}")
                st.session_state.studio_quote = {"video": video, "post": post, "path": str(path)}
            except Exception as e:
                st.error(f"Não foi possível gerar o Reel: {e}")
    res = st.session_state.get("studio_quote")
    if res:
        st.caption(f"Guardado em {res['path']}")
        row = res["post"].get("row_index")
        publish_block("quote", res["video"], res["post"].get("caption") or res["post"]["image_text"], COVER_OFFSET_MS,
                      on_published=(lambda mid: mark_used(int(row), media_id=mid)) if row else None)

# --- Clips 2.5D --------------------------------------------------------------------------------------
with tab_clips:
    st.markdown("Cada linha é uma cena: gera uma imagem vertical e transforma-a num clip de 5 s com movimento "
                f"de câmara. **Custo ≈ {studio.COST_PER_IMAGE_USD} $ por clip**, ~20 s cada. "
                "Os clips servem depois para a Montagem.")
    name = st.text_input("Nome do conjunto", "say no without guilt", key="c_name")
    prompts_txt = st.text_area("Cenas (uma por linha, em inglês, sem texto na imagem)", height=180, key="c_prompts",
                               placeholder="A woman closing her laptop at sunset, calm and relieved\n"
                                           "A man walking alone on a misty forest path, seen from behind")
    prompts = [p.strip() for p in prompts_txt.splitlines() if p.strip()][:10]
    st.caption(f"{len(prompts)} cena(s) · custo estimado {len(prompts) * studio.COST_PER_IMAGE_USD:.3f} $ · "
               f"~{len(prompts) * 20} s (máximo 10 por vez)")
    if st.button("Gerar clips", disabled=not prompts, key="c_go"):
        with st.spinner(f"A gerar {len(prompts)} clip(s)…"):
            try:
                folder = studio.make_parallax_clips(name, prompts)
                st.success(f"Clips prontos em {folder.name}")
            except Exception as e:
                st.error(f"Falhou: {e}")
    sets = studio.clip_sets()
    if sets:
        st.subheader("Conjuntos de clips")
        for s in sets[:6]:
            clips = sorted(s.glob("clip_*.mp4"))
            with st.expander(f"{s.name} — {len(clips)} clip(s)"):
                cols = st.columns(min(len(clips), 5) or 1)
                for i, c in enumerate(clips):
                    cols[i % len(cols)].video(str(c))

# --- Montagem ----------------------------------------------------------------------------------------
with tab_mont:
    sets = studio.clip_sets()
    if not sets:
        st.info("Primeiro gera um conjunto de clips no separador Clips 2.5D.")
    else:
        sel = st.selectbox("Conjunto de clips", sets, format_func=lambda p: f"{p.name} ({len(list(p.glob('clip_*.mp4')))} clips)",
                           key="m_set")
        mode = st.radio("Tipo de montagem", ["Simples (grátis, segundos)", "OpenStoryline (IA, minutos)"],
                        horizontal=True, key="m_mode")
        if mode.startswith("Simples"):
            st.caption("Junta os clips pela ordem, com dissolves e música livre.")
            audio_m = music_picker("m_music")
            if st.button("Montar", key="m_simple"):
                with st.spinner("A montar…"):
                    try:
                        clips = sorted(sel.glob("clip_*.mp4"))
                        track = audio_m if audio_m is not None else (str(MUSIC[0]) if MUSIC else "")
                        video = studio.simple_montage(clips, track or None)
                        path = studio.save_output(video, f"montagem-{sel.name}")
                        st.session_state.studio_mont = {"video": video, "path": str(path), "caption": ""}
                    except Exception as e:
                        st.error(f"Falhou: {e}")
        else:
            st.caption("O agente vê os clips, decide a ordem e os cortes, escreve legendas no ecrã e escolhe música da "
                       "biblioteca livre. Sem voz e sem transições por IA. Usa o modelo de texto configurado em "
                       "/video/ › OpenStoryline (custo de alguns cêntimos). Demora ~2–3 minutos.")
            st.warning("Ainda experimental: o vídeo sai em 608×1080 e as legendas usam fontes chinesas, que partem "
                       "palavras inglesas a meio e não mostram o apóstrofo. Revê antes de publicar.")
            req = st.text_area("Pedido (em inglês)", height=150, key="m_req", value=(
                "Edit my uploaded clips into one vertical 9:16 Instagram Reel of about 30 seconds. English only. "
                "Add 3 short on-screen tips as subtitles. Calm piano background music from the music library. "
                "No voiceover. No AI transitions. Simple fades between clips."))
            prev = st.session_state.get("studio_storyline")
            same = prev and prev.get("set") == str(sel)
            c1, c2 = st.columns(2)
            go_new = c1.button("Montar com OpenStoryline", key="m_story")
            go_more = c2.button("Pedir alterações ao último vídeo", key="m_story_more", disabled=not same,
                                help="Envia o texto acima como alteração, na mesma sessão.")
            if go_new or go_more:
                with st.spinner("O OpenStoryline está a montar (pode levar vários minutos)…"):
                    try:
                        res = studio.storyline_edit(sel, req, session_id=prev["session_id"] if go_more else None)
                        st.session_state.studio_storyline = {"session_id": res["session_id"], "set": str(sel)}
                        if res["video"]:
                            video = Path(res["video"]).read_bytes()
                            path = studio.save_output(video, f"storyline-{sel.name}")
                            st.session_state.studio_mont = {"video": video, "path": str(path), "caption": ""}
                        else:
                            st.warning("O agente respondeu mas não gerou vídeo. Resposta:")
                            st.code(res["log"][-3000:])
                    except Exception as e:
                        st.error(f"Falhou: {e}")
        res = st.session_state.get("studio_mont")
        if res:
            st.caption(f"Guardado em {res['path']}")
            publish_block("montage", res["video"], res.get("caption", ""), 3000)
