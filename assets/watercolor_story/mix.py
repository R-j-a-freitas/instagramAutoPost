# Score, foley, voice → out/mix.wav for a watercolor story. Timed by content.json (beats, stops, hits) and events.json.
# Music state per beat: crowd = rising kalimba ostinato, specimen/trio = guitar arpeggio, journey = walking pulse,
# transform = calm then silence then a hang note on the reveal, grow = rising kalimba steps. Silence in every "stop".
# Run with the Lemo-Opuscar venv: LIB=<library> $LIB/.venv/bin/python mix.py <film folder>
import json, os, sys
import numpy as np, soundfile as sf, soxr
HERE = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
LIB = os.environ.get('LIB') or sys.exit('set LIB to the Lemo-Opuscar library folder')
sys.path.insert(0, LIB); os.chdir(LIB)
from core.audio import sampler as S
from core.audio.sfx import SR, add, limit, compress, noise, bp, lp, hp, env_exp, t_, brown, thump, whoosh, norm, creak

C = json.load(open(f'{HERE}/content.json'))
EV = json.load(open(f'{HERE}/events.json'))['ev']; DUR = C['DUR']
N = int(DUR * SR) + SR
music, fol, voice = (np.zeros((N, 2), np.float32) for _ in range(3))
S.seed(7 + C.get('seed', 0))
BEAT = 60 / 84; BAR = 4 * BEAT
score = []
pent = ['D4', 'F#4', 'A4', 'B4', 'D5', 'A4', 'F#4', 'E4']
prog = [['D3', 'A3', 'D4', 'F#4'], ['G2', 'D3', 'G3', 'B3'], ['A2', 'E3', 'A3', 'C#4'], ['B2', 'F#3', 'B3', 'D4']]
bar_i = 0

def arpeggio(a, b, vel=.36):
    global bar_i
    t = a
    while t < b - .3:
        ch = prog[bar_i % 4]
        for k, n in enumerate(ch + ch[2:0:-1]):
            tt = t + k * BEAT * .66
            if tt < b - .2: score.append((tt, 'guitar_nylon', n, 1.4, vel, -.2 + .1 * k))
        if t + BEAT * 2 < b - .4: score.append((t + BEAT * 2, 'kalimba', ['D5', 'B4', 'C#5', 'A4'][bar_i % 4], .9, .38, .35))
        t += BAR; bar_i += 1

for b in C['beats']:
    a, e, ty = b['t0'], b['music_end'], b['type']
    if ty == 'crowd':
        t, i, span = a + .3, 0, max(1, e - a)
        while t < e - .05:
            score.append((t, 'kalimba', pent[i % 8], .6, .42 + .25 * (t - a) / span, -.3 + .6 * ((i * 3) % 5) / 4))
            t += BEAT / 2 if t < a + span * .6 else BEAT / 4; i += 1
        k = 0
        while a + .3 + k * BAR < e - 1:
            score += [(a + .3 + k * BAR, 'guitar_nylon', 'D3', 2.4, .5, -.15), (a + .3 + k * BAR + BEAT, 'guitar_nylon', 'A3', 1.6, .38, .1)]; k += 1
    elif ty == 'journey':
        t, k = a + .4, 0
        while t < e - .2:
            score.append((t, 'guitar_nylon', ['D3', 'A3', 'F#3', 'A3'][k % 4], .5, .34, -.1)); t += BEAT / 2; k += 1
        arpeggio(a + .4, e, .26)
    elif ty == 'grow':
        for k, t in enumerate(b.get('times', [])): score.append((t, 'kalimba', ['D4', 'A4', 'D5'][k % 3], 1.5, .45, 0))
        arpeggio(a + .4, e, .3)
    else:
        arpeggio(a + .3, e)
for h in C['hits']:
    score.append((h['t'], 'hang', h.get('note', 'A4'), 3.5, .6, 0))
    if h.get('chord'): score.append((h['t'], 'guitar_nylon', 'D3', 4.0, .32, -.1))
