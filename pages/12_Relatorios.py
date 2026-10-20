"""
Relatórios: métricas do Instagram com comparação entre o período atual e o anterior
(alcance, visualizações, gostos, guardados, partilhas, tempo visto nos Reels), por formato,
por hora de publicação, melhores/piores posts, evolução de seguidores e relatórios semanais guardados.
Os dados vêm da API do Instagram (só leitura) através de scripts/weekly_report.py.
"""
import pandas as pd
import streamlit as st

from instagram_poster.auth import require_auth, render_auth_sidebar

st.set_page_config(page_title="Relatórios | Instagram Auto Post", page_icon="📊", layout="wide")
require_auth()
with st.sidebar:
    render_auth_sidebar()

from scripts import weekly_report as wr  # noqa: E402

st.title("Relatórios")
st.caption("Métricas da conta, com comparação entre o período escolhido e o período anterior com a mesma duração.")

c1, c2, _ = st.columns([1, 1, 3])
days = c1.selectbox("Período", [7, 14, 30], index=0, format_func=lambda d: f"Últimos {d} dias")
if c2.button("Atualizar dados", help="Volta a pedir as métricas ao Instagram (os dados ficam em cache 1 hora)."):
    st.cache_data.clear()


@st.cache_data(ttl=3600, show_spinner="A pedir as métricas ao Instagram…")
def load(d: int) -> dict:
    return wr.collect(d)


try:
    data = load(days)
except Exception as e:  # token expirado, rede, limite da API
    st.error(f"Não foi possível obter as métricas: {e}")
    st.stop()

cur, prev, profile = data["summary_cur"], data["summary_prev"], data["profile"]
st.caption(f"Atualizado: {data['now'].astimezone():%d/%m/%Y %H:%M} · período atual: {cur['n']} publicações · "
           f"período anterior: {prev['n']} publicações")


def delta(a, b, pct=True):
    if a is None or b is None or not prev["n"]:  # sem publicações no período anterior não há comparação
        return None
    if pct and b:
        return f"{(a - b) / b * 100:+.0f}%"
    return f"{a - b:+.1f}" if isinstance(a, float) and not float(a).is_integer() else f"{a - b:+.0f}"


# --- Comparação principal ---
st.subheader("Este período vs. anterior")
hist = data["history"]
prev_followers = next((h["followers"] for h in reversed(hist[:-1])), None) if len(hist) > 1 else None
cols = st.columns(7)
cols[0].metric("Seguidores", profile.get("followers_count", "—"),
               f"{profile['followers_count'] - prev_followers:+d}" if prev_followers is not None and "followers_count" in profile else None,
               help="Comparado com o último registo guardado num dia anterior.")
cols[1].metric("Alcance (mediana)", f"{cur['reach']:.0f}", delta(cur["reach"], prev["reach"]))
cols[2].metric("Visualizações (mediana)", f"{cur['views']:.0f}", delta(cur["views"], prev["views"]))
cols[3].metric("Gostos (mediana)", f"{cur['likes']:.0f}", delta(cur["likes"], prev["likes"], pct=False))
cols[4].metric("Guardados", cur["saved"], delta(cur["saved"], prev["saved"], pct=False))
cols[5].metric("Partilhas", cur["shares"], delta(cur["shares"], prev["shares"], pct=False))
cols[6].metric("Tempo visto Reels", f"{cur['watch']:.1f} s" if cur["watch"] is not None else "—",
               delta(cur["watch"], prev["watch"], pct=False) if cur["watch"] is not None and prev["watch"] is not None else None)
st.caption("Medianas por publicação; guardados e partilhas são totais do período. Os guardados e as partilhas são "
           "os sinais que mais ajudam a chegar a quem ainda não segue a conta.")


