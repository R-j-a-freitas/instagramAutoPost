"""
Criacao de conteudo para Instagram via IA.
Gera N posts com quote, caption, e prompt de imagem, depois adiciona à base de dados interna.
"""
import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import requests
import streamlit as st

from instagram_poster.auth import require_auth, render_auth_sidebar
from instagram_poster.config import (
    get_content_extra_prompt,
    get_content_system_prompt_override,
    get_default_content_system_prompt,
)
from instagram_poster.db import append_rows, get_last_date
from instagram_poster.text_generator import generate_text
from instagram_poster.content_quality import (
    MIN_HOOK_SCORE,
    caption_warnings,
    carousel_slide_count,
    humanize_post,
    improve_weak_hooks,
    score_hook,
    system_prompt_with_quality_rules,
)

logger = logging.getLogger(__name__)


def _get_system_prompt() -> str:
    """Prompt de sistema (override do ficheiro se existir, senão o padrão) + regras de qualidade."""
    override = get_content_system_prompt_override()
    return system_prompt_with_quality_rules(override if override else get_default_content_system_prompt())


def _generate_content(
    n: int,
    extra_prompt: Optional[str] = None,
) -> list[dict]:
    """Usa a IA configurada (Pollinations/Kimi) para gerar N posts."""
    system_prompt = _get_system_prompt()
    user_base = f"Generate {n} new content rows as a JSON object with key 'posts' containing an array. Use 'YYYY-MM-DD' for Date. Make all {n} posts with varied micro-themes."
    extra = (extra_prompt or "").strip() or (get_content_extra_prompt() or "").strip()
    if extra:
        user_base += f" Current focus or themes to incorporate in this batch: {extra}"

    content = generate_text(system_prompt=system_prompt, user_prompt=user_base, json_mode=True)

    parsed = json.loads(content)
    posts = parsed.get("posts", parsed.get("rows", []))
    if isinstance(posts, dict):
        posts = [posts]
    # Qualidade: texto humanizado e ganchos fracos reescritos (uma chamada extra à IA, só se preciso).
    for p in posts:
        humanize_post(p)
    changes = improve_weak_hooks(posts, generate_text)
    st.session_state["hook_changes"] = changes
    return posts


def _posts_to_dataframe(posts: list[dict], start_date: date) -> pd.DataFrame:
    """Converte lista de posts em DataFrame com datas reais."""
    rows = []
    for i, p in enumerate(posts):
        post_type = (p.get("Post Type") or "single").strip().lower() or "single"
        rows.append({
            "Date": (start_date + timedelta(days=i)).strftime("%Y-%m-%d"),
            "Time": p.get("Time", "21:30"),
            "Image Text": p.get("Image Text", ""),
            "Caption": p.get("Caption", ""),
            "Gemini_Prompt": p.get("Gemini_Prompt", ""),
            "Status": "ready",
            "Published": "",
            "ImageURL": "",
            "Image Prompt": "yes",
            "Post Type": post_type,
            "Slide2 Text": p.get("Slide2 Text", "") if post_type == "carousel" else "",
        })
    return _with_quality_columns(pd.DataFrame(rows))


