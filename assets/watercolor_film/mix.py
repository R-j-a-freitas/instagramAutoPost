# Score, foley, voice → out/mix.wav, all timed by content.json (the same anchors the page uses).
# Run with the Lemo-Opuscar venv: LIB=<library> $LIB/.venv/bin/python mix.py <film folder>
import json, os, sys
import numpy as np, soundfile as sf, soxr
HERE = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
LIB = os.environ.get('LIB') or sys.exit('set LIB to the Lemo-Opuscar library folder')
sys.path.insert(0, LIB); os.chdir(LIB)
from core.audio import sampler as S
from core.audio.sfx import SR, add, limit, compress, noise, bp, lp, hp, env_exp, t_, brown, thump, whoosh, norm

C = json.load(open(f'{HERE}/content.json')); A = C['A']
EV = json.load(open(f'{HERE}/events.json'))['ev']; DUR = A['DUR']
N = int(DUR * SR) + SR
music, fol, voice = (np.zeros((N, 2), np.float32) for _ in range(3))
S.seed(7 + C.get('seed', 0))
BEAT = 60 / 84; BAR = 4 * BEAT
TA, ONE_T, L6 = A['TA'], A['one'], C['lines']['l6']['t']
STOP = TA - .8                                                    # the brush lifts: music out until the one note

# ---------- score ----------
score = []
pent = ['D4', 'F#4', 'A4', 'B4', 'D5', 'A4', 'F#4', 'E4']
t, i = .3, 0                                                      # A: kalimba ostinato, density rises
while t < STOP - .05:
    step = BEAT / 2 if t < TA * .61 else BEAT / 4
    score.append((t, 'kalimba', pent[i % len(pent)], .6, .42 + .25 * t / TA, -.3 + .6 * ((i * 3) % 5) / 4))
    t += step; i += 1
b = 0
while .3 + b * BAR < STOP - 1:
    score.append((.3 + b * BAR, 'guitar_nylon', 'D3', 2.4, .5, -.15))
    score.append((.3 + b * BAR + BEAT, 'guitar_nylon', 'A3', 1.6, .38, .1)); b += 1
score.append((ONE_T, 'hang', 'A4', 3.5, .62, 0))                  # the first sound after the silence
prog = [['D3', 'A3', 'D4', 'F#4'], ['G2', 'D3', 'G3', 'B3'], ['A2', 'E3', 'A3', 'C#4'], ['B2', 'F#3', 'B3', 'D4']]
t0, bar = ONE_T + BEAT * 2, 0                                     # B: guitar arpeggio D–G–A–Bm, sparse kalimba
while t0 + bar * BAR < L6 - 1.7:
    ch = prog[bar % 4]
    for k, n in enumerate(ch + ch[2:0:-1]):
        tt = t0 + bar * BAR + k * BEAT * .66
        if tt < L6 - 1.7: score.append((tt, 'guitar_nylon', n, 1.4, .36, -.2 + .1 * k))
    if t0 + bar * BAR + BEAT * 2 < L6 - 2.0:
        score.append((t0 + bar * BAR + BEAT * 2, 'kalimba', ['D5', 'B4', 'C#5', 'A4'][bar % 4], .9, .4, .35))
    bar += 1
for k, n in enumerate(['D3', 'A3', 'D4', 'F#4', 'A4']):            # C: resolve on D, the hang rings under the title
    score.append((L6 + k * BEAT * .75, 'guitar_nylon', n, 3.0, .34, -.2 + .1 * k))
score += [(A['later'] + .8, 'kalimba', 'F#4', 1.0, .36, .3), (A['title'], 'hang', 'D4', 4.5, .6, 0), (A['title'], 'guitar_nylon', 'D3', 4.0, .32, -.1),
          (A['title'] + .7, 'kalimba', 'A4', 1.2, .32, .25), (A['handle'] + .4, 'kalimba', 'D5', 2.0, .3, -.25)]
mus = S.render(score, dur=N / SR, master=False)
music[:len(mus)] += mus[:N]

def pad(f, d, a=.06):                                             # soft pad: detuned sines, slow swells
    tt = t_(d); x = sum(np.sin(2 * np.pi * f * m * tt + m) * g for m, g in [(1, 1), (2, .35), (1.003, .7), (.997, .7)])
    e = np.minimum(1, tt / 1.6) * np.minimum(1, (d - tt) / 1.6); return lp(x * e * a, 1800)
for st, d, f in [(.2, STOP - .1, 146.83), (.2, STOP - .1, 220.0), (ONE_T + .2, L6 - 1.4 - ONE_T, 146.83), (ONE_T + .2, L6 - 1.4 - ONE_T, 185.0),
                 (L6 - 1.0, DUR - L6 + 1.0, 146.83), (L6 - 1.0, DUR - L6 + 1.0, 220.0)]:
    p = pad(f, d); add(music, p, st, .9, -.3); add(music, p, st + .01, .9, .3)
music[int(STOP * SR):int(ONE_T * SR)] *= 0

