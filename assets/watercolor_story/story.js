// Watercolor story engine: a storyboard of beats painted on one long sheet of paper. Every time, place and text
// comes from content.js (window.CONTENT), written by watercolor_story.py; this file only knows how to paint.
// Beats: crowd · specimen · trio · journey · transform · grow, then the ending (unfinished note + title).
// World: beat regions side by side (x = ox .. ox+1080, y 0..1920); frame 1080×1920. Pure function of t.
const C = window.CONTENT;
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const DUR = C.DUR, BEAT = 60 / 84;
window.DUR = DUR;
window.SUBS = C.subs;

const FEEL = ['#7d93a8', '#c9a24a', '#8ea07a', '#8a6a86', '#b98378', '#6f8f96', '#a39a6a', '#9c7f9e'];
const ONE = '#d9744e';
const camZ = monotone(C.cam.z), camX = monotone(C.cam.x), camY = monotone(C.cam.y);
const cam = t => ({ z: camZ(t), x: camX(t), y: camY(t) });
const toScr = (c, x, y) => [540 + (x - c.x) * c.z, 960 + (y - c.y) * c.z];
const setCam = c => ctx.setTransform(c.z, 0, 0, c.z, 540 - c.x * c.z, 960 - c.y * c.z);

let PAPER_IMG, TITLE_PX = 86, UNDER = null;
const EV = [], OB = {};                // OB: built objects by key
let TX = [];

