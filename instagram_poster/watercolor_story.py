"""
História aguarela: Reel vertical feito em código (Lemo-Opuscar, estilo watercolor) com uma história montada pela IA.

Em vez de uma história fixa, o filme é um storyboard de momentos ("beats") pintados numa folha contínua:
  crowd      página cheia de sentimentos e notas aflitas; a névoa apaga tudo (pode guardar um)
  specimen   um objeto em destaque com uma nota escrita à mão (a pessoa recebe o sentimento guardado)
  trio       três coisas pintadas e ditas (ao lado do objeto anterior, ou sozinhas)
  journey    um caminho de um objeto até outro, com uma pequena figura a andar
  transform  um objeto apaga-se em silêncio e outro nasce no lugar (tempestade → sol)
  grow       dois ou três objetos em crescimento (semente → rebento → árvore)
e um final fixo (nota por acabar + título). Os objetos vêm de assets/watercolor_story/objects.js (~49).

- draft_storyboard(post): storyboard pelo modelo de texto da app (editável na página).
- normalize_storyboard(sb): valida tipos, objetos, tamanhos e duração.
- start_build(sb, name, post): pasta em Video/saida/filmes/ e build num processo à parte (mesmo build do filme fixo).
Uso direto: python -m instagram_poster.watercolor_story <pasta do filme>
"""
import json
import logging
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from instagram_poster import watercolor_film as WF

logger = logging.getLogger(__name__)

TEMPLATE = WF.APP_ROOT / "assets" / "watercolor_story"
TEMPLATE_FILES = ["index.html", "engine.js", "objects.js", "story.js", "mix.py", "fonts.css", "paper_tile.jpg"]
OBJECTS = re.findall(r"^  (\w+)\(", (TEMPLATE / "objects.js").read_text(), re.M)
BEAT_TYPES = ["crowd", "specimen", "trio", "journey", "transform", "grow"]
BEAT_NAMES = {"crowd": "página cheia → névoa", "specimen": "objeto em destaque", "trio": "três coisas",
              "journey": "caminho de A para B", "transform": "transformação A → B", "grow": "crescimento"}
SYNONYMS = {"tea": "cup", "coffee": "cup", "mug": "cup", "water": "glass", "music": "song", "notes": "song", "melody": "song",
            "sea": "wave", "ocean": "wave", "night": "moon", "star": "moon", "light": "lamp", "road": "bridge", "path": "bridge",
            "home": "house", "journal": "book", "diary": "book", "notebook": "book", "pages": "book", "plants": "plant",
            "seedling": "sprout", "growth": "sprout", "cloudy": "cloud", "rainy": "rain", "thunder": "storm", "list": "checklist",
            "todo": "checklist", "time": "clock", "watch": "clock", "message": "letter", "note": "letter", "mail": "letter",
            "pillow": "bed", "sleep": "bed", "rest": "bed", "weight": "backpack", "burden": "backpack", "bag": "backpack",
            "flame": "candle", "campfire": "fire", "self": "person", "you": "person", "figure": "walker", "rock": "stones",
            "stone": "stones", "rainbows": "rainbow", "doorway": "door_open", "open_door": "door_open", "screen": "phone",
            "day": "sun", "sunrise": "sun", "morning": "sun", "breathing": "breath", "air": "breath", "wind": "breath",
            "love": "heart", "feeling": "blot", "emotion": "blot", "gift_box": "gift", "seat": "bench", "palm": "hand"}
MAX_DUR = 58.0