def _with_quality_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Colunas só de leitura (não vão para a base de dados): nota do gancho, slides e avisos da legenda."""
    df = df.copy()
    scores = [score_hook(t) for t in df["Image Text"]]
    df["Gancho"] = [f"{s['score']:.0f} {s['verdict']}" for s in scores]
    df["Slides"] = [carousel_slide_count(t) if pt == "carousel" else 1 for t, pt in zip(df["Slide2 Text"], df["Post Type"])]
    df["Avisos"] = ["; ".join(caption_warnings(c)) or "ok" for c in df["Caption"]]
    return df


_UI_TO_DB_COLUMNS = {
    "Date": "date",
    "Time": "time",
    "Image Text": "image_text",
    "Caption": "caption",
    "Gemini_Prompt": "gemini_prompt",
    "Status": "status",
    "Published": "published",
    "ImageURL": "image_url",
    "Image Prompt": "image_prompt",
    "Post Type": "post_type",
    "Slide2 Text": "slide2_text",
}


def _dataframe_to_posts(df: pd.DataFrame) -> list[dict]:
    """Converte o DataFrame (colunas com nomes amigáveis) em dicts prontos para a base de dados."""
    result = []
    for _, row in df.iterrows():
        result.append({db_key: str(row.get(ui_key, "") or "") for ui_key, db_key in _UI_TO_DB_COLUMNS.items()})
    return result


# --- UI ---
st.set_page_config(page_title="Conteudo | Instagram Auto Post", page_icon="✏️", layout="wide")
require_auth()
with st.sidebar:
    render_auth_sidebar()

nav1, nav2, nav3, _ = st.columns([1, 1, 1, 3])
with nav1:
    if st.button("← Inicio", key="nav_home_content"):
        st.switch_page("app.py")
with nav2:
    if st.button("⚙️ Configuracao", key="nav_cfg_content"):
        st.switch_page("pages/1_Configuracao.py")
with nav3:
    if st.button("📸 Posts", key="nav_posts_content"):
        st.switch_page("pages/2_Posts.py")

st.title("Criacao de conteudo")
st.caption("Gera novos posts com IA e adiciona directamente à base de dados interna.")
st.info(
    "A maioria dos posts é gerada como **carrossel editorial**: gancho + 5 a 7 slides (um por "
    "parágrafo em **Slide2 Text**, separados por linha em branco), terminando num slide-resumo "
    "e num slide com um pedido (guardar ou enviar). Os slides são numerados automaticamente.",
    icon="🎠",
)

# Determinar data inicial (dia seguinte ao ultimo post na base de dados)
_default_start = date.today() + timedelta(days=1)
try:
    _last = get_last_date()
    if _last:
        _parsed = datetime.strptime(_last, "%Y-%m-%d").date()
        _default_start = _parsed + timedelta(days=1)
except Exception:
    pass

col_cfg1, col_cfg2 = st.columns(2)
with col_cfg1:
    n_posts = st.slider("Numero de posts a gerar", min_value=1, max_value=30, value=7)
with col_cfg2:
    start_date = st.date_input("Data do primeiro post", value=_default_start)

focus_this_run = st.text_input(
    "Foco desta geração (opcional)",
    placeholder="Ex.: temas de outono, limites saudáveis. Deixar vazio usa o foco definido em Configuração.",
    key="content_focus_this_run",
    help="Sobrescreve apenas para esta execução o foco guardado em Configuração.",
)

if st.button("Gerar conteudo", type="primary"):
    with st.spinner(f"A gerar {n_posts} posts com IA... (pode demorar 30-60s)"):
        try:
            extra = (focus_this_run or "").strip() or None
            posts = _generate_content(n_posts, extra_prompt=extra)
            if not posts:
                st.error("A IA nao devolveu posts. Tenta novamente.")
            else:
                df = _posts_to_dataframe(posts, start_date)
                st.session_state["generated_content"] = df
                st.success(f"{len(posts)} posts gerados com sucesso!")
        except requests.HTTPError as e:
            st.error(f"Erro da API: {e}")
        except json.JSONDecodeError:
            st.error("A resposta da IA nao e JSON valido. Tenta novamente.")
        except Exception as e:
            st.error(f"Erro: {e}")

# Pre-visualizacao e edicao
if "generated_content" in st.session_state and st.session_state["generated_content"] is not None:
    st.subheader("Pre-visualizacao")
    st.caption("Edita os campos antes de adicionar à base de dados. Clica numa celula para editar.")

    df = st.session_state["generated_content"]
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Date": st.column_config.TextColumn("Date", width="small"),
            "Time": st.column_config.TextColumn("Time", width="small"),
            "Image Text": st.column_config.TextColumn("Image Text", width="medium"),
            "Caption": st.column_config.TextColumn("Caption", width="large"),
            "Gemini_Prompt": st.column_config.TextColumn("Gemini_Prompt", width="large"),
            "Status": st.column_config.TextColumn("Status", width="small", disabled=True),
            "Published": st.column_config.TextColumn("Published", width="small", disabled=True),
            "ImageURL": st.column_config.TextColumn("ImageURL", width="small", disabled=True),
            "Image Prompt": st.column_config.TextColumn("Image Prompt", width="small", disabled=True),
            "Post Type": st.column_config.SelectboxColumn("Post Type", width="small", options=["single", "carousel"]),
            "Slide2 Text": st.column_config.TextColumn("Slide2 Text", width="large"),
            "Gancho": st.column_config.TextColumn("Gancho", width="small", disabled=True,
                                                  help=f"Nota do gancho (slide 1), 0-100. Abaixo de {MIN_HOOK_SCORE} é reescrito automaticamente."),
            "Slides": st.column_config.NumberColumn("Slides", width="small", disabled=True),
            "Avisos": st.column_config.TextColumn("Avisos da legenda", width="medium", disabled=True),
        },
        key="content_editor",
    )
    _changes = st.session_state.get("hook_changes") or []
    if _changes:
        with st.expander(f"{len(_changes)} gancho(s) fraco(s) reescrito(s) automaticamente"):
            for c in _changes:
                st.markdown(f"- ~~{c['old']}~~ ({c['old_score']:.0f}) → **{c['new']}** ({c['new_score']:.0f})")
    st.caption("A nota do gancho e os avisos são calculados na geração; não são atualizados quando editas as células.")

    col_act1, col_act2, _ = st.columns([1, 1, 2])
    with col_act1:
        if st.button("Adicionar à base de dados", type="primary", key="add_to_db"):
            try:
                rows = _dataframe_to_posts(edited_df)
                count = append_rows(rows)
                st.success(f"{count} posts adicionados à base de dados!")
                st.session_state["generated_content"] = None
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao gravar na base de dados: {e}")
    with col_act2:
        if st.button("Descartar", key="discard_content"):
            st.session_state["generated_content"] = None
            st.rerun()
