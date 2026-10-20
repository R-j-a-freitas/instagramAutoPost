"""
Base de Dados: ver e editar directamente a tabela de posts (posts.db) num grid tipo folha
de cálculo. Permite editar células, apagar linhas e adicionar novas linhas.
"""
import pandas as pd
import streamlit as st

from instagram_poster.auth import require_auth, render_auth_sidebar
from instagram_poster.db import append_rows, delete_post, get_all_posts, update_post

st.set_page_config(page_title="Base de Dados | Instagram Auto Post", page_icon="🗄️", layout="wide")
require_auth()
with st.sidebar:
    render_auth_sidebar()

nav1, nav2, nav3, _ = st.columns([1, 1, 1, 3])
with nav1:
    if st.button("← Início", key="nav_home_db"):
        st.switch_page("app.py")
with nav2:
    if st.button("⚙️ Configuração", key="nav_cfg_db"):
        st.switch_page("pages/1_Configuracao.py")
with nav3:
    if st.button("📸 Posts", key="nav_posts_db"):
        st.switch_page("pages/2_Posts.py")

st.title("Base de Dados")
st.caption("Vê e edita directamente a tabela `posts` da base de dados interna (posts.db).")

_DB_COLUMNS = [
    "row_index", "date", "time", "image_text", "caption", "gemini_prompt",
    "status", "published", "image_url", "image_prompt", "post_type", "slide2_text",
]
_COLUMN_LABELS = {
    "row_index": "ID",
    "date": "Date",
    "time": "Time",
    "image_text": "Image Text",
    "caption": "Caption",
    "gemini_prompt": "Gemini_Prompt",
    "status": "Status",
    "published": "Published",
    "image_url": "ImageURL",
    "image_prompt": "Image Prompt",
    "post_type": "Post Type",
    "slide2_text": "Slide2 Text",
}


def _load_df() -> pd.DataFrame:
    posts = get_all_posts()
    if not posts:
        return pd.DataFrame(columns=_DB_COLUMNS)
    df = pd.DataFrame(posts)[_DB_COLUMNS]
    df["row_index"] = df["row_index"].astype("Int64")
    return df


if "db_editor_original" not in st.session_state:
    st.session_state.db_editor_original = _load_df()

original_df = st.session_state.db_editor_original
st.metric("Total de linhas", len(original_df))

st.caption(
    "Edita células directamente na tabela. Usa o ícone 🗑️ no fim da linha para marcar para apagar, "
    "ou a linha em branco no fundo para adicionar um post novo. As alterações só são aplicadas à "
    "base de dados depois de clicares em **Guardar alterações**."
)

edited_df = st.data_editor(
    original_df,
    use_container_width=True,
    num_rows="dynamic",
    height=600,
    key="db_editor",
    column_config={
        "row_index": st.column_config.NumberColumn(_COLUMN_LABELS["row_index"], disabled=True, width="small"),
        "date": st.column_config.TextColumn(_COLUMN_LABELS["date"], width="small"),
        "time": st.column_config.TextColumn(_COLUMN_LABELS["time"], width="small"),
        "image_text": st.column_config.TextColumn(_COLUMN_LABELS["image_text"], width="medium"),
        "caption": st.column_config.TextColumn(_COLUMN_LABELS["caption"], width="large"),
        "gemini_prompt": st.column_config.TextColumn(_COLUMN_LABELS["gemini_prompt"], width="large"),
        "status": st.column_config.TextColumn(_COLUMN_LABELS["status"], width="small"),
        "published": st.column_config.SelectboxColumn(_COLUMN_LABELS["published"], options=["", "yes"], width="small"),
        "image_url": st.column_config.TextColumn(_COLUMN_LABELS["image_url"], width="medium"),
        "image_prompt": st.column_config.TextColumn(_COLUMN_LABELS["image_prompt"], width="small"),
        "post_type": st.column_config.SelectboxColumn(_COLUMN_LABELS["post_type"], options=["single", "carousel"], width="small"),
        "slide2_text": st.column_config.TextColumn(_COLUMN_LABELS["slide2_text"], width="large"),
    },
)

# --- Calcular alterações pendentes (comparação com a versão original carregada) ---
original_indexed = original_df.set_index("row_index")
original_ids = set(int(i) for i in original_df["row_index"].dropna().tolist())
edited_ids = set(int(i) for i in edited_df["row_index"].dropna().tolist())

deleted_ids = sorted(original_ids - edited_ids)
new_rows = edited_df[edited_df["row_index"].isna()]

changed: dict[int, dict] = {}
for _, row in edited_df.iterrows():
    rid = row.get("row_index")
    if pd.isna(rid):
        continue
    rid = int(rid)
    if rid not in original_indexed.index:
        continue
    orig_row = original_indexed.loc[rid]
    diff = {
        col: row[col]
        for col in _DB_COLUMNS
        if col != "row_index" and str(row.get(col) or "") != str(orig_row.get(col) or "")
    }
    if diff:
        changed[rid] = diff

n_new, n_changed, n_deleted = len(new_rows), len(changed), len(deleted_ids)
if n_new or n_changed or n_deleted:
    st.info(f"Alterações pendentes: {n_new} novo(s), {n_changed} editado(s), {n_deleted} para apagar.")

    confirm = st.checkbox("Confirmo que quero aplicar estas alterações à base de dados.")
    if st.button("💾 Guardar alterações", type="primary", disabled=not confirm):
        try:
            for rid, fields in changed.items():
                update_post(rid, fields)
            for rid in deleted_ids:
                delete_post(rid)
            if len(new_rows):
                payload = [
                    {col: str(row.get(col) or "") for col in _DB_COLUMNS if col != "row_index"}
                    for _, row in new_rows.iterrows()
                ]
                append_rows(payload)
            st.session_state.db_editor_original = _load_df()
            st.session_state.pop("db_editor", None)
            st.success(f"Guardado: {n_changed} editado(s), {n_deleted} apagado(s), {n_new} novo(s).")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao guardar alterações: {e}")
else:
    st.caption("Sem alterações pendentes.")

if st.button("🔄 Recarregar da base de dados"):
    st.session_state.db_editor_original = _load_df()
    st.session_state.pop("db_editor", None)
    st.rerun()
