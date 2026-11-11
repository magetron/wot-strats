/* Runs inside a loaded stratsketch.com/<code> page (the app's hidden import window).
   StratSketch has no export and no per-slide link, so this reads the briefing object the page itself
   holds (found through React's props) and serialises every slide: map, icons, shapes with their real
   stroke/fill/dash, and text notes. Coordinates are in 1/1000 of the map. */
(() => {
  function findBriefing() {
    for (const el of document.querySelectorAll('[class*="stage"], canvas')) {
      const fk = Object.keys(el).find(k => k.startsWith('__reactFiber'));
      let f = fk && el[fk];
      for (let i = 0; i < 40 && f; i++, f = f.return) {
        const p = f.memoizedProps;
        if (!p || typeof p !== 'object') continue;
        if (p.slide && p.slide.briefing && p.slide.briefing.slides) return p.slide.briefing;
        if (p.briefing && p.briefing.slides && p.briefing.code) return p.briefing;
      }
    }
    return null;
  }
  const slidesOf = b => Array.isArray(b.slides) ? b.slides : [...b.slides.values()];

  /* Cheap check the importer polls until the numbers stop changing. */
  window.__stratProbe = () => {
    const b = findBriefing();
    if (!b) return JSON.stringify({ found: false, title: document.title });
    const slides = slidesOf(b);
    return JSON.stringify({
      found: true, n: slides.length, game: b.game && b.game.name,
      ents: slides.reduce((a, s) => a + (s.entities ? s.entities.length : 0), 0),
      maps: slides.filter(s => s._map && s._map._definition).length,
    });
  };

  window.__stratExtract = () => {
    const b = findBriefing();
    const slides = slidesOf(b);
    const q = v => Math.round(v * 1000), q1 = v => Math.round(v * 10000) / 10;
    const hex = c => '#' + [c.r, c.g, c.b].map(v => Math.round(v).toString(16).padStart(2, '0')).join('');
    const col = s => {
      if (!s || typeof s !== 'string') return null;
      const m = s.match(/rgba?\(([^)]+)\)/); if (!m) return s;
      const [r, g, bl, a = 1] = m[1].split(',').map(Number);
      const h = '#' + [r, g, bl].map(v => Math.round(v).toString(16).padStart(2, '0')).join('');
      return a >= 1 ? h : h + Math.round(a * 255).toString(16).padStart(2, '0');
    };
    const unknown = {};
    function style(node, grp) {
      const o = {};
      const st = col(node._stroke ?? grp._stroke); if (st) o.c = st;
      const f = col(node._fill ?? grp._fill); if (f) o.f = f;
      const w = node.strokeWidth ?? grp.strokeWidth; if (w !== undefined) o.w = q1(w);
      const d = node.dash !== undefined ? node.dash : grp.dash; if (d && d.length) o.d = d.map(q1);
      const op = (node.opacity ?? 1) * (grp.opacity ?? 1); if (op !== 1) o.op = Math.round(op * 100) / 100;
      return o;
    }
    function shapes(e) {
      const g = e.group, out = [];
      for (const n of g.children) {
        if (!n._visible) continue;
        const x = g.x + n.x, y = g.y + n.y;
        if (n.points) {
          const rot = (n.rotation || 0) * Math.PI / 180, cs = Math.cos(rot), sn = Math.sin(rot);
          const small = n.points.every(p => Math.abs(p.x) < 0.02 && Math.abs(p.y) < 0.02);  // arrow heads keep a decimal
          const qq = small ? q1 : q;
          const o = { p: n.points.flatMap(p => [qq(x + p.x * cs - p.y * sn), qq(y + p.x * sn + p.y * cs)]), ...style(n, g) };
          if (n.closed) o.z = 1;
          out.push(o);
        } else if (n._start && n._end) {
          if (n._arc) {
            const a = n._arc;
            out.push({ a: [q1(x + n._start.x), q1(y + n._start.y), q1(x + n._end.x), q1(y + n._end.y), q1(a.radius),
              Math.abs(a.endAngle - a.startAngle) > Math.PI ? 1 : 0, a.isCounterClockwise ? 0 : 1], ...style(n, g) });
          } else out.push({ p: [q(x + n._start.x), q(y + n._start.y), q(x + n._end.x), q(y + n._end.y)], ...style(n, g) });
        } else if (n.radius !== undefined && n._width === undefined) {
          out.push({ o: [q(x), q(y), q1(n.radius)], ...style(n, g) });
        } else if (n._width !== undefined && n._height !== undefined && n._text === undefined) {
          out.push({ r: [q(x), q(y), q(n._width), q(n._height), q1(n.radius || 0)], ...style(n, g) });
        } else unknown[e.constructor.name] = 1;
      }
      return out;
    }
    function rdp(pts, eps) {
      if (pts.length < 3) return pts;
      const a = pts[0], z = pts[pts.length - 1]; let dmax = 0, idx = 0;
      const dx = z[0] - a[0], dy = z[1] - a[1], L = Math.hypot(dx, dy) || 1;
      for (let i = 1; i < pts.length - 1; i++) {
        const d = Math.abs(dy * pts[i][0] - dx * pts[i][1] + z[0] * a[1] - z[1] * a[0]) / L;
        if (d > dmax) { dmax = d; idx = i; }
      }
      if (dmax > eps) return rdp(pts.slice(0, idx + 1), eps).slice(0, -1).concat(rdp(pts.slice(idx), eps));
      return [a, z];
    }

    const raw = slides.map(s => {
      const def = s._map && s._map._definition;
      const o = { m: def ? def.name : null, v: (s._map && s._map._variant && s._map._variant.id) || 1,
        team: s._map ? s._map._team : 2, nm: s.name || '', bg: (s.background && s.background._src) || '', i: [], s: [], t: [] };
      for (const e of s.entities) {
        const isText = e.text !== undefined && !e.icon && e.width !== undefined && !e.points;
        if (e.icon) {
          if (e.position.x < -0.02 || e.position.x > 1.02 || e.position.y < -0.02 || e.position.y > 1.02) continue;
          const it = [q(e.position.x), q(e.position.y), hex(e.settings.color), e.settings.iconId];
          const label = (e.textNode && e.textNode._text) || ''; if (label) it.push(label);
          o.i.push(it);
        } else if (isText) {
          const t = (e.text || '').trim();
          if (t) o.t.push([q(e.position.x), q(e.position.y), q(e.width), e.settings.fontSize, hex(e.settings.color), t]);
        } else {
          for (const sh of shapes(e)) {
            const xs = [];
            if (sh.p) for (let k = 0; k < sh.p.length; k += 2) xs.push(sh.p[k]);
            if (sh.o) xs.push(sh.o[0] - sh.o[2], sh.o[0] + sh.o[2]);
            if (sh.r) xs.push(sh.r[0], sh.r[0] + sh.r[2]);
            if (sh.a) xs.push(sh.a[0], sh.a[2]);
            if (xs.length && (Math.max(...xs) < 0 || Math.min(...xs) > 1000)) continue;  // drawn beside the map (legend)
            if (sh.p && sh.p.length > 8) {
              const pts = []; for (let k = 0; k < sh.p.length; k += 2) pts.push([sh.p[k], sh.p[k + 1]]);
              const out = [];
              for (const p of rdp(pts, 0.5)) if (!out.length || p[0] !== out[out.length - 2] || p[1] !== out[out.length - 1]) out.push(p[0], p[1]);
              sh.p = out;
            }
            o.s.push(sh);
          }
        }
      }
      return o;
    });

    // text the author put on many slides (rules, legend) is strat-level, not per map
    const freq = {};
    raw.forEach(s => new Set(s.t.map(t => t[5])).forEach(t => freq[t] = (freq[t] || 0) + 1));
    const thr = Math.max(3, Math.ceil(raw.length * 0.3));
    const common = new Set(Object.keys(freq).filter(t => freq[t] >= thr));
    const first = new Map();
    raw.forEach(s => s.t.forEach(t => { if (common.has(t[5]) && !first.has(t[5])) first.set(t[5], [t[1], t[0], t[4], t[5]]); }));
    const rules = [...first.values()].sort((a, z) => a[0] - z[0] || a[1] - z[1]).map(r => [r[2], r[3]]);
    raw.forEach(s => { s.t = s.t.filter(t => !common.has(t[5])); });

    // StratSketch's own display names for maps (page translations)
    const codes = raw.map(s => s.m).filter(Boolean);
    const findNames = (o, depth) => {
      if (!o || typeof o !== 'object' || depth > 8) return null;
      for (const k in o) {
        if (k === 'maps' && o[k] && typeof o[k] === 'object' && codes.some(c => typeof o[k][c] === 'string')) return o[k];
        const r = findNames(o[k], depth + 1); if (r) return r;
      }
      return null;
    };
    const allNames = findNames(window.__NEXT_DATA__, 0) || {};
    const names = {};
    raw.forEach(s => { if (s.m && allNames[s.m]) names[s.m] = allNames[s.m]; });

    const game = b.game || {};
    const withMap = slides.find(s => s._map && s._map._definition);
    const icons = withMap ? withMap._map._definition.game.icons.map(ic => ({ id: ic.id, name: ic.name, path: ic.path, w: ic.width, h: ic.height, scale: ic.scale })) : [];
    return JSON.stringify({ code: b.code, title: document.title, game: { name: game.name, version: game.version },
      slides: raw, rules, icons, names, unknown: Object.keys(unknown) });
  };
})();