E = C['ending']
for k, n in enumerate(['D3', 'A3', 'D4', 'F#4', 'A4']): score.append((E['close_t'] + k * BEAT * .75, 'guitar_nylon', n, 3.0, .34, -.2 + .1 * k))
score += [(E['later_t'] + .8, 'kalimba', 'F#4', 1.0, .36, .3), (E['title_t'] + .7, 'kalimba', 'A4', 1.2, .32, .25), (E['handle_t'] + .4, 'kalimba', 'D5', 2.0, .3, -.25)]
mus = S.render(score, dur=N / SR, master=False)
music[:len(mus)] += mus[:N]

def pad(f, d, a=.06):
    tt = t_(d); x = sum(np.sin(2 * np.pi * f * m * tt + m) * g for m, g in [(1, 1), (2, .35), (1.003, .7), (.997, .7)])
    e = np.minimum(1, tt / 1.6) * np.minimum(1, (d - tt) / 1.6); return lp(x * e * a, 1800)
add(music, pad(146.83, DUR), 0, .9, -.3); add(music, pad(220.0, DUR), .01, .9, .3)
for a, b in C['stops']:                                            # real silences: music fully out
    i0, i1 = int(a * SR), int(b * SR); fade = int(.15 * SR)
    music[max(0, i0 - fade):i0] *= np.linspace(1, 0, min(fade, i0))[:, None]; music[i0:i1] *= 0

def wet(v=1.0):
    d = .45; n = bp(noise(d), 300, 1800) * env_exp(d, .1); th = thump(v * .5, 85)
    out = np.zeros(int(d * SR)); out[:len(n)] += n * .5; out[:min(len(th), len(out))] += th[:len(out)] * .6; return out * v
def pencil(d):
    tt = t_(d); return bp(noise(d), 2500, 7000) * (.55 + .45 * np.abs(np.sin(2 * np.pi * 7 * tt))) * np.minimum(1, tt / .03) * np.minimum(1, (d - tt) / .05) * .35
def brush(d=.45):
    tt = t_(d); return bp(noise(d), 700, 3500) * np.sin(np.pi * tt / d) ** 1.5 * (.7 + .3 * np.sin(2 * np.pi * 11 * tt)) * .3
def tap(f=2350):
    tt = t_(.6); return (np.sin(2 * np.pi * f * tt) * .5 + np.sin(2 * np.pi * f * 1.536 * tt) * .3) * env_exp(.6, .08) * .35 + bp(noise(.6), 2000, 6000) * env_exp(.6, .01) * .3
def swell(d, lo, hi, g):
    tt = t_(d); return lp(bp(noise(d), lo, hi), hi) * np.sin(np.pi * tt / d) ** 2 * g
def page():
    d = .5; tt = t_(d); return bp(noise(d), 900, 6000) * np.sin(np.pi * tt / d) ** 3 * .4
def chirp():
    tt = t_(.35); f = 3200 + 1400 * np.sin(np.pi * tt / .35); return np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(.35, .09) * .2
def drops(d=2.0):
    out = np.zeros(int(d * SR)); rng = np.random.default_rng(3)
    for t in rng.uniform(0, d - .1, 26): s = int(t * SR); x = tap(rng.uniform(1800, 3200))[:int(.08 * SR)] * .3; out[s:s + len(x)] += x[:len(out) - s]
    return out
def crackle(d=2.0):
    x = noise(d) * (np.random.default_rng(5).random(int(round(d * SR))) > .997); return hp(x, 1500) * .6 + swell(d, 200, 900, .05)
def step():
    return thump(.18, 120)[:int(.12 * SR)]

