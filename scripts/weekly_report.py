"""
Relatório de métricas do Instagram (só leitura na API).

Compara o período atual (por omissão 7 dias) com o anterior: alcance, visualizações, gostos,
guardados, partilhas e tempo médio visto nos Reels, por formato, por tipo de Reel (de frase vs
slideshow) e por hora de publicação. Guarda também o número de seguidores em
reports/historico.json para ver a evolução.

- CLI / cron: escreve reports/metricas_AAAA-MM-DD.md e imprime o caminho.
      .venv/bin/python scripts/weekly_report.py [--days 7]
- App: a página "Relatórios" usa collect() e as funções de resumo deste módulo.
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
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from instagram_poster.config import IG_GRAPH_API_VERSION, get_ig_access_token, get_ig_business_id  # noqa: E402
from instagram_poster.quote_reel import get_quote_reel_media_ids  # noqa: E402

BASE = f"https://graph.instagram.com/{IG_GRAPH_API_VERSION}"
METRICS = ("reach", "views", "saved", "shares")
REPORTS_DIR = ROOT / "reports"
HISTORY_FILE = REPORTS_DIR / "historico.json"


def get(path: str, **params) -> dict:
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


def ts(m: dict) -> datetime:
    return datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")


def fetch_media(since: datetime) -> list[dict]:
    ig_id, media, after = get_ig_business_id(), [], None
    while True:
        page = get(f"{ig_id}/media", fields="id,media_type,media_product_type,timestamp,like_count,comments_count,caption,permalink",
                   limit=50, **({"after": after} if after else {}))
        if "error" in page:
            raise RuntimeError(f"Erro da API do Instagram: {page['error']}")
        batch = page.get("data", [])
        media += batch
        after = page.get("paging", {}).get("cursors", {}).get("after")
        if not batch or not page.get("paging", {}).get("next") or ts(batch[-1]) < since:
            break
    media = [m for m in media if ts(m) >= since]
    for m in media:
        metrics = ",".join(METRICS) + (",ig_reels_avg_watch_time" if m.get("media_product_type") == "REELS" else "")
        ins = get(f"{m['id']}/insights", metric=metrics)
        m["insights"] = {d["name"]: d["values"][0]["value"] for d in ins.get("data", [])}
    return media


def kind(m: dict, quote_ids: set[str]) -> str:
    if m.get("media_product_type") == "REELS":
        return "Reel de frase" if m["id"] in quote_ids else "Reel slideshow/outro"
    return {"CAROUSEL_ALBUM": "Carrossel", "IMAGE": "Imagem"}.get(m["media_type"], m["media_type"])


def summary(items: list[dict]) -> dict[str, Any]:
    def med(f):
        vals = [(m["insights"].get(f) or 0) for m in items]
        return st.median(vals) if vals else 0
    watch = [m["insights"].get("ig_reels_avg_watch_time") for m in items if m["insights"].get("ig_reels_avg_watch_time")]
    return {"n": len(items), "reach": med("reach"), "views": med("views"),
            "likes": st.median([m.get("like_count", 0) for m in items]) if items else 0,
            "saved": sum(m["insights"].get("saved") or 0 for m in items),
            "shares": sum(m["insights"].get("shares") or 0 for m in items),
            "watch": (st.median(watch) / 1000) if watch else None}


def record_followers(profile: dict) -> list[dict]:
    """Acrescenta (no máximo uma vez por dia) os seguidores a reports/historico.json e devolve o histórico."""
    try:
        hist = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        hist = []
    if "followers_count" in profile:
        today = datetime.now().date().isoformat()
        hist = [h for h in hist if h.get("date") != today]
        hist.append({"date": today, "followers": profile["followers_count"], "follows": profile.get("follows_count")})
        hist.sort(key=lambda h: h["date"])
        REPORTS_DIR.mkdir(exist_ok=True)
        tmp = HISTORY_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(hist, indent=1), encoding="utf-8")
        tmp.replace(HISTORY_FILE)
    return hist


def collect(days: int = 7) -> dict[str, Any]:
    """Recolhe tudo o que o relatório e a página precisam para o período atual e o anterior."""
    now = datetime.now(timezone.utc)
    cur_start, prev_start = now - timedelta(days=days), now - timedelta(days=2 * days)
    media = fetch_media(prev_start)
    quote_ids = get_quote_reel_media_ids()
    for m in media:
        m["kind"] = kind(m, quote_ids)
        m["local_time"] = ts(m).astimezone()
    cur = [m for m in media if ts(m) >= cur_start]
    prev = [m for m in media if ts(m) < cur_start]
    profile = get(get_ig_business_id(), fields="followers_count,follows_count,media_count")
    by_kind: dict[str, dict[str, list]] = defaultdict(lambda: {"cur": [], "prev": []})
    for m in cur:
        by_kind[m["kind"]]["cur"].append(m)
    for m in prev:
        by_kind[m["kind"]]["prev"].append(m)
    hours = defaultdict(list)
    for m in media:
        hours[m["local_time"].hour].append(m)
    return {"now": now, "days": days, "profile": profile, "cur": cur, "prev": prev,
            "summary_cur": summary(cur), "summary_prev": summary(prev),
            "by_kind": {k: {"cur": summary(v["cur"]), "prev": summary(v["prev"])} for k, v in by_kind.items()},
            "by_hour": {h: summary(v) for h, v in sorted(hours.items())},
            "ranked": sorted(cur, key=lambda m: -(m["insights"].get("reach") or 0)),
            "history": record_followers(profile)}


def _row(label: str, s: dict) -> str:
    watch = f"{s['watch']:.1f} s" if s["watch"] is not None else "—"
    return f"| {label} | {s['n']} | {s['reach']:.0f} | {s['views']:.0f} | {s['likes']:.0f} | {s['saved']} | {s['shares']} | {watch} |"


def to_markdown(data: dict[str, Any]) -> str:
    p, days = data["profile"], data["days"]
    head = ("| | Posts | Alcance (mediana) | Visualizações (mediana) | Gostos (mediana) | Guardados (total) | "
            "Partilhas (total) | Tempo visto Reels (mediana) |\n|---|---|---|---|---|---|---|---|")
    out = [f"# Métricas Instagram — {days} dias até {data['now'].astimezone():%Y-%m-%d}", "",
           f"Seguidores: **{p.get('followers_count', '?')}** · a seguir: {p.get('follows_count', '?')} · "
           f"publicações: {p.get('media_count', '?')}", "",
           f"## Este período vs. anterior ({days} dias)", "", head,
           _row("Este período", data["summary_cur"]), _row("Período anterior", data["summary_prev"]), "",
           "## Por formato (este período)", "", head]
    out += [_row(k, v["cur"]) for k, v in sorted(data["by_kind"].items(), key=lambda kv: -kv[1]["cur"]["n"]) if v["cur"]["n"]]
    out += ["", "## Por hora de publicação (hora de Lisboa, os dois períodos)", "", head]
    out += [_row(f"{h:02d}h", s) for h, s in data["by_hour"].items()]
    out += ["", "## Melhores e piores (este período, por alcance)", ""]
    ranked = data["ranked"]
    for label, items in (("Melhores", ranked[:3]), ("Piores", ranked[-3:][::-1] if len(ranked) > 3 else [])):
        if items:
            out.append(f"**{label}**")
            for m in items:
                cap = (m.get("caption") or "").split("\n")[0][:80]
                out.append(f"- {m['local_time']:%d/%m %Hh} · {m['kind']} · alcance {m['insights'].get('reach', 0)} · "
                           f"gostos {m.get('like_count', 0)} · guardados {m['insights'].get('saved', 0)} · "
                           f"partilhas {m['insights'].get('shares', 0)} — [{cap}]({m.get('permalink', '')})")
            out.append("")
    return "\n".join(out) + "\n"


def write_report(data: dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"metricas_{data['now'].astimezone():%Y-%m-%d}.md"
    path.write_text(to_markdown(data), encoding="utf-8")
    return path


def list_reports() -> list[Path]:
    return sorted(REPORTS_DIR.glob("metricas_*.md"), reverse=True)


def main(argv: Optional[list[str]] = None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args(argv)
    print(write_report(collect(args.days)))


if __name__ == "__main__":
    main()
