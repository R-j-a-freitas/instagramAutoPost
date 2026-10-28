// Painted object library for watercolor stories. Every object is built from brush strokes (engine.js) in local
// coordinates around (0,0) and returns { S: strokes, anchor?: [x,y], steam?: strokes }. Size does not matter:
// the beats measure each object's box and scale it to the height they need. Build under withSeed.
const OC = {
  skin: '#9fb0b8', shade: '#6f8494', blue: '#6f9fbf', sky: '#9fb4c4', night: '#56627a', cup: '#c9a86a', leaf: '#7f9a5a',
  leaf2: '#a3b56a', sun: '#e3b04b', one: '#d9744e', earth: '#8a6a4a', terra: '#c98a5e', stone: '#9a948a', wood: '#a07a52',
  rose: '#c98b80', plum: '#8a6a86', cream: '#e6d6b0', grey: '#8d9399', water: '#7fa9bf',
};
const inkL = (pts, w = 4, a = .6) => mk(pts, w, INK2, { prof: 'even', nb: 0, a, rough: .35 });
const inPoly = (x, y, P) => { let c = false; for (let i = 0, j = P.length - 1; i < P.length; j = i++) { const [xi, yi] = P[i], [xj, yj] = P[j]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; };
const pbox = P => [Math.min(...P.map(p => p[0])), Math.min(...P.map(p => p[1])), Math.max(...P.map(p => p[0])), Math.max(...P.map(p => p[1]))];
// fill a polygon with overlapping diagonal washes (the watercolor "body" of a shape)
function fillPoly(S, P, col, o = {}) {
  const [x0, y0, x1, y1] = pbox(P), area = (x1 - x0) * (y1 - y0), n = o.n ?? Math.round(clamp(area / 2600, 6, 90));
  const ang = o.ang ?? -.75, w0 = o.w0 ?? clamp(Math.sqrt(area) / 6, 14, 60), pts = [];
  for (let k = 0; k < n * 6 && pts.length < n; k++) { const x = rnd(x0, x1), y = rnd(y0, y1); if (inPoly(x, y, P)) pts.push([x, y]); }
  pts.sort((a, b) => a[1] - b[1]);
  for (const [x, y] of pts) {
    const d = ang + rnd(-.3, .3), len = w0 * rnd(1.4, 2.4);
    S.push(mk(polar(x - Math.cos(d) * len / 2, y - Math.sin(d) * len / 2, d, len, rnd(-6, 6), 6), w0 * rnd(.8, 1.2), rnd() < (o.mix ?? .25) ? mixc(col, INK, .18) : col,
      { prof: 'leaf', nb: rnd() < .3 ? 2 : 0, a: rnd(o.a0 ?? .2, o.a1 ?? .32) }));
  }
}
// brush along the outline (a pooled edge), optionally an ink line. Polygons with few points (boxes, triangles) get one
// stroke per side; smooth outlines (circles) get strokes over runs of points. Never curves across a corner.
function densify(A, B, n = 6) { const out = []; for (let i = 0; i <= n; i++) out.push([lerp(A[0], B[0], i / n), lerp(A[1], B[1], i / n)]); return out; }
function edge(S, P, col, w = 10, a = .45, closed = true, inkA = 0) {
  const Q = closed ? [...P, P[0]] : P, n = Q.length, runs = [];
  if (P.length <= 8) for (let i = 0; i < n - 1; i++) runs.push(densify(Q[i], Q[i + 1]));
  else for (let i = 0; i < n - 1; i += 4) { const r = Q.slice(i, Math.min(n, i + 5)); if (r.length > 1) runs.push(r); }
  for (const r of runs) {
    const j = r.map(([x, y]) => [x + rnd(-1.5, 1.5), y + rnd(-1.5, 1.5)]);
    S.push(mk(j, w, col, { prof: 'even', nb: w > 8 ? 3 : 0, a }));
    if (inkA > 0) S.push(inkL(j, 3.2, inkA));
  }
}
const circ = (cx, cy, rx, ry = rx, n = 28, a0 = 0, a1 = Math.PI * 2) => { const P = []; for (let i = 0; i < n; i++) { const a = a0 + (a1 - a0) * i / (n - (a1 - a0 >= 6.28 ? 0 : 1)); P.push([cx + Math.cos(a) * rx, cy + Math.sin(a) * ry]); } return P; };
const rect = (x0, y0, x1, y1) => [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
const shape = (P, col, o = {}) => { const S = []; fillPoly(S, P, col, o); edge(S, P, o.edge || col, o.ew ?? 12, o.ea ?? .45, true, o.ink ?? .35); return S; };

const OBJ = {
  blot() { const S = []; clump(S, 0, 0, 34, 9, [OC.one], { sx: 1.1, sy: 1, l0: 31, l1: 59, w0: 24, w1: 38, a0: .32, a1: .55 }); clump(S, 0, 0, 25, 7, [OC.one, mixc(OC.one, INK, .25)], { l0: 12, l1: 28, w0: 9, w1: 16, a0: .45, a1: .75 }); return { S }; },
  heart(sc = 8, dy = 0) {
    const P = []; for (let i = 0; i < 40; i++) { const t = i / 40 * Math.PI * 2; P.push([16 * Math.sin(t) ** 3 * sc, -(13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t)) * sc + dy]); }
    return { S: shape(P, OC.one, { a0: .25, a1: .4, ink: .25 }) };
  },
  person() {                               // a bust; the feeling sits at the anchor (chest)
    const S = [], cx = 0, hy = -268, hr = 104, top = hy + 178, bot = hy + 640;
    const halfW = y => lerp(46, 262, ss(clamp((y - top) / 150))) + 28 * clamp((y - top - 150) / 340), fade = y => 1 - ss(seg(y, bot - 220, bot));
    for (let i = 0; i < 10; i++) { const a0 = i / 10 * Math.PI * 2, a1 = a0 + .8, am = (a0 + a1) / 2;
      S.push(mk(qctrl(cx + Math.cos(a0) * hr, hy + Math.sin(a0) * hr * 1.08, cx + Math.cos(am) * hr * 1.12, hy + Math.sin(am) * hr * 1.2, cx + Math.cos(a1) * hr, hy + Math.sin(a1) * hr * 1.08, 10), rnd(26, 34), OC.skin, { prof: 'leaf', nb: 3, a: rnd(.4, .5) })); }
    for (let i = 0; i < 18; i++) { const a = rnd(0, Math.PI * 2), rr = hr * .72 * Math.sqrt(rnd()), x = cx + Math.cos(a) * rr, y = hy + Math.sin(a) * rr * 1.08, d = -.7 + rnd(-.3, .3);
      S.push(mk(polar(x - Math.cos(d) * 30, y - Math.sin(d) * 30, d, 60, rnd(-6, 6), 6), rnd(50, 66), OC.skin, { prof: 'leaf', nb: 0, a: rnd(.2, .3) })); }
    for (let i = 0; i < 8; i++) { const a0 = Math.PI * (1.05 + i * .11), a1 = a0 + .32;
      S.push(mk(qcurve(cx + Math.cos(a0) * hr * .98, hy + Math.sin(a0) * hr * 1.02, cx + Math.cos(a1) * hr * 1.02, hy + Math.sin(a1) * hr * 1.06, -8, 6), rnd(22, 30), OC.shade, { prof: 'leaf', nb: 3, a: .5 })); }
    S.push(mk(qcurve(cx - 4, hy + 96, cx - 2, top + 30, 0, 8), 64, OC.skin, { prof: 'even', nb: 3, a: .38 }));
    for (const s of [-1, 1]) { const pts = []; for (let i = 0; i <= 16; i++) { const y = top + i / 16 * 330; pts.push([cx + s * halfW(y), y]); } S.push(mk(pts, 30, OC.skin, { prof: 'brush', nb: 4, a: .5 })); }
    const fill = [];
    for (let i = 0; i < 150; i++) { const y = rnd(top + 20, bot), hw = halfW(y), x = cx + rnd(-hw * .92, hw * .92), d = -.75 + rnd(-.28, .28), len = rnd(70, 130);
      fill.push([y, mk(polar(x - Math.cos(d) * len / 2, y - Math.sin(d) * len / 2, d, len, rnd(-10, 10), 6), rnd(44, 72), rnd() < .3 ? OC.shade : OC.skin, { prof: 'leaf', nb: rnd() < .4 ? 2 : 0, a: rnd(.16, .26) * fade(y) })]); }
    fill.sort((a, b) => a[0] - b[0]); for (const [, st] of fill) S.push(st);
    for (const s of [-1, 1]) { const pts = []; for (let i = 0; i <= 12; i++) { const y = top + 6 + i / 12 * 200; pts.push([cx + s * (halfW(y) + 8), y]); } S.push(mk(pts, 3.5, INK2, { prof: 'tip', nb: 0, a: .38, rough: .4 })); }
    S.push(mk(qctrl(cx - 100, hy + 20, cx - 112, hy - 116, cx + 30, hy - 112, 14), 3.5, INK2, { prof: 'tip', nb: 0, a: .4, rough: .4 }));
    return { S, anchor: [40, 52] };
  },
  walker() {                               // a small standing figure (for journeys)
    const S = []; clump(S, 0, -112, 16, 8, [OC.shade], { l0: 14, l1: 24, w0: 14, w1: 20, a0: .45, a1: .7 });
    S.push(mk(qcurve(0, -86, 2, 4, 3, 8), 34, OC.skin, { prof: 'leaf', nb: 3, a: .6 }));
    S.push(mk(qcurve(-6, 0, -18, 92, -4, 6), 12, OC.shade, { prof: 'even', a: .65 }), mk(qcurve(6, 0, 18, 92, 4, 6), 12, OC.shade, { prof: 'even', a: .65 }));
    S.push(mk(qcurve(-12, -70, -30, -12, -6, 6), 10, OC.skin, { prof: 'even', a: .6 }), mk(qcurve(12, -70, 30, -14, 6, 6), 10, OC.skin, { prof: 'even', a: .6 }));
    return { S };
  },
  cup() {
    const S = [];
    S.push(mk(qctrl(-95, -70, -100, 90, 0, 92, 14), 26, OC.cup, { prof: 'even', a: .6 }), mk(qctrl(0, 92, 100, 90, 95, -70, 14), 26, OC.cup, { prof: 'even', a: .6 }));
    for (let k = 0; k < 4; k++) S.push(mk(qcurve(-86, -40 + k * 34, 86, -40 + k * 34, 6, 10), 30, mixc(OC.cup, '#e8d6a8', k / 4), { prof: 'even', a: .42 }));
    S.push(mk(qcurve(-98, -72, 98, -72, -10, 12), 9, mixc(OC.cup, INK, .3), { prof: 'even', a: .6 }), mk(qctrl(92, -40, 160, -10, 88, 40, 10), 14, OC.cup, { prof: 'even', a: .6 }));
    S.push(mk(qcurve(-140, 104, 140, 104, 4, 12), 10, mixc(OC.cup, INK, .45), { prof: 'even', a: .5 }));
    const steam = [0, 1, 2].map(k => { const p = []; for (let i = 0; i <= 20; i++) { const s = i / 20; p.push([-40 + k * 40 + Math.sin(s * 5 + k) * 16, -110 - s * 190]); } return mk(p, 8, '#b7c3c8', { prof: 'tip', nb: 2, a: .55 }); });
    return { S, steam };
  },
  glass() {
    const P = [[-70, -120], [70, -120], [55, 120], [-55, 120]], S = [];
    fillPoly(S, [[-64, -40], [64, -40], [55, 116], [-55, 116]], OC.water, { a0: .25, a1: .38 });
    edge(S, P, OC.sky, 8, .45, true, .5); S.push(mk(qcurve(-62, -40, 62, -40, 6, 8), 6, OC.blue, { prof: 'even', nb: 0, a: .6 }));
    return { S };
  },
  breath() { const pts = []; for (let i = 0; i <= 40; i++) { const s = i / 40; pts.push([-220 + s * 440, 30 - s * 60 + Math.sin(s * Math.PI * 3) * 34]); } return { S: [mk(pts, 14, OC.blue, { prof: 'even', a: .78, rough: .3 })], line: true }; },
  song() {
    const x = -35, y = 64;
    return { S: [mk(qcurve(x, y, x, y - 110, 0, 6), 6, INK2, { prof: 'even', nb: 0, a: .8 }), mk(qcurve(x + 70, y - 18, x + 70, y - 128, 0, 6), 6, INK2, { prof: 'even', nb: 0, a: .8 }),
      mk(qcurve(x, y - 110, x + 70, y - 128, -6, 6), 12, INK2, { prof: 'even', nb: 0, a: .8 }), mk(polar(x - 16, y + 4, 0, 34, 10, 6), 22, OC.one, { prof: 'leaf', a: .75 }), mk(polar(x + 54, y - 14, 0, 34, 10, 6), 22, OC.one, { prof: 'leaf', a: .75 })] };
  },
  sprout() {
    return { S: [mk(qcurve(-100, 80, 100, 80, -26, 12), 30, OC.earth, { prof: 'even', a: .55 }), mk(qcurve(0, 74, 8, -80, 14, 10), 12, OC.leaf, { prof: 'tip', a: .8 }),
      mk(polar(6, -20, -2.5, 90, 22, 8), 38, OC.leaf, { prof: 'leaf', a: .7 }), mk(polar(8, -52, -.55, 96, -22, 8), 42, mixc(OC.leaf, '#c9c96a', .3), { prof: 'leaf', a: .7 }), mk(polar(8, -78, -1.7, 44, 8, 6), 22, OC.leaf, { prof: 'leaf', a: .75 })] };
  },
  seed() {
    const S = shape(circ(0, 0, 46, 30), OC.earth, { a0: .45, a1: .62, ink: .4, ang: -.3, n: 16, w0: 22 });
    S.push(inkL(qcurve(-26, -4, 28, 6, -8, 8), 3, .45), mk(qcurve(-120, 60, 120, 60, -10, 12), 18, mixc(OC.earth, PAPER, .3), { prof: 'even', a: .45 }));
    return { S };
  },
  plant() {
    const S = shape([[-70, 40], [70, 40], [52, 150], [-52, 150]], OC.terra, { a0: .3, a1: .45, ink: .35 });
    S.push(mk(qcurve(-80, 40, 80, 40, -4, 8), 16, mixc(OC.terra, INK, .2), { prof: 'even', a: .55 }));
    for (let k = 0; k < 7; k++) { const a = -Math.PI / 2 + (k - 3) * .38, len = rnd(110, 160); S.push(mk(polar(0, 34, a, len, rnd(-24, 24), 8), rnd(34, 46), k % 2 ? OC.leaf : OC.leaf2, { prof: 'leaf', a: .62 })); }
    return { S };
  },
  tree() {
    const S = [mk(qcurve(0, 160, 6, -30, 10, 10), 46, OC.wood, { prof: 'trunk', a: .7 })];
    S.push(mk(qcurve(4, 20, -70, -70, 14, 8), 14, OC.wood, { prof: 'tip', a: .65 }), mk(qcurve(6, 0, 80, -80, -14, 8), 14, OC.wood, { prof: 'tip', a: .65 }));
    clump(S, 0, -110, 110, 38, [OC.leaf, OC.leaf2, mixc(OC.leaf, INK, .2)], { sx: 1.2, sy: .8, l0: 30, l1: 60, w0: 26, w1: 44, a0: .45, a1: .75 });
    S.push(mk(qcurve(-120, 164, 120, 164, -6, 12), 14, mixc(OC.earth, PAPER, .3), { prof: 'even', a: .45 }));
    return { S };
  },
  flower() {
    const S = [mk(qcurve(0, 150, 4, -40, 16, 10), 9, OC.leaf, { prof: 'even', a: .75 }), mk(polar(2, 70, -2.6, 70, 18, 6), 30, OC.leaf, { prof: 'leaf', a: .7 }), mk(polar(3, 40, -.5, 70, -18, 6), 30, OC.leaf2, { prof: 'leaf', a: .7 })];
    for (let k = 0; k < 6; k++) { const a = k / 6 * Math.PI * 2; S.push(mk(polar(4 + Math.cos(a) * 14, -60 + Math.sin(a) * 14, a, 62, 8, 6), 42, k % 2 ? OC.rose : mixc(OC.rose, OC.one, .3), { prof: 'leaf', a: .7 })); }
    clump(S, 4, -60, 12, 6, [OC.sun], { l0: 10, l1: 18, w0: 12, w1: 18, a0: .7, a1: .9 });
    return { S };
  },
  leaf() { return { S: [mk(qcurve(-120, 90, 120, -90, 40, 14), 110, OC.leaf, { prof: 'leaf', a: .5 }), mk(qcurve(-120, 90, 120, -90, 40, 14), 70, OC.leaf2, { prof: 'leaf', a: .35 }), inkL(qcurve(-130, 100, 100, -74, 30, 12), 4, .5)] }; },
  sun() {
    const S = []; clump(S, 0, 0, 34, 12, [OC.sun, mixc(OC.sun, OC.one, .3)], { l0: 30, l1: 56, w0: 30, w1: 46, a0: .45, a1: .7 });
    for (let k = 0; k < 10; k++) { const a = k / 10 * Math.PI * 2; S.push(mk(polar(Math.cos(a) * 78, Math.sin(a) * 78, a, 46, 4, 6), 11, mixc(OC.sun, OC.one, .2), { prof: 'tip', nb: 0, a: .75 })); }
    return { S };
  },
  moon() {
    const P = [...circ(0, 0, 110, 110, 20, -Math.PI * .55, Math.PI * .55).map(([x, y]) => [x, y]), ...circ(46, -6, 92, 96, 20, Math.PI * .5, -Math.PI * .5).map(([x, y]) => [x, y])];
    const S = shape(P, '#e9d39a', { a0: .3, a1: .5, ink: .2, edge: OC.sun });
    for (let k = 0; k < 5; k++) S.push(mk(polar(rnd(-160, 160), rnd(-150, 150), rnd(0, 6), 10, 0, 4), 8, OC.sun, { prof: 'leaf', nb: 0, a: .6 }));
    return { S };
  },
  cloud() { const P = [...circ(-70, 10, 70, 56, 12, Math.PI * .5, Math.PI * 1.5), ...circ(0, -30, 80, 70, 12, Math.PI, Math.PI * 2), ...circ(80, 14, 62, 50, 12, Math.PI * 1.5, Math.PI * 2.5)]; return { S: shape(P, OC.sky, { a0: .2, a1: .32, ink: .2 }) }; },
  rain() {
    const c = OBJ.cloud(), S = c.S;
    for (let k = 0; k < 13; k++) { const x = -120 + k * 20 + rnd(-6, 6), y = 90 + rnd(0, 60); S.push(mk(qcurve(x, y, x - 16, y + 60, 0, 4), 6, OC.blue, { prof: 'tip', nb: 0, a: .7 })); }
    return { S };
  },
  storm() {
    const P = [...circ(-70, 10, 70, 56, 12, Math.PI * .5, Math.PI * 1.5), ...circ(0, -30, 80, 70, 12, Math.PI, Math.PI * 2), ...circ(80, 14, 62, 50, 12, Math.PI * 1.5, Math.PI * 2.5)];
    const S = shape(P, OC.night, { a0: .28, a1: .42, ink: .3 });
    const L = [[10, 60], [-30, 140], [6, 140], [-24, 230], [50, 120], [14, 120], [40, 60]]; S.push(...shape(L, OC.sun, { a0: .5, a1: .7, ink: .3, n: 10 }));
    return { S };
  },
  rainbow() { const S = []; [OC.rose, OC.sun, OC.leaf2, OC.blue].forEach((c, k) => { const r = 160 - k * 26; S.push(mk(circ(0, 80, r, r, 24, Math.PI, Math.PI * 2), 26, c, { prof: 'even', nb: 3, a: .6 })); }); S.push(...OBJ.cloud().S.map(s => s)); return { S }; },
  mountain() {
    const S = shape([[-190, 140], [-40, -120], [60, 20], [110, -40], [200, 140]], OC.sky, { a0: .25, a1: .38, ink: .3 });
    S.push(...shape([[-80, -50], [-40, -120], [4, -46], [-30, -60]], OC.cream, { a0: .5, a1: .7, ink: .2, n: 8 }));
    return { S };
  },
  wave() {
    const S = [];
    for (let k = 0; k < 4; k++) { const p = []; for (let i = 0; i <= 30; i++) { const s = i / 30; p.push([-200 + s * 400, -40 + k * 40 + Math.sin(s * Math.PI * 4 + k) * 18]); } S.push(mk(p, 30 - k * 3, k % 2 ? OC.blue : OC.water, { prof: 'even', nb: 4, a: .55 })); }
    for (let k = 0; k < 3; k++) S.push(inkL(qcurve(-150 + k * 120, -60, -110 + k * 120, -78, -10, 6), 3, .45));
    return { S };
  },
  boat() {
    const S = shape([[-130, 40], [130, 40], [90, 100], [-90, 100]], OC.wood, { a0: .35, a1: .5, ink: .4 });
    S.push(inkL(qcurve(0, 40, 0, -150, 0, 8), 4.5, .7), ...shape([[6, -140], [6, 20], [110, 20]], OC.cream, { a0: .4, a1: .6, ink: .3, n: 10 }));
    S.push(mk(qcurve(-190, 110, 190, 110, -8, 16), 16, OC.water, { prof: 'even', a: .5 }));
    return { S };
  },
  bird() {
    return { S: [mk(qcurve(-70, 10, 70, -6, -14, 10), 44, OC.plum, { prof: 'leaf', a: .65 }), mk(qcurve(-10, 0, -60, -90, 20, 8), 30, mixc(OC.plum, OC.sky, .3), { prof: 'tip', a: .6 }),
      mk(qcurve(10, -4, 70, -84, -16, 8), 26, OC.plum, { prof: 'tip', a: .55 }), mk(qcurve(70, -6, 96, 0, 0, 4), 8, OC.sun, { prof: 'tip', a: .8 }), mk(polar(-70, 10, 3.0, 50, 6, 6), 18, OC.plum, { prof: 'tip', a: .55 })] };
  },
  feather() { const S = [inkL(qcurve(-110, 130, 100, -130, -30, 14), 4, .6)]; for (let i = 1; i < 14; i++) { const s = i / 14, x = -110 + s * 210, y = 130 - s * 260 - Math.sin(s * Math.PI) * 18; S.push(mk(polar(x, y, -2.2, 60 * Math.sin(s * Math.PI) + 10, 6, 5), 10, OC.sky, { prof: 'tip', nb: 0, a: .6 }), mk(polar(x, y, .2, 60 * Math.sin(s * Math.PI) + 10, -6, 5), 10, OC.sky, { prof: 'tip', nb: 0, a: .6 })); } return { S }; },
  stones() { const S = []; [[0, 110, 120, 44], [-6, 30, 90, 36], [4, -36, 64, 30], [0, -86, 38, 22]].forEach(([x, y, rx, ry], k) => S.push(...shape(circ(x, y, rx, ry, 22), k % 2 ? OC.stone : mixc(OC.stone, OC.sky, .3), { a0: .3, a1: .45, ink: .3, n: 12 }))); return { S }; },
  house() {
    const S = shape(rect(-120, -20, 120, 150), OC.cream, { a0: .35, a1: .5, ink: .35 });
    S.push(...shape([[-150, -10], [0, -140], [150, -10]], OC.rose, { a0: .35, a1: .5, ink: .35 }), ...shape(rect(-30, 50, 30, 150), OC.wood, { a0: .4, a1: .6, ink: .3, n: 8 }));
    S.push(...shape(rect(55, 20, 100, 65), OC.sun, { a0: .4, a1: .6, ink: .35, n: 6 }));
    return { S };
  },
  door() {
    const S = shape(rect(-80, -150, 80, 150), OC.wood, { a0: .3, a1: .45, ink: .4 });
    S.push(...shape(rect(-55, -120, 55, -10), mixc(OC.wood, INK, .15), { a0: .25, a1: .35, ink: .3, n: 8 }), ...shape(rect(-55, 20, 55, 120), mixc(OC.wood, INK, .15), { a0: .25, a1: .35, ink: .3, n: 8 }));
    clump(S, 52, 6, 6, 4, [OC.sun], { l0: 8, l1: 12, w0: 10, w1: 14, a0: .8, a1: .9 });
    return { S };
  },
  door_open() {
    const S = shape(rect(-80, -150, 80, 150), '#f2d98e', { a0: .3, a1: .45, ink: .2 });
    S.push(...shape([[-80, -150], [-160, -120], [-160, 170], [-80, 150]], OC.wood, { a0: .35, a1: .5, ink: .4 }));
    S.push(...shape([[-80, 150], [80, 150], [190, 230], [-40, 230]], OC.sun, { a0: .15, a1: .25, ink: 0, n: 12 }));
    edge(S, rect(-86, -156, 86, 150), OC.wood, 12, .55, true, .4);
    return { S };
  },
  window() {
    const S = shape(rect(-110, -130, 110, 130), OC.sky, { a0: .2, a1: .3, ink: .2 });
    edge(S, rect(-116, -136, 116, 136), OC.wood, 18, .6, true, .45); S.push(mk(qcurve(0, -130, 0, 130, 0, 8), 14, OC.wood, { prof: 'even', a: .6 }), mk(qcurve(-110, 0, 110, 0, 0, 8), 14, OC.wood, { prof: 'even', a: .6 }));
    S.push(...OBJ.sun().S.slice(0, 6).map(s => s));
    return { S };
  },
  lamp() {
    const S = shape([[-90, -40], [90, -40], [60, -140], [-60, -140]], OC.sun, { a0: .35, a1: .5, ink: .35 });
    S.push(inkL(qcurve(0, -40, 0, 120, 0, 8), 6, .65), mk(qcurve(-70, 130, 70, 130, -6, 8), 18, OC.wood, { prof: 'even', a: .6 }));
    clump(S, 0, 10, 70, 14, ['#f3dc9c'], { l0: 40, l1: 70, w0: 40, w1: 60, a0: .12, a1: .2 });
    return { S };
  },
  candle() {
    const S = shape(rect(-34, -40, 34, 150), '#e9cf9a', { a0: .45, a1: .62, ink: .45, edge: OC.cup });
    S.push(mk(qcurve(0, -50, 2, -130, 10, 8), 34, OC.sun, { prof: 'leaf', a: .85 }), mk(qcurve(0, -54, 2, -100, 6, 6), 16, OC.one, { prof: 'leaf', a: .85 }));
    clump(S, 0, -90, 60, 10, ['#f3dc9c'], { l0: 40, l1: 70, w0: 40, w1: 60, a0: .1, a1: .18 });
    return { S };
  },
  bed() {
    const S = shape(rect(-190, 0, 190, 90), OC.blue, { a0: .3, a1: .45, ink: .35 });
    S.push(...shape(circ(-130, -16, 50, 26), OC.cream, { a0: .45, a1: .6, ink: .3, n: 8 }));
    edge(S, [[-200, -80], [-200, 140]], OC.wood, 20, .65, false, .4); edge(S, [[200, -20], [200, 140]], OC.wood, 20, .65, false, .4);
    return { S };
  },
  chair() { const S = []; edge(S, [[-60, -150], [-60, 150]], OC.wood, 16, .7, false, .4); edge(S, [[-60, 10], [70, 10], [70, 150]], OC.wood, 16, .7, false, .4); S.push(...shape(rect(-64, -4, 76, 26), OC.wood, { a0: .4, a1: .55, ink: .3, n: 8 })); edge(S, [[-60, -130], [10, -130]], OC.wood, 12, .6, false, .3); return { S }; },
  book() {
    const S = [], PG = OC.cream;
    for (const s of [-1, 1]) { for (let k = 0; k < 3; k++) S.push(mk(qcurve(s * 8, -48 + k * 36, s * 140, -60 + k * 36 + 10, s * 8, 10), 40, PG, { prof: 'even', a: .5 })); for (let k = 0; k < 3; k++) S.push(inkL(qcurve(s * 30, -40 + k * 30, s * 118, -48 + k * 30, s * 4, 8), 3, .35)); }
    S.push(inkL(qcurve(0, -62, 0, 70, 0, 8), 4, .7), mk(qcurve(-150, 78, 150, 78, -14, 12), 12, OC.earth, { prof: 'even', a: .6 }));
    return { S };
  },
  letter() {
    const S = shape(rect(-150, -90, 150, 90), OC.cream, { a0: .4, a1: .55, ink: .4 });
    S.push(inkL(qcurve(-150, -90, 0, 20, 0, 8), 3.5, .55), inkL(qcurve(150, -90, 0, 20, 0, 8), 3.5, .55), ...OBJ.heart(1.8, 24).S);
    return { S };
  },
  phone() {
    const S = shape(rect(-70, -140, 70, 140), OC.night, { a0: .35, a1: .5, ink: .4 });
    S.push(...shape(rect(-52, -112, 52, 104), mixc(OC.sky, PAPER, .3), { a0: .35, a1: .5, ink: 0, n: 10 }));
    return { S };
  },
  clock() {
    const S = shape(circ(0, 0, 130, 130), OC.cream, { a0: .3, a1: .45, ink: 0 }); edge(S, circ(0, 0, 134, 134, 24), OC.wood, 16, .55, true, .4);
    for (let k = 0; k < 12; k++) { const a = k / 12 * Math.PI * 2; S.push(inkL(polar(Math.cos(a) * 104, Math.sin(a) * 104, a, 14, 0, 3), 4, .55)); }
    S.push(inkL(qcurve(0, 0, 0, -84, 0, 4), 7, .8), inkL(qcurve(0, 0, 60, 24, 0, 4), 6, .8));
    return { S };
  },
  key() {
    const S = []; edge(S, circ(-90, 0, 46, 46, 16), OC.sun, 20, .7, true, .4);
    S.push(mk(qcurve(-44, 0, 150, 0, 0, 10), 18, OC.sun, { prof: 'even', a: .7 }), mk(qcurve(110, 0, 110, 44, 0, 4), 16, OC.sun, { prof: 'even', a: .7 }), mk(qcurve(140, 0, 140, 34, 0, 4), 16, OC.sun, { prof: 'even', a: .7 }), inkL(qcurve(-44, -9, 150, -9, 0, 8), 2.5, .4));
    return { S };
  },
  bridge() {
    const S = []; S.push(mk(circ(0, 120, 200, 150, 26, Math.PI, Math.PI * 2), 26, OC.wood, { prof: 'even', nb: 4, a: .6 }), mk(qcurve(-230, -20, 230, -20, 10, 20), 18, OC.wood, { prof: 'even', a: .65 }));
    for (let k = -3; k <= 3; k++) S.push(mk(qcurve(k * 60, -20, k * 60, 120 - Math.sqrt(Math.max(0, 1 - (k * 60 / 200) ** 2)) * 150, 0, 4), 9, OC.wood, { prof: 'even', a: .55 }));
    S.push(mk(qcurve(-260, 140, 260, 140, -10, 16), 18, OC.water, { prof: 'even', a: .5 }));
    return { S };
  },
  umbrella() {
    const P = [...circ(0, 0, 160, 110, 24, Math.PI, Math.PI * 2), [160, 0], [-160, 0]], S = shape(P, OC.rose, { a0: .3, a1: .45, ink: .35 });
    S.push(inkL(qcurve(0, -110, 0, 150, 0, 8), 5, .7), inkL(qctrl(0, 150, 0, 190, 36, 180, 8), 5, .7));
    return { S };
  },
  backpack() {
    const S = shape([[-100, -110], [100, -110], [118, 150], [-118, 150]], OC.earth, { a0: .3, a1: .45, ink: .4 });
    S.push(...shape(rect(-70, 40, 70, 120), mixc(OC.earth, OC.terra, .5), { a0: .3, a1: .45, ink: .35, n: 8 }));
    edge(S, [[-60, -110], [-50, -170], [50, -170], [60, -110]], OC.earth, 14, .6, false, .35);
    return { S };
  },
  hand() {
    const S = shape([[-80, 0], [80, 0], [70, 140], [-70, 140]], OC.skin, { a0: .3, a1: .42, ink: .3 });
    [[-60, -100], [-20, -130], [20, -126], [56, -96]].forEach(([x, y]) => S.push(mk(qcurve(x * .8, 4, x, y, 0, 6), 34, OC.skin, { prof: 'even', a: .45 })));
    S.push(mk(qcurve(-80, 60, -150, -10, -10, 6), 34, OC.skin, { prof: 'even', a: .45 }));
    return { S };
  },
  calendar() {
    const S = shape(rect(-140, -120, 140, 140), OC.cream, { a0: .35, a1: .5, ink: .4 });
    S.push(...shape(rect(-140, -120, 140, -70), OC.rose, { a0: .4, a1: .55, ink: .3, n: 8 }));
    for (let k = 1; k < 4; k++) S.push(inkL(qcurve(-140 + k * 70, -70, -140 + k * 70, 140, 0, 4), 2.5, .4));
    for (let k = 1; k < 4; k++) S.push(inkL(qcurve(-140, -70 + k * 52, 140, -70 + k * 52, 0, 4), 2.5, .4));
    S.push(...shape(rect(-66, -14, -4, 34), OC.one, { a0: .4, a1: .6, ink: 0, n: 5 }));
    return { S };
  },
  checklist() {
    const S = shape(rect(-120, -150, 120, 150), OC.cream, { a0: .35, a1: .5, ink: .35 });
    for (let k = 0; k < 4; k++) { const y = -96 + k * 64; S.push(inkL(qcurve(-30, y, 90, y, 0, 6), 3, .5)); if (k < 2) S.push(mk([[-90, y], [-74, y + 16], [-50, y - 18]], 8, OC.leaf, { prof: 'even', nb: 0, a: .85 })); else edge(S, rect(-92, y - 14, -64, y + 14), INK2, 3, .4, true, 0); }
    return { S };
  },
  gift() {
    const S = shape(rect(-110, -40, 110, 140), OC.plum, { a0: .3, a1: .45, ink: .35 });
    S.push(...shape(rect(-124, -80, 124, -40), mixc(OC.plum, PAPER, .2), { a0: .35, a1: .5, ink: .3, n: 8 }), mk(qcurve(0, -80, 0, 140, 0, 8), 24, OC.sun, { prof: 'even', a: .7 }));
    S.push(mk(qctrl(0, -80, -70, -150, -10, -150, 8), 16, OC.sun, { prof: 'even', a: .7 }), mk(qctrl(0, -80, 70, -150, 10, -150, 8), 16, OC.sun, { prof: 'even', a: .7 }));
    return { S };
  },
  fire() {
    const S = [mk(qcurve(-120, 120, 110, 80, 0, 8), 26, OC.wood, { prof: 'even', a: .6 }), mk(qcurve(-110, 80, 120, 124, 0, 8), 26, mixc(OC.wood, INK, .2), { prof: 'even', a: .6 })];
    for (let k = 0; k < 7; k++) S.push(mk(qcurve(-60 + k * 20, 90, -50 + k * 18 + rnd(-10, 10), -40 - Math.sin(k / 6 * Math.PI) * 90, rnd(-20, 20), 8), rnd(30, 44), k % 2 ? OC.sun : OC.one, { prof: 'tip', a: .55 }));
    return { S };
  },
  mirror() {
    const S = shape(circ(0, 0, 100, 140), mixc(OC.sky, PAPER, .3), { a0: .25, a1: .35, ink: 0 }); edge(S, circ(0, 0, 106, 146, 24), OC.wood, 20, .6, true, .4);
    S.push(mk(qcurve(-40, -60, 10, -100, 0, 6), 10, PAPER, { prof: 'even', a: .7 }));
    return { S };
  },
  bench() { const S = shape(rect(-200, -10, 200, 20), OC.wood, { a0: .4, a1: .55, ink: .35, n: 10 }); S.push(...shape(rect(-200, -90, 200, -60), OC.wood, { a0: .4, a1: .55, ink: .3, n: 10 })); edge(S, [[-170, 20], [-180, 120]], OC.wood, 14, .7, false, .35); edge(S, [[170, 20], [180, 120]], OC.wood, 14, .7, false, .35); return { S }; },
};
const OBJECT_NAMES = Object.keys(OBJ);
// build an object normalised to a box: returns { S, spr, w, h, cx, cy, anchor (relative to centre), steam, line }
function buildObject(name, seed) {
  return withSeed(seed, () => {
    const g = (OBJ[name] || OBJ.blot)(); const [x0, y0, x1, y1] = bbox(g.S, 0), cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    const S = g.S.map(s => ({ ...s, pts: s.pts.map(([x, y]) => [x - cx, y - cy]) }));
    const steam = g.steam ? g.steam.map(s => ({ ...s, pts: s.pts.map(([x, y]) => [x - cx, y - cy]) })) : null;
    return { name, S, steam, line: !!g.line, spr: g.line ? null : sprite(S), w: x1 - x0, h: y1 - y0, anchor: g.anchor ? [g.anchor[0] - cx, g.anchor[1] - cy] : [0, 0] };
  });
}
