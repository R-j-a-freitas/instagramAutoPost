// Watercolor film template (from "One Feeling at a Time"): a page crowded with feelings, a mist that keeps one,
// the person it belongs to, three grounding things, an unfinished note, the title.
// Pure function of t. Every text and time comes from content.js (window.CONTENT), written by watercolor_film.py.
// World = one paper sheet (x -260..1340, y -340..2260); frame 1080×1920.
const C = window.CONTENT, A = C.A;
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const DUR = A.DUR, BEAT = 60 / 84;
window.DUR = DUR;
window.SUBS = C.subs;

// ---------- palette ----------
const FEEL = ['#7d93a8', '#c9a24a', '#8ea07a', '#8a6a86', '#b98378', '#6f8f96', '#a39a6a', '#9c7f9e'];
const ONE = '#d9744e';                 // the one feeling, the film's single accent
const SKIN = '#9fb0b8', SHADE = '#6f8494', BREATH = '#6f9fbf', CUP = '#c9a86a', LEAF = '#7f9a5a', SUN = '#e3b04b';

// ---------- camera: one world → screen function ----------
const camZ = monotone(C.cam.z), camX = monotone(C.cam.x), camY = monotone(C.cam.y);
const cam = t => ({ z: camZ(t), x: camX(t), y: camY(t) });
const toScr = (c, x, y) => [540 + (x - c.x) * c.z, 960 + (y - c.y) * c.z];
const setCam = c => ctx.setTransform(c.z, 0, 0, c.z, 540 - c.x * c.z, 960 - c.y * c.z);

// three places for the grounding things, right of the figure: centre, scale, label offset
const SLOTS = [{ x: 900, y: 640, sc: 1, lx: 40, ly: -110 }, { x: 1030, y: 1170, sc: 1, lx: -150, ly: 160 }, { x: 1180, y: 830, sc: .85, lx: -40, ly: -130 }];
const RIGHT = 1300;                    // labels never run past this world x

let PAPER_IMG, BLOTS = [], NOTES = [], FIG, FIG_SPR, ICONS = [], UNDER, TITLE_PX = 86;
const EV = [];
let TX = [];                           // texts drawn this frame, for readcheck

// ---------- annotations ----------
function hand(id, txt, x, y, p, o = {}) {          // world coords, revealed left to right like writing
  if (p <= 0) return;
  const size = o.size || 44;
  ctx.save(); ctx.font = `${o.w || 500} ${size}px Caveat`; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
  const w = ctx.measureText(txt).width; if (x + w > RIGHT) x = RIGHT - w;
  ctx.translate(x, y); if (o.rot) ctx.rotate(o.rot);
  ctx.beginPath(); ctx.rect(-6, -size, (w + 12) * eo(p), size * 2); ctx.clip();
  ctx.shadowColor = rgba(PAPER, .95); ctx.shadowBlur = 12; ctx.fillStyle = rgba(o.col || INK, o.a ?? .9);
  ctx.fillText(txt, 0, 0); ctx.fillText(txt, 0, 0);
  ctx.restore();
  TX.push({ id, text: txt, wx0: x - 6, wy0: y - size * .6, wx1: x + w + 6, wy1: y + size * .6 });
}
function leader(x0, y0, x1, y1, p, bend = 20, a = .75) {
  if (p <= 0) return;
  const pts = qcurve(x0, y0, x1, y1, bend, 16), m = Math.max(1, Math.round(16 * clamp(p)));
  ctx.beginPath(); for (let i = 0; i <= m; i++) i ? ctx.lineTo(pts[i][0], pts[i][1]) : ctx.moveTo(pts[i][0], pts[i][1]);
  ctx.strokeStyle = rgba(INK, a); ctx.lineWidth = 2.2; ctx.lineCap = 'round'; ctx.stroke();
  if (p >= 1) { ctx.beginPath(); ctx.arc(x1, y1, 4, 0, 7); ctx.fillStyle = rgba(INK, a); ctx.fill(); }
}