_SYSTEM = f"""You are the director of a 35-55 second hand-painted watercolor Reel for the Instagram account @keepcalmnbepositive
(mindset, self-compassion, slow growth). Turn the post into a SHORT STORY told with painted objects on one long journal page.
Build it from 3 or 4 beats (in any order that tells the story best), then the film ends with a fixed title card.

Beat types:
- "crowd": a page fills with colour blots (feelings) and anxious hand-written notes, then a mist erases it. Good to open on overwhelm.
  keys: "lines" (1-3 narration lines), "notes" (8-10 anxious inner thoughts, 1-4 words, lowercase), "keep" (true = one warm feeling survives the mist and goes into the next beat)
- "specimen": one object painted large, with a short hand-written note pointing at it. If it follows a crowd with keep=true and the object is "person", the surviving feeling lands in the person's chest.
  keys: "lines" (1-2), "object", "note" (1-3 words)
- "trio": three small things painted one by one as the narrator names them. keys: "lead" (max 6 words, spoken before the three labels), "items": exactly 3 of {{"label": 1-3 words lowercase, spoken, "object"}}
- "journey": a path from one object to another, a small figure walks along it. keys: "lines" (1-2), "from", "to", "label" (1-3 words, optional)
- "transform": an object is painted, the film goes quiet, it washes away and a new object grows in its place. keys: "lines" (exactly 2: one before, one after the change), "from", "to", "note" (optional, 1-3 words)
- "grow": 2 or 3 objects grow left to right in stages. keys: "lines" (1-2), "objects" (2-3 names, smallest first), "note" (optional)
Optional on any beat after the first: "transition": "pan" (camera glides along the page, default) or "mist" (paper wash, for a change of time or place).

Objects (use ONLY these names): {", ".join(OBJECTS)}

Rules: English; warm, plain and specific to the post; no clichés, no em dashes, no hashtags, no emoji. Each narration line max 12 words.
Whole film max 70 spoken words. Every beat must show the idea of its line with its objects. Vary the beats from post to post.
Return ONLY a JSON object: {{"beats": [...], "close": "a final spoken line, max 9 words", "later": "max 18 characters, a calm hand-written note", "title": "max 26 characters, ends with a full stop"}}"""


# ---------------------------------------------------------------- storyboard

def _obj(name: Any, default: str = "heart") -> str:
    n = re.sub(r"[^a-z_]", "", str(name or "").lower().replace(" ", "_"))
    if n in OBJECTS:
        return n
    if n in SYNONYMS:
        return SYNONYMS[n]
    for w in re.split(r"_", n):
        if w in OBJECTS:
            return w
        if w in SYNONYMS:
            return SYNONYMS[w]
    return default


def _line(s: Any, n: int = 13) -> str:
    v = WF._clip_words(str(s or ""), n)
    if not v:
        return ""
    v = v[:1].upper() + v[1:]
    return v if v[-1] in ".!?" else v + "."


def _short(s: Any, n: int) -> str:
    v = re.sub(r"\s+", " ", str(s or "")).strip().replace("—", ",").replace("–", ",")
    if len(v) > n:
        v = v[:n].rsplit(" ", 1)[0].rstrip(",;:")
    return v


def _note(s: Any, n: int, default: str) -> str:
    """A short hand-written note: whole or not at all (a note cut mid-phrase reads as a mistake)."""
    v = re.sub(r"\s+", " ", str(s or "")).strip().replace("—", ",").replace("–", ",")
    return v if 0 < len(v) <= n else default


def trio_line(b: dict) -> str:
    return b["lead"].rstrip(".") + ". " + " ".join(it["label"][:1].upper() + it["label"][1:] + "." for it in b["items"])


