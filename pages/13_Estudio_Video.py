"""
Estúdio de vídeo: gerar vídeos com as ferramentas instaladas no servidor (~/video) e publicá-los como Reels.

- Reel de frase: modelo HyperFrames (palavras a entrar, paralaxe 2.5D, música livre). ~0,002 $ por vídeo.
- Clips 2.5D: um clip de 5 s com movimento de câmara por cada prompt (imagem flux + recorte por profundidade).
- Montagem: junta clips numa sequência — simples (ffmpeg, grátis, segundos) ou com o OpenStoryline (agente
  que escolhe a ordem, escreve legendas e escolhe música; minutos, alguns cêntimos de modelo de texto).
Todos os resultados ficam também em Video/saida (https://magnific1.ddns.net/video/files/saida/).
"""
import json
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


tab_quote, tab_film, tab_clips, tab_mont = st.tabs(["🎞️ Reel de frase", "🖌️ Filme aguarela", "🌄 Clips 2.5D", "🎬 Montagem"])

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

# --- Filme aguarela ----------------------------------------------------------------------------------
from instagram_poster import watercolor_film as WF  # noqa: E402


@st.fragment(run_every=3)
def film_progress(job: str):
    """Estado do build, atualizado a cada 3 s; quando acaba, recarrega a página para mostrar o filme."""
    stt = WF.job_status(Path(job))
    state = stt.get("state")
    if state in ("queued", "waiting", "running"):
        import time as _t
        secs = int(_t.time() - stt["started"]) if stt.get("started") else 0
        st.info(f"⏳ {stt.get('step', '…')}" + (f" · {secs} s" if secs else ""))
        with st.expander("Registo"):
            st.code(WF.build_log_tail(Path(job)) or "…")
    elif state == "done":
        if st.session_state.get("film_done") != job:
            st.session_state.film_done = job
            st.rerun(scope="app")
    elif state == "error":
        st.error(f"O filme falhou: {stt.get('error')}")
        st.code(WF.build_log_tail(Path(job), 25))


from instagram_poster import watercolor_story as WS  # noqa: E402

TRANS_NAMES = {"pan": "travelling pela página", "mist": "névoa (mudança de tempo/lugar)"}


def _objsel(col, label, val, key):
    return col.selectbox(label, WS.OBJECTS, index=WS.OBJECTS.index(val) if val in WS.OBJECTS else 0, key=key)


def story_editor(sb: dict, ver: int) -> tuple[dict, tuple]:
    """Editor do storyboard. Devolve (storyboard com os valores dos campos, ação pedida: ('rm', i) / ('up', i) / None)."""
    beats, action = [], None
    for i, b in enumerate(sb["beats"]):
        with st.container(border=True):
            c1, c2, c3 = st.columns([6, 1, 1])
            ty = c1.selectbox(f"Momento {i + 1}", WS.BEAT_TYPES, index=WS.BEAT_TYPES.index(b["type"]), key=f"sb{ver}_{i}_ty",
                              format_func=lambda x: WS.BEAT_NAMES[x])
            if c2.button("⬆️", key=f"sb{ver}_{i}_up", disabled=i == 0, help="Subir"):
                action = ("up", i)
            if c3.button("🗑️", key=f"sb{ver}_{i}_rm", disabled=len(sb["beats"]) <= 1, help="Apagar"):
                action = ("rm", i)
            k = f"sb{ver}_{i}_{ty}_"
            nb = {"type": ty}
            if i:
                tr = b.get("transition", "pan")
                nb["transition"] = st.radio("Passagem do momento anterior", ["pan", "mist"], index=["pan", "mist"].index(tr), key=k + "tr",
                                            horizontal=True, format_func=lambda x: TRANS_NAMES[x])
            if ty == "trio":
                nb["lead"] = st.text_input("Frase antes das três coisas", b.get("lead", "Then give it something steady."), key=k + "lead")
                items = (b.get("items") or []) + [{"label": "slow breath", "object": "breath"}, {"label": "warm tea", "object": "cup"}, {"label": "a song", "object": "song"}]
                cols = st.columns(3)
                nb["items"] = [{"label": cols[j].text_input(f"Coisa {j + 1} (dita)", items[j]["label"], key=k + f"lab{j}"),
                                "object": _objsel(cols[j], "Desenho", items[j]["object"], k + f"ob{j}")} for j in range(3)]
            else:
                nb["lines"] = [x for x in st.text_area("Falas (uma por linha, ditas e legendadas)", "\n".join(b.get("lines") or []),
                                                       key=k + "ln", height=80).splitlines() if x.strip()]
                c1, c2, c3 = st.columns(3)
                if ty == "crowd":
                    nb["notes"] = [x for x in st.text_area("Notas aflitas (uma por linha, até 10)", "\n".join(b.get("notes") or WF.DEFAULT_SCRIPT["notes"]),
                                                           key=k + "nt", height=110).splitlines() if x.strip()]
                    nb["keep"] = st.checkbox("A névoa guarda um sentimento (passa para o momento seguinte)", b.get("keep", True), key=k + "keep")
                elif ty == "specimen":
                    nb["object"] = _objsel(c1, "Objeto", b.get("object", "person"), k + "ob")
                    nb["note"] = c2.text_input("Nota escrita", (b.get("note") or {}).get("text") if isinstance(b.get("note"), dict) else b.get("note", "here"), key=k + "note")
                elif ty == "journey":
                    nb["from"] = _objsel(c1, "De", b.get("from", "house"), k + "from")
                    nb["to"] = _objsel(c2, "Para", b.get("to", "tree"), k + "to")
                    nb["label"] = c3.text_input("Nota à chegada", b.get("label", ""), key=k + "lab")
                elif ty == "transform":
                    nb["from"] = _objsel(c1, "Antes", b.get("from", "storm"), k + "from")
                    nb["to"] = _objsel(c2, "Depois", b.get("to", "sun"), k + "to")
                    nb["note"] = c3.text_input("Nota", b.get("note", "") if isinstance(b.get("note", ""), str) else "", key=k + "note")
                    st.caption("Duas falas: uma antes da mudança, outra depois.")
                elif ty == "grow":
                    nb["objects"] = st.multiselect("Etapas (2 ou 3, da mais pequena para a maior)", WS.OBJECTS, default=[o for o in b.get("objects", ["seed", "sprout", "tree"]) if o in WS.OBJECTS][:3],
                                                   max_selections=3, key=k + "obs")
                    nb["note"] = c1.text_input("Nota", b.get("note", "") if isinstance(b.get("note", ""), str) else "", key=k + "note")
            beats.append(nb)
    return {**sb, "beats": beats}, action