// ---------- builders (all under fixed seeds) ----------
function blotStrokes(r, col) {
  const S = [];
  clump(S, 0, 0, r * .55, 9, [col], { sx: 1.1, sy: 1, l0: r * .5, l1: r * .95, w0: r * .38, w1: r * .62, a0: .32, a1: .55 });
  clump(S, 0, 0, r * .4, 7, [col, mixc(col, INK, .25)], { sx: 1, sy: .9, l0: r * .2, l1: r * .45, w0: r * .14, w1: r * .26, a0: .45, a1: .75 });
  return S;
}
function buildBlots() {
  BLOTS = [];
  // the one feeling comes first and stays
  BLOTS.push(withSeed(101, () => { const S = blotStrokes(62, ONE); return { x: 600, y: 1010, r: 62, col: ONE, t: .3, S, spr: sprite(S), one: true }; }));
  const times = []; let t = .3 + BEAT, end = A.TA - .9;
  while (t < end) { times.push(t); t += t < A.TA * .47 ? BEAT : t < A.TA * .76 ? BEAT / 2 : BEAT / 4; }
  withSeed(202 + C.seed, () => {
    for (let i = 0; i < times.length; i++) {
      let best = null;
      for (let k = 0; k < 40; k++) {
        const x = rnd(110, 970), y = rnd(240, 1240), r = rnd(38, 90);
        const d = Math.min(...BLOTS.map(b => Math.hypot(b.x - x, b.y - y) - b.r - r));
        if (!best || d > best.d) best = { x, y, r, d };
      }
      const col = FEEL[i % FEEL.length], S = blotStrokes(best.r, col);
      BLOTS.push({ x: best.x, y: best.y, r: best.r, col, t: times[i], S, spr: sprite(S) });
    }
  });
  for (const b of BLOTS) EV.push({ t: b.t, type: 'blot', pan: (b.x - 540) / 540, v: b.one ? 1 : .55 + b.r / 200 });
}
function buildNotes() {
  const o1 = BLOTS[0], boxes = [[o1.x - o1.r * 1.5, o1.y - o1.r * 1.5, o1.x + o1.r * 1.5, o1.y + o1.r * 1.5]];   // keep the one feeling clear
  NOTES = withSeed(303 + C.seed, () => C.notes.map(([t, txt], i) => {
    const cands = BLOTS.filter(b => b.t < t - .2 && !b.one), w = txt.length * 19 + 20;
    for (let k = 0; k < cands.length; k++) {
      const b = cands[(i * 7 + k * 3) % cands.length], side = b.x < 540 ? 1 : -1;
      const lx = b.x + side * (b.r + 50) - (side < 0 ? txt.length * 19 : 0);
      for (const ly of [b.y - b.r - 40, b.y + b.r + 30]) {          // above the blot, else below it
        const box = [lx - 10, ly - 34, lx + w, ly + 34];
        if (lx > 60 && lx + w < 1020 && ly > 200 && ly < 1330 && !boxes.some(o => box[0] < o[2] && box[2] > o[0] && box[1] < o[3] && box[3] > o[1])) {
          boxes.push(box);
          EV.push({ t: t + .3, type: 'pencil', d: .25 + txt.length * .05, pan: (b.x - 540) / 540 });
          return { t, txt, b, lx, ly, rot: rnd(-.09, .09) };
        }
      }
    }
    return null;                                                     // no free place: leave this note out
  }).filter(Boolean));
}
function buildFigure() {
  // a bust silhouette filled with overlapping diagonal washes: contour first, then fill, then a little ink
  FIG = withSeed(404, () => {
    const cx = 560, hy = 690, hr = 104, top = hy + 178, bot = hy + 640;
    const halfW = y => { const u = clamp((y - top) / 150); return lerp(46, 262, ss(u)) + 28 * clamp((y - top - 150) / 340); };
    const fade = y => 1 - ss(seg(y, bot - 220, bot));
    const S = [];
    for (let i = 0; i < 10; i++) {                                    // head contour
      const a0 = i / 10 * Math.PI * 2, a1 = a0 + .8, am = (a0 + a1) / 2;
      S.push(mk(qctrl(cx + Math.cos(a0) * hr, hy + Math.sin(a0) * hr * 1.08, cx + Math.cos(am) * hr * 1.12, hy + Math.sin(am) * hr * 1.2,
        cx + Math.cos(a1) * hr, hy + Math.sin(a1) * hr * 1.08, 10), rnd(26, 34), SKIN, { prof: 'leaf', nb: 3, a: rnd(.4, .5) }));
    }
    for (let i = 0; i < 18; i++) {                                    // head fill, soft and even
      const a = rnd(0, Math.PI * 2), rr = hr * .72 * Math.sqrt(rnd()), x = cx + Math.cos(a) * rr, y = hy + Math.sin(a) * rr * 1.08, d = -.7 + rnd(-.3, .3);
      S.push(mk(polar(x - Math.cos(d) * 30, y - Math.sin(d) * 30, d, 60, rnd(-6, 6), 6), rnd(50, 66), SKIN, { prof: 'leaf', nb: 0, a: rnd(.2, .3) }));
    }
    for (let i = 0; i < 8; i++) {                                     // hair along the crown
      const a0 = Math.PI * (1.05 + i * .11), a1 = a0 + .32;
      S.push(mk(qcurve(cx + Math.cos(a0) * hr * .98, hy + Math.sin(a0) * hr * 1.02, cx + Math.cos(a1) * hr * 1.02, hy + Math.sin(a1) * hr * 1.06, -8, 6), rnd(22, 30), SHADE, { prof: 'leaf', nb: 3, a: .5 }));
    }
    S.push(mk(qcurve(cx - 4, hy + 96, cx - 2, top + 30, 0, 8), 64, SKIN, { prof: 'even', nb: 3, a: .38 }));   // neck
    for (const s of [-1, 1]) {                                        // shoulder contours
      const pts = []; for (let i = 0; i <= 16; i++) { const y = top + i / 16 * 330; pts.push([cx + s * halfW(y), y]); }
      S.push(mk(pts, 30, SKIN, { prof: 'brush', nb: 4, a: .5 }));
    }
    const fill = [];
    for (let i = 0; i < 150; i++) {                                   // torso fill
      const y = rnd(top + 20, bot), hw = halfW(y), x = cx + rnd(-hw * .92, hw * .92), d = -.75 + rnd(-.28, .28), len = rnd(70, 130);
      fill.push([y, mk(polar(x - Math.cos(d) * len / 2, y - Math.sin(d) * len / 2, d, len, rnd(-10, 10), 6), rnd(44, 72), rnd() < .3 ? SHADE : SKIN, { prof: 'leaf', nb: rnd() < .4 ? 2 : 0, a: rnd(.16, .26) * fade(y) })]);
    }
    fill.sort((a, b) => a[0] - b[0]); for (const [, st] of fill) S.push(st);
    for (const s of [-1, 1]) {                                        // one thin ink edge on each shoulder
      const pts = []; for (let i = 0; i <= 12; i++) { const y = top + 6 + i / 12 * 200; pts.push([cx + s * (halfW(y) + 8), y]); }
      S.push(mk(pts, 3.5, INK2, { prof: 'tip', nb: 0, a: .38, rough: .4 }));
    }
    S.push(mk(qctrl(cx - 100, hy + 20, cx - 112, hy - 116, cx + 30, hy - 112, 14), 3.5, INK2, { prof: 'tip', nb: 0, a: .4, rough: .4 }));
    return S;
  });
  FIG_SPR = sprite(FIG);
  for (let t = A.fig0 + .1; t < A.fig1 - .1; t += .42) EV.push({ t, type: 'brush', pan: -.1 });
}

