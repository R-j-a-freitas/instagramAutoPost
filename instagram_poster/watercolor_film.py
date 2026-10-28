"""
Filme aguarela: Reel vertical de ~40 s feito em código (Lemo-Opuscar, estilo watercolor) a partir de um post.

História fixa, texto do post: uma página cheia de sentimentos → a névoa apaga tudo menos um → a pessoa a quem ele
pertence → três coisas que acalmam → uma nota por acabar e o título. Modelo em assets/watercolor_film/.

- draft_script(post): guião (falas, notas, 3 objetos, título) escrito pelo modelo de texto da app, editável na página.
- start_build(script, name): cria a pasta do filme em Video/saida/filmes/ e corre o build num processo à parte.
- job_status(job_dir): estado lido de status.json (a página consulta-o).
Uso direto: python -m instagram_poster.watercolor_film <pasta do filme>
Precisa da biblioteca Lemo-Opuscar (WATERCOLOR_FILM_LIB, por defeito /mnt/storage/repos/lemo-opuscar) com
`deps`, `deps voice` e a biblioteca de sons freepats, e de node + ffmpeg no PATH.
"""
import fcntl
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

APP_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = APP_ROOT / "assets" / "watercolor_film"
LIB = Path(os.getenv("WATERCOLOR_FILM_LIB", "/mnt/storage/repos/lemo-opuscar"))
FILMS_DIR = Path("/DATA/shares/workspace/Video/saida/filmes")
LOCK_FILE = FILMS_DIR / ".build.lock"
ICONS = ["breath", "cup", "song", "sprout", "sun", "book"]
ICON_NAMES = {"breath": "respiração (onda)", "cup": "chávena com vapor", "song": "notas de música",
              "sprout": "rebento", "sun": "sol", "book": "livro aberto"}
HANDLE = "@keepcalmnbepositive"
VOICE = "af_heart"
TEMPLATE_FILES = ["index.html", "engine.js", "main.js", "mix.py", "fonts.css", "paper.jpg"]

DEFAULT_SCRIPT = {
    "l1": "", "l2": "", "l3": "",
    "l4": "Pick one feeling. Notice where it lives in your body.",
    "l5_lead": "Then give it something steady.",
    "items": [{"label": "slow breath", "icon": "breath"}, {"label": "warm water", "icon": "cup"},
              {"label": "a song", "icon": "song"}],
    "l6": "Insight can wait for a calmer day.",
    "notes": ["why?", "fix it", "understand it", "now", "still?", "what does it mean?", "again", "solve it",
              "all of it", "today"],
    "here": "here", "later": "insight: later", "title": "One feeling at a time.",
}

_SYSTEM = """You write the script for a 40-second hand-painted watercolor Reel for the Instagram account @keepcalmnbepositive
(mindset, self-compassion, slow growth). The film's story is FIXED, only the words change:
1) a journal page fills with colour blots (feelings) and anxious hand-written notes; the narrator states the post's hook and the trap;
2) a mist erases everything except ONE feeling; it settles in a person's chest;
3) three small grounding things are painted next to the person;
4) an unfinished hand-written note and the title close the film.

Return ONLY a JSON object with these keys (English, warm, plain, no clichés, no em dashes, no hashtags, no emoji):
- "l1": the hook, max 10 words (close to the post's headline)
- "l2": max 11 words, why the struggle happens
- "l3": max 11 words, the trap that makes it heavier
- "l4": max 11 words, invite the viewer to pick one thing and notice it
- "l5_lead": max 6 words, leads into the three things (e.g. "Then give it something steady.")
- "items": exactly 3 objects {"label": 1-3 words, lowercase, "icon": one of breath, cup, song, sprout, sun, book}; the label is spoken, so it must match the icon (e.g. "slow breath"/breath, "warm tea"/cup, "a song"/song, "one small step"/sprout, "morning light"/sun, "a few pages"/book)
- "l6": max 9 words, a gentle closing line
- "notes": exactly 10 anxious inner thoughts, 1-4 words each, lowercase, varied (e.g. "why?", "fix it", "not again")
- "here": 1-2 words written next to the feeling in the chest (e.g. "here", "right here")
- "later": max 18 characters, a calm hand-written note (e.g. "insight: later", "rest first")
- "title": max 26 characters, the film's title, ending with a full stop."""


# ---------------------------------------------------------------- script

def _clip_words(s: str, n: int) -> str:
    w = str(s or "").replace("—", ",").replace("–", ",").split()
    return " ".join(w[:n]).strip()


def _sentences(text: str) -> list[str]:
    text = re.sub(r"#\S+", "", text or "")
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip().split()) >= 3]