with tab_film:
    st.markdown("Reel vertical **pintado em aguarela, feito em código**, a partir de um post. Voz em inglês (Kokoro, local), "
                "legendas, música original. **Custo 0 $** (só o guião usa o modelo de texto). Demora ~1–2 min.")
    probs = WF.check_ready()
    if probs:
        st.error("Falta preparar o servidor: " + "; ".join(probs))
    fposts = {int(p["row_index"]): p for p in get_upcoming_posts(30) + get_published_posts_with_image()[:60]
              if (p.get("image_text") or "").strip()}
    mode = st.radio("Tipo de filme", ["História livre", "Modelo original"], horizontal=True, key="f_mode",
                    help="História livre: a IA monta uma história com momentos e objetos pintados. "
                         "Modelo original: a história de 'One Feeling at a Time', só com as palavras do post.")
    if not fposts:
        st.info("Não há posts com frase na base de dados.")
    elif mode == "História livre":
        fr = st.selectbox("Post", list(fposts), key="f_row",
                          format_func=lambda i: f"{i} · {fposts[i].get('date', '')} · {fposts[i]['image_text'][:70]}")
        fpost = fposts[fr]
        with st.expander("Momentos e objetos disponíveis"):
            st.markdown(" · ".join(f"**{WS.BEAT_NAMES[t]}**" for t in WS.BEAT_TYPES))
            st.image(str(WS.TEMPLATE / "objects_sheet.jpg"), caption=f"{len(WS.OBJECTS)} objetos pintados", width=520)
        if st.button("1 · Montar história", key="sb_draft", disabled=bool(probs)):
            with st.spinner("A IA está a montar a história a partir do post…"):
                st.session_state.film_sb = WS.draft_storyboard(fpost)
                st.session_state.film_sb_row = fr
                st.session_state.film_sb_ver = st.session_state.get("film_sb_ver", 0) + 1
        sb = st.session_state.get("film_sb") if st.session_state.get("film_sb_row") == fr else None
        if sb:
            ver = st.session_state.get("film_sb_ver", 0)
            edited, action = story_editor(sb, ver)
            c1, c2 = st.columns([3, 1])
            add_ty = c1.selectbox("Novo momento", WS.BEAT_TYPES, key=f"sb{ver}_addty", format_func=lambda x: WS.BEAT_NAMES[x],
                                  label_visibility="collapsed")
            if c2.button("➕ Adicionar momento", key=f"sb{ver}_add", disabled=len(edited["beats"]) >= 5):
                action = ("add", add_ty)
            c1, c2, c3 = st.columns(3)
            edited["close"] = c1.text_input("Fala final", sb.get("close", ""), key=f"sb{ver}_close")
            edited["later"] = c2.text_input("Nota final (escrita à mão)", sb.get("later", ""), key=f"sb{ver}_later")
            edited["title"] = c3.text_input("Título", sb.get("title", ""), key=f"sb{ver}_title")
            if action:
                bs = edited["beats"]
                if action[0] == "rm":
                    bs.pop(action[1])
                elif action[0] == "up":
                    bs[action[1] - 1], bs[action[1]] = bs[action[1]], bs[action[1] - 1]
                else:
                    bs.append({"type": action[1]})
                st.session_state.film_sb = WS.normalize_storyboard(edited)
                st.session_state.film_sb_ver = ver + 1
                st.rerun()
            norm = WS.normalize_storyboard(edited)
            est = WS.estimate_duration(norm)
            st.caption(f"Duração estimada ≈ {est:.0f} s" + (" · ⚠️ longa: a validação corta momentos acima de 58 s" if est > WS.MAX_DUR else ""))
            if st.button("2 · Fazer filme", type="primary", key=f"sb{ver}_go", disabled=bool(probs)):
                st.session_state.film_sb = norm
                st.session_state.film_job = str(WS.start_build(norm, fpost["image_text"], fpost))
                st.session_state.film_done = None
    else:
        fr = st.selectbox("Post", list(fposts), key="f_row",
                          format_func=lambda i: f"{i} · {fposts[i].get('date', '')} · {fposts[i]['image_text'][:70]}")
        fpost = fposts[fr]
        if st.button("1 · Escrever guião", key="f_draft", disabled=bool(probs)):
            with st.spinner("A escrever o guião a partir do post…"):
                st.session_state.film_script = WF.draft_script(fpost)
                st.session_state.film_row = fr
        fs = st.session_state.get("film_script") if st.session_state.get("film_row") == fr else None
        if fs:
            with st.form("film_form"):
                st.caption("Edita à vontade. As falas são ditas pela voz e aparecem como legendas.")
                l1 = st.text_input("Abertura (o gancho)", fs["l1"])
                l2 = st.text_input("Porque custa", fs["l2"])
                l3 = st.text_input("A armadilha (antes da névoa)", fs["l3"])
                l4 = st.text_input("Depois da névoa: escolher uma coisa", fs["l4"])
                l5 = st.text_input("Frase antes das três coisas", fs["l5_lead"])
                cols = st.columns(3)
                items = []
                for k, (col, it) in enumerate(zip(cols, fs["items"])):
                    with col:
                        lab = st.text_input(f"Coisa {k + 1} (dita e escrita)", it["label"], key=f"f_lab{k}")
                        ic = st.selectbox("Desenho", WF.ICONS, index=WF.ICONS.index(it["icon"]), key=f"f_ic{k}",
                                          format_func=lambda x: WF.ICON_NAMES[x])
                        items.append({"label": lab, "icon": ic})
                l6 = st.text_input("Fecho", fs["l6"])
                notes = st.text_area("Notas aflitas na página cheia (uma por linha, 10)", "\n".join(fs["notes"]), height=150)
                c1, c2, c3 = st.columns(3)
                here = c1.text_input("Nota no peito", fs["here"])
                later = c2.text_input("Nota final (escrita à mão)", fs["later"])
                title = c3.text_input("Título", fs["title"])
                go = st.form_submit_button("2 · Fazer filme", type="primary", disabled=bool(probs))
            if go:
                script = {"l1": l1, "l2": l2, "l3": l3, "l4": l4, "l5_lead": l5, "items": items, "l6": l6,
                          "notes": [n for n in notes.splitlines() if n.strip()], "here": here, "later": later, "title": title}
                st.session_state.film_script = WF.normalize_script(script)
                st.session_state.film_job = str(WF.start_build(script, fpost["image_text"], fpost))
                st.session_state.film_done = None
    job = st.session_state.get("film_job")
    if job and st.session_state.get("film_done") != job:
        film_progress(job)
    done = st.session_state.get("film_done")
    if done:
        stt = WF.job_status(Path(done))
        vp = Path(stt.get("video") or Path(done) / "film.mp4")
        if vp.exists():
            st.caption(f"Guardado em {vp.parent}" + (f" · ⚠️ {stt['warning']}" if stt.get("warning") else ""))
            if (Path(done) / "sheet.jpg").exists():
                st.image(str(Path(done) / "sheet.jpg"), caption="Fotogramas do filme", width="stretch")
            pj = Path(done) / "post.json"
            cap = (json.loads(pj.read_text()).get("caption") if pj.exists() else "") or ""
            publish_block("film", vp.read_bytes(), cap, int(max(0.5, float(stt.get("duration", 40)) - 2.9) * 1000))
    with st.expander("Filmes recentes"):
        for jp in WF.recent_jobs():
            js = WF.job_status(jp)
            c1, c2 = st.columns([4, 1])
            c1.write(f"`{jp.name}` · {js.get('state')} · {js.get('step', '')}")
            if js.get("state") == "done" and c2.button("Abrir", key=f"open_{jp.name}"):
                st.session_state.film_done = str(jp)
                st.session_state.film_job = str(jp)
                st.rerun()

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
            st.warning("Ainda experimental: o vídeo sai em 608×1080. Revê antes de publicar.")
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