def normalize_storyboard(sb: dict[str, Any]) -> dict[str, Any]:
    """Storyboard sempre válido: tipos e objetos conhecidos, tamanhos e duração dentro dos limites."""
    beats = []
    for raw in (sb.get("beats") or [])[:5]:
        if not isinstance(raw, dict) or raw.get("type") not in BEAT_TYPES:
            continue
        ty = raw["type"]; b: dict[str, Any] = {"type": ty}
        if beats and raw.get("transition") in ("pan", "mist"):
            b["transition"] = raw["transition"]
        lines = [_line(x) for x in (raw.get("lines") or []) if str(x).strip()]
        if ty == "crowd":
            b["lines"] = lines[:3] or ["Everything asks for you at once."]
            notes = [_short(n, 22).lower() for n in (raw.get("notes") or []) if str(n).strip()]
            b["notes"] = (notes + WF.DEFAULT_SCRIPT["notes"])[:10]
            b["keep"] = bool(raw.get("keep", True))
        elif ty == "specimen":
            b["lines"] = lines[:2] or ["Look at one thing, and only that."]
            b["object"] = _obj(raw.get("object"), "person")
            b["note"] = _short(raw.get("note") or "here", 16)
        elif ty == "trio":
            items = [it for it in (raw.get("items") or []) if isinstance(it, dict) and str(it.get("label", "")).strip()][:3]
            while len(items) < 3:
                items.append(WF.DEFAULT_SCRIPT["items"][len(items)] | {"object": WF.DEFAULT_SCRIPT["items"][len(items)]["icon"]})
            b["lead"] = _line(raw.get("lead") or "Then give it something steady.", 7)
            b["items"] = [{"label": WF._clip_words(it["label"], 3).lower().strip(".,"), "object": _obj(it.get("object") or it.get("icon"), "heart")} for it in items]
        elif ty == "journey":
            b["lines"] = lines[:2] or ["One small step, then the next."]
            b["from"], b["to"] = _obj(raw.get("from"), "house"), _obj(raw.get("to"), "tree")
            b["label"] = _short(raw.get("label") or "", 18)
        elif ty == "transform":
            b["lines"] = (lines + ["It changes when you let it.", "And something softer grows."])[:2] if len(lines) < 2 else lines[:2]
            b["from"], b["to"] = _obj(raw.get("from"), "storm"), _obj(raw.get("to"), "sun")
            b["note"] = _short(raw.get("note") or "", 18)
        elif ty == "grow":
            b["lines"] = lines[:2] or ["Small steps grow quietly."]
            objs = [_obj(o, "sprout") for o in (raw.get("objects") or [])][:3]
            b["objects"] = objs if len(objs) >= 2 else ["seed", "sprout", "tree"]
            b["note"] = _short(raw.get("note") or "", 18)
        beats.append(b)
    if not beats:
        beats = default_storyboard()["beats"]
    out = {"beats": beats, "close": _line(sb.get("close") or "Be gentle with the pace you need.", 10),
           "later": _note(sb.get("later"), 22, "rest first"),
           "title": _short(sb.get("title") or "One step at a time.", 30) or "One step at a time."}
    if out["title"][-1] not in ".!?":
        out["title"] += "."
    while len(out["beats"]) > 2 and estimate_duration(out) > MAX_DUR:   # too long: drop beats from the middle
        out["beats"].pop(len(out["beats"]) // 2)
    return out


def estimate_duration(sb: dict) -> float:
    words = sum(len(l.split()) for b in sb["beats"] for l in spoken(b)) + len(sb["close"].split())
    extra = {"crowd": 6.5, "specimen": 4.5, "trio": 3.0, "journey": 5.0, "transform": 6.0, "grow": 4.5}
    return words / 2.5 + sum(extra[b["type"]] for b in sb["beats"]) + 2.0 * (len(sb["beats"]) - 1) + 9.0


def spoken(b: dict) -> list[str]:
    return [trio_line(b)] if b["type"] == "trio" else list(b.get("lines") or [])


def default_storyboard(post: Optional[dict] = None) -> dict[str, Any]:
    """O filme original como storyboard (também o plano B quando a IA falha)."""
    s = WF.fallback_script(post) if post else WF.DEFAULT_SCRIPT | {"l1": "You don't have to carry it all at once.",
                                                                   "l2": "Some feelings need time to settle.", "l3": "Rushing them only makes them heavier."}
    return {"beats": [{"type": "crowd", "lines": [s["l1"], s["l2"], s["l3"]], "notes": s["notes"], "keep": True},
                      {"type": "specimen", "lines": [s["l4"]], "object": "person", "note": s["here"]},
                      {"type": "trio", "lead": s["l5_lead"], "items": [{"label": it["label"], "object": it["icon"]} for it in s["items"]]}],
            "close": s["l6"], "later": s["later"], "title": s["title"]}


def draft_storyboard(post: dict[str, Any]) -> dict[str, Any]:
    from instagram_poster.text_generator import generate_text
    user = (f"Post headline: {post.get('image_text', '')}\n\nCaption: {post.get('caption', '')}\n\n"
            f"Carousel text: {post.get('slide2_text', '')}")
    try:
        raw = generate_text(_SYSTEM, user, json_mode=True)
        m = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(m.group(0) if m else raw)
        if not data.get("beats"):
            raise ValueError("storyboard sem beats")
        return normalize_storyboard(data)
    except Exception as e:
        logger.warning("História aguarela: storyboard por IA falhou (%s); a usar o original.", e)
        return normalize_storyboard(default_storyboard(post))


# ---------------------------------------------------------------- timeline

def timeline(sb: dict[str, Any], dur: dict[str, float], words: dict[str, list]) -> dict[str, Any]:
    """Regiões, tempos de cada momento, câmara, silêncios e legendas a partir das durações da voz."""
    lines, cam, mists, stops, hits, beats = [], [], [], [], [], []
    lid = iter(f"l{i + 1}" for i in range(99))
    def say(text: str, t: float) -> float:              # place a line, return its end
        k = next(lid); lines.append({"id": k, "t": round(t, 3), "d": dur[k], "text": text}); return t + dur[k]
    def key(t, x, y, z): cam.append([round(t, 3), x, y, z])
    ox, prev, T = 0.0, None, 0.0
    groups: list[list[dict]] = []
    for i, src in enumerate(sb["beats"]):
        b = json.loads(json.dumps(src)); ty = b["type"]
        attach = prev is not None and ((ty == "specimen" and prev["type"] == "crowd" and prev.get("keep")) or
                                       (ty == "trio" and prev["type"] == "specimen"))
        if prev is None:
            T = 0.0; key(0, 540, 960, 1.0)
        elif attach:
            T = prev["t1"]
        else:
            gap = 2.2 if b.get("transition") == "mist" else 1.8
            ox = prev["next_ox"]
            if b.get("transition") == "mist":
                mid = prev["t1"] + gap / 2
                mists.append({"t0": round(prev["t1"] - .1, 3), "t1": round(prev["t1"] + gap + .1, 3)})
                key(mid - .03, *cam[-1][1:]); key(mid + .03, ox + 540, 960, 1.0)
            T = prev["t1"] + gap
            key(T, ox + 540, 960, 1.0)
        b["ox"], b["t0"] = ox, round(T, 3); b["next_ox"] = ox + 1600
        if ty == "crowd":
            end, t = T, T + .5
            for k, ln in enumerate(b["lines"]):
                end = say(ln, t); t = end + (1.7 if k == 0 else .55)
            lift = end + .35
            n = len(b["notes"]); start = T + 1.9
            b["notes"] = [[round(start + (lift - 1.2 - start) * (j / max(1, n - 1)) ** .8, 3), txt] for j, txt in enumerate(b["notes"])]
            b.update(lift=round(lift, 3), mist0=round(lift + .5, 3), end=round(lift + 3.4, 3), one=round(lift + 3.6, 3), t1=round(lift + 3.6, 3), music_end=round(lift - .8, 3))
            key(T + 4.5, ox + 540, 940, 1.06); key(lift - .8, ox + 540, 900, 1.12)
            stops.append([round(lift - .8, 3), round(lift + 3.6, 3)])
            if b["keep"]:
                hits.append({"t": round(lift + 3.6, 3), "note": "A4"})
            else:
                b["t1"] = round(lift + 3.0, 3)
            key(b["t1"], ox + 540 + (20 if b["keep"] else 0), 940, 1.12)
        elif ty == "specimen":
            first = T + (.8 if attach else .5)
            paint = [T + 1.2, T + 6.0] if attach else [T + .4, T + 4.4]
            end, t = T, first
            for ln in b["lines"]:
                end = say(ln, t); t = end + .6
            b["paint"] = [round(paint[0], 3), round(paint[1], 3)]
            b["note"] = {"text": b["note"], "t": round(paint[1] - 1.4, 3)} if b.get("note") else None
            b["accent"] = attach
            if attach and b["object"] != "person":
                prev["absorb"] = b["paint"][0]           # the kept feeling fades into the new object
            b["t1"] = round(max(paint[1] + 1.0, end + 1.0), 3); b["music_end"] = b["t1"]
            key(b["t1"], ox + 560, 980, 1.0)
        elif ty == "trio":
            lead_n = len(b["lead"].split())
            t_line = T + .4; end = say(trio_line(b), t_line)
            w5 = words.get(lines[-1]["id"]) or []
            prev_w = w5[lead_n - 1][1] if len(w5) >= lead_n else 0
            for k, it in enumerate(b["items"]):
                wt = WF._word_time(w5, it["label"], prev_w)
                it["t"] = round(t_line + (wt if wt is not None else (end - t_line) * (.4 + .22 * k)), 3); prev_w = (wt or prev_w) + .05
            b["attach"] = attach
            b["t1"] = round(end + 2.0, 3); b["music_end"] = b["t1"]
            key(b["t1"], ox + (750 if attach else 540), 1000 if attach else 950, .94 if attach else 1.04)
        elif ty == "journey":
            end, t = T, T + .6
            for ln in b["lines"]:
                end = say(ln, t); t = end + .6
            t1 = max(T + 8.0, end + 2.0)
            b["pa"], b["path_t"] = [round(T + .3, 3), round(T + 1.6, 3)], [round(T + 1.2, 3), round(T + 2.8, 3)]
            b["walk"] = [round(T + 2.4, 3), round(t1 - 1.4, 3)]; b["pb"] = [round(t1 - 3.8, 3), round(t1 - 2.4, 3)]
            b["t1"] = round(t1, 3); b["music_end"] = b["t1"]; b["next_ox"] = ox + 2400
            key(T + 2.4, ox + 640, 960, 1.0); key(t1 - 1.4, ox + 1360, 940, 1.0); key(t1, ox + 1400, 930, 1.02)
            hits.append({"t": round(t1 - 1.4, 3), "note": "D5"})
        elif ty == "transform":
            end0 = say(b["lines"][0], T + .5)
            pa = [T + .3, T + 2.6]; e0 = max(pa[1] + .6, end0 + .8)
            b["pa"], b["erase"] = [round(pa[0], 3), round(pa[1], 3)], [round(e0, 3), round(e0 + 1.6, 3)]
            b["pb"] = [round(e0 + 1.4, 3), round(e0 + 3.0, 3)]
            end = say(b["lines"][1], e0 + 2.0) if len(b["lines"]) > 1 else e0 + 3.0
            b["note"] = {"text": b["note"], "t": round(b["pb"][1] + .2, 3)} if b.get("note") else None
            b["t1"] = round(max(b["pb"][1] + 1.6, end + 1.2), 3); b["music_end"] = b["t1"]
            stops.append([round(end0 + .2, 3), round(e0 + 1.4, 3)]); hits.append({"t": round(e0 + 1.4, 3), "note": "A4", "chord": True})
            key(e0, ox + 540, 930, 1.08); key(e0 + 1.4, ox + 540, 930, 1.08); key(b["t1"], ox + 540, 950, 1.0)
        elif ty == "grow":
            end, t = T, T + .5
            for ln in b["lines"]:
                end = say(ln, t); t = end + .6
            b["times"] = [round(T + .6 + k * 1.7, 3) for k in range(len(b["objects"]))]
            b["note"] = {"text": b["note"], "t": round(b["times"][-1] + 1.6, 3)} if b.get("note") else None
            b["t1"] = round(max(b["times"][-1] + 2.6, end + 1.2), 3); b["music_end"] = b["t1"]
            key(b["t1"], ox + 540, 950, 1.06)
        if attach:
            groups[-1].append(b)
        else:
            groups.append([b])
        beats.append(b); prev = b
    # ending: a quiet breath, the closing line, the unfinished note, the title, on the last region
    last = beats[-1]
    close_t = last["t1"] + 1.4
    stops.append([round(last["t1"], 3), round(close_t, 3)])
    close_end = say(sb["close"], close_t)
    ex = cam[-1][1]
    later_t = close_t + 1.4; title_t = max(close_t + 3.6, close_end + .8)
    E = {"x": ex, "close_t": round(close_t, 3), "later": sb["later"], "later_t": round(later_t, 3),
         "under": [round(later_t + 2.4, 3), round(later_t + 4.5, 3)], "title": sb["title"], "title_t": round(title_t, 3),
         "handle": WF.HANDLE, "handle_t": round(title_t + 1.4, 3)}
    DUR = round(title_t + 4.4, 2)
    key(DUR, ex, cam[-1][2] + 10, cam[-1][3] + .04)
    hits.append({"t": round(title_t, 3), "note": "D4", "chord": True})
    # notes and labels fade before the group's camera leaves, or before the closing line
    for gi, g in enumerate(groups):
        fade = (groups[gi + 1][0]["t0"] - 2.0) if gi + 1 < len(groups) else close_t - .4
        for b in g:
            b["fade"] = round(fade, 3)
    cam.sort(key=lambda k: k[0])
    clean = []
    for k in cam:                                        # strictly increasing times for the monotone tracks
        if clean and k[0] <= clean[-1][0]:
            k = [clean[-1][0] + .01] + k[1:]
        clean.append(k)
    subs = []
    for j, ln in enumerate(lines):
        nxt = lines[j + 1]["t"] - .15 if j + 1 < len(lines) else DUR
        subs.append({"t0": ln["t"], "t1": round(min(nxt, max(ln["t"] + ln["d"] + .6, ln["t"] + 1.8)), 3), "text": ln["text"]})
    for b in beats:
        b.pop("next_ox", None)
    return {"DUR": DUR, "beats": beats, "lines": lines, "subs": subs, "mists": mists, "stops": stops, "hits": hits, "ending": E,
            "cam": {"x": [[k[0], k[1]] for k in clean], "y": [[k[0], k[2]] for k in clean], "z": [[k[0], k[3]] for k in clean]}}


def all_lines(sb: dict) -> list[str]:
    return [l for b in sb["beats"] for l in spoken(b)] + [sb["close"]]


# ---------------------------------------------------------------- build

def build(job: Path) -> Path:
    job = Path(job)
    py = str(WF.LIB / ".venv/bin/python")
    env = {**__import__("os").environ, "LIB": str(WF.LIB), "HF_HOME": "/mnt/storage/repos/_tools/hf-cache"}
    sb = json.loads((job / "storyboard.json").read_text())
    WF.FILMS_DIR.mkdir(parents=True, exist_ok=True)
    import fcntl
    with open(WF.LOCK_FILE, "w") as lock:
        WF._status(job, state="waiting", step="à espera de outro filme")
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            WF._status(job, state="running", step="voz (Kokoro)", started=time.time())
            texts = all_lines(sb)
            (job / "lines.json").write_text(json.dumps([{"id": f"l{i + 1}", "text": t, "voice": WF.VOICE, "speed": .9} for i, t in enumerate(texts)], indent=1))
            WF._run(job, [py, "core/tts/tts.py", str(job / "lines.json"), str(job / "voices")], WF.LIB, env)
            WF._status(job, step="verificar voz (whisper)")
            try:
                WF._run(job, [py, "core/tts/asr_check.py", str(job / "lines.json"), str(job / "voices"), "--lang", "en"], WF.LIB, env)
            except RuntimeError:
                WF._status(job, warning="a verificação da voz encontrou diferenças (ver build.log)")
            dur = json.loads((job / "voices/dur.json").read_text())
            wpath = job / "voices/words.json"
            words = json.loads(wpath.read_text()) if wpath.exists() else {}
            content = timeline(sb, dur, words)
            content["seed"] = int(sb.get("seed", 0))
            (job / "content.json").write_text(json.dumps(content, ensure_ascii=False, indent=1))
            (job / "content.js").write_text("window.CONTENT = " + json.dumps(content, ensure_ascii=False) + ";\n")
            size = ["--size", "1080x1920"]
            WF._status(job, step="eventos de som")
            WF._run(job, ["node", "core/render/events.mjs", str(job), *size], WF.LIB, env)
            WF._status(job, step=f"pintar {int(content['DUR'] * 30)} fotogramas")
            WF._run(job, ["node", "core/render/video.mjs", str(job), "--fps", "30", "--workers", "4", *size, "--out", str(job / "out/video.mp4")], WF.LIB, env, timeout=1800)
            WF._status(job, step="música e mistura")
            WF._run(job, [py, str(job / "mix.py"), str(job)], WF.LIB, env)
            (job / "out/cues.json").write_text(json.dumps(content["subs"]))
            WF._run(job, [py, "core/render/srt.py", str(job / "out/cues.json"), str(job / "film.srt")], WF.LIB, env)
            WF._status(job, step="masterização (−14 LUFS)")
            WF._run(job, ["sh", "core/render/mux.sh", str(job / "out/video.mp4"), str(job / "out/mix.wav"), str(job / "film.mp4"), "30", "1"], WF.LIB, env)
            E = content["ending"]
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(E["title_t"] + 1.5), "-i", str(job / "film.mp4"), "-frames:v", "1", str(job / "poster.jpg")], check=False)
            step_s = max(1.0, content["DUR"] / 15)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(job / "film.mp4"), "-vf", f"fps=1/{step_s:.2f},scale=216:384,tile=15x1",
                            "-frames:v", "1", str(job / "sheet.jpg")], check=False)
            WF._status(job, state="done", step="pronto", video=str(job / "film.mp4"), duration=content["DUR"], finished=time.time())
            return job / "film.mp4"
        except Exception as e:
            WF._status(job, state="error", step="erro", error=str(e))
            raise
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def new_job(sb: dict[str, Any], name: str, post: Optional[dict[str, Any]] = None) -> Path:
    from instagram_poster.studio import slugify
    job = WF.FILMS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}_{slugify(name, 36)}"
    job.mkdir(parents=True)
    for f in TEMPLATE_FILES:
        shutil.copy2(TEMPLATE / f, job / f)
    shutil.copytree(TEMPLATE / "fonts", job / "fonts")
    s = normalize_storyboard(sb)
    s["seed"] = int(time.time()) % 997
    (job / "storyboard.json").write_text(json.dumps(s, ensure_ascii=False, indent=1))
    if post:
        (job / "post.json").write_text(json.dumps({k: post.get(k) for k in ("row_index", "date", "image_text", "caption")}, ensure_ascii=False, indent=1))
    WF._status(job, state="queued", step="na fila", kind="story")
    return job


def start_build(sb: dict[str, Any], name: str, post: Optional[dict[str, Any]] = None) -> Path:
    job = new_job(sb, name, post)
    log = open(job / "build.log", "a")
    subprocess.Popen([sys.executable, "-m", "instagram_poster.watercolor_story", str(job)], cwd=str(WF.APP_ROOT),
                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    return job


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build(Path(sys.argv[1]))
