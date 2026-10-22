"""
Qualidade do conteúdo gerado: ganchos avaliados, texto "humanizado", legenda verificada
e a estrutura de carrossel que leva a guardar/enviar.

Baseado na instagram-agent-skill (MIT, vendor/ig_agent): o hookscore avalia o gancho
(slide 1) e o humanize limpa marcas de texto gerado (aspas curvas, caracteres
invisíveis, travessões, expressões feitas). As regras abaixo são acrescentadas ao prompt
de sistema na geração e têm prioridade sobre regras anteriores que as contradigam,
sem alterar o prompt personalizado guardado em content_system_prompt_override.txt.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Callable

from instagram_poster.vendor.ig_agent import hookscore
from instagram_poster.vendor.ig_agent import humanize as _humanize

logger = logging.getLogger(__name__)

# Abaixo disto o gancho é reescrito (o hookscore chama "OK" a 50+ e "STRONG" a 70+).
MIN_HOOK_SCORE = 55
FEED_VISIBLE_CHARS = 125
MAX_HASHTAGS = 5

QUALITY_RULES = """
## Quality rules (these take precedence over any earlier rule that contradicts them)

### Image prompts
- Never describe people, faces, hands or body parts, nor screens or papers with writing: AI renders them incoherently.
  Use nature, light, weather, objects and empty interiors instead.

### Image Text (the hook, slide 1)
- Make it SPECIFIC. Name a concrete moment, scene, number or behaviour the reader recognises from their own day:
  "the text you rewrote four times before sending", "replaying one conversation at 2 a.m.", "saying sorry three times in one email".
  Abstract nouns alone ("peace", "growth", "negativity", "your mindset") are not a hook.
- Include a number, count or time whenever it's honest ("At 2 a.m.", "eleven times", "10 minutes", "the 3rd apology"):
  it's the single detail that makes people stop scrolling.
- Put the tension in the first three words. No greeting, no "Sometimes", no "Remember", no "Let's".
- 6 to 14 words. One idea. It must make sense with no caption.
- Speak to the reader ("you") or confess in first person ("I"). Never sound like a poster or a brand.