# ---------- foley ----------
def wet(v=1.0):                                                   # a wet brush dab blooming into paper
    d = .45; n = bp(noise(d), 300, 1800) * env_exp(d, .1); th = thump(v * .5, 85)
    out = np.zeros(int(d * SR)); out[:len(n)] += n * .5; out[:min(len(th), len(out))] += th[:len(out)] * .6; return out * v
def pencil(d):
    tt = t_(d); x = bp(noise(d), 2500, 7000) * (.55 + .45 * np.abs(np.sin(2 * np.pi * 7 * tt))) * np.minimum(1, tt / .03) * np.minimum(1, (d - tt) / .05)
    return x * .35
def brush(d=.45):
    tt = t_(d); return bp(noise(d), 700, 3500) * np.sin(np.pi * tt / d) ** 1.5 * (.7 + .3 * np.sin(2 * np.pi * 11 * tt)) * .3
def tap():
    tt = t_(.6); x = (np.sin(2 * np.pi * 2350 * tt) * .5 + np.sin(2 * np.pi * 3610 * tt) * .3) * env_exp(.6, .08)
    return x * .35 + bp(noise(.6), 2000, 6000) * env_exp(.6, .01) * .3
def breath_s():
    d = 1.6; tt = t_(d); return lp(bp(noise(d), 300, 2600), 2200) * np.sin(np.pi * tt / d) ** 2 * .3
def steam_s():
    d = 3.0; tt = t_(d); return hp(noise(d), 3000) * np.sin(np.pi * tt / d) ** 2 * .05
def page():
    d = .5; tt = t_(d); return bp(noise(d), 900, 6000) * np.sin(np.pi * tt / d) ** 3 * .4
for e in EV:
    ty, t = e['type'], e['t']; pan = e.get('pan', 0)
    if ty == 'blot': add(fol, wet(e.get('v', .7)), t, .8, pan * .7)
    elif ty == 'pencil': add(fol, pencil(e.get('d', .4)), t, .9, pan * .5)
    elif ty == 'brush': add(fol, brush(), t, .7, pan)
    elif ty == 'mist': add(fol, whoosh(2.6, .6), t, .5, 0); add(fol, lp(brown(2.8), 900) * .08, t, 1, 0)
    elif ty == 'lift': add(fol, brush(.25), t, .9, 0)
    elif ty == 'one': add(fol, wet(.5), t + .05, .6, .1)
    elif ty == 'title': add(fol, thump(.35, 70), t, .5, 0)
    elif ty == 'icon':
        ic = e.get('icon')
        if ic == 'breath': add(fol, breath_s(), t, .9, pan)
        elif ic == 'cup': add(fol, tap(), t, .8, pan); add(fol, steam_s(), t + .4, 1, pan)
        elif ic == 'song':
            for k, n in enumerate(['A4', 'B4', 'D5']): add(music, S.note('kalimba', n, .8, .45), t + k * .18, 1, pan)
        elif ic == 'sun': add(music, S.note('hang', 'D5', 2.0, .4), t, 1, pan)
        elif ic == 'book': add(fol, page(), t, .9, pan); add(fol, page(), t + .35, .6, pan)
        else: add(fol, brush(.6), t, .8, pan); add(music, S.note('kalimba', 'E4', .8, .35), t + .5, 1, pan)
room = lp(brown(N / SR), 500) * .012                              # room tone, a little louder in the two silences
add(fol, room, 0, 1, 0); add(fol, lp(brown(ONE_T - STOP + .4), 600) * .02, STOP + .2, 1, 0); add(fol, lp(brown(1.2), 600) * .015, L6 - 1.4, 1, 0)

# ---------- voice ----------
vmask = np.zeros(N, np.float32)
for k, ln in C['lines'].items():
    x, sr = sf.read(f'{HERE}/voices/{k}.wav', dtype='float32')
    if x.ndim > 1: x = x.mean(1)
    if sr != SR: x = soxr.resample(x, sr, SR)
    x = norm(compress(x, thr=.18, ratio=4), .9)
    add(voice, x, ln['t'], 1, 0); s = int(ln['t'] * SR); vmask[s:s + len(x)] = 1

# ---------- balance and duck ----------
def rms(x): return float(np.sqrt(np.mean(x[np.abs(x).sum(1) > 1e-4] ** 2)) + 1e-9)
vr = rms(voice)
music *= (vr / rms(music)) * 10 ** (-11 / 20)                     # voice ≈ 11 dB over the music
kern = np.ones(int(.25 * SR)) / int(.25 * SR); env = np.convolve(vmask, kern, 'same')
music *= (1 - (1 - 10 ** (-4 / 20)) * env)[:, None]               # duck 4 dB under the voice
fol *= (vr / rms(fol)) * 10 ** (-9 / 20)
mix = S.room(music, size=.45, mix=.2) + S.room(fol, size=.3, mix=.12) + voice
mix = limit(mix / np.abs(mix).max() * .8, .82)
os.makedirs(f'{HERE}/out', exist_ok=True)
sf.write(f'{HERE}/out/mix.wav', mix[:int(DUR * SR)], SR)
print('mix.wav', round(DUR, 2), 's')