// grounding things, in local coordinates around (0,0); each returns { S: strokes, steam?: strokes }
const ICON = {
  breath(w) {
    const pts = []; for (let i = 0; i <= 40; i++) { const s = i / 40; pts.push([-w / 2 + s * w, 30 - s * 60 + Math.sin(s * Math.PI * 3) * 34]); }
    return { S: [mk(pts, 14, BREATH, { prof: 'even', a: .78, rough: .3 })], line: true };
  },
  cup() {
    const S = [];
    S.push(mk(qctrl(-95, -70, -100, 90, 0, 92, 14), 26, CUP, { prof: 'even', a: .6 }));
    S.push(mk(qctrl(0, 92, 100, 90, 95, -70, 14), 26, CUP, { prof: 'even', a: .6 }));
    for (let k = 0; k < 4; k++) S.push(mk(qcurve(-86, -40 + k * 34, 86, -40 + k * 34, 6, 10), 30, mixc(CUP, '#e8d6a8', k / 4), { prof: 'even', a: .42 }));
    S.push(mk(qcurve(-98, -72, 98, -72, -10, 12), 9, mixc(CUP, INK, .3), { prof: 'even', a: .6 }));
    S.push(mk(qctrl(92, -40, 160, -10, 88, 40, 10), 14, CUP, { prof: 'even', a: .6 }));
    S.push(mk(qcurve(-140, 104, 140, 104, 4, 12), 10, mixc(CUP, INK, .45), { prof: 'even', a: .5 }));
    const steam = [0, 1, 2].map(k => { const p = []; for (let i = 0; i <= 20; i++) { const s = i / 20; p.push([-40 + k * 40 + Math.sin(s * 5 + k) * 16, -110 - s * 190]); } return mk(p, 8, '#b7c3c8', { prof: 'tip', nb: 2, a: .55 }); });
    return { S, steam };
  },
  song() {
    const x = -35, y = 64;
    return { S: [mk(qcurve(x, y, x, y - 110, 0, 6), 6, INK2, { prof: 'even', nb: 0, a: .8 }),
      mk(qcurve(x + 70, y - 18, x + 70, y - 128, 0, 6), 6, INK2, { prof: 'even', nb: 0, a: .8 }),
      mk(qcurve(x, y - 110, x + 70, y - 128, -6, 6), 12, INK2, { prof: 'even', nb: 0, a: .8 }),
      mk(polar(x - 16, y + 4, 0, 34, 10, 6), 22, ONE, { prof: 'leaf', a: .75 }),
      mk(polar(x + 54, y - 14, 0, 34, 10, 6), 22, ONE, { prof: 'leaf', a: .75 })] };
  },
  sprout() {
    return { S: [mk(qcurve(-100, 80, 100, 80, -26, 12), 30, '#8a6a4a', { prof: 'even', a: .55 }),
      mk(qcurve(0, 74, 8, -80, 14, 10), 12, LEAF, { prof: 'tip', a: .8 }),
      mk(polar(6, -20, -2.5, 90, 22, 8), 38, LEAF, { prof: 'leaf', a: .7 }),
      mk(polar(8, -52, -.55, 96, -22, 8), 42, mixc(LEAF, '#c9c96a', .3), { prof: 'leaf', a: .7 }),
      mk(polar(8, -78, -1.7, 44, 8, 6), 22, LEAF, { prof: 'leaf', a: .75 })] };
  },
  sun() {
    const S = []; clump(S, 0, 0, 34, 12, [SUN, mixc(SUN, ONE, .3)], { l0: 30, l1: 56, w0: 30, w1: 46, a0: .45, a1: .7 });
    for (let k = 0; k < 10; k++) { const a = k / 10 * Math.PI * 2; S.push(mk(polar(Math.cos(a) * 78, Math.sin(a) * 78, a, 46, 4, 6), 11, mixc(SUN, ONE, .2), { prof: 'tip', nb: 0, a: .75 })); }
    return { S };
  },
  book() {
    const S = [], PG = '#e6d6b0';
    for (const s of [-1, 1]) {
      for (let k = 0; k < 3; k++) S.push(mk(qcurve(s * 8, -48 + k * 36, s * 140, -60 + k * 36 + 10, s * 8, 10), 40, PG, { prof: 'even', a: .5 }));
      for (let k = 0; k < 3; k++) S.push(mk(qcurve(s * 30, -40 + k * 30, s * 118, -48 + k * 30, s * 4, 8), 3, INK2, { prof: 'even', nb: 0, a: .35 }));
    }
    S.push(mk(qcurve(0, -62, 0, 70, 0, 8), 4, INK2, { prof: 'even', nb: 0, a: .7 }));
    S.push(mk(qcurve(-150, 78, 150, 78, -14, 12), 12, '#8a6a4a', { prof: 'even', a: .6 }));
    return { S };
  },
};
function buildIcons() {
  ICONS = withSeed(505, () => C.items.map((it, k) => {
    const sl = SLOTS[k], g = it.icon === 'breath' ? ICON.breath(k === 0 ? 440 : 280) : (ICON[it.icon] || ICON.cup)();
    return { ...it, sl, ...g, spr: g.line ? null : sprite(g.S) };
  }));
  for (const it of ICONS) EV.push({ t: it.t, type: 'icon', icon: it.icon, pan: (it.sl.x - 700) / 600 });
}
function buildEnding() {
  ctx.font = '600 60px Caveat'; const w = ctx.measureText(C.later).width;
  UNDER = withSeed(606, () => mk(qcurve(500, 1368, 520 + w + 40, 1360, 6, 24), 9, ONE, { prof: 'brush', a: .8 }));
  ctx.font = `600 ${TITLE_PX}px "Cormorant Garamond"`;
  while (ctx.measureText(C.title).width > 920 && TITLE_PX > 48) { TITLE_PX -= 2; ctx.font = `600 ${TITLE_PX}px "Cormorant Garamond"`; }
  EV.push({ t: A.lift, type: 'lift' }, { t: A.mist0, type: 'mist' }, { t: A.one, type: 'one' }, { t: A.here, type: 'pencil', d: .4, pan: .3 });
  EV.push({ t: A.later, type: 'pencil', d: 2.0, pan: -.1 }, { t: A.title, type: 'title' }, { t: A.under1 + .1, type: 'lift' });
}

