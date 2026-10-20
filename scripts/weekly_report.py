"""
Relatório semanal de métricas do Instagram (só leitura na API).

Compara os últimos 7 dias com os 7 anteriores: alcance, visualizações, gostos, guardados,
partilhas e tempo médio visto nos Reels, por formato, por tipo de Reel (de frase vs slideshow)
e por hora de publicação. Escreve reports/metricas_AAAA-MM-DD.md e imprime o caminho.

Corre: .venv/bin/python scripts/weekly_report.py   [--days 7]
"""
import argparse
import json
import statistics as st
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from instagram_poster.config import IG_GRAPH_API_VERSION, get_ig_access_token, get_ig_business_id  # noqa: E402
from instagram_poster.quote_reel import get_quote_reel_media_ids  # noqa: E402

BASE = f"https://graph.instagram.com/{IG_GRAPH_API_VERSION}"
METRICS = ("reach", "views", "saved", "shares")


def get(path: str, **params):
    params["access_token"] = get_ig_access_token()
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read() or b"{}").get("error", {}).get("message", "")
        except ValueError:
            msg = ""
        return {"error": msg or f"HTTP {e.code}"}


def fetch_media(since: datetime) -> list[dict]:
    ig_id, media, after = get_ig_business_id(), [], None
    while True:
        page = get(f"{ig_id}/media", fields="id,media_type,media_product_type,timestamp,like_count,comments_count,caption,permalink",
                   limit=50, **({"after": after} if after else {}))
        if "error" in page:
            raise SystemExit(f"Erro da API: {page['error']}")
        batch = page.get("data", [])
        media += batch
        after = page.get("paging", {}).get("cursors", {}).get("after")
        if not batch or not page.get("paging", {}).get("next") or _ts(batch[-1]) < since:
            break
    media = [m for m in media if _ts(m) >= since]
    for m in media:
        metrics = ",".join(METRICS) + (",ig_reels_avg_watch_time" if m.get("media_product_type") == "REELS" else "")
        ins = get(f"{m['id']}/insights", metric=metrics)
        m["insights"] = {d["name"]: d["values"][0]["value"] for d in ins.get("data", [])}
    return media


def _ts(m: dict) -> datetime:
    return datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")


def kind(m: dict, quote_ids: set[str]) -> str:
    if m.get("media_product_type") == "REELS":
        return "Reel de frase" if m["id"] in quote_ids else "Reel slideshow/outro"
    return {"CAROUSEL_ALBUM": "Carrossel", "IMAGE": "Imagem"}.get(m["media_type"], m["media_type"])


def summary(items: list[dict]) -> dict:
    def med(f):
        vals = [(m["insights"].get(f) or 0) for m in items]
        return st.median(vals) if vals else 0
    reels = [m["insights"].get("ig_reels_avg_watch_time") for m in items if m["insights"].get("ig_reels_avg_watch_time")]
    return {"n": len(items), "reach": med("reach"), "views": med("views"),
            "likes": st.median([m.get("like_count", 0) for m in items]) if items else 0,
            "saved": sum(m["insights"].get("saved") or 0 for m in items),
            "shares": sum(m["insights"].get("shares") or 0 for m in items),
            "watch": (st.median(reels) / 1000) if reels else None}


def row(label: str, s: dict) -> str:
    watch = f"{s['watch']:.1f} s" if s["watch"] is not None else "—"
    return f"| {label} | {s['n']} | {s['reach']:.0f} | {s['views']:.0f} | {s['likes']:.0f} | {s['saved']} | {s['shares']} | {watch} |"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    cur_start, prev_start = now - timedelta(days=args.days), now - timedelta(days=2 * args.days)
    media = fetch_media(prev_start)
    cur = [m for m in media if _ts(m) >= cur_start]
    prev = [m for m in media if _ts(m) < cur_start]
    quote_ids = get_quote_reel_media_ids()
    profile = get(get_ig_business_id(), fields="followers_count,follows_count,media_count")

    head = "| | Posts | Alcance (mediana) | Visualizações (mediana) | Gostos (mediana) | Guardados (total) | Partilhas (total) | Tempo visto Reels (mediana) |\n|---|---|---|---|---|---|---|---|"
    out = [f"# Métricas Instagram — semana até {now.astimezone():%Y-%m-%d}", "",
           f"Seguidores: **{profile.get('followers_count', '?')}** · a seguir: {profile.get('follows_count', '?')} · "
           f"publicações: {profile.get('media_count', '?')}", "",
           f"## Esta semana vs. semana anterior ({args.days} dias)", "", head,
           row("Esta semana", summary(cur)), row("Semana anterior", summary(prev)), "",
           "## Por formato (esta semana)", "", head]
    by = defaultdict(list)
    for m in cur:
        by[kind(m, quote_ids)].append(m)
    out += [row(k, summary(v)) for k, v in sorted(by.items(), key=lambda kv: -len(kv[1]))]
    out += ["", "## Por hora de publicação (hora de Lisboa, últimas 2 semanas)", "", head]
    hours = defaultdict(list)
    for m in media:
        hours[_ts(m).astimezone().hour].append(m)
    out += [row(f"{h:02d}h", summary(v)) for h, v in sorted(hours.items())]
    out += ["", "## Melhores e piores (esta semana, por alcance)", ""]
    ranked = sorted(cur, key=lambda m: -(m["insights"].get("reach") or 0))
    for label, items in (("Melhores", ranked[:3]), ("Piores", ranked[-3:][::-1] if len(ranked) > 3 else [])):
        if items:
            out.append(f"**{label}**")
            for m in items:
                cap = (m.get("caption") or "").split("\n")[0][:80]
                out.append(f"- {_ts(m).astimezone():%d/%m %Hh} · {kind(m, quote_ids)} · alcance {m['insights'].get('reach', 0)} · "
                           f"gostos {m.get('like_count', 0)} · guardados {m['insights'].get('saved', 0)} · "
                           f"partilhas {m['insights'].get('shares', 0)} — [{cap}]({m.get('permalink', '')})")
            out.append("")
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    path = reports / f"metricas_{now.astimezone():%Y-%m-%d}.md"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