### Voice (Image Text, Slide2 Text and Caption)
- Write the way a person talks: use contractions (you're, it's, don't, I'm, can't).
- Vary sentence length: mix very short sentences with longer ones. Never three sentences of the same shape in a row.
- Prefer one concrete example over two general statements.
- Use straight quotes and apostrophes ("like this", it's), never curly ones, and never the long dash character.

### Carousels (Post Type "carousel", Slide2 Text)
- Slide2 Text has 5 to 7 paragraphs separated by one blank line. Each paragraph is one slide (headline-like first sentence, at most 30 words).
- Order: the stake (why this matters, one sentence) -> 2 to 4 slides with ONE idea each (name what's happening, the reframe, one small action for today)
  -> a RECAP slide that starts with "In short:" and lists the whole idea in 3 short lines (this is the slide people screenshot and send)
  -> a final ASK slide with exactly one gentle, honest action: "Save this for the next time ..." or "Send this to someone who ...".
- Slide numbers are added automatically; do not write them.

### Caption
- The first line (at most 125 characters, it's what the feed shows before "... more") must work on its own: a concrete line, never a greeting, emoji or hashtag.
- 2 to 5 short paragraphs, including 1 or 2 natural phrases people would search for (e.g. "people pleasing", "overthinking at night", "setting boundaries").
- End with exactly ONE honest ask: save it, or send it to someone it would help. This is not engagement bait; bait is "tag a friend", "double tap", "comment YES".
- At most 3 hashtags, on their own last line.
"""


def system_prompt_with_quality_rules(base_prompt: str) -> str:
    """Acrescenta as regras de qualidade ao prompt de sistema (base ou personalizado)."""
    return base_prompt.rstrip() + "\n\n" + QUALITY_RULES.strip() + "\n"


# ── Gancho ────────────────────────────────────────────────────────────────────

def score_hook(text: str) -> dict:
    """Avalia um gancho: {score, verdict, weakest, flags}."""
    text = (text or "").strip().replace("\n", " ")
    if not text:
        return {"score": 0.0, "verdict": "WEAK", "weakest": "LENGTH", "flags": ["vazio"]}
    results, overall, verdict, flags = hookscore.run(text)
    weakest = min(hookscore.CHECKS, key=lambda c: results[c][0])
    return {"score": round(overall, 1), "verdict": verdict, "weakest": weakest, "flags": flags}


_REWRITE_SYSTEM = (
    "You rewrite Instagram carousel hooks for a calm, honest self-compassion account (@keepcalmnbepositive). "
    "Keep the meaning and the gentle tone. Make each hook specific: a concrete moment, scene or behaviour "
    "the reader recognises, and include a number, count or time whenever it's honest (\"At 2 a.m.\", \"eleven times\", "
    "\"10 minutes\"). Tension in the first three words. 6 to 14 words. Use contractions and straight quotes. "
    "No greetings, no 'Sometimes', no emojis, no hashtags, no long dashes, no engagement bait."
)


def improve_weak_hooks(
    posts: list[dict],
    generate: Callable[..., str],
    min_score: float = MIN_HOOK_SCORE,
    key: str = "Image Text",
) -> list[dict]:
    """
    Para cada post com gancho abaixo de min_score pede à IA 3 alternativas (uma só chamada
    para o lote), avalia-as e fica com a melhor se for melhor do que a original.
    Devolve uma lista de alterações [{index, old, new, old_score, new_score}].
    """
    weak = []
    for i, p in enumerate(posts):
        s = score_hook(p.get(key, ""))
        if s["score"] < min_score:
            weak.append((i, p.get(key, ""), s))
    if not weak:
        return []

    items = [{"id": i, "hook": hook, "caption_context": (posts[i].get("Caption") or "")[:300],
              "weakest": s["weakest"]} for i, hook, s in weak]
    user = (
        "Rewrite each hook below. For each id return exactly 3 alternatives. "
        'Reply as JSON: {"hooks": [{"id": <id>, "alternatives": ["...", "...", "..."]}]}.\n\n'
        + json.dumps(items, ensure_ascii=False)
    )
    try:
        raw = generate(system_prompt=_REWRITE_SYSTEM, user_prompt=user, json_mode=True)
        data = json.loads(raw)
    except Exception as e:  # a geração principal continua válida sem a reescrita
        logger.warning("Reescrita de ganchos falhou: %s", e)
        return []

    by_id = {}
    for entry in data.get("hooks", []) if isinstance(data, dict) else []:
        try:
            by_id[int(entry.get("id"))] = [str(a) for a in entry.get("alternatives", []) if str(a).strip()]
        except (TypeError, ValueError):
            continue

    changes = []
    for i, old, old_s in weak:
        candidates = [humanize_text(a) for a in by_id.get(i, [])]
        if not candidates:
            continue
        best = max(candidates, key=lambda c: score_hook(c)["score"])
        best_s = score_hook(best)
        if best_s["score"] > old_s["score"]:
            posts[i][key] = best
            changes.append({"index": i, "old": old, "new": best,
                            "old_score": old_s["score"], "new_score": best_s["score"]})
    return changes


# ── Texto ─────────────────────────────────────────────────────────────────────

_LEXICON = None


def humanize_text(text: str) -> str:
    """Limpa marcas de texto gerado (invisíveis, aspas curvas, travessões, expressões feitas)."""
    global _LEXICON
    if not (text or "").strip():
        return text or ""
    if _LEXICON is None:
        _LEXICON = _humanize.load_lexicon()
    cleaned, _report = _humanize.humanize(text, _LEXICON)
    return cleaned.strip()


def humanize_post(post: dict, fields=("Image Text", "Caption", "Slide2 Text")) -> None:
    """Humaniza os campos de texto de um post no lugar, preservando as linhas em branco dos slides."""
    for f in fields:
        value = post.get(f)
        if not value:
            continue
        if f == "Slide2 Text":
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", value) if p.strip()]
            post[f] = "\n\n".join(humanize_text(p) for p in paragraphs)
        else:
            post[f] = humanize_text(value)


# ── Legenda ───────────────────────────────────────────────────────────────────

_ASK_RE = re.compile(r"\b(save|send|share)\b", re.I)
_BAIT_RE = re.compile(r"\b(tag (a|your)|double[- ]tap|comment (yes|below|a|an)|like if|follow for more)\b", re.I)


def caption_warnings(caption: str) -> list[str]:
    """Avisos sobre a legenda, na lógica do ig-caption (janela do feed, hashtags, um pedido)."""
    caption = (caption or "").strip()
    warnings = []
    if not caption:
        return ["legenda vazia"]
    first = caption.split("\n", 1)[0].strip()
    if len(first) > FEED_VISIBLE_CHARS:
        warnings.append(f"1.ª linha com {len(first)} caracteres (o feed corta aos {FEED_VISIBLE_CHARS})")
    if first.startswith("#") or re.match(r"^[^\w\"']", first):
        warnings.append("1.ª linha começa com hashtag ou emoji")
    tags = re.findall(r"(?:^|\s)#\w+", caption)
    if len(tags) > MAX_HASHTAGS:
        warnings.append(f"{len(tags)} hashtags (máximo {MAX_HASHTAGS})")
    if not _ASK_RE.search(caption):
        warnings.append("sem pedido para guardar/enviar")
    if _BAIT_RE.search(caption):
        warnings.append("tem isco de engagement (tag/double tap/comment)")
    return warnings


def carousel_slide_count(slide2_text: str) -> int:
    return 1 + len([p for p in re.split(r"\n\s*\n", (slide2_text or "").strip()) if p.strip()])
