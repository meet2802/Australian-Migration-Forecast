/* Migration by Skill: the report's interactive exhibits. Find your job, Your state, Build your own plan, and All
   claims. Each tool keeps its own settings, saves them in the address (#ex17?job=3411&state=NSW) so a view can be
   shared or cited, and draws small charts with lineChart and barList. Needs data/data-explore.js. */
(function () {
  "use strict";
  const MBS = (window.MBS = window.MBS || {});
  const { el, textWidth } = MBS.util;
  const F = MBS.fmt;
  const H = () => MBS.chartHelpers;

  // ---------------------------------------------------------------- data access
  let OCC = null, BYCODE = null, OCCST = null;
  function occ() {
    if (OCC) return OCC;
    const E = MBS.explore.occupations;
    OCC = E.rows.map(r => Object.fromEntries(E.columns.map((c, i) => [c, r[i]])));
    BYCODE = new Map(OCC.map(o => [o.code, o]));
    const T = MBS.explore.occ_state;
    OCCST = new Map();
    for (const r of T.rows) {
      const o = Object.fromEntries(T.columns.map((c, i) => [c, r[i]]));
      OCCST.set(`${o.code}|${o.state}`, o);
    }
    return OCC;
  }
  const sectorName = id => { const s = MBS.explore.sectors.find(x => x.id === id); return s ? s.name : null; };
  const placeName = code => MBS.data.places[code] || code;
  function monthLabel(mm) { const [y, m] = mm.split("-"); return `${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][+m - 1]} ${y}`; }
  function stat(v, l) { return el("div", { class: "stat" }, el("div", { class: "v", text: v }), el("div", { class: "l", text: l })); }
  function select(id, label, options, value, onchange) {
    return el("label", { class: "tool-field", for: id }, label,
      el("select", { id, onchange: e => onchange(e.target.value) }, options.map(([v, t]) => el("option", { value: v, selected: v === value, text: t }))));
  }
  const stateOptions = () => Object.entries(MBS.data.places);

  // ---------------------------------------------------------------- address bar: one tool's settings at a time
  function readHash(id) {
    const m = new RegExp(`^#${id}\\?(.*)$`).exec(location.hash || "");
    return m ? new URLSearchParams(m[1]) : null;
  }
  let lastHash = null;
  function writeHash(id, params) {
    const p = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v != null && v !== "" && v !== false) p.set(k, Array.isArray(v) ? v.join(",") : v); });
    const h = `#${id}` + (p.toString() ? `?${p}` : "");
    lastHash = h;
    try { history.replaceState(null, "", h); } catch (e) { /* some browsers block this on file:// pages */ }
  }
  function cite(view) {
    const now = new Date();
    const today = `${now.toLocaleDateString("en-US", { month: "long" })} ${now.getDate()}, ${now.getFullYear()}`;
    const name = MBS.content.meta.author.trim().split(/\s+/);
    const author = name.length > 1 ? `${name[name.length - 1]}, ${name.slice(0, -1).map(n => n[0] + ".").join(" ")}` : name[0];
    return el("details", { class: "cite-box" }, el("summary", null, "Cite this view"),
      el("p", { class: "cite", text: `${author} (2026). ${MBS.content.meta.title}: ${view} [Interactive data story and report, version ${MBS.data.version}]. Retrieved ${today}, from ${location.href}` }));
  }

  // ---------------------------------------------------------------- jobs: search box and card
  function searchBox(id, onPick, initial) {
    occ();
    const input = el("input", { id, type: "text", role: "combobox", "aria-autocomplete": "list", "aria-expanded": "false",
      "aria-controls": `${id}-list`, autocomplete: "off", placeholder: "Type a job, e.g. nurse, electrician, chef", value: initial || "" });
    const list = el("ul", { id: `${id}-list`, role: "listbox", hidden: true, "aria-label": "Matching jobs" });
    let items = [], act = -1;
    const norm = s => s.toLowerCase().replace(/[^a-z0-9 ]/g, " ");
    function search(qs) {
      const q = norm(qs).trim();
      if (q.length < 2) return [];
      const terms = q.split(/\s+/);
      return OCC.filter(o => !o.nfd).map(o => {
        const n = norm(o.name);
        if (!terms.every(t => n.includes(t.replace(/s$/, "")))) return null;
        const wordStart = terms.every(t => new RegExp("(^| )" + t.replace(/s$/, "")).test(n));
        const score = -Math.log10((o.employed || 0) + 10) - (n.startsWith(terms[0]) ? 0.3 : 0) - (wordStart ? 0.3 : 0);
        return { o, score };
      }).filter(Boolean).sort((a, b) => a.score - b.score).slice(0, 12).map(x => x.o);
    }
    function draw() {
      list.textContent = "";
      items.forEach((o, i) => list.appendChild(el("li", { role: "option", id: `${id}-opt-${i}`, "aria-selected": String(i === act),
        onmousedown: e => { e.preventDefault(); pick(i); } }, o.name, " ", el("span", { class: "hint", text: sectorName(o.sector) || "" }))));
      const open = items.length > 0;
      list.hidden = !open;
      input.setAttribute("aria-expanded", String(open));
      if (act >= 0) input.setAttribute("aria-activedescendant", `${id}-opt-${act}`); else input.removeAttribute("aria-activedescendant");
    }
    function pick(i) {
      const o = items[i];
      if (!o) return;
      input.value = o.name;
      items = []; act = -1; draw();
      onPick(o.code);
    }
    input.addEventListener("input", () => { items = search(input.value); act = -1; draw(); });
    input.addEventListener("keydown", e => {
      if (e.key === "ArrowDown") { act = Math.min(items.length - 1, act + 1); draw(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { act = Math.max(0, act - 1); draw(); e.preventDefault(); }
      else if (e.key === "Enter") { if (items.length) { pick(act < 0 ? 0 : act); e.preventDefault(); } }
      else if (e.key === "Escape") { items = []; act = -1; draw(); }
    });
    input.addEventListener("blur", () => setTimeout(() => { items = []; act = -1; draw(); }, 120));
    const wrap = el("div", { class: "search" }, el("label", { for: id, class: "sr-only" }, "Search for a job"), input, list);
    wrap.search = search;
    wrap.input = input;
    return wrap;
  }

  function shortLabel(o, st) {
    const r = st && st !== "AUS" ? OCCST.get(`${o.code}|${st}`) : null;
    const rating = r ? r.osl : o.osl;
    if (!rating || rating === "Not assessed") return { text: "Not checked for shortages", cls: "f-context-2", short: null };
    const short = /shortage/i.test(rating) && !/^No shortage/i.test(rating);
    const where = r ? ` in ${placeName(st)}` : "";
    const kind = /^Regional/i.test(rating) ? " (regional areas)" : /^Metropolitan/i.test(rating) ? " (cities)" : "";
    return { text: short ? `Short of workers${where}${kind}` : `Not short of workers${where}`, cls: short ? "f-focus" : "f-context", short };
  }

  function card(box, code, st) {
    occ();
    const o = BYCODE.get(code);
    box.textContent = "";
    if (!o) return null;
    const all = MBS.explore.all_jobs;
    const sl = shortLabel(o, st);
    const r = st && st !== "AUS" ? OCCST.get(`${o.code}|${st}`) : null;
    const pill = el("span", { class: "pill" }, el("span", { class: "sw", style: `background:var(--${sl.cls.replace("f-", "")})` }), sl.text);
    const growth = o.growth_pct == null ? "No projection" : `${o.growth_pct > 0 ? "+" : ""}${F.pct1(o.growth_pct)}`;
    box.appendChild(el("h4", { class: "job-name", text: o.name }));
    const skill = o.skill == null ? null : String(o.skill).replace(/, (\d)$/, " or $1");
    box.appendChild(el("p", { class: "sub", text: [sectorName(o.sector), skill ? `skill level ${skill} (1 is the highest, 5 the lowest)` : null].filter(Boolean).join(" · ") }));
    box.appendChild(pill);
    const ads = r ? r.ads : o.ads, adsAgo = r ? r.ads_ago : o.ads_ago;
    box.appendChild(el("div", { class: "stat-row" },
      stat(growth, `growth in workers to 2030 (all jobs: ${F.pct1(all.growth_pct)})`),
      stat(o.need == null ? "–" : F.int(o.need), "new workers needed a year, Australia (our estimate)"),
      stat(ads == null ? "–" : F.int(ads), `job ads${r ? " in " + st : ""}, August 2026` + (adsAgo ? ` (${F.int(adsAgo)} a year earlier)` : "")),
      stat(F.int(r ? r.visa_grants : o.visa_grants || 0), `temporary skilled visas granted${r ? " in " + st : ""}, 2025-26`)));
    const line = `${o.name}: ${sl.short == null ? "not checked for shortages" : sl.short ? "short of workers now" : "not short now"}` +
      (o.growth_pct != null ? `, growing ${F.pct1(o.growth_pct)} by 2030 (all jobs ${F.pct1(all.growth_pct)}).` : ".");
    box.appendChild(el("p", { class: "try-result", text: line }));
    return o;
  }
  MBS.jobs = { searchBox, card, occ: () => occ() };

  // ---------------------------------------------------------------- small charts
  function lineChart(host, series, o) {
    host.textContent = "";
    const w = H().widthOf(host);
    const h = o.height || 240;
    // optional names where each line ends: beside the plot when there is room, inside it on a phone
    const vf = o.vfmt || F.int;
    const lastOf = s => s.values.slice().reverse().find(v => v.v != null);
    let endMode = null, endW = 0;
    if (o.endLabels) {
      endW = Math.ceil(d3.max(series, s => Math.max(textWidth(s.short || s.name, 12), textWidth(vf(lastOf(s).v), 12))) * 1.12) + 14;
      endMode = w - (o.left || 46) - endW >= 300 ? "out" : "in";
    }
    const m = { t: 16, r: endMode === "out" ? endW : (o.right || 16), b: 26, l: o.left || 46 };
    const all = series.flatMap(s => s.values);
    const x = d3.scaleLinear().domain(d3.extent(all, v => v.x)).range([m.l, w - m.r]);
    const lo = d3.min(all, v => v.v), hi = d3.max(all, v => v.v) || 1;
    const y = d3.scaleLinear().domain(o.zero === false ? [lo - (hi - lo) * 0.15, hi + (hi - lo) * 0.1] : [Math.min(0, lo), hi]).nice().range([h - m.b, m.t]);
    if (series.length > 1) H().legend(host, series.map(s => ({ shape: s.dash ? "dash" : "line", cls: s.cls, label: s.name })));
    const svg = d3.select(host).append("svg").attr("viewBox", `0 0 ${w} ${h}`).attr("width", w).attr("height", h).attr("role", "img").attr("aria-label", o.summary || "");
    const g = svg.append("g");
    const yt = y.ticks(4);
    g.append("g").attr("class", "grid").selectAll("line").data(yt).join("line").attr("x1", m.l).attr("x2", w - m.r).attr("y1", y).attr("y2", y);
    g.append("g").selectAll("text").data(yt).join("text").attr("class", "tick-label").attr("x", m.l - 6).attr("y", v => y(v) + 4).attr("text-anchor", "end").text(o.yfmt || F.short);
    const xt = o.xticks || x.ticks(5);
    g.append("g").selectAll("text").data(xt).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - 6).attr("text-anchor", "middle").text(o.xfmt || (v => v));
    if (y.domain()[0] < 0) g.append("line").attr("class", "baseline").attr("x1", m.l).attr("x2", w - m.r).attr("y1", y(0)).attr("y2", y(0));
    const ln = d3.line().defined(v => v.v != null).x(v => x(v.x)).y(v => y(v.v));
    series.forEach(s => g.append("path").datum(s.values).attr("class", `line ${s.cls}${s.dash ? " dash" : ""}`).attr("stroke-opacity", s.light ? 0.6 : 1).attr("d", ln));
    // name each line where it ends, so lines that share the grey can still be told apart
    if (endMode) {
      const gap = endMode === "out" ? 31 : 14;
      const items = series.map(s => ({ s, last: lastOf(s) })).filter(it => it.last)
        .map(it => Object.assign(it, { y: y(it.last.v) + (endMode === "out" ? 0 : -7) })).sort((a, b) => a.y - b.y);
      for (let i = 1; i < items.length; i++) if (items[i].y - items[i - 1].y < gap) items[i].y = items[i - 1].y + gap;
      const floor = h - m.b - (endMode === "out" ? 14 : 4);
      const over = items.length ? items[items.length - 1].y - floor : 0;
      if (over > 0) items.forEach(it => { it.y -= over; });
      if (items.length && items[0].y < m.t + 8) { const up = m.t + 8 - items[0].y; items.forEach(it => { it.y += up; }); }
      items.forEach(it => {
        const cls = it.s.cls === "s-focus" ? "lbl-strong" : "lbl-2";
        const name = it.s.short || it.s.name;
        if (endMode === "out") {
          const t = g.append("text").attr("class", `${cls} end-label`).attr("x", w - m.r + 8).attr("y", it.y + 1).text(name);
          t.append("tspan").attr("class", "lbl-2 end-value").attr("x", w - m.r + 8).attr("dy", 14).text(vf(it.last.v));
          t.attr("data-label", `${name}: ${vf(it.last.v)}`);
        } else {
          g.append("text").attr("class", `${cls} end-label`).attr("x", w - m.r - 2).attr("y", it.y).attr("text-anchor", "end")
            .attr("data-label", `${name}: ${vf(it.last.v)}`).text(`${name}: ${vf(it.last.v)}`);
        }
      });
    }
    const ch = g.append("line").attr("class", "crosshair").attr("y1", m.t).attr("y2", h - m.b).style("opacity", 0);
    const xs = series[0].values.map(v => v.x);
    g.append("rect").attr("class", "hover-target").attr("x", m.l).attr("y", m.t).attr("width", w - m.l - m.r).attr("height", h - m.t - m.b)
      .on("pointermove", ev => {
        const [px] = d3.pointer(ev);
        const i = d3.bisector(v => v).center(xs, x.invert(px));
        ch.attr("x1", x(xs[i])).attr("x2", x(xs[i])).style("opacity", 1);
        MBS.ui.showTip(series[0].values[i].label, series.map(s => ({ value: s.values[i] && s.values[i].v != null ? (o.vfmt || F.int)(s.values[i].v) : "–", label: s.name, color: getComputedStyle(document.documentElement).getPropertyValue(s.cls === "s-focus" ? "--focus" : s.cls === "s-comparison" ? "--comparison" : "--context").trim() })), ev);
      })
      .on("pointerleave", () => { ch.style("opacity", 0); MBS.ui.hideTip(); });
    MBS.ui.keyNav(svg.node(), () => series[0].values.filter((v, i) => i % Math.max(1, Math.round(xs.length / 12)) === 0 || i === xs.length - 1)
      .map(v => ({ node: ch.attr("x1", x(v.x)).attr("x2", x(v.x)).style("opacity", 1).node(), title: v.label,
        rows: series.map(s => { const z = s.values.find(q => q.x === v.x); return { value: z && z.v != null ? (o.vfmt || F.int)(z.v) : "–", label: s.name }; }) })), o.summary);
  }

  function barList(host, rows, o) {
    host.textContent = "";
    const w = H().widthOf(host);
    const fs = w < 520 ? 12 : 13;
    const labW = Math.min(w * 0.45, d3.max(rows, r => textWidth(r.label, fs)) + 10);
    const rowH = o.minH ? Math.max(24, Math.min(46, Math.floor((o.minH - 44) / rows.length))) : 24, bh = Math.min(20, Math.round(rowH * 0.58));
    const m = { t: o.refLabel ? 22 : 6, r: 52, b: 20, l: labW };
    const h = m.t + rows.length * rowH + m.b;
    const max = o.max || d3.max(rows, r => Math.max(r.v || 0, o.ref || 0)) || 1;
    const x = d3.scaleLinear().domain([0, max]).nice().range([m.l, w - m.r]);
    const svg = d3.select(host).append("svg").attr("viewBox", `0 0 ${w} ${h}`).attr("width", w).attr("height", h).attr("role", "img").attr("aria-label", o.summary || "");
    const g = svg.append("g");
    const ticks = x.ticks(4);
    g.append("g").attr("class", "grid").selectAll("line").data(ticks).join("line").attr("x1", x).attr("x2", x).attr("y1", m.t).attr("y2", h - m.b);
    g.append("g").selectAll("text").data(ticks).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - 4).attr("text-anchor", "middle").text(o.tfmt || (v => v));
    rows.forEach((r, i) => {
      const yy = m.t + i * rowH;
      g.append("text").attr("class", r.strong ? "lbl-strong" : "lbl-2").attr("x", m.l - 8).attr("y", yy + bh - 2).attr("text-anchor", "end").style("font-size", fs + "px").text(r.label);
      if (r.v != null) {
        const p = g.append("path").attr("class", r.cls || "f-focus").attr("d", H().barPath(x(0), x(Math.max(0, r.v)), yy, bh));
        if (r.hatch) p.attr("fill", "url(#hatch-focus)");
      }
      g.append("text").attr("class", "lbl").attr("x", x(Math.max(0, r.v || 0)) + 6).attr("y", yy + bh - 2).text(r.v == null ? "no data" : (o.vfmt || F.int)(r.v));
      g.append("rect").attr("class", "hover-target").attr("x", 0).attr("width", w).attr("y", yy - 4).attr("height", rowH).datum(r);
    });
    if (o.ref != null) {
      g.append("line").attr("class", "s-comparison").attr("stroke-width", 2).attr("x1", x(o.ref)).attr("x2", x(o.ref)).attr("y1", m.t - 4).attr("y2", h - m.b);
      if (o.refLabel) {
        const tw = textWidth(o.refLabel, 13);
        g.append("text").attr("class", "lbl-strong").attr("x", Math.max(4, Math.min(w - tw - 4, x(o.ref) - tw / 2))).attr("y", m.t - 8).text(o.refLabel);
      }
    }
    g.selectAll(".hover-target").on("pointermove", (ev, r) => MBS.ui.showTip(r.label, [{ value: r.v == null ? "no data" : (o.vfmt || F.int)(r.v), label: o.unit || "" }], ev))
      .on("pointerleave", () => MBS.ui.hideTip());
    MBS.ui.keyNav(svg.node(), () => g.selectAll(".hover-target").nodes().map((nd, i) => ({ node: nd, title: rows[i].label, rows: [{ value: rows[i].v == null ? "no data" : (o.vfmt || F.int)(rows[i].v), label: o.unit || "" }] })), o.summary);
  }
  MBS.mini = { lineChart, barList };

  // a small titled chart inside a tool, with its own table
  let figN = 0;
  function miniFig(title, build, table, note) {
    figN += 1;
    const id = `mini-${figN}`;
    const host = el("div", { class: "chart-host" });
    const tId = `${id}-table`;
    const box = el("figure", { class: "mini-fig", id },
      el("figcaption", { class: "mini-title", text: title }), host,
      el("div", { class: "card-foot" }, note ? el("span", { class: "source", text: note }) : null, el("span", { class: "spacer" }), MBS.ui.tableToggle(tId)),
      MBS.ui.tableView(tId, table));
    const run = () => build(host);
    if (window.requestAnimationFrame) window.requestAnimationFrame(run); else setTimeout(run, 0);
    return box;
  }

  // ---------------------------------------------------------------- tool: find your job
  function toolJob(view) {
    occ();
    const S = { job: null, state: "AUS" };
    const p = readHash("ex17");
    if (p) { if (p.get("job") && BYCODE.get(p.get("job"))) S.job = p.get("job"); if (p.get("state") && MBS.data.places[p.get("state")]) S.state = p.get("state"); }
    const out = el("div", { class: "tool-out", "aria-live": "polite" });
    const box = searchBox("job-input", code => { S.job = code; save(); draw(); }, S.job ? BYCODE.get(S.job).name : "");
    const picks = ["Registered Nurses", "Electricians", "Aged and Disabled Carers", "Software and Applications Programmers", "Chefs", "Child Carers", "Carpenters and Joiners", "Truck Drivers"]
      .map(n => OCC.find(o => o.name === n)).filter(Boolean);
    view.appendChild(el("div", { class: "tool-controls" },
      el("div", { class: "tool-field tool-grow" }, el("span", null, "Job"), box),
      select("job-state", "Shortage rating for", stateOptions(), S.state, v => { S.state = v; save(); draw(); })));
    view.appendChild(el("div", { class: "chips" }, el("span", { class: "chips-label", text: "Popular:" }),
      picks.map(o => el("button", { class: "chip", type: "button", onclick: () => { S.job = o.code; box.input.value = o.name; save(); draw(); } }, o.name))));
    view.appendChild(out);
    function save() { writeHash("ex17", { job: S.job, state: S.state !== "AUS" ? S.state : null }); }
    function draw() {
      out.textContent = "";
      if (!S.job) { out.appendChild(el("p", { class: "job-empty", text: "Pick a job to see its numbers." })); return; }
      const o = BYCODE.get(S.job);
      const cardBox = el("div", { class: "job-card" });
      out.appendChild(cardBox);
      card(cardBox, S.job, S.state);
      const grid = el("div", { class: "grid-2" });
      out.appendChild(grid);
      const months = MBS.explore.job_ads.months;
      const series = MBS.explore.job_ads.series[o.code];
      if (series) {
        const vals = months.map((mm, i) => ({ x: +mm.slice(0, 4) + (+mm.slice(5, 7) - 0.5) / 12, v: series[i], label: monthLabel(mm) }));
        grid.appendChild(miniFig("Job ads, Australia (three-month average)", hh => lineChart(hh, [{ name: "Job ads", cls: "s-focus", values: vals }],
          { summary: `Job ads for ${o.name}, ${monthLabel(months[0])} to ${monthLabel(months[months.length - 1])}: from ${F.int(series[0] || 0)} to ${F.int(series[series.length - 1] || 0)}.`, xticks: [2018, 2020, 2022, 2024, 2026], xfmt: v => v, height: 220 }),
          { caption: `Job ads for ${o.name}`, columns: [{ key: "label", label: "Month" }, { key: "v", label: "Job ads", num: true }], rows: vals.slice().reverse() },
          "Source: Jobs and Skills Australia, Internet Vacancy Index"));
      }
      const per = [{ label: "Trained here", v: o.grp_trained_100, cls: "f-context" }, { label: "Skilled visas", v: o.grp_visa_100, cls: "f-focus" }];
      grid.appendChild(miniFig(`Per 100 workers needed a year (group: ${o.grp_name || "not grouped"})`, hh => barList(hh, per,
        { ref: 100, refLabel: "100", unit: "per 100 needed", minH: 200, summary: `Per 100 workers needed: trained here ${o.grp_trained_100 == null ? "no data" : o.grp_trained_100}, skilled visas ${o.grp_visa_100 == null ? "no data" : o.grp_visa_100}.` }),
        { caption: `Per 100 workers needed a year, ${o.grp_name || ""}`, columns: [{ key: "label", label: "Measure" }, { key: "v", label: "Per 100 needed", num: true }], rows: per },
        `Our estimate. Training counted: ${o.train_cover || "not known"}.`));
      const rows = [
        ["Occupation code (ANZSCO)", o.code], ["Job group", sectorName(o.sector)], ["Shortage rating, 2025 (national)", o.osl],
        ["Workers, May 2025", o.employed], ["Projected workers, May 2030", o.proj_2030], ["Growth to 2030", o.growth_pct == null ? null : F.pct1(o.growth_pct)],
        ["New jobs a year (projected)", o.growth_per_year], ["Retirements a year (estimate)", o.retire], ["Net loss to other jobs a year (estimate)", o.moves],
        ["New workers needed a year (estimate)", o.need], ["Median weekly earnings", o.earn == null ? null : `$${F.int(o.earn)}`], ["Aged 55 and over", o.age55 == null ? null : F.pct1(o.age55)],
        ["Apprentices and trainees finishing (year to March 2026)", o.appr_done], ["Temporary skilled visas granted, 2025-26", o.visa_grants],
        ["Temporary skilled visa holders (main applicants)", o.visa_holders], ["Visa holders per 1,000 workers", o.visa_per_1000]];
      const tb = el("div", { class: "table-view" });
      MBS.ui.fillTable(tb, { caption: `${o.name}: every figure`, columns: [{ key: "k", label: "Measure" }, { key: "v", label: "Value", num: true }], rows: rows.map(([k, v]) => ({ k, v })) });
      out.appendChild(el("details", { class: "more-box" }, el("summary", null, "Every figure for this job"), tb,
        el("p", { class: "chart-note", text: "Workers needed = projected new jobs + retirements + net moves to other jobs. Estimates use Jobs and Skills Australia projections and ABS data." })));
      out.appendChild(cite(o.name));
    }
    draw();
    return { set: patch => { Object.assign(S, patch); if (S.job && BYCODE.get(S.job)) box.input.value = BYCODE.get(S.job).name; draw(); }, state: S };
  }

  // ---------------------------------------------------------------- tool: your state
  function presetList() {
    const P = MBS.explore.model.presets;
    const name = { gov: "Government", coa: "Coalition", on: "One Nation", ref: "If the last 12 months continued" };
    const caseName = { central: "", low: " (low)", high: " (high)" };
    return P.map(p => ({ id: p.id, label: name[p.plan] + (p.plan === "on" && p.case === "central" ? " (midpoint)" : caseName[p.case]), nom: p.nom, plan: p.plan, case: p.case }));
  }
  function planPhrase(p) {
    if (!p.id || p.id === "custom") return "under your own plan";
    if (p.plan === "ref") return "if the last 12 months continued";
    return `under the ${p.label} plan`;
  }
  function toolState(view) {
    const S = { state: "NSW", plan: "gov_central" };
    const p = readHash("ex11");
    if (p) { if (p.get("state") && MBS.explore.states[p.get("state")]) S.state = p.get("state"); if (p.get("plan") && presetList().some(z => z.id === p.get("plan"))) S.plan = p.get("plan"); }
    const out = el("div", { class: "tool-out", "aria-live": "polite" });
    view.appendChild(el("div", { class: "tool-controls" },
      select("state-pick", "State or territory", stateOptions(), S.state, v => { S.state = v; save(); draw(); }),
      select("state-plan", "Plan for 2030", presetList().map(z => [z.id, z.label]), S.plan, v => { S.plan = v; save(); draw(); })));
    view.appendChild(out);
    function save() { writeHash("ex11", { state: S.state, plan: S.plan }); }
    function draw() {
      out.textContent = "";

      const code = S.state;
      const st = MBS.explore.states[code];
      const sum = MBS.data.q12.states.find(s => s.code === code);
      const plan = presetList().find(z => z.id === S.plan) || presetList()[0];
      const proj = MBS.model.run(plan.nom, code);
      out.appendChild(el("p", { class: "tool-lead", text: `${st.name} grew by ${F.int(sum.growth)} people in ${MBS.data.q12.period_label}; ${F.int(sum.nom)} of them came through net overseas migration. ${F.int(sum.homes)} new homes were finished.` }));
      out.appendChild(el("div", { class: "stat-row" },
        stat(F.int(sum.population), `people, ${monthLabel(MBS.data.data_to)} (official)`),
        stat(`${F.m2(proj.pop_2030)}m`, `by June 2030 ${planPhrase(plan)} (our estimate)`),
        stat(F.k(Math.max(0, proj.homes_per_year)), "new homes needed a year under that plan"),
        stat(F.int(proj.built), "homes finished last year")));
      const grid = el("div", { class: "grid-3" });
      out.appendChild(grid);
      const qx = q => +q.slice(0, 4) + (+q.slice(5, 7)) / 12;
      const pop = st.pop.map(([q, erp, n12, g12]) => ({ q, x: qx(q), label: `Year to ${monthLabel(q)}`, n12, g12 }));
      grid.appendChild(miniFig("Population growth and net overseas migration, each 12 months", hh => lineChart(hh, [
        { name: "Population growth", cls: "s-context", values: pop.map(z => ({ x: z.x, v: z.g12, label: z.label })) },
        { name: "Net overseas migration", cls: "s-focus", values: pop.map(z => ({ x: z.x, v: z.n12, label: z.label })) }],
        { summary: `Population growth and net overseas migration in ${st.name}, 12 months to each quarter since 2001.`, xticks: [2005, 2010, 2015, 2020, 2025], height: 220 }),
        { caption: `${st.name}: population growth and net overseas migration (12 months to each quarter)`, columns: [{ key: "label", label: "Period" }, { key: "g12", label: "Population growth", num: true }, { key: "n12", label: "Net overseas migration", num: true }], rows: pop.slice().reverse() },
        "Source: ABS, National, state and territory population"));
      const pph = MBS.explore.model.people_per_home;
      const hm = st.homes.map(([ye, c, g, pp]) => ({ x: qx(ye), label: `Year to ${monthLabel(ye)}`, c, need: g == null ? null : g / pph, pp }));
      grid.appendChild(miniFig("Homes finished, and homes needed for the growth (each 12 months)", hh => lineChart(hh, [
        { name: "Homes finished", cls: "s-focus", values: hm.map(z => ({ x: z.x, v: z.c, label: z.label })) },
        { name: `Homes needed (growth ÷ ${pph}, our estimate)`, cls: "s-context", light: true, values: hm.map(z => ({ x: z.x, v: z.need, label: z.label })) }],
        { summary: `New homes finished against homes needed for population growth in ${st.name}, since 2001.`, xticks: [2005, 2010, 2015, 2020, 2025], height: 220 }),
        { caption: `${st.name}: homes finished and homes needed for growth`, columns: [{ key: "label", label: "Period" }, { key: "c", label: "Homes finished", num: true }, { key: "need", label: "Homes needed (estimate)", num: true }, { key: "pp", label: "People added per home", num: true, fmt: v => v.toFixed(2) }], rows: hm.slice().reverse() },
        "Source: ABS, Building activity; ABS population; our estimate"));
      const SS = MBS.explore.sector_state;
      const idx = Object.fromEntries(SS.columns.map((c, i) => [c, i]));
      let rows = code === "AUS" ? MBS.explore.sectors.map(s => ({ label: s.name, v: s.short_pct, assessed: s.assessed_pct }))
        : SS.rows.filter(r => r[idx.state] === code).map(r => ({ label: sectorName(r[idx.sector]), v: r[idx.short_pct], assessed: r[idx.assessed_pct] }));
      rows.sort((a, b) => (b.v || 0) - (a.v || 0));
      const top = rows.slice(0, 10).map((r, i) => ({ ...r, cls: i < 5 ? "f-focus" : "f-context", strong: i < 5 }));
      grid.appendChild(miniFig(`Job groups most short of workers in ${st.name}`, hh => barList(hh, top,
        { max: 100, vfmt: v => `${Math.round(v)}%`, tfmt: v => `${v}%`, unit: "of jobs short", summary: "Top ten job groups by share of jobs short: " + top.map(r => `${r.label} ${Math.round(r.v)}%`).join(", ") }),
        { caption: `Job groups by share of jobs short, ${st.name}`, columns: [{ key: "label", label: "Job group" }, { key: "v", label: "Jobs short", num: true, fmt: v => `${v}%` }, { key: "assessed", label: "Jobs checked", num: true, fmt: v => `${v}%` }], rows },
        "Source: Jobs and Skills Australia, 2025 Occupation Shortage List (state ratings)"));
      out.appendChild(el("p", { class: "chart-note", text: "Homes finished are gross: homes knocked down are not subtracted. Homes needed assume 2.5 people per home (the 2021 Census average). State shortage ratings come from the 2025 list; small states have fewer occupations rated." }));
      out.appendChild(cite(st.name));
    }
    draw();
    return { set: patch => { Object.assign(S, patch); draw(); }, state: S };
  }

  // ---------------------------------------------------------------- tool: build your own plan
  function toolPlans(view) {
    const M = MBS.explore.model;
    const S = { plan: "gov_central", custom: null, state: "AUS", pph: M.people_per_home };
    const p = readHash("ex8");
    if (p) {
      if (p.get("plan")) S.plan = p.get("plan");
      if (p.get("custom")) S.custom = p.get("custom").split(",").map(Number);
      if (p.get("state") && M.places[p.get("state")]) S.state = p.get("state");
      if (p.get("pph")) S.pph = +p.get("pph");
    }
    const ctl = el("div", { class: "tool-controls tool-controls-wrap" });
    const out = el("div", { class: "tool-out", "aria-live": "polite" });
    view.appendChild(ctl);
    view.appendChild(out);
    function save() { writeHash("ex8", { plan: S.plan, custom: S.plan === "custom" ? S.custom : null, state: S.state !== "AUS" ? S.state : null, pph: S.pph !== M.people_per_home ? S.pph : null }); }
    function set(patch) { Object.assign(S, patch); save(); draw(); }
    function draw() {
      const presets = presetList();
      const cur = S.plan === "custom" ? { id: "custom", label: "Your own", nom: S.custom || presets[0].nom.slice() } : (presets.find(z => z.id === S.plan) || presets[0]);
      const place = S.state;
      const res = MBS.model.run(cur.nom, place, { peoplePerHome: S.pph });
      ctl.textContent = "";
      ctl.appendChild(el("div", { class: "chips", role: "group", "aria-label": "Pick a plan" },
        presets.map(z => el("button", { class: "chip", type: "button", "aria-pressed": String(z.id === cur.id), onclick: () => set({ plan: z.id, custom: null }) }, z.label)),
        el("button", { class: "chip", type: "button", "aria-pressed": String(cur.id === "custom"), onclick: () => set({ plan: "custom", custom: cur.nom.slice() }) }, "Your own")));
      ctl.appendChild(el("div", { class: "year-inputs" }, M.years.map((fy, i) => el("label", null, `${fy} (national)`,
        el("input", { class: "num-input", type: "number", step: "5000", min: "-400000", max: "800000", value: Math.round(cur.nom[i]),
          onchange: e => { const nom = cur.nom.slice(); nom[i] = +e.target.value || 0; set({ plan: "custom", custom: nom }); } })))));
      ctl.appendChild(el("div", { class: "tool-row" },
        select("plan-state", "Place", stateOptions(), S.state, v => set({ state: v })),
        el("label", { class: "tool-field", for: "pph" }, `People per home: ${S.pph.toFixed(1)} (2.5 is the 2021 Census average)`,
          el("input", { type: "range", min: "2.2", max: "2.9", step: "0.1", value: String(S.pph), id: "pph", oninput: e => set({ pph: +e.target.value }) }))));
      out.textContent = "";

      out.appendChild(el("p", { class: "tool-lead", text: `Under this plan, ${placeName(place)} would have about ${F.m2(res.pop_2030)} million people by June 2030, needing about ${F.k(Math.max(0, res.homes_per_year))} new homes a year. Last year, ${F.int(res.built)} were finished.` }));
      out.appendChild(el("div", { class: "stat-row" },
        stat(`${F.m2(res.pop_2030)}m`, `people in ${placeName(place)}, June 2030`),
        stat(F.signed(res.growth_4y), "people added over four years"),
        stat(F.k(Math.max(0, res.homes_per_year)), "new homes needed a year (our estimate)"),
        stat(F.signed(res.working_age_4y), "working-age people (15 to 64) added through migration")));
      const grid = el("div", { class: "grid-2" });
      out.appendChild(grid);
      const others = presets.filter(z => z.case === "central");
      const pathOf = nom => {
        const r = MBS.model.run(nom, place, { peoplePerHome: S.pph });
        return [{ x: 2026, v: r.start_pop, label: "June 2026" }].concat(r.years.map((y, i) => ({ x: 2027 + i, v: y.end, label: `June ${2027 + i}` })));
      };
      const shortName = z => (z.plan === "ref" ? "Last 12 months" : z.label);
      const series = [{ name: cur.label, short: cur.id === "custom" ? "Your plan" : shortName(cur), cls: "s-focus", values: pathOf(cur.nom) }].concat(others.filter(z => z.id !== cur.id).map(z => ({ name: z.label, short: shortName(z), cls: "s-context", values: pathOf(z.nom) })));
      grid.appendChild(miniFig(`Population of ${placeName(place)}, June each year`, hh => lineChart(hh, series,
        { summary: `Population path under ${cur.label}: ${F.m2(res.pop_2030)} million by June 2030.`, xticks: [2026, 2027, 2028, 2029, 2030], vfmt: v => `${F.m2(v)}m`, yfmt: v => `${(v / 1e6).toFixed(2)}m`, zero: false, left: 54, height: 230, endLabels: true }),
        { caption: `Population, June each year, ${placeName(place)}`, columns: [{ key: "label", label: "Date" }, ...series.map((s, i) => ({ key: `s${i}`, label: s.name, num: true }))],
          rows: series[0].values.map((v, k) => Object.assign({ label: v.label }, ...series.map((s, i) => ({ [`s${i}`]: s.values[k].v })))) },
        "Our model, from ABS data and each plan's published numbers"));
      const hb = res.years.map(y => ({ label: y.fy, v: Math.max(0, y.homes_needed), cls: "f-focus est" }));
      grid.appendChild(miniFig(`Homes needed each year, against homes finished last year (${F.int(res.built)})`, hh => barList(hh, hb,
        { ref: res.built, refLabel: "Finished last year", unit: "homes needed", minH: 230, summary: `Homes needed each year: ${hb.map(r => F.int(r.v)).join(", ")}. Finished last year: ${F.int(res.built)}.`, tfmt: F.short }),
        { caption: `Homes needed each year, ${placeName(place)}`, columns: [{ key: "fy", label: "Year" }, { key: "nom", label: "Net overseas migration", num: true }, { key: "growth", label: "Population growth", num: true }, { key: "homes_needed", label: "Homes needed", num: true }, { key: "end", label: "Population at 30 June", num: true }], rows: res.years },
        "Our estimate"));
      if (cur.plan === "on") out.appendChild(el("p", { class: "chart-note", text: "One Nation's first three years are our illustration: the party says more people would leave than arrive but gives no number. Low, midpoint and high cases are shown as presets." }));
      out.appendChild(el("p", { class: "chart-note", text: `How it works: each year, ${placeName(place)} gets ${F.pct1(100 * M.places[place].nom_share)} of national net overseas migration (its share over the last three years), plus births minus deaths (${F.int(M.places[place].natural_increase)} a year) and moves from other states (${F.int(M.places[place].interstate)} a year), held at the latest 12 months. Homes needed = growth ÷ people per home.` }));
      out.appendChild(cite(`Build your own plan, ${cur.label}, ${placeName(place)}`));
    }
    draw();
    return { set, state: S };
  }

  // ---------------------------------------------------------------- tool: all claims
  function toolClaims(view) {
    const cards = MBS.explore.claims;
    const S = { side: "All", verdict: "All", topic: "All", all: false };
    const p = readHash("ex20");
    if (p) ["side", "verdict", "topic"].forEach(k => { if (p.get(k)) S[k] = p.get(k); });
    const sides = ["All", ...Array.from(new Set(cards.map(c => c.side)))];
    const verdicts = ["All", ...Array.from(new Set(cards.map(c => c.verdict)))];
    const topics = ["All", ...Array.from(new Set(cards.flatMap(c => c.topic.split(/;\s*/).map(t => t.replace(/\s*\(.*\)$/, "")))))];
    const count = el("p", { class: "tool-count" });
    const grid = el("div", { class: "cards cards-3" });
    view.appendChild(el("div", { class: "tool-controls" },
      select("cl-side", "Side", sides.map(s => [s, s]), S.side, v => { S.side = v; save(); draw(); }),
      select("cl-verdict", "Verdict", verdicts.map(s => [s, s]), S.verdict, v => { S.verdict = v; save(); draw(); }),
      select("cl-topic", "Topic", topics.map(s => [s, s]), S.topic, v => { S.topic = v; save(); draw(); })));
    view.appendChild(count);
    view.appendChild(grid);
    const tb = el("div", { class: "table-view" });
    MBS.ui.fillTable(tb, { caption: "All claims", columns: [{ key: "id", label: "Card" }, { key: "side", label: "Side" }, { key: "speaker", label: "Who" }, { key: "date", label: "Date" }, { key: "verdict", label: "Verdict" }, { key: "tables", label: "Data used" }], rows: cards });
    view.appendChild(el("details", { class: "more-box" }, el("summary", null, "Every claim in one table"), tb,
      el("p", { class: "chart-note", text: "Verdict rules, the same for every side: accurate within 5% of the official figure, mostly accurate within 15%, partly accurate within 35%, otherwise inaccurate. Predictions are judged against published research where it exists. We never test motives or who is to blame." })));
    function save() { writeHash("ex20", { side: S.side !== "All" ? S.side : null, verdict: S.verdict !== "All" ? S.verdict : null, topic: S.topic !== "All" ? S.topic : null }); }
    const more = el("button", { class: "btn show-all", type: "button", onclick: () => { S.all = !S.all; draw(); } });
    grid.after(more);
    function draw() {
      const pick = cards.filter(c => (S.side === "All" || c.side === S.side) && (S.verdict === "All" || c.verdict === S.verdict) && (S.topic === "All" || c.topic.includes(S.topic)));
      const filtered = S.side !== "All" || S.verdict !== "All" || S.topic !== "All";
      const show = filtered || S.all ? pick : pick.slice(0, 6);
      count.textContent = `Showing ${show.length} of ${filtered ? pick.length + " matching" : cards.length}`;
      grid.textContent = "";
      show.forEach(c => grid.appendChild(MBS.charts.claimCard(c)));
      more.hidden = filtered || pick.length <= 6;
      more.textContent = S.all ? "Show fewer" : `Show all ${pick.length} claims`;
      more.setAttribute("aria-expanded", String(!!S.all));
    }
    draw();
    return { set: patch => { Object.assign(S, patch); draw(); }, state: S };
  }

  MBS.tools = { job: toolJob, state: toolState, plans: toolPlans, claims: toolClaims, presetList, lastHash: () => lastHash };
})();