// ---------- paper ----------
function drawPaper(c, clipFn) {        // tiles of the seamless sheet across whatever the camera sees
  const x0 = c.x - 540 / c.z - 40, x1 = c.x + 540 / c.z + 40;
  for (let k = Math.floor((x0 + 260) / 1600); k * 1600 - 260 < x1; k++) ctx.drawImage(PAPER_IMG, k * 1600 - 260, -340);
}
function vignette() {
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
  const g = ctx.createRadialGradient(540, 960, 700, 540, 960, 1250); g.addColorStop(0, 'rgba(60,40,20,0)'); g.addColorStop(1, 'rgba(60,40,20,.08)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, 1080, 1920); ctx.restore();
}

// ---------- annotations ----------
function hand(id, txt, x, y, p, o = {}) {
  if (p <= 0) return;
  const size = o.size || 44;
  ctx.save(); ctx.font = `${o.w || 500} ${size}px Caveat`; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
  const w = ctx.measureText(txt).width;
  if (o.center) x -= w / 2;
  if (o.maxX !== undefined && x + w > o.maxX) x = o.maxX - w;
  if (o.minX !== undefined && x < o.minX) x = o.minX;
  ctx.translate(x, y); if (o.rot) ctx.rotate(o.rot);
  ctx.beginPath(); ctx.rect(-6, -size, (w + 12) * eo(p), size * 2); ctx.clip();
  ctx.shadowColor = rgba(PAPER, .95); ctx.shadowBlur = 12; ctx.fillStyle = rgba(o.col || INK, o.a ?? .9);
  ctx.fillText(txt, 0, 0); ctx.fillText(txt, 0, 0);
  ctx.restore();
  TX.push({ id, text: txt, wx0: x - 6, wy0: y - size * .6, wx1: x + w + 6, wy1: y + size * .6 });
  return [x, w];
}
function leader(x0, y0, x1, y1, p, bend = 20, a = .75) {
  if (p <= 0) return;
  const pts = qcurve(x0, y0, x1, y1, bend, 16), m = Math.max(1, Math.round(16 * clamp(p)));
  ctx.beginPath(); for (let i = 0; i <= m; i++) i ? ctx.lineTo(pts[i][0], pts[i][1]) : ctx.moveTo(pts[i][0], pts[i][1]);
  ctx.strokeStyle = rgba(INK, a); ctx.lineWidth = 2.2; ctx.lineCap = 'round'; ctx.stroke();
  if (p >= 1) { ctx.beginPath(); ctx.arc(x1, y1, 4, 0, 7); ctx.fillStyle = rgba(INK, a); ctx.fill(); }
}

// ---------- objects on the page ----------
let SEEDN = 0;
function place(name, x, y, h, maxW = 1e9) {     // a built object placed at (x,y), scaled to height h (and width ≤ maxW)
  const o = buildObject(name, 1000 + C.seed + (SEEDN++) * 17);
  const sc = Math.min(h / Math.max(1, o.h), maxW / Math.max(1, o.w));
  return { ...o, x, y, sc, ax: x + o.anchor[0] * sc, ay: y + o.anchor[1] * sc };
}
function paintObj(o, p, am = 1) {               // p: 0..1 paint-in progress
  if (p <= 0) return;
  ctx.save(); ctx.translate(o.x, o.y); ctx.scale(o.sc, o.sc); ctx.globalAlpha = am;
  if (o.line) drawS(ctx, o.S[0], eio(p));
  else if (p < 1) drawList(ctx, o.S, p); else ctx.drawImage(o.spr.cv, o.spr.x0, o.spr.y0);
  ctx.restore();
}
function steamOf(o, t, t0) {
  if (!o.steam) return;
  ctx.save(); ctx.translate(o.x, o.y); ctx.scale(o.sc, o.sc);
  o.steam.forEach((s, k) => { const q = seg(t, t0 + k * .2, t0 + 1.1 + k * .2); if (q <= 0) return;
    ctx.save(); ctx.transform(1, 0, .05 * Math.sin(t * 1.3 + k * 2), 1, 0, 0); drawS(ctx, s, q, null, .9 - .3 * Math.sin(t * .8 + k) ** 2); ctx.restore(); });
  ctx.restore();
}
function eraseLocal(t, a, b, x0, y0, x1, y1) { // paper mist rising over a box (world), soft wavy edge
  const q = eio(seg(t, a, b)); if (q <= 0) return;
  const base = lerp(y1 + 120, y0 - 160, q);
  for (let j = 0; j < 6; j++) {
    ctx.save(); ctx.beginPath(); const pts = [];
    for (let x = x0 - 60; x <= x1 + 60; x += 20) pts.push([x, base + j * 24 + 30 * Math.sin(x * .01 + t) + 14 * Math.sin(x * .03)]);
    pts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.lineTo(x1 + 60, y1 + 300); ctx.lineTo(x0 - 60, y1 + 300); ctx.closePath(); ctx.clip();
    ctx.globalAlpha = j < 5 ? .35 : 1; drawPaper(cam(t)); ctx.restore();
  }
}

// ---------- beats ----------
const BEATS = {
  crowd: {
    build(b) {
      const times = []; let t = b.t0 + .3 + BEAT, end = b.lift - .9, span = b.lift - b.t0;
      b.blots = [];
      if (b.keep) b.blots.push({ ...place('blot', b.ox + 600, 1010, 110), t: b.t0 + .3, one: true, r: 62 });
      while (t < end) { times.push(t); t += t < b.t0 + span * .47 ? BEAT : t < b.t0 + span * .76 ? BEAT / 2 : BEAT / 4; }
      withSeed(202 + C.seed + b.i, () => {
        for (let i = 0; i < times.length; i++) {
          let best = null;
          for (let k = 0; k < 40; k++) {
            const x = b.ox + rnd(110, 970), y = rnd(240, 1240), r = rnd(38, 90);
            const d = Math.min(1e9, ...b.blots.map(o => Math.hypot(o.x - x, o.y - y) - o.r - r));
            if (!best || d > best.d) best = { x, y, r, d };
          }
          const col = FEEL[i % FEEL.length], S = []; const r = best.r;
          clump(S, 0, 0, r * .55, 9, [col], { sx: 1.1, sy: 1, l0: r * .5, l1: r * .95, w0: r * .38, w1: r * .62, a0: .32, a1: .55 });
          clump(S, 0, 0, r * .4, 7, [col, mixc(col, INK, .25)], { l0: r * .2, l1: r * .45, w0: r * .14, w1: r * .26, a0: .45, a1: .75 });
          b.blots.push({ S, spr: sprite(S), x: best.x, y: best.y, r, sc: 1, t: times[i] });
        }
      });
      for (const o of b.blots) EV.push({ t: o.t, type: 'blot', pan: (o.x - b.ox - 540) / 540, v: o.one ? 1 : .55 + o.r / 200 });
      const k1 = b.blots.find(o => o.one), boxes = k1 ? [[k1.x - 95, k1.y - 95, k1.x + 95, k1.y + 95]] : [];
      b.notesP = withSeed(303 + C.seed + b.i, () => b.notes.map(([t, txt], i) => {
        const cands = b.blots.filter(o => o.t < t - .2 && !o.one), w = txt.length * 19 + 20;
        for (let k = 0; k < cands.length; k++) {
          const o = cands[(i * 7 + k * 3) % cands.length], side = o.x - b.ox < 540 ? 1 : -1, lx = o.x + side * (o.r + 50) - (side < 0 ? txt.length * 19 : 0);
          for (const ly of [o.y - o.r - 40, o.y + o.r + 30]) {
            const box = [lx - 10, ly - 34, lx + w, ly + 34];
            if (lx > b.ox + 60 && lx + w < b.ox + 1020 && ly > 200 && ly < 1330 && !boxes.some(q => box[0] < q[2] && box[2] > q[0] && box[1] < q[3] && box[3] > q[1])) {
              boxes.push(box); EV.push({ t: t + .3, type: 'pencil', d: .25 + txt.length * .05, pan: side * -.4 });
              return { t, txt, o, lx, ly, rot: rnd(-.09, .09) };
            }
          }
        }
        return null;
      }).filter(Boolean));
      EV.push({ t: b.lift, type: 'lift' }, { t: b.mist0, type: 'mist' });
    },
    draw(b, t) {
      if (t < b.end) {
        for (const o of b.blots) if (!o.one) drawBlot(o, t, 1 - .25 * seg(t, b.lift - .8, b.mist0));
        for (const n of b.notesP) {
          const above = n.ly < n.o.y, lx0 = n.lx + (n.o.x - b.ox < 540 ? -10 : n.txt.length * 19 + 10);
          leader(lx0, n.ly + (above ? 14 : -14), n.o.x + (n.o.x - b.ox < 540 ? .5 : -.5) * n.o.r, n.o.y + (above ? -.5 : .5) * n.o.r, seg(t, n.t, n.t + .4), 14);
          hand('n' + b.i + n.txt, n.txt, n.lx, n.ly, seg(t, n.t + .2, n.t + .9), { rot: n.rot, size: 46 });
        }
        eraseLocal(t, b.mist0, b.mist0 + 2.4, b.ox - 200, 150, b.ox + 1280, 1500);
      }
      const k1 = b.blots.find(o => o.one); if (k1) drawBlot(k1, t, b.absorb ? 1 - ss(seg(t, b.absorb, b.absorb + 1.6)) : 1, b.one);
    },
  },
  specimen: {
    build(b) {
      const h = b.object === 'person' ? 850 : 560;
      b.o = place(b.object, b.ox + 560, 940, h, 820);
      if (b.accent) { const dx = b.ox + 600 - b.o.ax, dy = 1010 - b.o.ay; b.o.x += dx; b.o.y += dy; b.o.ax += dx; b.o.ay += dy; }   // the kept feeling lands on the anchor (a person's chest, else the centre)
      for (let t = b.paint[0] + .1; t < b.paint[1] - .1; t += .42) EV.push({ t, type: 'brush', pan: -.1 });
      if (b.note) EV.push({ t: b.note.t, type: 'pencil', d: .5, pan: .3 });
    },
    draw(b, t) {
      paintObj(b.o, seg(t, b.paint[0], b.paint[1])); steamOf(b.o, t, b.paint[1]);
      if (b.note && t > b.note.t) {
        const f = 1 - ss(seg(t, b.fade, b.fade + .8)); if (f <= 0) return; ctx.globalAlpha = f;
        const tx = b.o.ax + 230, ty = b.o.ay - 130;
        leader(tx - 10, ty + 30, b.o.ax + 20, b.o.ay - 10, seg(t, b.note.t, b.note.t + .6), 18);
        hand('sp' + b.i, b.note.text, tx, ty, seg(t, b.note.t + .3, b.note.t + 1.1), { size: 52, maxX: b.ox + 990 });
        ctx.globalAlpha = 1;
      }
    },
  },
  trio: {
    build(b) {
      const S = b.attach ? [[900, 640, 220, 40, -110], [1030, 1170, 220, -150, 160], [1180, 830, 190, -40, -130]]
                         : [[300, 640, 260, -60, 170], [780, 800, 260, -60, 170], [520, 1060, 260, -60, 170]];
      b.objs = b.items.map((it, k) => {
        const [x, y, h, lx, ly] = S[k], o = place(it.object, b.ox + x, y, it.object === 'breath' ? 70 : h, it.object === 'breath' ? (b.attach && k === 0 ? 440 : 300) : 300);
        EV.push({ t: it.t, type: 'icon', icon: it.object, pan: b.attach ? .4 : (x - 540) / 540 });
        return { ...o, it, lx: b.ox + x + lx, ly: y + ly };
      });
    },
    draw(b, t) {
      const f = 1 - ss(seg(t, b.fade, b.fade + .8));
      for (const o of b.objs) {
        paintObj(o, seg(t, o.it.t, o.it.t + (o.line ? 1.6 : 1.2))); steamOf(o, t, o.it.t + .9);
        if (f > 0 && t > o.it.t + .3) { ctx.globalAlpha = f; hand('tr' + b.i + o.it.label, o.it.label, o.lx, o.ly, seg(t, o.it.t + .3, o.it.t + 1.0), { size: 44, maxX: b.ox + (b.attach ? 1300 : 1030), minX: b.ox + 50 }); ctx.globalAlpha = 1; }
      }
    },
  },
  journey: {
    build(b) {
      b.a = place(b.from, b.ox + 300, 960, 420, 440); b.b = place(b.to, b.ox + 1560, 900, 520, 520);
      b.w = place('walker', 0, 0, 210);
      const P = []; for (let i = 0; i <= 40; i++) { const s = i / 40; P.push([lerp(b.ox + 470, b.ox + 1380, s), lerp(1190, 1120, s) + Math.sin(s * Math.PI * 2) * 50]); }
      b.P = P; b.path = withSeed(700 + b.i, () => mk(P, 16, mixc('#c9a86a', PAPER, .2), { prof: 'even', nb: 5, a: .55, rough: .35 }));
      EV.push({ t: b.pa[0], type: 'brush', pan: -.4 }, { t: b.pb[0], type: 'brush', pan: .4 }, { t: b.path_t[0], type: 'brush', pan: 0 });
      for (let t = b.walk[0]; t < b.walk[1]; t += .45) EV.push({ t, type: 'step' });
      EV.push({ t: b.walk[1], type: 'icon', icon: b.to, pan: .4 });
    },
    draw(b, t) {
      paintObj(b.a, seg(t, b.pa[0], b.pa[1])); drawS(ctx, b.path, eio(seg(t, b.path_t[0], b.path_t[1]))); paintObj(b.b, seg(t, b.pb[0], b.pb[1])); steamOf(b.b, t, b.pb[1]);
      const q = seg(t, b.walk[0], b.walk[1]); if (t < b.walk[0] - .6) return;
      const m = eio(q) * (b.P.length - 1), i = Math.min(b.P.length - 2, Math.floor(m)), f = m - i;
      const x = lerp(b.P[i][0], b.P[i + 1][0], f), y = lerp(b.P[i][1], b.P[i + 1][1], f) - 110 - Math.abs(Math.sin(t * 7)) * 10 * (q > 0 && q < 1);
      paintObj({ ...b.w, x, y }, seg(t, b.walk[0] - .6, b.walk[0]));
      const fa = 1 - ss(seg(t, b.fade, b.fade + .8));
      if (b.label && t > b.walk[1] && fa > 0) { ctx.globalAlpha = fa; hand('jl' + b.i, b.label, b.b.x, b.b.y - b.b.h * b.b.sc / 2 - 50, seg(t, b.walk[1] + .2, b.walk[1] + 1), { size: 50, center: true }); ctx.globalAlpha = 1; }
    },
  },
  transform: {
    build(b) {
      b.a = place(b.from, b.ox + 540, 880, 520, 760); b.b = place(b.to, b.ox + 540, 880, 520, 760);
      EV.push({ t: b.pa[0], type: 'brush' }, { t: b.erase[0], type: 'mist' }, { t: b.pb[0], type: 'reveal' }, { t: b.pb[0] + .2, type: 'icon', icon: b.to });
      if (b.note) EV.push({ t: b.note.t, type: 'pencil', d: .5 });
    },
    draw(b, t) {
      if (t < b.erase[1]) { paintObj(b.a, seg(t, b.pa[0], b.pa[1])); eraseLocal(t, b.erase[0], b.erase[1], b.ox + 120, 520, b.ox + 960, 1240); }
      paintObj(b.b, seg(t, b.pb[0], b.pb[1])); steamOf(b.b, t, b.pb[1]);
      const f = 1 - ss(seg(t, b.fade, b.fade + .8));
      if (b.note && t > b.note.t && f > 0) { ctx.globalAlpha = f; hand('tf' + b.i, b.note.text, b.ox + 540, 1210, seg(t, b.note.t, b.note.t + .9), { size: 50, center: true }); ctx.globalAlpha = 1; }
    },
  },
  grow: {
    build(b) {
      const n = b.objects.length, xs = n === 2 ? [320, 760] : [190, 520, 860], hs = n === 2 ? [360, 600] : [230, 400, 620];
      b.objs = b.objects.map((name, k) => { const h = hs[k], o = place(name, b.ox + xs[k], 1180 - h / 2, h, n === 2 ? 420 : 310); return o; });
      b.times.forEach((t, k) => EV.push({ t, type: 'icon', icon: b.objects[k], pan: (xs[k] - 540) / 540 }));
      if (b.note) EV.push({ t: b.note.t, type: 'pencil', d: .5 });
    },
    draw(b, t) {
      b.objs.forEach((o, k) => { paintObj(o, seg(t, b.times[k], b.times[k] + 1.3)); steamOf(o, t, b.times[k] + 1); });
      const f = 1 - ss(seg(t, b.fade, b.fade + .8));
      if (b.note && t > b.note.t && f > 0) { ctx.globalAlpha = f; hand('gr' + b.i, b.note.text, b.ox + 540, 440, seg(t, b.note.t, b.note.t + .9), { size: 54, center: true }); ctx.globalAlpha = 1; }
    },
  },
};
function drawBlot(o, t, am = 1, oneT = null) {
  const p = seg(t, o.t, o.t + .55); if (p <= 0) return;
  const bloom = 1 + .2 * eo(seg(t, o.t + .4, o.t + 3.2)) + (oneT && t > oneT ? .05 * Math.sin((t - oneT) * 1.6) : 0);
  ctx.save(); ctx.translate(o.x, o.y); ctx.scale(bloom * (o.sc || 1), bloom * (o.sc || 1)); ctx.globalAlpha = am;
  if (p < 1) drawList(ctx, o.S, p); else ctx.drawImage(o.spr.cv, o.spr.x0, o.spr.y0);
  ctx.restore();
}

// screen-space mist between distant beats: paper rises over the frame, the camera moves underneath, it lifts away
function mistOverlay(t) {
  for (const m of C.mists) {
    if (t < m.t0 || t > m.t1) continue;
    const mid = (m.t0 + m.t1) / 2;
    const top = lerp(2150, -250, eio(seg(t, m.t0, mid)));            // leading edge: covers the frame from below
    const bot = lerp(2150, -700, eio(seg(t, mid, m.t1)));            // trailing edge: uncovers the next scene from below
    for (let j = 0; j < 5; j++) {
      const wave = (x, y0) => y0 + 40 * Math.sin(x * .006 + j + t) + 18 * Math.sin(x * .02);
      ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.beginPath();
      for (let x = -40; x <= 1120; x += 20) { const y = wave(x, top + j * 26); x === -40 ? ctx.moveTo(x, y) : ctx.lineTo(x, y); }
      for (let x = 1120; x >= -40; x -= 20) ctx.lineTo(x, wave(x, bot + 300 - j * 26));
      ctx.closePath(); ctx.clip(); ctx.globalAlpha = j < 4 ? .3 : 1;
      ctx.drawImage(PAPER_IMG, -260, -340); ctx.drawImage(PAPER_IMG, -260, -340 + 2600); ctx.restore();
    }
  }
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
function ending(t) {
  const E = C.ending;
  const [lx] = hand('later', E.later, E.x - 170, 1340, seg(t, E.later_t, E.later_t + 2.2), { size: 60, w: 600 }) || [E.x - 170];
  if (UNDER) drawS(ctx, UNDER, .82 * eio(seg(t, E.under[0], E.under[1])));
  if (t > E.title_t) {
    const pt = seg(t, E.title_t, E.title_t + 1.2);
    ctx.save(); ctx.font = `600 ${TITLE_PX}px "Cormorant Garamond"`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    const w = ctx.measureText(E.title).width;
    ctx.beginPath(); ctx.rect(E.x - w / 2 - 10, 330, (w + 20) * eo(pt), 140); ctx.clip();
    ctx.shadowColor = rgba(PAPER, 1); ctx.shadowBlur = 14; ctx.fillStyle = rgba(INK, .9); ctx.fillText(E.title, E.x, 400); ctx.restore();
    TX.push({ id: 'title', text: E.title, wx0: E.x - w / 2, wy0: 350, wx1: E.x + w / 2, wy1: 450 });
  }
  if (t > E.handle_t && E.handle) {
    ctx.save(); ctx.font = '400 30px "IBM Plex Mono"'; ctx.textAlign = 'center'; ctx.letterSpacing = '6px';
    ctx.fillStyle = rgba(INK2, .75 * ss(seg(t, E.handle_t, E.handle_t + .8))); ctx.fillText(E.handle, E.x, 486); ctx.restore();
    TX.push({ id: 'handle', text: E.handle, wx0: E.x - 200, wy0: 466, wx1: E.x + 200, wy1: 500 });
  }
}

function render(t) {
  TX = [];
  const c = cam(t);
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.fillStyle = PAPER; ctx.fillRect(0, 0, 1080, 1920);
  setCam(c); drawPaper(c);
  for (const b of C.beats) if (t >= b.t0 - .05 && Math.abs(b.ox + 540 - c.x) < 2600) BEATS[b.type].draw(b, t);
  ending(t);
  mistOverlay(t);
  vignette();
  subtitles(t);
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1;
}
window.render = render;
window.TEXTS = t => { render(t); const c = cam(t); return TX.map(o => { const [x0, y0] = toScr(c, o.wx0, o.wy0), [x1, y1] = toScr(c, o.wx1, o.wy1); return { id: o.id, text: o.text, x0, y0, x1, y1 }; }); };

(async () => {
  PAPER_IMG = new Image(); PAPER_IMG.src = 'paper_tile.jpg'; await PAPER_IMG.decode();
  await Promise.all(['500 46px Caveat', '600 60px Caveat', 'italic 500 54px "Cormorant Garamond"', '600 86px "Cormorant Garamond"', '400 30px "IBM Plex Mono"'].map(f => document.fonts.load(f)));
  C.beats.forEach((b, i) => { b.i = i; BEATS[b.type].build(b); });
  const E = C.ending;
  ctx.font = '600 60px Caveat'; const w = ctx.measureText(E.later).width;
  UNDER = withSeed(606 + C.seed, () => mk(qcurve(E.x - 190, 1388, E.x - 150 + w + 40, 1380, 6, 24), 9, ONE, { prof: 'brush', a: .8 }));
  ctx.font = `600 ${TITLE_PX}px "Cormorant Garamond"`;
  while (ctx.measureText(E.title).width > 920 && TITLE_PX > 48) { TITLE_PX -= 2; ctx.font = `600 ${TITLE_PX}px "Cormorant Garamond"`; }
  EV.push({ t: E.later_t, type: 'pencil', d: 2.0 }, { t: E.title_t, type: 'title' }, { t: E.under[1] + .1, type: 'lift' });
  for (const m of C.mists) EV.push({ t: m.t0, type: 'mist' });
  EV.sort((a, b) => a.t - b.t); window.EV = EV;
  window.READY = true;
})();
