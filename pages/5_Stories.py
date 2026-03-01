"""
Monitorização de Stories e publicação manual (a partir de um post aleatório).
"""
import random
import streamlit as st

from instagram_poster.auth import require_auth, render_auth_sidebar

st.set_page_config(page_title="Stories | Instagram Auto Post", page_icon="📱", layout="wide")
require_auth()
with st.sidebar:
    render_auth_sidebar()

# Navegação
nav1, nav2, nav3, nav4, nav5, _ = st.columns([1, 1, 1, 1, 1, 2])
with nav1:
    if st.button("← Inicio", key="nav_home_st"):
        st.switch_page("app.py")
with nav2:
    if st.button("⚙️ Configuracao", key="nav_cfg_st"):
        st.switch_page("pages/1_Configuracao.py")
with nav3:
    if st.button("📸 Posts", key="nav_posts_st"):
        st.switch_page("pages/2_Posts.py")
with nav4:
    if st.button("✏️ Conteudo", key="nav_content_st"):
        st.switch_page("pages/3_Conteudo.py")
with nav5:
    if st.button("🔄 Autopublish", key="nav_ap_st"):
        st.switch_page("pages/4_Autopublish.py")

st.title("Stories")
st.caption("Monitoriza as Stories publicadas e publica uma Story a partir de um post (aleatório ou escolhido).")

from instagram_poster import autopublish, image_generator
from instagram_poster.scheduler import publish_story_from_post
from instagram_poster.sheets_client import get_published_posts_with_image, get_published_rows_missing_image_url, update_image_url

# Métrica (get_log primeiro para recarregar do ficheiro se outro processo gravou)
_ = autopublish.get_log()
stats = autopublish.get_stats()
st.metric("Stories publicadas (sessão)", stats.get("total_stories", 0))

st.divider()

# Reparar: linhas já publicadas sem ImageURL (ex.: publicações antigas)
rows_missing_url = get_published_rows_missing_image_url()
if rows_missing_url:
    with st.expander(f"Reparar: {len(rows_missing_url)} linha(s) publicada(s) sem ImageURL no Sheet", expanded=True):
        st.caption(
            "Se publicaste posts pela app antes de guardar o URL, ou editaste o Sheet à mão, "
            "estas linhas têm Published=yes mas ImageURL vazio. Preenche agora: gera a imagem (Cloudinary) e grava o URL no Sheet — sem republicar no Instagram."
        )
        if st.button("Preencher ImageURL nestas linhas (gerar imagem e gravar)", key="fill_image_url"):
            progress = st.progress(0, text="A processar...")
            ok, skip, err = 0, 0, 0
            for i, rec in enumerate(rows_missing_url):
                progress.progress((i + 1) / len(rows_missing_url), text=f"Linha {rec.get('row_index')}...")
                row_index = rec.get("row_index")
                gemini_prompt = (rec.get("gemini_prompt") or "").strip()
                image_text = (rec.get("image_text") or "").strip()
                if not gemini_prompt and not image_text:
                    skip += 1
                    continue
                try:
                    url = image_generator.get_image_url_from_prompt(
                        prompt=gemini_prompt or image_text,
                        quote_text=image_text if image_text else None,
                        use_full_prompt=bool(gemini_prompt),
                        public_id_prefix=f"keepcalm_{row_index}",
                    )
                    update_image_url(row_index, url)
                    ok += 1
                except Exception:
                    err += 1
            progress.empty()
            st.success(f"Concluído: {ok} URL(s) gravados, {skip} ignorados (sem prompt), {err} erro(s).")
            st.rerun()

st.subheader("Publicar Story manualmente")
posts = get_published_posts_with_image()
_no_posts_msg = (
    "Nenhum post publicado com imagem no Sheet. "
    "Se já tens publicações no Instagram, usa o bloco «Reparar: linha(s) publicada(s) sem ImageURL» acima para preencher o ImageURL; ou publica um novo post pela app (o URL passa a ser guardado automaticamente)."
)


def _get_music_options(key_prefix: str) -> tuple[bool, float, str | None]:
    """Retorna (with_music, duration_seconds, music_track_path) para um bloco com key_prefix."""
    with_music = st.toggle(
        "Adicionar musica (video com audio)",
        value=False,
        key=f"{key_prefix}_music_toggle",
        help="Gera um video (ate 60s, maximo da API) com a imagem + musica da pasta MUSIC. Requer moviepy.",
    )
    duration_seconds = 30.0
    music_track_path = None
    if with_music:
        duration_seconds = st.slider(
            "Duracao do video (segundos)",
            min_value=10,
            max_value=59,
            value=30,
            key=f"{key_prefix}_duration_slider",
        )
        try:
            from instagram_poster.reel_generator import get_available_music_tracks
            tracks = get_available_music_tracks()
            if tracks:
                options = ["(Aleatorio)"] + [t.get("name", t["file"]) for t in tracks]
                track_paths = [None] + [t["path"] for t in tracks]
                sel = st.selectbox(
                    "Faixa de musica",
                    options=range(len(options)),
                    format_func=lambda i: options[i],
                    key=f"{key_prefix}_music_track",
                )
                if sel is not None and sel > 0:
                    music_track_path = track_paths[sel]
            else:
                st.caption("Nenhuma faixa em assets/music/MUSIC/. Coloca ficheiros .mp3 na pasta.")
        except Exception as e:
            st.caption(f"Não foi possível carregar faixas: {e}")
    return with_music, duration_seconds, music_track_path