def table(rows: dict[str, dict], label: str) -> pd.DataFrame:
    df = pd.DataFrame([{label: k, "Publicações": s["n"], "Alcance (med.)": round(s["reach"]), "Visualizações (med.)": round(s["views"]),
                        "Gostos (med.)": s["likes"], "Guardados": s["saved"], "Partilhas": s["shares"],
                        "Tempo visto (s)": round(s["watch"], 1) if s["watch"] is not None else None}
                       for k, s in rows.items()])
    return df


# --- Por formato ---
st.subheader("Por formato")
fmt_rows = []
for k, v in sorted(data["by_kind"].items(), key=lambda kv: -(kv[1]["cur"]["n"] + kv[1]["prev"]["n"])):
    a, b = v["cur"], v["prev"]
    fmt_rows.append({"Formato": k, "Publicações (atual)": a["n"], "Publicações (anterior)": b["n"],
                     "Alcance med. (atual)": round(a["reach"]), "Alcance med. (anterior)": round(b["reach"]),
                     "Variação alcance": delta(a["reach"], b["reach"]) if b["n"] else "—",
                     "Guardados (atual)": a["saved"], "Partilhas (atual)": a["shares"],
                     "Tempo visto (s, atual)": round(a["watch"], 1) if a["watch"] is not None else None})
if fmt_rows:
    df = pd.DataFrame(fmt_rows)
    st.dataframe(df, hide_index=True, width="stretch")
    st.bar_chart(df.set_index("Formato")[["Alcance med. (atual)", "Alcance med. (anterior)"]])
else:
    st.info("Sem publicações nos dois períodos.")

# --- Por hora ---
st.subheader("Por hora de publicação (hora de Lisboa, os dois períodos)")
if data["by_hour"]:
    dfh = table({f"{h:02d}h": s for h, s in data["by_hour"].items()}, "Hora")
    st.dataframe(dfh, hide_index=True, width="stretch")
    st.bar_chart(dfh.set_index("Hora")[["Alcance (med.)"]])

# --- Melhores e piores ---
st.subheader("Publicações do período")
ranked = data["ranked"]
if ranked:
    dfp = pd.DataFrame([{"Data": m["local_time"].strftime("%d/%m %H:%M"), "Formato": m["kind"],
                         "Alcance": m["insights"].get("reach", 0), "Visualizações": m["insights"].get("views", 0),
                         "Gostos": m.get("like_count", 0), "Guardados": m["insights"].get("saved", 0),
                         "Partilhas": m["insights"].get("shares", 0),
                         "Frase": (m.get("caption") or "").split("\n")[0][:90], "Link": m.get("permalink", "")}
                        for m in ranked])
    st.dataframe(dfp, hide_index=True, width="stretch",
                 column_config={"Link": st.column_config.LinkColumn("Link", display_text="abrir")})

# --- Evolução de seguidores ---
st.subheader("Evolução de seguidores")
if len(hist) > 1:
    dfs = pd.DataFrame(hist).set_index("date")[["followers"]].rename(columns={"followers": "Seguidores"})
    st.line_chart(dfs)
else:
    st.caption("O gráfico aparece quando houver registos de mais de um dia (um por dia, com o relatório semanal "
               "ou ao abrir esta página).")

# --- Relatórios semanais guardados ---
st.subheader("Relatórios semanais")
colr1, colr2 = st.columns([1, 3])
if colr1.button("Gerar relatório agora", help="Escreve o ficheiro em reports/ com os dados mostrados acima."):
    path = wr.write_report(data)
    colr2.success(f"Relatório guardado: {path.name}")
reports = wr.list_reports()
if reports:
    choice = st.selectbox("Abrir relatório", reports, format_func=lambda p: p.stem.replace("metricas_", "Semana até "))
    with st.expander(choice.name, expanded=False):
        st.markdown(choice.read_text(encoding="utf-8"))
    st.download_button("Descarregar", choice.read_bytes(), file_name=choice.name, mime="text/markdown")
else:
    st.caption("Ainda não há relatórios guardados. O cron gera um todas as segundas às 9h.")