// ---------- drawing ----------
function drawBlot(b, t, am = 1) {
  const p = seg(t, b.t, b.t + .55); if (p <= 0) return;
  const bloom = 1 + .2 * eo(seg(t, b.t + .4, b.t + 3.2)) + (b.one && t > A.one ? .05 * Math.sin((t - A.one) * 1.6) : 0);
  ctx.save(); ctx.translate(b.x, b.y); ctx.scale(bloom, bloom); ctx.globalAlpha = am;
  if (p < 1) drawList(ctx, b.S, p); else ctx.drawImage(b.spr.cv, b.spr.x0, b.spr.y0);
  ctx.restore();
}
function mist(t) {                      // paper-coloured layers rise and wash the crowded page back to paper
  for (let k = 0; k < 3; k++) {
    const q = eio(seg(t, A.mist0 + k * .3, A.mist0 + 2.2 + k * .2)); if (q <= 0) continue;
    const base = lerp(2350, -420, q), Al = k < 2 ? .6 : 1;
    for (let j = 0; j < 6; j++) {          // six stacked passes along the same wave: a soft edge that follows it
      const off = j * 26, pts = [];
      for (let x = -300; x <= 1400; x += 20) pts.push([x, base + off + 46 * Math.sin(x * .006 + k * 2.1 + t * .9) + 22 * Math.sin(x * .019 + k)]);
      ctx.save(); ctx.beginPath(); pts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
      ctx.lineTo(1400, 2400); ctx.lineTo(-300, 2400); ctx.closePath(); ctx.clip();
      ctx.globalAlpha = Al >= 1 ? (j < 5 ? .35 : 1) : 1 - Math.pow(1 - Al, 1 / 6);
      ctx.drawImage(PAPER_IMG, -260, -340); ctx.restore();
    }
  }
}
function drawIcon(it, t, f) {
  const p = seg(t, it.t, it.t + (it.line ? 1.6 : 1.2)); if (p <= 0) return;
  ctx.save(); ctx.translate(it.sl.x, it.sl.y); ctx.scale(it.sl.sc, it.sl.sc);
  if (it.line) drawS(ctx, it.S[0], eio(p));
  else if (p < 1) drawList(ctx, it.S, p); else ctx.drawImage(it.spr.cv, it.spr.x0, it.spr.y0);
  if (it.steam) it.steam.forEach((s, k) => {
    const q = seg(t, it.t + .9 + k * .2, it.t + 2 + k * .2); if (q <= 0) return;
    ctx.save(); const sk = .05 * Math.sin(t * 1.3 + k * 2); ctx.transform(1, 0, sk, 1, 0, 0); drawS(ctx, s, q, null, .9 - .3 * Math.sin(t * .8 + k) ** 2); ctx.restore();
  });
  ctx.restore();
  if (f > 0) { ctx.globalAlpha = f; hand('item' + it.label, it.label, it.sl.x + it.sl.lx, it.sl.y + it.sl.ly, seg(t, it.t + .3, it.t + 1.0), { size: 44 }); ctx.globalAlpha = 1; }
}
function wrap(txt, maxW) {
  const words = txt.split(' '), lines = []; let cur = '';
  for (const w of words) { const s = cur ? cur + ' ' + w : w; if (ctx.measureText(s).width > maxW && cur) { lines.push(cur); cur = w; } else cur = s; }
  if (cur) lines.push(cur); return lines;
}
function subtitles(t) {
  const s = C.subs.find(x => t >= x.t0 && t < x.t1); if (!s) return;
  const f = ss(seg(t, s.t0, s.t0 + .25)) * (1 - ss(seg(t, s.t1 - .25, s.t1)));
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.font = 'italic 500 54px "Cormorant Garamond"'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  const L = wrap(s.text, 900); ctx.shadowColor = rgba(PAPER, 1); ctx.shadowBlur = 16; ctx.fillStyle = rgba(INK, .8 * f);
  L.forEach((l, i) => { const y = 1500 + (i - (L.length - 1) / 2) * 62; ctx.fillText(l, 540, y); ctx.fillText(l, 540, y); });
  ctx.restore();
}