ICON_SFX = {
    'breath': lambda: swell(1.6, 300, 2600, .3), 'cup': lambda: tap(), 'glass': lambda: tap(3100), 'song': None,
    'book': page, 'letter': page, 'checklist': lambda: pencil(.6), 'calendar': lambda: pencil(.5), 'bird': chirp, 'feather': lambda: swell(1.2, 2000, 7000, .1),
    'rain': drops, 'storm': lambda: lp(brown(2.4), 300) * .3, 'wave': lambda: swell(2.4, 200, 1500, .35), 'boat': lambda: swell(2.0, 200, 1200, .25),
    'fire': crackle, 'candle': lambda: crackle(1.2) * .5, 'door': lambda: creak(.6), 'door_open': lambda: creak(.8), 'clock': lambda: sum(np.roll(np.pad(tap(4200)[:int(.05 * SR)], (0, int(1.6 * SR))), int(k * .5 * SR)) for k in range(3)) * .6,
    'key': lambda: tap(5200), 'phone': lambda: tap(1600), 'stones': lambda: thump(.3, 140), 'bench': lambda: thump(.25, 90), 'chair': lambda: creak(.3),
}
KAL = {'song': ['A4', 'B4', 'D5'], 'sun': ['D5'], 'moon': ['F#4'], 'heart': ['A4'], 'rainbow': ['D4', 'F#4', 'A4', 'D5'], 'gift': ['A4', 'D5'], 'flower': ['B4'], 'tree': ['D4'], 'sprout': ['E4'], 'plant': ['E4'], 'seed': ['D4'], 'lamp': ['F#4'], 'window': ['A4'], 'house': ['D4']}
for e in EV:
    ty, t = e['type'], e['t']; pan = e.get('pan', 0)
    if ty == 'blot': add(fol, wet(e.get('v', .7)), t, .8, pan * .7)
    elif ty == 'pencil': add(fol, pencil(e.get('d', .4)), t, .9, pan * .5)
    elif ty == 'brush': add(fol, brush(), t, .7, pan)
    elif ty == 'mist': add(fol, whoosh(2.6, .6), t, .5, 0); add(fol, lp(brown(2.8), 900) * .08, t, 1, 0)
    elif ty == 'lift': add(fol, brush(.25), t, .9, 0)
    elif ty == 'reveal': add(fol, wet(.5), t, .6, 0)
    elif ty == 'title': add(fol, thump(.35, 70), t, .5, 0)
    elif ty == 'step': add(fol, step(), t, .5, 0)
    elif ty == 'icon':
        ic = e.get('icon'); f = ICON_SFX.get(ic)
        add(fol, brush(.5), t, .5, pan)
        if f: add(fol, f(), t + .2, .9, pan)
        for k, n in enumerate(KAL.get(ic, [])): add(music, S.note('kalimba', n, .8, .4), t + .3 + k * .18, 1, pan)
room = lp(brown(N / SR), 500) * .012
add(fol, room, 0, 1, 0)
for a, b in C['stops']: add(fol, lp(brown(b - a + .4), 600) * .02, a, 1, 0)

vmask = np.zeros(N, np.float32)
for ln in C['lines']:
    x, sr = sf.read(f"{HERE}/voices/{ln['id']}.wav", dtype='float32')
    if x.ndim > 1: x = x.mean(1)
    if sr != SR: x = soxr.resample(x, sr, SR)
    x = norm(compress(x, thr=.18, ratio=4), .9)
    add(voice, x, ln['t'], 1, 0); s = int(ln['t'] * SR); vmask[s:s + len(x)] = 1

def rms(x): return float(np.sqrt(np.mean(x[np.abs(x).sum(1) > 1e-4] ** 2)) + 1e-9)
vr = rms(voice)
music *= (vr / rms(music)) * 10 ** (-11 / 20)
kern = np.ones(int(.25 * SR)) / int(.25 * SR); env = np.convolve(vmask, kern, 'same')
music *= (1 - (1 - 10 ** (-4 / 20)) * env)[:, None]
fol *= (vr / rms(fol)) * 10 ** (-9 / 20)
mix = S.room(music, size=.45, mix=.2) + S.room(fol, size=.3, mix=.12) + voice
mix = limit(mix / np.abs(mix).max() * .8, .82)
os.makedirs(f'{HERE}/out', exist_ok=True)
sf.write(f'{HERE}/out/mix.wav', mix[:int(DUR * SR)], SR)
print('mix.wav', round(DUR, 2), 's')
