// GridPilot deck: navigation, scaling, presenter view, and the charts (data from data.js).
(() => {
  'use strict';
  const D = window.DECK_DATA;
  const DASH = 'http://127.0.0.1:4173/?year=test'; // ?year=test opens the dashboard on the sealed test year (T21)
  const DASH_WINDOW = 'gridpilot'; // one named tab: every link reuses it
  const W = 1600, H = 900;
  const stage = document.getElementById('stage');
  const slides = [...document.querySelectorAll('.slide')];
  const notes = document.getElementById('notes');
  const counter = document.getElementById('counter');
  const main = slides.filter((s) => !s.classList.contains('appx')).length;
  const NS = 'http://www.w3.org/2000/svg';
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  let cur = 0;
  let presenter = null;
  const t0 = Date.now();

  // ---- scale the 1600 × 900 stage to the window
  function fit() {
    const s = Math.min(window.innerWidth / W, window.innerHeight / H);
    stage.style.transform = `translate(-50%, -50%) scale(${s})`;
  }

  // ---- crops of dashboard screenshots: data-crop="x y w h" in source pixels
  for (const el of document.querySelectorAll('.crop[data-crop]')) {
    const [x, y, w, h] = el.dataset.crop.split(' ').map(Number);
    const srcW = Number(el.dataset.srcW);
    el.style.aspectRatio = `${w} / ${h}`;
    const img = el.querySelector('img');
    img.style.width = `${(srcW / w) * 100}%`;
    img.style.left = `${(-x / w) * 100}%`;
    img.style.top = `${(-y / h) * 100}%`;
  }

  // ---- dashboard deep links on the beat slides, all into one named tab
  const icon = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M9 3h4v4M13 3 7.5 8.5M12 9.5V13H3V4h3.5"/></svg>';
  for (const s of slides) {
    if (!s.dataset.link) continue;
    const a = document.createElement('a');
    a.className = 'dash';
    a.href = DASH + s.dataset.link;
    a.target = DASH_WINDOW;
    a.innerHTML = `Open in dashboard: ${s.dataset.linkLabel} ${icon}`;
    a.title = `${DASH}${s.dataset.link}: opens on the test year, in the "gridpilot" tab`;
    s.appendChild(a);
  }

  // ---- presenter view: notes in their own window (for an extended display), so a mirrored screen never shows them
  function presenterHTML() {
    const s = slides[cur];
    const nx = slides[cur + 1];
    const n = s.querySelector('.notes');
    const m = Math.floor((Date.now() - t0) / 60000), sec = Math.floor(((Date.now() - t0) / 1000) % 60);
    return `<div class="pv"><p class="pv-top"><b>${s.dataset.label}</b> ${s.dataset.title}<span>${nx ? `next: ${nx.dataset.label} ${nx.dataset.title}` : 'last slide'} · ${m}:${String(sec).padStart(2, '0')}</span></p>${n ? n.innerHTML : ''}</div>`;
  }
  function renderPresenter() {
    if (!presenter || presenter.closed) return;
    presenter.document.getElementById('pv').innerHTML = presenterHTML();
  }
  function openPresenter() {
    presenter = window.open('', 'gridpilot-presenter', 'width=980,height=720');
    if (!presenter) return;
    const d = presenter.document;
    d.open();
    d.write(`<!doctype html><html><head><meta charset="utf-8"><title>GridPilot presenter notes</title><style>
      body{margin:0;background:${css('--notes-bg')};color:${css('--notes-ink')};font:20px/1.5 ${css('--sans')};padding:24px 32px}
      h2{font:600 15px ${css('--sans')};color:${css('--notes-meta')};margin:0 0 10px} p{margin:0 0 12px;max-width:900px}
      .meta,.cut{color:${css('--notes-meta')}} .meta{font-size:16px}
      .cut::before{content:attr(data-c) ' ';font-size:12px;border:1px solid #8a7666;border-radius:4px;padding:0 4px;margin-right:2px}
      .pv-top{display:flex;justify-content:space-between;gap:20px;border-bottom:1px solid #5b493f;padding-bottom:10px;margin-bottom:16px}
      .pv-top span{color:${css('--notes-meta')};font-size:16px}
    </style></head><body><div id="pv"></div><p style="font-size:13px;color:#a8988b">Keys work here too. Close this window to end the presenter view.</p></body></html>`);
    d.close();
    presenter.addEventListener('keydown', onKey);
    renderPresenter();
  }
  setInterval(renderPresenter, 1000);

  // ---- navigation
  function show(i, push = true) {
    cur = Math.max(0, Math.min(slides.length - 1, i));
    slides.forEach((s, k) => { s.classList.toggle('on', k === cur); s.setAttribute('aria-hidden', String(k !== cur)); s.inert = k !== cur; });
    const s = slides[cur];
    const lab = s.dataset.label;
    counter.textContent = s.classList.contains('appx') ? `${lab} · appendix` : `${lab} / ${main}`;
    const n = s.querySelector('.notes');
    notes.innerHTML = n ? n.innerHTML : '';
    document.title = `GridPilot deck · ${lab} ${s.dataset.title}`;
    if (push) history.replaceState(null, '', `#${lab}`);
    renderPresenter();
  }
  function fromHash() {
    const h = decodeURIComponent(location.hash.slice(1));
    const k = slides.findIndex((s) => s.dataset.label === h);
    return k < 0 ? 0 : k;
  }
  function onKey(e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const k = e.key;
    if ((k === ' ' && e.shiftKey) || k === 'ArrowLeft' || k === 'PageUp' || k === 'ArrowUp') { e.preventDefault(); show(cur - 1); }
    else if (k === 'ArrowRight' || k === ' ' || k === 'PageDown' || k === 'ArrowDown') { e.preventDefault(); show(cur + 1); }
    else if (k === 'Home') { e.preventDefault(); show(0); }
    else if (k === 'End') { e.preventDefault(); show(main - 1); }
    else if (/^[1-8]$/.test(k)) show(Math.min(Number(k), main) - 1);
    else if (k === '9') show(main);
    else if (k === 'n' || k === 'N') notes.classList.toggle('on');
    else if (k === 'p' || k === 'P') openPresenter();
    else if (k === 'f' || k === 'F') { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen?.().catch(() => {}); }
  }
  window.addEventListener('keydown', onKey);
  // a click on the right/left edge of the stage steps, except on links and charts
  stage.addEventListener('click', (e) => {
    if (e.target.closest('a, button, svg, .chart-wrap, table')) return;
    const r = stage.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width;
    if (x > 0.7) show(cur + 1); else if (x < 0.15) show(cur - 1);
  });
  window.addEventListener('hashchange', () => show(fromHash(), false));
  window.addEventListener('resize', fit);

  // ---- svg helpers
  function el(tag, attrs, parent, text) {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
    if (text != null) n.textContent = text;
    if (parent) parent.appendChild(n);
    return n;
  }
  const fmt = (x) => Math.round(x).toLocaleString('en-US');
  const pct = (x) => (x * 100).toFixed(1);
  const hr = (h) => `${h % 12 === 0 ? 12 : h % 12} ${h % 24 < 12 ? 'AM' : 'PM'}`;
  function tipAt(tip, html, x, y) { tip.innerHTML = html; tip.style.display = 'block'; tip.style.left = `${x}px`; tip.style.top = `${y}px`; }
  const AX = 19; // axis text, px on the stage

  // ---- slide 2: Utah's July weekday, test year
  function july() {
    const svg = document.getElementById('ch-july');
    const tip = document.getElementById('tip-july');
    const { net, demand, solar, rush, netPeakH, demPeakH } = D.july;
    const w = 1000, h = 440, m = { l: 62, r: 24, t: 36, b: 40 };
    const iw = w - m.l - m.r, ih = h - m.t - m.b;
    const yMax = 10000;
    const X = (i) => m.l + (i / 23) * iw;
    const Y = (v) => m.t + ih - (v / yMax) * ih;
    const defs = el('defs', {}, svg);
    const pat = el('pattern', { id: 'hatch', width: 6, height: 6, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' }, defs);
    el('rect', { width: 6, height: 6, fill: css('--rush-fill'), 'fill-opacity': .7 }, pat);
    el('line', { x1: 0, y1: 0, x2: 0, y2: 6, stroke: css('--rush'), 'stroke-width': 1, 'stroke-opacity': .45 }, pat);
    // evening rush: [rush[0], rush[1]) on the hour axis (7 PM to 11 PM on the test year)
    const bx0 = X(rush[0]), bx1 = X(Math.min(rush[1], 23));
    el('rect', { x: bx0, y: m.t, width: bx1 - bx0, height: ih, fill: 'url(#hatch)', rx: 4 }, svg);
    for (let v = 0; v <= yMax; v += 2000) {
      el('line', { x1: m.l, x2: m.l + iw, y1: Y(v), y2: Y(v), stroke: css('--hair'), 'stroke-width': 1 }, svg);
      el('text', { x: m.l - 10, y: Y(v) + 6, 'text-anchor': 'end', 'font-size': AX, fill: css('--ink-3') }, svg, v === 0 ? '0' : `${v / 1000}k`);
    }
    el('text', { x: m.l - 10, y: m.t - 14, 'text-anchor': 'end', 'font-size': AX, fill: css('--ink-3') }, svg, 'MW');
    for (const i of [0, 3, 6, 9, 12, 15, 18, 21]) el('text', { x: X(i), y: h - 10, 'text-anchor': 'middle', 'font-size': AX, fill: css('--ink-3') }, svg, hr(i));
    const p = solar.map((v, i) => `${X(i)},${Y(Math.max(0, v))}`).join(' L');
    el('path', { d: `M${X(0)},${Y(0)} L${p} L${X(23)},${Y(0)} Z`, fill: css('--solar'), 'fill-opacity': .75 }, svg);
    const line = (vals, attrs) => el('path', { d: 'M' + vals.map((v, i) => `${X(i)},${Y(v)}`).join(' L'), fill: 'none', 'stroke-linejoin': 'round', 'stroke-linecap': 'round', ...attrs }, svg);
    line(demand, { stroke: css('--ink-4'), 'stroke-width': 2 });
    line(net, { stroke: css('--ink'), 'stroke-width': 3 });
    el('circle', { cx: X(netPeakH), cy: Y(net[netPeakH]), r: 7, fill: css('--ink'), stroke: '#fff', 'stroke-width': 2 }, svg);
    el('text', { x: X(netPeakH), y: Y(net[netPeakH]) - 18, 'text-anchor': 'middle', 'font-size': 21, 'font-weight': 600, fill: css('--ink') }, svg, `${hr(netPeakH)} · ${fmt(net[netPeakH])} MW`);
    el('circle', { cx: X(demPeakH), cy: Y(demand[demPeakH]), r: 6, fill: css('--ink-4'), stroke: '#fff', 'stroke-width': 2 }, svg);
    el('text', { x: X(demPeakH), y: Y(demand[demPeakH]) - 16, 'text-anchor': 'middle', 'font-size': 20, fill: css('--ink-2') }, svg, `Demand peaks ${hr(demPeakH)}`);
    el('text', { x: X(0) + 4, y: Y(net[0]) + 28, 'font-size': 20, fill: css('--ink') }, svg, 'Net load');
    el('text', { x: X(0) + 4, y: Y(demand[0]) - 12, 'font-size': 20, fill: css('--ink-3') }, svg, 'Demand');
    el('text', { x: X(12), y: Y(Math.max(...solar) / 2) + 6, 'text-anchor': 'middle', 'font-size': 20, fill: css('--solar-ink') }, svg, 'Solar');
    const cross = el('line', { y1: m.t, y2: m.t + ih, stroke: css('--ink-3'), 'stroke-width': 1, 'stroke-dasharray': '3 3', visibility: 'hidden' }, svg);
    const hit = el('rect', { x: m.l, y: m.t, width: iw, height: ih, fill: 'transparent' }, svg);
    hit.addEventListener('mousemove', (e) => {
      const r = svg.getBoundingClientRect();
      const sx = (e.clientX - r.left) * (w / r.width);
      const i = Math.max(0, Math.min(23, Math.round(((sx - m.l) / iw) * 23)));
      cross.setAttribute('x1', X(i)); cross.setAttribute('x2', X(i)); cross.setAttribute('visibility', 'visible');
      tipAt(tip, `<b>${hr(i)}</b><br>Demand ${fmt(demand[i])} MW<br>Net load ${fmt(net[i])} MW<br>Solar ${fmt(Math.max(0, solar[i]))} MW`, Math.min(X(i) + 14, w - 220), Y(net[i]) - 20);
    });
    hit.addEventListener('mouseleave', () => { cross.setAttribute('visibility', 'hidden'); tip.style.display = 'none'; });
  }

  // ---- slide 5: each policy's own interval
  function intervals() {
    const svg = document.getElementById('ch-int');
    const tip = document.getElementById('tip-int');
    const names = { S: 'S fixed clean-region ranking', K: 'K seasonal-average forecast', W: 'W weekly-profile forecast', L: 'L learned model', W_time: 'W wait-only, in Utah', L_time: 'L wait-only, in Utah' };
    const w = 760, h = 360, m = { l: 300, r: 78, t: 6, b: 40 };
    const iw = w - m.l - m.r;
    const X = (v) => m.l + (v / 0.3) * iw;
    const rowH = (h - m.t - m.b) / D.policies.length;
    for (const v of [0, 0.1, 0.2, 0.3]) {
      el('line', { x1: X(v), x2: X(v), y1: m.t, y2: h - m.b, stroke: css('--hair'), 'stroke-width': 1 }, svg);
      el('text', { x: X(v), y: h - 10, 'text-anchor': 'middle', 'font-size': AX, fill: css('--ink-3') }, svg, `${v * 100}%`);
    }
    D.policies.forEach((p, k) => {
      const y = m.t + rowH * (k + 0.5);
      const isS = p.p === 'S';
      const col = isS ? css('--route') : css('--ink-3');
      el('text', { x: 0, y: y + 7, 'font-size': 20, 'font-weight': isS ? 600 : 400, fill: isS ? css('--ink') : css('--ink-2') }, svg, names[p.p]);
      el('line', { x1: X(p.ci[0]), x2: X(p.ci[1]), y1: y, y2: y, stroke: col, 'stroke-width': isS ? 3 : 2, 'stroke-linecap': 'round' }, svg);
      el('circle', { cx: X(p.saving), cy: y, r: isS ? 8 : 6, fill: col, stroke: css('--paper'), 'stroke-width': 2 }, svg);
      el('text', { x: w - 2, y: y + 7, 'text-anchor': 'end', 'font-size': 20, 'font-weight': isS ? 600 : 400, fill: css('--ink') }, svg, `${pct(p.saving)}%`);
      const hit = el('rect', { x: 0, y: y - rowH / 2, width: w, height: rowH, fill: 'transparent' }, svg);
      hit.addEventListener('mousemove', () => tipAt(tip, `<b>${names[p.p]}</b><br>${pct(p.saving)}%, 95% interval ${pct(p.ci[0])}–${pct(p.ci[1])}%`, 120, y + 24));
      hit.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
    });
  }

  // ---- slide 6: the largest 1% of jobs, and the mobility bars
  function top1() {
    const svg = document.getElementById('ch-top1');
    const w = 560, bh = 44, x0 = 100, iw = w - x0 - 4;
    const rows = [['Jobs', 0.01, 'largest 1%'], ['Energy', D.top1, `${(D.top1 * 100).toFixed(0)}%`]];
    rows.forEach(([lab, f, txt], k) => {
      const y = 16 + k * 100;
      el('text', { x: 0, y: y + bh / 2 + 7, 'font-size': 21, fill: css('--ink-2') }, svg, lab);
      el('rect', { x: x0, y, width: iw, height: bh, rx: 4, fill: css('--ground-3') }, svg);
      el('rect', { x: x0, y, width: Math.max(4, iw * f), height: bh, rx: 4, fill: css('--ink') }, svg);
      const big = f > 0.5;
      el('text', { x: big ? x0 + iw * f - 14 : x0 + Math.max(4, iw * f) + 12, y: y + bh / 2 + 7, 'text-anchor': big ? 'end' : 'start', 'font-size': 21, 'font-weight': 600, fill: big ? css('--paper') : css('--ink') }, svg, txt);
    });
    el('path', { d: `M${x0 + 2},${16 + bh} L${x0 + 2},${116}`, stroke: css('--ink'), 'stroke-width': 1.5, 'stroke-dasharray': '3 3', fill: 'none' }, svg);
  }
  function mobility() {
    const svg = document.getElementById('ch-mob');
    const tip = document.getElementById('tip-mob');
    const M = D.mobility;
    const w = 800, h = 330, x0 = 4, iw = w - x0 - 140;
    const X = (v) => x0 + (v / 0.3) * iw;
    for (const v of [0, 0.1, 0.2, 0.3]) {
      el('line', { x1: X(v), x2: X(v), y1: 40, y2: h - 34, stroke: css('--hair'), 'stroke-width': 1 }, svg);
      el('text', { x: Math.max(X(v), 14), y: h - 8, 'text-anchor': 'middle', 'font-size': AX, fill: css('--ink-3') }, svg, `${v * 100}%`);
    }
    const rows = [
      ['All flexible jobs may move', M.all, M.all_ci, M.all_val, M.all_val_ci],
      ['Only jobs of ≤ 8 GPUs may move', M.S, M.S_ci, M.S_val, M.S_val_ci],
    ];
    rows.forEach(([lab, t, ci, val, vci], k) => {
      const y = 26 + k * 140;
      el('text', { x: x0, y, 'font-size': 21, 'font-weight': 600, fill: css('--ink') }, svg, lab);
      el('rect', { x: X(0), y: y + 14, width: X(t) - X(0), height: 40, rx: 4, fill: css('--route') }, svg);
      el('line', { x1: X(ci[0]), x2: X(ci[1]), y1: y + 34, y2: y + 34, stroke: css('--ink'), 'stroke-width': 2 }, svg);
      for (const c of ci) el('line', { x1: X(c), x2: X(c), y1: y + 25, y2: y + 43, stroke: css('--ink'), 'stroke-width': 2 }, svg);
      el('text', { x: X(ci[1]) + 12, y: y + 42, 'font-size': 24, 'font-weight': 600, fill: css('--ink') }, svg, `${pct(t)}%`);
      el('text', { x: X(ci[1]) + 90, y: y + 42, 'font-size': 20, fill: css('--ink-3') }, svg, 'test year');
      el('rect', { x: X(0), y: y + 60, width: Math.max(2, X(val) - X(0)), height: 16, rx: 3, fill: css('--val') }, svg);
      el('text', { x: X(val) + 12, y: y + 75, 'font-size': 20, fill: css('--ink-3') }, svg, `validation ${pct(val)}%`);
      const hit = el('rect', { x: 0, y: y - 6, width: w, height: 90, fill: 'transparent' }, svg);
      hit.addEventListener('mousemove', () => tipAt(tip, `<b>${lab}</b><br>Test ${pct(t)}% [${pct(ci[0])}, ${pct(ci[1])}]<br>Validation ${pct(val)}% [${pct(vci[0])}, ${pct(vci[1])}]`, 360, y + 80));
      hit.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
    });
  }

  // ---- slide 3: bars to scale against staying
  function jobBar() {
    const s = Number(document.querySelector('[data-n="job_stay"]').textContent.replace(/,/g, ''));
    const n = Number(document.querySelector('[data-n="job_nw"]').textContent.replace(/,/g, ''));
    document.getElementById('bar-nw').style.width = `${(n / s) * 100}%`;
  }

  // ---- slide 7: rush-draw dumbbells on a labelled 0–1 MW scale; open = before, ink = after (discharge wears ink)
  function dumbbells() {
    for (const svg of document.querySelectorAll('svg.dumb')) {
      const a = D.dumbbells.before, b = D.dumbbells[svg.dataset.case];
      const X = (v) => 10 + v * 160;
      el('line', { x1: X(0), x2: X(1), y1: 12, y2: 12, stroke: css('--hair-2'), 'stroke-width': 1 }, svg);
      for (const t of [0, 1]) el('line', { x1: X(t), x2: X(t), y1: 6, y2: 18, stroke: css('--ink-4'), 'stroke-width': 1 }, svg);
      el('text', { x: X(0), y: 38, 'text-anchor': 'middle', 'font-size': 18, fill: css('--ink-3') }, svg, '0');
      el('text', { x: X(1), y: 38, 'text-anchor': 'middle', 'font-size': 18, fill: css('--ink-3') }, svg, '1 MW');
      el('line', { x1: X(b), x2: X(a), y1: 12, y2: 12, stroke: css('--ink'), 'stroke-width': 2 }, svg);
      el('circle', { cx: X(a), cy: 12, r: 6, fill: css('--paper'), stroke: css('--ink'), 'stroke-width': 1.5 }, svg);
      el('circle', { cx: X(b), cy: 12, r: 6.5, fill: css('--ink'), stroke: css('--paper'), 'stroke-width': 1.5 }, svg);
    }
  }

  // ---- appendix tables from data.js
  function drift() {
    const tb = document.querySelector('#tbl-drift tbody');
    for (const [lab, v, t] of D.drift) {
      const tr = document.createElement('tr');
      if (lab === 'Registered primary') tr.className = 'hl';
      tr.innerHTML = `<td>${lab}</td><td>${v}%</td><td>${t}%</td>`;
      tb.appendChild(tr);
    }
    document.getElementById('claim-frame').textContent = `Claim frame (verbatim): “${D.claim_frame}”`;
  }

  july(); intervals(); top1(); mobility(); jobBar(); dumbbells(); drift();
  fit();
  show(fromHash(), false);
  document.documentElement.dataset.ready = '1';
})();