def fallback_script(post: dict[str, Any]) -> dict[str, Any]:
    """Guião sem IA: frase do post + duas frases da legenda + o resto do modelo."""
    s = json.loads(json.dumps(DEFAULT_SCRIPT))
    sents = _sentences(post.get("caption", "")) + _sentences(post.get("slide2_text", ""))
    s["l1"] = _clip_words(post.get("image_text", ""), 12) or "You don't have to carry it all at once."
    s["l2"] = _clip_words(sents[0], 12) if sents else "Some feelings need time to settle."
    s["l3"] = _clip_words(sents[1], 12) if len(sents) > 1 else "Rushing them only makes them heavier."
    title = re.sub(r"[\"“”]", "", post.get("image_text", "")).split(".")[0].strip()
    if title and len(title) <= 26:
        s["title"] = title + "."
    return s


def normalize_script(s: dict[str, Any]) -> dict[str, Any]:
    """Aplica limites e valores por defeito, para o build nunca receber um guião partido."""
    out = json.loads(json.dumps(DEFAULT_SCRIPT))
    for k, n in [("l1", 12), ("l2", 13), ("l3", 13), ("l4", 13), ("l5_lead", 7), ("l6", 11)]:
        v = _clip_words(s.get(k, ""), n)
        if v:
            v = v[:1].upper() + v[1:]
            out[k] = v if v[-1] in ".!?" else v + "."
    items = [it for it in (s.get("items") or []) if isinstance(it, dict) and str(it.get("label", "")).strip()][:3]
    for i, it in enumerate(items):
        icon = it.get("icon") if it.get("icon") in ICONS else DEFAULT_SCRIPT["items"][i]["icon"]
        out["items"][i] = {"label": _clip_words(it["label"], 3).lower().strip(".,"), "icon": icon}
    notes = [_clip_words(n, 4).lower() for n in (s.get("notes") or []) if str(n).strip()]
    out["notes"] = (notes + DEFAULT_SCRIPT["notes"])[:10]
    for k, n in [("here", 16), ("later", 20), ("title", 30)]:
        v = re.sub(r"\s+", " ", str(s.get(k, "") or "")).strip()
        if len(v) > n:
            v = v[:n].rsplit(" ", 1)[0].rstrip(",;:")
        if v:
            out[k] = v
    if out["title"][-1] not in ".!?":
        out["title"] += "."
    return out


def draft_script(post: dict[str, Any]) -> dict[str, Any]:
    """Guião a partir do post (modelo de texto da app); se falhar, o guião sem IA."""
    from instagram_poster.text_generator import generate_text
    user = (f"Post headline: {post.get('image_text', '')}\n\nCaption: {post.get('caption', '')}\n\n"
            f"Carousel text: {post.get('slide2_text', '')}")
    try:
        raw = generate_text(_SYSTEM, user, json_mode=True)
        m = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(m.group(0) if m else raw)
        if not data.get("l1"):
            raise ValueError("guião sem l1")
        return normalize_script(data)
    except Exception as e:
        logger.warning("Filme aguarela: guião por IA falhou (%s); a usar o guião simples.", e)
        return normalize_script(fallback_script(post))


def spoken_lines(s: dict[str, Any]) -> dict[str, str]:
    labels = [it["label"] for it in s["items"]]
    l5 = s["l5_lead"].rstrip(".") + ". " + " ".join(lab[:1].upper() + lab[1:] + "." for lab in labels)
    return {"l1": s["l1"], "l2": s["l2"], "l3": s["l3"], "l4": s["l4"], "l5": l5, "l6": s["l6"]}


# ---------------------------------------------------------------- timeline

def _word_time(words: list, label: str, after: float) -> Optional[float]:
    first = re.sub(r"[^a-z']", "", label.split()[0].lower())
    for w, t0, _ in words:
        if t0 >= after and re.sub(r"[^a-z']", "", w.lower()) == first:
            return t0
    return None