# --- Secção 1: Post aleatório ---
with st.expander("Publicar Story a partir de um post aleatório", expanded=True):
    st.caption("Escolhe um post já publicado ao acaso para gerar uma Story.")
    with_music_rand, duration_rand, music_path_rand = _get_music_options("story_random")
    if st.button("Publicar Story (post aleatório)", type="primary", key="story_random"):
        try:
            if not posts:
                st.warning(_no_posts_msg)
            else:
                post = random.choice(posts)
                with st.spinner("A gerar imagem Story e a publicar no Instagram..." if not with_music_rand else "A gerar video Story com musica e a publicar..."):
                    success, message, media_id = publish_story_from_post(
                        post, with_music=with_music_rand, music_track_path=music_path_rand,
                        duration_seconds=duration_rand if with_music_rand else 60.0,
                        source="aleatorio",
                    )
                if success:
                    st.success(message)
                    quote = (post.get("image_text") or "").strip()
                    st.info(f"Post usado: \"{quote[:80]}{'...' if len(quote) > 80 else ''}\" (linha {post.get('row_index')}, {post.get('date')})")
                    st.rerun()
                else:
                    st.error(message)
        except Exception as e:
            st.error(f"Erro: {e}")
            st.info("Verifica a ligação ao Google Sheet e ao Instagram na Configuração.")

st.divider()

# --- Secção 2: Post à escolha do utilizador ---
with st.expander("Publicar Story a partir de um post à tua escolha", expanded=True):
    st.caption("Selecciona um post específico para gerar uma Story.")
    if posts:
        row_options = [f"Linha {p['row_index']} — {p.get('date')} {p.get('time')} — {(p.get('image_text') or '')[:40]}..." for p in posts]
        selected_label = st.selectbox(
            "Post para Story:",
            options=row_options,
            index=0,
            key="story_post_select",
        )
        selected_idx = row_options.index(selected_label) if selected_label else 0
        selected_post = posts[selected_idx]
        with_music_sel, duration_sel, music_path_sel = _get_music_options("story_selected")
        if st.button("Publicar Story do post selecionado", key="story_selected"):
            try:
                with st.spinner("A gerar imagem Story e a publicar no Instagram..." if not with_music_sel else "A gerar video Story com musica e a publicar..."):
                    success, message, media_id = publish_story_from_post(
                        selected_post, with_music=with_music_sel, music_track_path=music_path_sel,
                        duration_seconds=duration_sel if with_music_sel else 60.0,
                        source="manual",
                    )
                if success:
                    st.success(message)
                    quote = (selected_post.get("image_text") or "").strip()
                    st.info(f"Post usado: \"{quote[:80]}{'...' if len(quote) > 80 else ''}\" (linha {selected_post.get('row_index')}, {selected_post.get('date')})")
                    st.rerun()
                else:
                    st.error(message)
            except Exception as e:
                st.error(f"Erro: {e}")
                st.info("Verifica a ligação ao Google Sheet e ao Instagram na Configuração.")
    else:
        st.caption("Sem posts publicados para escolher.")

st.divider()

# Histórico de Stories publicadas
st.subheader("Stories publicadas")
ap_log = autopublish.get_log()
story_entries = [e for e in ap_log if e.get("type") == "story"]

_ORIGEM_LABELS = {"reuse": "Reuse", "com_post": "Com post", "aleatorio": "Aleatório", "manual": "Manual"}

if story_entries:
    for entry in reversed(story_entries):
        ts = entry["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        quote = entry.get("quote", "")
        post_date = entry.get("date", "")
        post_time = entry.get("time", "")
        row = entry.get("row", "")
        mid = entry.get("media_id", "")
        origem = _ORIGEM_LABELS.get(entry.get("story_source", ""), "—")
        schedule_info = f"{post_date} {post_time}".strip()

        col_p1, col_p2 = st.columns([3, 1])
        with col_p1:
            st.markdown(f"**\"{quote}\"**" if quote else "*(sem quote)*")
        with col_p2:
            st.caption(f"Story: {ts}")
        detail_parts = [f"Origem: {origem}"]
        if schedule_info:
            detail_parts.append(f"Post: {schedule_info}")
        if row:
            detail_parts.append(f"Linha: {row}")
        if mid:
            detail_parts.append(f"Media ID: `{mid}`")
        if detail_parts:
            st.caption(" | ".join(detail_parts))
        st.divider()
else:
    st.caption("Nenhuma Story registada nesta sessão. Publica uma com o botão acima ou activa \"Publicar Story automaticamente com cada post\" na Configuração.")
