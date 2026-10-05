/* Migration by Skill: shared helpers. Number formatting, DOM building, badges, (i) panels, table views,
   the tooltip, keyboard reading of charts, the theme switch and the shared hatch patterns. */
(function () {
  "use strict";
  const MBS = (window.MBS = window.MBS || {});

  // ---------------------------------------------------------------- numbers
  const nf = new Intl.NumberFormat("en-AU", { maximumFractionDigits: 0 });
  const WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
  const MONTHS = { Jan: "January", Feb: "February", Mar: "March", Apr: "April", May: "May", Jun: "June", Jul: "July",
    Aug: "August", Sep: "September", Oct: "October", Nov: "November", Dec: "December" };
  const fmt = {
    int: v => nf.format(Math.round(v)).replace("-", "−"),
    // rounded to the nearest 1,000 for sentences: 292,137 -> 292,000
    k: v => nf.format(Math.round(v / 1000) * 1000).replace("-", "−"),
    // two significant figures for "a day" style counts: 800, 1,500, 670
    about: v => {
      const a = Math.abs(v);
      const step = a >= 10000 ? 1000 : a >= 1000 ? 100 : a >= 100 ? 10 : 1;
      return nf.format(Math.round(a / step) * step);
    },
    one: v => (Math.round(v * 10) / 10).toFixed(1),
    round0: v => nf.format(Math.round(v)),
    pct0: v => `${Math.round(v)}%`,
    pct1: v => `${(Math.round(v * 10) / 10).toFixed(1)}%`,
    m1: v => (Math.round(v / 1e5) / 10).toFixed(1),
    m2: v => (Math.round(v / 1e4) / 100).toFixed(2),
    short: v => {   // axis ticks: 250k, 1.5m
      const a = Math.abs(v), s = v < 0 ? "−" : "";
      if (a >= 1e6) return s + (a / 1e6).toFixed(a % 1e6 === 0 ? 0 : 1) + "m";
      if (a >= 1000) return s + Math.round(a / 1000) + "k";
      return s + Math.round(a);
    },
    signed: v => (v > 0 ? "+" : "") + nf.format(Math.round(v)).replace("-", "−"),
    word: n => (n >= 0 && n <= 10 ? WORDS[n] : String(n)),
    yearTo: label => label.replace(/^Year to (\w{3}) (\d{4})$/, (m, mon, y) => `year to ${MONTHS[mon] || mon} ${y}`),
    theName: name => (/Territory$/.test(name) ? "the " + name : name)
  };
  MBS.fmt = fmt;

  // ---------------------------------------------------------------- DOM
  function el(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v == null || v === false) continue;
        if (k === "class") n.className = v;
        else if (k === "text") n.textContent = v;
        else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
        else n.setAttribute(k, v === true ? "" : v);
      }
    }
    for (const kid of kids.flat(Infinity)) {
      if (kid == null || kid === false) continue;
      n.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid);
    }
    return n;
  }
  const words = s => String(s).trim().split(/\s+/).filter(Boolean).length;
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
  const reducedMotion = () => !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  let uid = 0;
  const nextId = p => `${p || "id"}-${++uid}`;
  // Width of a label in px without layout (works headless too): average glyph widths for system-ui.
  function textWidth(s, size) {
    const narrow = /[ilIjtf.,:;'|!()[\]\s]/;
    const wide = /[mwMW@%]/;
    let w = 0;
    for (const ch of String(s)) w += narrow.test(ch) ? 0.3 : wide.test(ch) ? 0.85 : /[A-Z0-9]/.test(ch) ? 0.64 : 0.54;
    return w * (size || 13);
  }
  MBS.util = { el, words, debounce, reducedMotion, nextId, textWidth };
  // "**bold**" in content becomes <strong>; returns nodes to append
  MBS.rich = function rich(text) {
    const out = [];
    String(text).split(/(\*\*[^*]+\*\*)/).forEach(part => {
      if (!part) return;
      const m = /^\*\*([^*]+)\*\*$/.exec(part);
      out.push(m ? el("strong", { text: m[1] }) : part);
    });
    return out;
  };

  // ---------------------------------------------------------------- number-type badges
  function typeSwatch(type) {
    const ns = "http://www.w3.org/2000/svg";
    const s = document.createElementNS(ns, "svg");
    s.setAttribute("viewBox", "0 0 18 10");
    s.setAttribute("aria-hidden", "true");
    if (type === "illustration") {
      const r = document.createElementNS(ns, "rect");
      r.setAttribute("x", "1"); r.setAttribute("y", "1"); r.setAttribute("width", "16"); r.setAttribute("height", "8");
      r.setAttribute("fill", "url(#hatch-ink)");
      s.appendChild(r);
    } else {
      const l = document.createElementNS(ns, "line");
      l.setAttribute("x1", "1"); l.setAttribute("x2", "17"); l.setAttribute("y1", "5"); l.setAttribute("y2", "5");
      l.setAttribute("stroke", "currentColor"); l.setAttribute("stroke-width", "2");
      if (type === "forecast") l.setAttribute("stroke-dasharray", "4 3");
      if (type === "estimate") l.setAttribute("stroke-opacity", "0.5");
      s.appendChild(l);
    }
    return s;
  }
  function badges(types) {
    const T = MBS.content.types;
    return el("span", { class: "badges", role: "list", "aria-label": "Kinds of numbers on this chart" },
      types.map(t => el("span", { class: "badge", role: "listitem", title: T[t].note }, typeSwatch(t), T[t].label)));
  }

  // ---------------------------------------------------------------- (i) panel and table view
  function infoToggle(panelId) {
    return el("button", { class: "icon-btn", type: "button", "aria-expanded": "false", "aria-controls": panelId,
      onclick: e => toggle(e.currentTarget) }, el("span", { class: "i", "aria-hidden": "true" }, "i"), "About this chart");
  }
  function toggle(btn) {
    const panel = document.getElementById(btn.getAttribute("aria-controls"));
    const open = btn.getAttribute("aria-expanded") !== "true";
    btn.setAttribute("aria-expanded", String(open));
    panel.hidden = !open;
  }
  function infoPanel(id, parts) {
    const p = el("div", { class: "info-panel", id, hidden: true },
      el("div", { class: "info-parts" },
        [["Why this chart", parts.why], ["How it's built", parts.how], ["What it shows", parts.shows], ["Limits", parts.limits]]
          .map(([h, t]) => el("div", { class: "info-part" }, el("h3", { text: h }), el("p", { text: t })))),
      parts.link ? el("p", { style: "margin-top:10px" }, el("a", { href: parts.link.href, text: parts.link.text })) : null,
      parts.sources && parts.sources.length ? [el("h3", { text: "Sources for the plans" }),
        el("ul", null, parts.sources.map(s => el("li", null, s.url ? el("a", { href: s.url, target: "_blank", rel: "noopener", text: s.text }) : s.text)))] : null);
    p.dataset.parts = "4";
    return p;
  }
  function tableToggle(tableId) {
    return el("button", { class: "icon-btn", type: "button", "aria-expanded": "false", "aria-controls": tableId,
      onclick: e => toggle(e.currentTarget) }, "Table");
  }
  // table: {caption, columns: [{key, label, num, fmt}], rows: [{...}]}
  function tableView(id, table) {
    const wrap = el("div", { class: "table-view", id, hidden: true });
    fillTable(wrap, table);
    return wrap;
  }
  function fillTable(wrap, table) {
    wrap.textContent = "";
    const t = el("table", { class: "data" },
      el("caption", { text: table.caption }),
      el("thead", null, el("tr", null, table.columns.map(c => el("th", { scope: "col", class: c.num ? "num" : null, text: c.label })))),
      el("tbody", null, table.rows.map(r => el("tr", null, table.columns.map((c, i) => {
        const v = r[c.key];
        const txt = v == null ? "–" : c.fmt ? c.fmt(v, r) : typeof v === "number" ? fmt.int(v) : String(v);
        return i === 0 ? el("th", { scope: "row", class: c.num ? "num" : null, text: txt }) : el("td", { class: c.num ? "num" : null, text: txt });
      })))));
    wrap.appendChild(t);
  }

  // ---------------------------------------------------------------- tooltip
  let tipEl = null;
  function tip() {
    if (!tipEl) {
      tipEl = el("div", { class: "tooltip", role: "status", "aria-live": "off" });
      document.body.appendChild(tipEl);
    }
    return tipEl;
  }
  // rows: [{value, label, color}] ; position from a pointer event or an element's box
  function showTip(title, rows, at) {
    const t = tip();
    t.textContent = "";
    if (title) t.appendChild(el("div", { class: "tt-title", text: title }));
    for (const r of rows) {
      const key = el("span", { class: "tt-key" });
      if (r.color) key.style.color = r.color; else key.style.visibility = "hidden";
      t.appendChild(el("div", { class: "tt-row" }, key, el("span", { class: "tt-val", text: r.value }),
        r.label ? el("span", { class: "tt-lab", text: r.label }) : null));
    }
    t.classList.add("on");
    let x, y;
    if (at && at.clientX != null) { x = at.clientX; y = at.clientY; }
    else if (at && at.getBoundingClientRect) { const b = at.getBoundingClientRect(); x = b.left + b.width / 2; y = b.top; }
    else { x = 20; y = 20; }
    const w = t.offsetWidth || 200, h = t.offsetHeight || 60;
    const vw = window.innerWidth || 800;
    let left = x + 14, top = y - h - 12;
    if (left + w > vw - 8) left = Math.max(8, x - w - 14);
    if (top < 8) top = y + 18;
    t.style.left = left + "px";
    t.style.top = top + "px";
  }
  function hideTip() { if (tipEl) tipEl.classList.remove("on"); }

  // Keyboard reading: focus the chart, then arrow keys step through its marks and show the same tooltip.
  // items: [{node, title, rows}] ; highlight draws a ring around the active mark.
  function keyNav(svgNode, getItems, label) {
    svgNode.setAttribute("tabindex", "0");
    svgNode.setAttribute("aria-describedby", ensureHint());
    let i = -1;
    const ns = "http://www.w3.org/2000/svg";
    let ring = null;
    function show() {
      const items = getItems();
      if (!items.length) return;
      i = (i + items.length) % items.length;
      const it = items[i];
      showTip(it.title, it.rows, it.node);
      if (!ring) { ring = document.createElementNS(ns, "rect"); ring.setAttribute("class", "kbd-hi"); ring.setAttribute("rx", "4"); }
      try {
        const b = it.node.getBBox();
        ring.setAttribute("x", b.x - 3); ring.setAttribute("y", b.y - 3);
        ring.setAttribute("width", b.width + 6); ring.setAttribute("height", b.height + 6);
        (it.node.ownerSVGElement || svgNode).appendChild(ring);
      } catch (e) { /* no layout (headless) */ }
    }
    svgNode.addEventListener("keydown", e => {
      if (["ArrowRight", "ArrowDown"].includes(e.key)) { i += 1; show(); e.preventDefault(); }
      else if (["ArrowLeft", "ArrowUp"].includes(e.key)) { i = i < 0 ? -1 : i - 1; show(); e.preventDefault(); }
      else if (e.key === "Home") { i = 0; show(); e.preventDefault(); }
      else if (e.key === "End") { i = -1; show(); e.preventDefault(); }
      else if (e.key === "Escape") { hideTip(); if (ring) ring.remove(); }
    });
    svgNode.addEventListener("blur", () => { hideTip(); if (ring) ring.remove(); i = -1; });
    if (label) svgNode.setAttribute("aria-label", label);
  }
  let hintId = null;
  function ensureHint() {
    if (!hintId) {
      hintId = "kbd-hint";
      if (!document.getElementById(hintId)) {
        document.body.appendChild(el("p", { id: hintId, class: "sr-only", text: "Use the arrow keys to read each value. The Table button shows every value." }));
      }
    }
    return hintId;
  }

  // ---------------------------------------------------------------- shared SVG defs (hatching = our illustration)
  function ensureDefs() {
    if (document.getElementById("mbs-defs")) return;
    const ns = "http://www.w3.org/2000/svg";
    const s = document.createElementNS(ns, "svg");
    s.setAttribute("id", "mbs-defs"); s.setAttribute("aria-hidden", "true");
    s.setAttribute("width", "0"); s.setAttribute("height", "0"); s.style.position = "absolute";
    const defs = document.createElementNS(ns, "defs");
    for (const [id, cls] of [["hatch-focus", "hatch-focus"], ["hatch-context", "hatch-context"], ["hatch-ink", "hatch-ink"]]) {
      const p = document.createElementNS(ns, "pattern");
      p.setAttribute("id", id); p.setAttribute("patternUnits", "userSpaceOnUse");
      p.setAttribute("width", "6"); p.setAttribute("height", "6"); p.setAttribute("patternTransform", "rotate(45)");
      p.setAttribute("class", cls);
      const l = document.createElementNS(ns, "line");
      l.setAttribute("x1", "0"); l.setAttribute("y1", "0"); l.setAttribute("x2", "0"); l.setAttribute("y2", "6");
      l.setAttribute("class", "hatch-line");
      if (id === "hatch-ink") { l.setAttribute("stroke", "currentColor"); l.setAttribute("stroke-width", "1.5"); }
      p.appendChild(l);
      defs.appendChild(p);
    }
    s.appendChild(defs);
    document.body.insertBefore(s, document.body.firstChild);
  }

  // ---------------------------------------------------------------- theme
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } return null; }
  function effectiveDark() {
    const t = document.documentElement.getAttribute("data-theme");
    if (t) return t === "dark";
    return !!(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  }
  function initTheme() {
    const saved = store("mbs-theme");
    if (saved === "dark" || saved === "light") document.documentElement.setAttribute("data-theme", saved);
  }
  function toggleTheme() {
    const next = effectiveDark() ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    store("mbs-theme", next);
    syncThemeToggles();
    return next;
  }
  // The light/dark switch: a visible button in the top bar. Shows the mode it switches to.
  const ICON = {
    moon: "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z",
    sun: "M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zm0-5v3m0 14v3M4.2 4.2l2.1 2.1m11.4 11.4 2.1 2.1M2 12h3m14 0h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"
  };
  function themeIcon(name) {
    const ns = "http://www.w3.org/2000/svg";
    const s = document.createElementNS(ns, "svg");
    s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("width", "18"); s.setAttribute("height", "18");
    s.setAttribute("aria-hidden", "true"); s.setAttribute("class", `ico ico-${name}`);
    const pth = document.createElementNS(ns, "path");
    pth.setAttribute("d", ICON[name]); pth.setAttribute("fill", "none"); pth.setAttribute("stroke", "currentColor");
    pth.setAttribute("stroke-width", "2"); pth.setAttribute("stroke-linecap", "round"); pth.setAttribute("stroke-linejoin", "round");
    s.appendChild(pth);
    return s;
  }
  function themeToggle() {
    const b = el("button", { class: "theme-toggle", type: "button", onclick: () => toggleTheme() },
      themeIcon("moon"), themeIcon("sun"), el("span", { class: "tt-label" }, ""));
    setTimeout(syncThemeToggles, 0);
    return b;
  }
  function syncThemeToggles() {
    const dark = effectiveDark();
    document.querySelectorAll(".theme-toggle").forEach(b => {
      b.setAttribute("aria-pressed", String(dark));
      b.setAttribute("aria-label", dark ? "Dark mode is on. Switch to light mode" : "Switch to dark mode");
      b.setAttribute("title", dark ? "Switch to light mode" : "Switch to dark mode");
      b.classList.toggle("is-dark", dark);
      const l = b.querySelector(".tt-label");
      if (l) l.textContent = dark ? "Light" : "Dark";
    });
  }
  if (window.matchMedia) {
    try { window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", syncThemeToggles); } catch (e) { /* older browsers */ }
  }

  // ---------------------------------------------------------------- sources
  function sourceLine(keys) {
    const S = MBS.data.sources;
    const items = keys.map(k => S[k]).filter(Boolean);
    if (!items.length) return null;
    return el("span", { class: "source" }, "Source: ", items.map((s, i) => [i ? "; " : "",
      s.url ? el("a", { href: s.url, target: "_blank", rel: "noopener", text: s.short }) : s.short]));
  }

  MBS.ui = { badges, typeSwatch, infoToggle, infoPanel, tableToggle, tableView, fillTable, showTip, hideTip, keyNav,
    ensureDefs, initTheme, toggleTheme, themeToggle, syncThemeToggles, effectiveDark, sourceLine, store };
})();
