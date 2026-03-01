"""
Criacao de conteudo para Instagram via IA.
Gera N posts com quote, caption, e prompt de imagem, depois adiciona ao Google Sheet.
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
    get_pollinations_api_key,
)
from instagram_poster.sheets_client import append_rows, get_last_date

logger = logging.getLogger(__name__)


def _get_system_prompt() -> str:
    """Devolve o prompt de sistema a usar: override do ficheiro se existir, senão o padrão."""
    override = get_content_system_prompt_override()
    return override if override else get_default_content_system_prompt()


def _generate_content(
    n: int,
    api_key: str,
    extra_prompt: Optional[str] = None,
) -> list[dict]:
    """Chama a API de texto do Pollinations para gerar N posts."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    system_prompt = _get_system_prompt()
    user_base = f"Generate {n} new content rows as a JSON object with key 'posts' containing an array. Use 'YYYY-MM-DD' for Date. Make all {n} posts with varied micro-themes."
    extra = (extra_prompt or "").strip() or (get_content_extra_prompt() or "").strip()
    if extra:
        user_base += f" Current focus or themes to incorporate in this batch: {extra}"

    payload = {
        "model": "openai",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_base},
        ],
        "response_format": {"type": "json_object"},
    }

    resp = requests.post(
        "https://gen.pollinations.ai/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=180,
    )
    resp.raise_for_status()
    data = resp.json()

    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    posts = parsed.get("posts", parsed.get("rows", []))
    if isinstance(posts, dict):
        posts = [posts]
    return posts


def _posts_to_dataframe(posts: list[dict], start_date: date) -> pd.DataFrame:
    """Converte lista de posts em DataFrame com datas reais."""
    rows = []
    for i, p in enumerate(posts):
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
        })
    return pd.DataFrame(rows)


def _dataframe_to_sheet_rows(df: pd.DataFrame) -> list[list[str]]:
    """Converte DataFrame para lista de listas (ordem das colunas do Sheet)."""
    col_order = ["Date", "Time", "Image Text", "Caption", "Gemini_Prompt",
                 "Status", "Published", "ImageURL", "Image Prompt"]
    result = []
    for _, row in df.iterrows():
        result.append([str(row.get(c, "")) for c in col_order])
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
st.caption("Gera novos posts com IA e adiciona directamente ao Google Sheet.")

# Determinar data inicial (dia seguinte ao ultimo post no Sheet)
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

api_key = get_pollinations_api_key()
if not api_key:
    st.warning("Configura a POLLINATIONS_API_KEY na pagina Configuracao para usar a geracao de conteudo.")

if st.button("Gerar conteudo", type="primary", disabled=not api_key):
    with st.spinner(f"A gerar {n_posts} posts com IA... (pode demorar 30-60s)"):
        try:
            extra = (focus_this_run or "").strip() or None
            posts = _generate_content(n_posts, api_key, extra_prompt=extra)
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
    st.caption("Edita os campos antes de adicionar ao Sheet. Clica numa celula para editar.")

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
        },
        key="content_editor",
    )

    col_act1, col_act2, _ = st.columns([1, 1, 2])
    with col_act1:
        if st.button("Adicionar ao Sheet", type="primary", key="add_to_sheet"):
            try:
                rows = _dataframe_to_sheet_rows(edited_df)
                count = append_rows(rows)
                st.success(f"{count} posts adicionados ao Google Sheet!")
                st.session_state["generated_content"] = None
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao escrever no Sheet: {e}")
    with col_act2:
        if st.button("Descartar", key="discard_content"):
            st.session_state["generated_content"] = None
            st.rerun()
