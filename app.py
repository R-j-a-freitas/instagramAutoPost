"""
App Streamlit para automatizar posts no Instagram.
- Ver próximos posts planeados (a partir de hoje).
- Publicar manualmente um post ("Post selected row") ou o próximo ("Post next").
"""
import streamlit as st
from datetime import date, datetime

from instagram_poster.scheduler import run_publish_next, run_publish_row
from instagram_poster.sheets_client import get_upcoming_posts

# Estado leve da última publicação
if "last_publish_result" not in st.session_state:
    st.session_state.last_publish_result = None  # (success: bool, message: str, media_id: str | None)


def main():
    st.set_page_config(page_title="Instagram Auto Post", page_icon="📸", layout="wide")
    st.title("Instagram Auto Post")
    st.caption("Publicação via Instagram Graph API + Google Sheet")

    try:
        # Próximos posts (7–14 dias)
        n_posts = st.sidebar.slider("N.º de posts a mostrar", min_value=7, max_value=21, value=14)
        from_date = date.today()
        posts = get_upcoming_posts(n=n_posts, from_date=from_date)
    except Exception as e:
        st.error(f"Erro ao ler o Google Sheet: {e}")
        st.info("Verifica GOOGLE_SERVICE_ACCOUNT_JSON e IG_SHEET_ID no .env e se o Sheet está partilhado com o email da service account.")
        return

    if not posts:
        st.warning("Nenhum post encontrado a partir de hoje no Sheet.")
        return

    # Tabela: Data, Hora, Image Text, Preview Caption, Published/Status
    st.subheader("Próximos posts")
    table_data = []
    for p in posts:
        caption_preview = (p.get("caption") or "")[:80]
        if len(p.get("caption") or "") > 80:
            caption_preview += "..."
        table_data.append({
            "Linha": p.get("row_index"),
            "Data": p.get("date", ""),
            "Hora": p.get("time", ""),
            "Image Text": (p.get("image_text") or "")[:50] + ("..." if len(p.get("image_text") or "") > 50 else ""),
            "Caption (preview)": caption_preview,
            "Status": p.get("status", ""),
            "Published": p.get("published", ""),
        })
    st.dataframe(table_data, use_container_width=True, hide_index=True)

    # Detalhes da linha selecionada
    st.subheader("Publicar")
    row_options = [f"Linha {p['row_index']} — {p.get('date')} {p.get('time')} — {(p.get('image_text') or '')[:40]}..." for p in posts]
    row_values = [p["row_index"] for p in posts]
    selected_label = st.selectbox(
        "Escolhe a linha para publicar (Post selected row):",
        options=row_options,
        index=0,
    )
    selected_row_index = row_values[row_options.index(selected_label)] if selected_label else row_values[0]

    col1, col2, _ = st.columns([1, 1, 2])
    with col1:
        if st.button("Post next", type="primary"):
            success, message, media_id = run_publish_next(today=date.today(), now=datetime.now().time())
            st.session_state.last_publish_result = (success, message, media_id)
            st.rerun()
    with col2:
        if st.button("Post selected row"):
            success, message, media_id = run_publish_row(selected_row_index)
            st.session_state.last_publish_result = (success, message, media_id)
            st.rerun()

    # Mostrar resultado da última publicação (persistido no session_state)
    if st.session_state.last_publish_result:
        success, message, media_id = st.session_state.last_publish_result
        if success:
            st.success(f"Última ação: {message}")
        else:
            st.error(f"Última ação: {message}")

    # Detalhes do post selecionado (expandível)
    with st.expander("Ver detalhes do post selecionado"):
        detail = next((p for p in posts if p["row_index"] == selected_row_index), None)
        if detail:
            st.write("**Image Text:**", detail.get("image_text") or "(vazio)")
            st.write("**Caption:**", detail.get("caption") or "(vazio)")
            st.write("**ImageURL:**", detail.get("image_url") or "(vazio — preenche no Sheet para publicar)")
            st.write("**Status:**", detail.get("status"), "| **Published:**", detail.get("published"))


if __name__ == "__main__":
    main()