def timeline(s: dict[str, Any], dur: dict[str, float], words: dict[str, list]) -> dict[str, Any]:
    """Todos os tempos do filme a partir das durações da voz (o mesmo desenho do filme original)."""
    L = {}
    L["l1"] = .5
    L["l2"] = L["l1"] + dur["l1"] + 1.7
    L["l3"] = L["l2"] + dur["l2"] + .55
    TA = L["l3"] + dur["l3"] + .35                       # the brush lifts
    A = {"TA": TA, "lift": TA, "mist0": TA + .5, "crowdEnd": TA + 3.4, "one": TA + 3.6}
    L["l4"] = TA + 4.4
    A["fig0"], A["fig1"], A["here"] = L["l4"] + .4, L["l4"] + 5.2, L["l4"] + 3.8
    L["l5"] = max(L["l4"] + dur["l4"] + 3.0, A["fig1"] + 1.0)
    L["l6"] = L["l5"] + dur["l5"] + 4.5
    A["fade0"] = L["l6"] - 1.6
    A["later"] = L["l6"] + 1.4
    A["under0"], A["under1"] = A["later"] + 2.4, A["later"] + 4.5
    A["title"] = L["l6"] + 3.6
    A["handle"] = A["title"] + 1.4
    A["DUR"] = round(A["title"] + 4.4, 2)
    # the three things land on their spoken words
    lead_n = len(s["l5_lead"].split())
    w5 = words.get("l5") or []
    after = w5[lead_n - 1][1] if len(w5) >= lead_n else 0
    items, prev = [], after
    for k, it in enumerate(s["items"]):
        wt = _word_time(w5, it["label"], prev)
        t = L["l5"] + (wt if wt is not None else dur["l5"] * (.4 + .22 * k))
        items.append({**it, "t": round(t, 3)}); prev = (wt or prev) + .05
    # overload notes, denser towards the lift
    n = len(s["notes"])
    notes = [[round(2.4 + (TA - 3.6) * (i / (n - 1)) ** .8, 3), txt] for i, txt in enumerate(s["notes"])]
    one, l5, l6, D = A["one"], L["l5"], L["l6"], A["DUR"]
    cam = {"z": [[0, 1], [L["l2"] + .9, 1.06], [TA - .8, 1.12], [one, 1.12], [l5 - .4, 1.0], [l6 - 2, .94], [l6, .95], [D, 1.0]],
           "x": [[0, 540], [TA - .8, 540], [one, 560], [l5 - .4, 560], [l6 - 2, 750], [l6, 700], [D, 690]],
           "y": [[0, 960], [L["l2"] + .9, 940], [TA - .8, 900], [one, 940], [l5 - .4, 980], [l6 - 2, 1000], [l6, 990], [D, 1010]]}
    lines = spoken_lines(s)
    ks = list(L)
    subs = []
    for i, k in enumerate(ks):
        nxt = L[ks[i + 1]] - .15 if i + 1 < len(ks) else D
        subs.append({"t0": round(L[k], 3), "t1": round(min(nxt, max(L[k] + dur[k] + .6, L[k] + 1.8)), 3), "text": lines[k]})
    return {"A": {k: round(v, 3) for k, v in A.items()},
            "lines": {k: {"t": round(L[k], 3), "d": dur[k], "text": lines[k]} for k in ks},
            "notes": notes, "items": items, "cam": cam, "subs": subs,
            "here": s["here"], "later": s["later"], "title": s["title"], "handle": HANDLE}


# ---------------------------------------------------------------- build

def _status(job: Path, **kw) -> None:
    p = job / "status.json"
    st = json.loads(p.read_text()) if p.exists() else {}
    st.update(kw, updated=datetime.now().isoformat(timespec="seconds"))
    p.write_text(json.dumps(st, ensure_ascii=False, indent=1))