function render(t) {
  TX = [];
  const c = cam(t);
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.fillStyle = PAPER; ctx.fillRect(0, 0, 1080, 1920);
  setCam(c); ctx.drawImage(PAPER_IMG, -260, -340);
  // act 1: the crowded page (gone once the mist has passed)
  if (t < A.crowdEnd) {
    for (const b of BLOTS) if (!b.one) drawBlot(b, t, 1 - .25 * seg(t, A.TA - .8, A.mist0));
    for (const n of NOTES) {
      leader(n.lx + (n.b.x < 540 ? -10 : n.txt.length * 19 + 10), n.ly + (n.ly < n.b.y ? 14 : -14), n.b.x + (n.b.x < 540 ? .5 : -.5) * n.b.r, n.b.y + (n.ly < n.b.y ? -.5 : .5) * n.b.r, seg(t, n.t, n.t + .4), 14);
      hand('n_' + n.txt, n.txt, n.lx, n.ly, seg(t, n.t + .2, n.t + .9), { rot: n.rot, size: 46 });
    }
    mist(t);
  }
  // act 2: the person the feeling belongs to
  const pf = seg(t, A.fig0, A.fig1);
  if (pf > 0) { if (pf < 1) drawList(ctx, FIG, pf); else ctx.drawImage(FIG_SPR.cv, FIG_SPR.x0, FIG_SPR.y0); }
  drawBlot(BLOTS[0], t);
  const fNotes = 1 - ss(seg(t, A.fade0, A.fade0 + .8));
  if (t > A.here && fNotes > 0) { ctx.globalAlpha = fNotes; leader(820, 900, 640, 990, seg(t, A.here, A.here + .6), 18); hand('here', C.here, 830, 870, seg(t, A.here + .3, A.here + 1.1), { size: 52 }); ctx.globalAlpha = 1; }
  // three grounding things
  for (const it of ICONS) drawIcon(it, t, fNotes);
  // ending: the unfinished note and the title
  hand('later', C.later, 520, 1320, seg(t, A.later, A.later + 2.2), { size: 60, w: 600 });
  drawS(ctx, UNDER, .82 * eio(seg(t, A.under0, A.under1)));
  if (t > A.title) {
    const pt = seg(t, A.title, A.title + 1.2);
    ctx.save(); ctx.font = `600 ${TITLE_PX}px "Cormorant Garamond"`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    const w = ctx.measureText(C.title).width;
    ctx.beginPath(); ctx.rect(690 - w / 2 - 10, 330, (w + 20) * eo(pt), 140); ctx.clip();
    ctx.shadowColor = rgba(PAPER, 1); ctx.shadowBlur = 14; ctx.fillStyle = rgba(INK, .9); ctx.fillText(C.title, 690, 400); ctx.restore();
    TX.push({ id: 'title', text: C.title, wx0: 690 - w / 2, wy0: 350, wx1: 690 + w / 2, wy1: 450 });
  }
  if (t > A.handle && C.handle) {
    ctx.save(); ctx.font = '400 30px "IBM Plex Mono"'; ctx.textAlign = 'center'; ctx.letterSpacing = '6px';
    ctx.fillStyle = rgba(INK2, .75 * ss(seg(t, A.handle, A.handle + .8))); ctx.fillText(C.handle, 690, 486); ctx.restore();
    TX.push({ id: 'handle', text: C.handle, wx0: 490, wy0: 466, wx1: 890, wy1: 500 });
  }
  subtitles(t);
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1;
}
window.render = render;
window.TEXTS = t => { render(t); const c = cam(t); return TX.map(o => { const [x0, y0] = toScr(c, o.wx0, o.wy0), [x1, y1] = toScr(c, o.wx1, o.wy1); return { id: o.id, text: o.text, x0, y0, x1, y1 }; }); };

(async () => {
  PAPER_IMG = new Image(); PAPER_IMG.src = 'paper.jpg'; await PAPER_IMG.decode();
  await Promise.all(['500 46px Caveat', '600 60px Caveat', 'italic 500 54px "Cormorant Garamond"', '600 86px "Cormorant Garamond"', '400 30px "IBM Plex Mono"'].map(f => document.fonts.load(f)));
  buildBlots(); buildNotes(); buildFigure(); buildIcons(); buildEnding();
  EV.sort((a, b) => a.t - b.t); window.EV = EV;
  window.READY = true;
})();
