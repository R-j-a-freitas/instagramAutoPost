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

from instagram_poster import config
from instagram_poster.config import get_pollinations_api_key
from instagram_poster.sheets_client import append_rows, get_last_date

logger = logging.getLogger(__name__)

_CONTENT_SYSTEM_PROMPT = r"""You are a content creator for the Instagram account @keepcalmnbepositive.

## Account context

- Niche: personal development, positive mindset, self-compassion, emotional healing, healthy boundaries, rest, slow growth.
- Tone: calm, encouraging, practical. No toxic positivity, no aggressive "hustle" culture.
- Goal: help people think and feel in a kinder, more conscious and responsible way, without guilt or unrealistic demands.

## Google Sheet structure

Each row has these columns (fixed order):

1. Date – post date (YYYY-MM-DD)
2. Time – post time (HH:MM)
3. Image Text – the short quote/phrase that will be overlaid on the image
4. Caption – the post caption in English, a mini-text/reflection with 2-6 short paragraphs
5. Gemini_Prompt – technical prompt to generate the background image, in English, describing what the image should show (NO text in the image)
6. Status – always "ready"
7. Published – always empty string
8. ImageURL – always empty string
9. Image Prompt – always "yes"

## Rules for each field

### Date and Time
- For Date use literally the placeholder "YYYY-MM-DD" (will be filled later).
- For Time always use "21:30".

### Image Text (quote)
- Short, strong phrase that stands on its own.
- In simple English, first person, aligned with the account style.
- Style examples (do NOT repeat these, only use as reference):
  - "Today I focus on what I can do, not on what I can't control."
  - "Resting is not losing time. Resting prepares me for the time ahead."
  - "I give myself permission to grow at my own pace."
- Avoid empty cliches like "good vibes only", "think positive".
- Each quote should focus on a concrete micro-theme (self-talk, boundaries, rest, gratitude, anxiety, etc.).

### Caption
- Text in English, 2-6 short paragraphs.
- Typical structure:
  - 1-2 sentences expanding the quote idea.
  - Practical explanation of the concept.
  - 1 small exercise/action for today (e.g., "Today, try...", "Write down...", "Notice when...").
  - 0-2 relevant hashtags at the end (ideally include #keepcalmnbepositive).
- Style: direct conversation with the reader ("you", "your mind", "your body"). Gentle but honest.

### Gemini_Prompt (for image generation)
- Written in English.
- Describes a concrete image that matches the quote and caption.
- IMPORTANT rules:
  - Do NOT include any text, letters, or words in the image.
  - Mention: main scene, environment, color palette, emotion/mood.
  - If there are people: no close-up faces; can be from behind, silhouette, or distant.
- Example style (do NOT copy, only reference for detail level):
  - "Serene breathing moment: a person sitting near a window with plants, hands resting gently on their chest. Soft blue and green tones, lots of calm space. No text in the image."

### Status, Published, ImageURL, Image Prompt
- Status: always "ready"
- Published: always ""
- ImageURL: always ""
- Image Prompt: always "yes"

## Output format

Return a JSON object with a single key "posts" containing an array of objects.
Each object must have exactly these keys: "Date", "Time", "Image Text", "Caption", "Gemini_Prompt", "Status", "Published", "ImageURL", "Image Prompt".

Vary the micro-themes across posts. Be creative but stay consistent with @keepcalmnbepositive style."""


def _generate_content(n: int, api_key: str) -> list[dict]:
    """Chama a API de texto do Pollinations para gerar N posts."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": "openai",
        "messages": [
            {"role": "system", "content": _CONTENT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Generate {n} new content rows as a JSON object with key 'posts' containing an array. Use 'YYYY-MM-DD' for Date. Make all {n} posts with varied micro-themes."},
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

api_key = get_pollinations_api_key()
if not api_key:
    st.warning("Configura a POLLINATIONS_API_KEY na pagina Configuracao para usar a geracao de conteudo.")

if st.button("Gerar conteudo", type="primary", disabled=not api_key):
    with st.spinner(f"A gerar {n_posts} posts com IA... (pode demorar 30-60s)"):
        try:
            posts = _generate_content(n_posts, api_key)
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