def _run(job: Path, cmd: list[str], cwd: Path, env: dict, timeout: int = 900) -> None:
    with open(job / "build.log", "a") as log:
        log.write(f"\n$ {' '.join(cmd)}\n"); log.flush()
        r = subprocess.run(cmd, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{Path(cmd[1] if len(cmd) > 1 else cmd[0]).name} falhou (código {r.returncode}); ver build.log")


def check_ready() -> list[str]:
    """Problemas que impedem o build (vazio = pronto)."""
    probs = []
    if not (LIB / "core/render/video.mjs").exists():
        probs.append(f"biblioteca Lemo-Opuscar não encontrada em {LIB}")
    if not (LIB / ".venv/bin/python").exists():
        probs.append("falta o ambiente Python da biblioteca (setup.sh deps)")
    if not (LIB / "core/audio/instruments/freepats").exists():
        probs.append("falta a biblioteca de sons freepats (tools/fetch.sh instruments freepats)")
    for b in ("node", "ffmpeg"):
        if not shutil.which(b):
            probs.append(f"'{b}' não está no PATH")
    return probs


def build(job: Path) -> Path:
    """Voz → tempos → content.js → render → mistura → masterização. Devolve o MP4."""
    job = Path(job)
    py = str(LIB / ".venv/bin/python")
    env = {**os.environ, "LIB": str(LIB), "HF_HOME": os.getenv("HF_HOME", "/mnt/storage/repos/_tools/hf-cache")}
    s = json.loads((job / "script.json").read_text())
    FILMS_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOCK_FILE, "w") as lock:
        _status(job, state="waiting", step="à espera de outro filme")
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            _status(job, state="running", step="voz (Kokoro)", started=time.time())
            lines = spoken_lines(s)
            (job / "lines.json").write_text(json.dumps([{"id": k, "text": v, "voice": VOICE, "speed": .9} for k, v in lines.items()], indent=1))
            _run(job, [py, "core/tts/tts.py", str(job / "lines.json"), str(job / "voices")], LIB, env)
            _status(job, step="verificar voz (whisper)")
            try:
                _run(job, [py, "core/tts/asr_check.py", str(job / "lines.json"), str(job / "voices"), "--lang", "en"], LIB, env)
            except RuntimeError:
                _status(job, warning="a verificação da voz encontrou diferenças (ver build.log)")
            dur = json.loads((job / "voices/dur.json").read_text())
            wpath = job / "voices/words.json"
            words = json.loads(wpath.read_text()) if wpath.exists() else {}
            content = timeline(s, dur, words)
            content["seed"] = int(s.get("seed", 0))
            (job / "content.json").write_text(json.dumps(content, ensure_ascii=False, indent=1))
            (job / "content.js").write_text("window.CONTENT = " + json.dumps(content, ensure_ascii=False) + ";\n")
            size = ["--size", "1080x1920"]
            _status(job, step="eventos de som")
            _run(job, ["node", "core/render/events.mjs", str(job), *size], LIB, env)
            _status(job, step=f"pintar {int(content['A']['DUR'] * 30)} fotogramas")
            _run(job, ["node", "core/render/video.mjs", str(job), "--fps", "30", "--workers", "4", *size,
                       "--out", str(job / "out/video.mp4")], LIB, env, timeout=1800)
            _status(job, step="música e mistura")
            _run(job, [py, str(job / "mix.py"), str(job)], LIB, env)
            (job / "out").mkdir(exist_ok=True)
            (job / "out/cues.json").write_text(json.dumps(content["subs"]))
            _run(job, [py, "core/render/srt.py", str(job / "out/cues.json"), str(job / "film.srt")], LIB, env)
            _status(job, step="masterização (−14 LUFS)")
            _run(job, ["sh", "core/render/mux.sh", str(job / "out/video.mp4"), str(job / "out/mix.wav"),
                       str(job / "film.mp4"), "30", "1"], LIB, env)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(content["A"]["title"] + 1.5), "-i", str(job / "film.mp4"),
                            "-frames:v", "1", str(job / "poster.jpg")], check=False)
            _status(job, state="done", step="pronto", video=str(job / "film.mp4"), duration=content["A"]["DUR"],
                    finished=time.time())
            return job / "film.mp4"
        except Exception as e:
            _status(job, state="error", step="erro", error=str(e))
            raise
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def new_job(script: dict[str, Any], name: str, post: Optional[dict[str, Any]] = None) -> Path:
    """Pasta nova com o modelo e o guião."""
    from instagram_poster.studio import slugify
    job = FILMS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}_{slugify(name, 36)}"
    job.mkdir(parents=True)
    for f in TEMPLATE_FILES:
        shutil.copy2(TEMPLATE / f, job / f)
    shutil.copytree(TEMPLATE / "fonts", job / "fonts")
    s = normalize_script(script)
    s["seed"] = int(time.time()) % 997
    (job / "script.json").write_text(json.dumps(s, ensure_ascii=False, indent=1))
    if post:
        (job / "post.json").write_text(json.dumps({k: post.get(k) for k in ("row_index", "date", "image_text", "caption")},
                                                  ensure_ascii=False, indent=1))
    _status(job, state="queued", step="na fila")
    return job


def start_build(script: dict[str, Any], name: str, post: Optional[dict[str, Any]] = None) -> Path:
    """Cria a pasta e corre o build num processo separado (a página não bloqueia). Devolve a pasta."""
    job = new_job(script, name, post)
    log = open(job / "build.log", "a")
    subprocess.Popen([sys.executable, "-m", "instagram_poster.watercolor_film", str(job)], cwd=str(APP_ROOT),
                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    return job


def job_status(job: Path) -> dict[str, Any]:
    p = Path(job) / "status.json"
    try:
        st = json.loads(p.read_text())
    except Exception:
        return {"state": "unknown"}
    if st.get("state") == "running" and time.time() - p.stat().st_mtime > 1800:
        st["state"], st["error"] = "error", "o build parou sem terminar (mais de 30 min sem progresso)"
    return st


def recent_jobs(n: int = 12) -> list[Path]:
    if not FILMS_DIR.is_dir():
        return []
    jobs = [p for p in FILMS_DIR.iterdir() if p.is_dir() and (p / "status.json").exists()]
    return sorted(jobs, key=lambda p: p.name, reverse=True)[:n]


def build_log_tail(job: Path, n: int = 12) -> str:
    p = Path(job) / "build.log"
    if not p.exists():
        return ""
    return "\n".join(p.read_text(errors="replace").splitlines()[-n:])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build(Path(sys.argv[1]))
