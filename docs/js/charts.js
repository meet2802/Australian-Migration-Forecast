/* Migration by Skill: the story charts. One function per chart; each returns
   {render(animate) -> Promise, table, summary, update?(scene)}.
   Scenes let the story change a chart as the reader scrolls (for example, light up one group); the report uses
   the default scene ("report"), which shows everything.
   Colour follows meaning, never rank: focus (blue), comparison (orange), context (grey), viridis for continuous
   values only. Text always wears ink tokens. Every chart has a table twin and a written summary. */
(function () {
  "use strict";
  const MBS = (window.MBS = window.MBS || {});
  const { el, textWidth, nextId } = MBS.util;
  const F = MBS.fmt;
  const DUR = 850;

  // ---------------------------------------------------------------- shared helpers
  function widthOf(host) {
    const w = host.clientWidth || (host.parentNode && host.parentNode.clientWidth) || 0;
    return Math.max(300, Math.min(1400, w || 680));
  }
  function makeSvg(host, w, h, label) {
    const svg = d3.select(host).append("svg")
      .attr("viewBox", `0 0 ${w} ${h}`).attr("width", w).attr("height", h)
      .attr("role", "img").attr("aria-label", label || "")
      .attr("preserveAspectRatio", "xMinYMin meet");
    return svg;
  }
  const done = (t) => new Promise(res => { if (!t) { res(); return; } t.end().then(res, res); });
  const wait = ms => new Promise(res => setTimeout(res, ms));
  function fade(sel, on, animate) {
    const s = animate && !MBS.util.reducedMotion() ? sel.transition().duration(350) : sel;
    s.attr("opacity", on ? 1 : 0);
  }
  function dim(sel, on, animate, low) {
    const s = animate && !MBS.util.reducedMotion() ? sel.transition().duration(350) : sel;
    s.attr("opacity", on ? 1 : (low == null ? 0.28 : low));
  }
  function hoverable(sel, info) {
    sel.on("pointermove", (ev, d) => { const i = info(d); MBS.ui.showTip(i.title, i.rows, ev); })
      .on("pointerleave", () => MBS.ui.hideTip())
      .on("focus", function (ev, d) { const i = info(d); MBS.ui.showTip(i.title, i.rows, this); })
      .on("blur", () => MBS.ui.hideTip());
  }
  function css(name) {
    try { return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || null; } catch (e) { return null; }
  }
  const COL = { focus: () => css("--focus") || "#1f77b4", comparison: () => css("--comparison") || "#ff7f0e",
    context: () => css("--context") || "#a3a199" };
  // round-ended bar path: square at the baseline, 4px radius at the data end (works for negative values too)
  function barPath(x0, x1, y, h, r) {
    const dir = x1 >= x0 ? 1 : -1;
    const len = Math.abs(x1 - x0);
    r = Math.min(r == null ? 4 : r, len / 2, h / 2);
    if (len < 0.5) return "";
    const xe = x1;
    return dir > 0
      ? `M${x0},${y}H${xe - r}Q${xe},${y} ${xe},${y + r}V${y + h - r}Q${xe},${y + h} ${xe - r},${y + h}H${x0}Z`
      : `M${x0},${y}H${xe + r}Q${xe},${y} ${xe},${y + r}V${y + h - r}Q${xe},${y + h} ${xe + r},${y + h}H${x0}Z`;
  }
  function yGrid(g, y, ticks, left, right, fmt) {
    const gg = g.append("g").attr("class", "grid");
    gg.selectAll("line").data(ticks).join("line")
      .attr("x1", left).attr("x2", right).attr("y1", d => y(d)).attr("y2", d => y(d));
    g.append("g").attr("class", "axis").selectAll("text").data(ticks).join("text")
      .attr("class", "tick-label").attr("x", left - 6).attr("y", d => y(d) + 4).attr("text-anchor", "end").text(fmt);
  }
  function legend(host, items) {
    const box = el("div", { class: "chart-legend", "aria-hidden": "true" });
    for (const it of items) {
      const sw = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      sw.setAttribute("width", "18"); sw.setAttribute("height", "12");
      let m;
      if (it.shape === "line" || it.shape === "dash") {
        m = document.createElementNS("http://www.w3.org/2000/svg", "line");
        m.setAttribute("x1", "1"); m.setAttribute("x2", "17"); m.setAttribute("y1", "6"); m.setAttribute("y2", "6");
        m.setAttribute("class", `line ${it.cls}${it.shape === "dash" ? " dash" : ""}`);
      } else if (it.shape === "dot") {
        m = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        m.setAttribute("cx", "9"); m.setAttribute("cy", "6"); m.setAttribute("r", "4.5"); m.setAttribute("class", it.cls);
      } else {
        m = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        m.setAttribute("x", "2"); m.setAttribute("y", "1"); m.setAttribute("width", "14"); m.setAttribute("height", "10");
        m.setAttribute("rx", "2"); m.setAttribute("class", it.cls || "");
        if (it.fill) m.setAttribute("fill", it.fill);
      }
      sw.appendChild(m);
      box.appendChild(el("span", { class: "key" }, sw, it.label));
    }
    host.appendChild(box);
    return box;
  }
  function wrapText(txt, width, size) {
    const out = [];
    let line = "";
    for (const wd of String(txt).split(/\s+/)) {
      const t = line ? line + " " + wd : wd;
      if (textWidth(t, size) > width && line) { out.push(line); line = wd; } else line = t;
    }
    if (line) out.push(line);
    return out;
  }
  const lum = hex => {
    const c = d3.color(hex).rgb();
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  // a chart's scene: remembered across re-renders (resize) and applied after drawing
  function scened(ctx, fallback) {
    const s = { scene: (ctx && ctx.scene) || fallback || "report", apply: null };
    s.set = (scene, animate) => { s.scene = scene; if (s.apply) s.apply(scene, animate); };
    return s;
  }
  MBS.chartHelpers = { barPath, widthOf, legend, lum, makeSvg, hoverable, wrapText, yGrid, done, COL, dim, fade };

  // ================================================================ Q1: MCG crowds filling up
  function mcg(host, d) {
    const q = d.q1;
    const n = Math.ceil(q.mcgs);
    const fills = d3.range(n).map(i => Math.max(0, Math.min(1, q.mcgs - i)));
    const table = {
      caption: `Net overseas migration, ${q.period_label}, in full MCGs`,
      columns: [{ key: "k", label: "Stadium" }, { key: "people", label: "People", num: true },
        { key: "full", label: "How full", num: true, fmt: v => `${Math.round(v * 100)}%` }],
      rows: fills.map((f, i) => ({ k: `MCG ${i + 1}`, people: Math.round(Math.min(q.mcg_capacity, q.nom - i * q.mcg_capacity)), full: f }))
    };
    const summary = `${n} stadium shapes. ${fills.filter(f => f >= 1).length} are full and the last is ${Math.round(fills[n - 1] * 100)}% full: ${F.int(q.nom)} people, or ${F.one(q.mcgs)} full MCGs.`;
    function render(animate) {
      host.textContent = "";
      const w = widthOf(host);
      const gap = 12;
      const iw = Math.min(170, (w - gap * (n - 1)) / n);
      const ih = iw * 0.72;
      const h = ih + 44;
      const svg = makeSvg(host, w, h, summary);
      const x0 = (w - (n * iw + (n - 1) * gap)) / 2;
      const ts = [];
      fills.forEach((f, i) => {
        const g = svg.append("g").attr("transform", `translate(${x0 + i * (iw + gap)},4)`);
        const cid = nextId("clip");
        const rx = iw / 2 - 2, ry = ih / 2 - 2;
        g.append("ellipse").attr("cx", iw / 2).attr("cy", ih / 2).attr("rx", rx).attr("ry", ry).attr("class", "f-context-2");
        const clip = g.append("clipPath").attr("id", cid).append("rect").attr("x", 0).attr("width", iw)
          .attr("y", animate ? ih : ih * (1 - f)).attr("height", animate ? 0 : ih * f);
        g.append("ellipse").attr("cx", iw / 2).attr("cy", ih / 2).attr("rx", rx).attr("ry", ry).attr("class", "f-focus")
          .attr("clip-path", `url(#${cid})`);
        g.append("ellipse").attr("cx", iw / 2).attr("cy", ih / 2).attr("rx", rx * 0.6).attr("ry", ry * 0.56)
          .attr("class", "f-surface").attr("stroke", "var(--axis)").attr("stroke-width", 1);
        g.append("rect").attr("x", iw / 2 - iw * 0.025).attr("y", ih / 2 - ih * 0.15).attr("width", iw * 0.05).attr("height", ih * 0.3)
          .attr("rx", 1).attr("fill", "var(--axis)");
        g.append("ellipse").attr("cx", iw / 2).attr("cy", ih / 2).attr("rx", rx).attr("ry", ry).attr("fill", "none")
          .attr("stroke", "var(--axis)").attr("stroke-width", 1);
        g.append("text").attr("class", f >= 1 ? "lbl" : "lbl-strong").attr("x", iw / 2).attr("y", ih + 20)
          .attr("text-anchor", "middle").text(f >= 1 ? "Full MCG" : `${Math.round(f * 100)}% full`);
        g.append("rect").attr("class", "hover-target").attr("width", iw).attr("height", ih + 24)
          .datum(table.rows[i]);
        if (animate) {
          ts.push(clip.transition().delay(i * 260).duration(420).ease(d3.easeCubicOut)
            .attr("y", ih * (1 - f)).attr("height", ih * f));
        }
      });
      hoverable(svg.selectAll(".hover-target"), r => ({ title: r.k, rows: [{ value: F.int(r.people), label: `people (${Math.round(r.full * 100)}% full)` }] }));
      svg.append("text").attr("class", "lbl-3").attr("x", w / 2).attr("y", h - 2).attr("text-anchor", "middle")
        .text(`One full MCG holds ${F.int(q.mcg_capacity)} people`);
      MBS.ui.keyNav(svg.node(), () => svg.selectAll(".hover-target").nodes().map((nd, i) => ({ node: nd, title: table.rows[i].k,
        rows: [{ value: F.int(table.rows[i].people), label: "people" }] })), summary);
      host.appendChild(el("div", { class: "stat-row stat-row-tight" },
        el("div", { class: "stat" }, el("div", { class: "v", text: F.about(q.per_day) }), el("div", { class: "l", text: "more people a day" })),
        el("div", { class: "stat" }, el("div", { class: "v", text: F.int(q.growth_12m) }), el("div", { class: "l", text: "total population growth, with births minus deaths" }))));
      return Promise.all(ts.map(t => done(t)));
    }
    return { render, table, summary };
  }

  // ================================================================ Q2: net migration since 1950
  function nomLine(host, d, ctx) {
    const q = d.q2;
    const s = q.series;
    const sc = scened(ctx);
    const table = {
      caption: "Net overseas migration, each year since 1950 (12 months to each quarter from 1982)",
      columns: [{ key: "label", label: "Period" }, { key: "v", label: "More arrived than left", num: true }],
      rows: s.slice().reverse()
    };
    const summary = `Line chart of net overseas migration since 1950. Highest: ${F.int(q.peak.v)} in the ${F.yearTo(q.peak.label)}. Lowest: ${F.int(q.low.v)} in the ${F.yearTo(q.low.label)}. Latest: ${F.int(q.latest.v)}.`;
    function render(animate) {
      host.textContent = "";
      const w = widthOf(host);
      const narrow = w < 520;
      const h = narrow ? 280 : 340;
      const m = { t: 30, r: narrow ? 66 : 108, b: 26, l: 44 };
      const svg = makeSvg(host, w, h, summary);
      const x = d3.scaleLinear().domain([1950, 2026.6]).range([m.l, w - m.r]);
      const y = d3.scaleLinear().domain([Math.min(-100000, d3.min(s, p => p.v)), Math.max(600000, d3.max(s, p => p.v))]).nice().range([h - m.b, m.t]);
      const g = svg.append("g");
      yGrid(g, y, y.ticks(5), m.l, w - m.r, F.short);
      const xt = narrow ? [1960, 1980, 2000, 2020] : [1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020];
      g.append("g").attr("class", "axis").selectAll("text").data(xt).join("text").attr("class", "tick-label")
        .attr("x", v => x(v)).attr("y", h - 6).attr("text-anchor", "middle").text(v => v);
      g.append("line").attr("class", "baseline").attr("x1", m.l).attr("x2", x(2026.6)).attr("y1", y(0)).attr("y2", y(0));
      const line = d3.line().x(p => x(p.x)).y(p => y(p.v)).curve(d3.curveMonotoneX);
      const path = g.append("path").datum(s).attr("class", "line s-focus").attr("d", line);
      let t = null;
      if (animate) {
        const len = path.node().getTotalLength ? path.node().getTotalLength() : 2000;
        path.attr("stroke-dasharray", `${len} ${len}`).attr("stroke-dashoffset", len);
        t = path.transition().duration(1400).ease(d3.easeCubicInOut).attr("stroke-dashoffset", 0)
          .on("end", () => path.attr("stroke-dasharray", null));
      }
      // annotations, one group each, shown by scene
      const annLow = g.append("g").attr("opacity", 0);
      if (q.fy_2020_21 < 0) {
        annLow.append("circle").attr("cx", x(q.low.x)).attr("cy", y(q.low.v)).attr("r", 5).attr("class", "f-comparison ring");
        annLow.append("text").attr("class", "lbl-strong").attr("x", x(q.low.x) - 9).attr("y", y(q.low.v) + 4)
          .attr("text-anchor", "end").text(narrow ? "2020-21: more left" : "2020-21: more left than arrived");
      }
      const annPeak = g.append("g").attr("opacity", 0);
      annPeak.append("circle").attr("cx", x(q.peak.x)).attr("cy", y(q.peak.v)).attr("r", 5).attr("class", "f-comparison ring");
      annPeak.append("text").attr("class", "lbl-strong").attr("x", x(q.peak.x) - 9).attr("y", y(q.peak.v) + 4)
        .attr("text-anchor", "end").text(`Record: ${F.k(q.peak.v)}`);
      annPeak.append("text").attr("class", "lbl-3").attr("x", x(q.peak.x) - 9).attr("y", y(q.peak.v) + 19)
        .attr("text-anchor", "end").text(F.yearTo(q.peak.label));
      const annNow = g.append("g").attr("opacity", 0);
      annNow.append("circle").attr("cx", x(q.latest.x)).attr("cy", y(q.latest.v)).attr("r", 5).attr("class", "f-focus ring");
      // on a phone the label sits under the point, clear of the bracket that comes down to it
      annNow.append("text").attr("class", "lbl-strong").attr("x", x(q.latest.x) + (narrow ? 6 : 9)).attr("y", y(q.latest.v) + (narrow ? 19 : 4))
        .attr("text-anchor", "start").text(narrow ? "Now" : `Now: ${F.k(q.latest.v)}`);
      if (narrow) annNow.append("text").attr("class", "lbl").attr("x", x(q.latest.x) + 6).attr("y", y(q.latest.v) + 34).text(F.k(q.latest.v));
      // the fall from the record: a bracket beside the latest point
      const annFall = g.append("g").attr("opacity", 0);
      const bx = x(q.latest.x) + (narrow ? 30 : 46);
      annFall.append("line").attr("class", "s-ink dash").attr("x1", x(q.peak.x)).attr("x2", bx).attr("y1", y(q.peak.v)).attr("y2", y(q.peak.v)).attr("stroke-width", 1);
      annFall.append("line").attr("class", "s-ink").attr("x1", bx).attr("x2", bx).attr("y1", y(q.peak.v)).attr("y2", y(q.latest.v) - 10).attr("stroke-width", 1.5);
      annFall.append("path").attr("class", "f-ink").attr("d", `M${bx - 4},${y(q.latest.v) - 14}L${bx},${y(q.latest.v) - 7}L${bx + 4},${y(q.latest.v) - 14}Z`);
      annFall.append("text").attr("class", "lbl-strong").attr("x", bx + 6).attr("y", (y(q.peak.v) + y(q.latest.v)) / 2).text(`−${F.pct0(q.fall_from_peak_pct)}`);
      // crosshair
      const ch = g.append("line").attr("class", "crosshair").attr("y1", m.t).attr("y2", h - m.b).style("opacity", 0);
      const dot = g.append("circle").attr("r", 4).attr("class", "f-focus ring").style("opacity", 0).attr("pointer-events", "none");
      const bis = d3.bisector(p => p.x).center;
      g.append("rect").attr("class", "hover-target").attr("x", m.l).attr("y", m.t).attr("width", w - m.l - m.r).attr("height", h - m.t - m.b)
        .on("pointermove", ev => {
          const [px] = d3.pointer(ev);
          const p = s[bis(s, x.invert(px))];
          ch.attr("x1", x(p.x)).attr("x2", x(p.x)).style("opacity", 1);
          dot.attr("cx", x(p.x)).attr("cy", y(p.v)).style("opacity", 1);
          MBS.ui.showTip(p.label, [{ value: F.int(p.v), label: "more arrived than left", color: COL.focus() }], ev);
        })
        .on("pointerleave", () => { ch.style("opacity", 0); dot.style("opacity", 0); MBS.ui.hideTip(); });
      MBS.ui.keyNav(svg.node(), () => {
        const pick = [s[0], ...s.filter(p => p.kind !== "rolling" && p.x % 10 === 1), q.peak, q.low, q.latest];
        return pick.map(p => ({ node: dot.attr("cx", x(p.x)).attr("cy", y(p.v)).style("opacity", 1).node(), title: p.label,
          rows: [{ value: F.int(p.v), label: "more arrived than left" }] }));
      }, summary);
      sc.apply = (scene, anim) => {
        fade(annLow, scene === "low" || scene === "report", anim);
        fade(annPeak, scene === "peak" || scene === "now" || scene === "report", anim);
        fade(annNow, scene === "now" || scene === "report", anim);
        fade(annFall, scene === "now", anim);
      };
      if (animate) return done(t).then(() => { sc.apply(sc.scene, true); return wait(300); });
      sc.apply(sc.scene, false);
      return Promise.resolve();
    }
    return { render, table, summary, update: s => sc.set(s, true), get scene() { return sc.scene; } };
  }

  // ================================================================ Q3: 100 squares by visa type
  function waffle(host, d, ctx) {
    const q = d.q3;
    const sc = scened(ctx);
    const kinds = [
      { kind: "permanent", label: "Permanent visa", cls: "f-focus" },
      { kind: "temporary", label: "Temporary visa", cls: "f-context" },
      { kind: "citizen", label: "Citizens", cls: "f-context-2" }];
    const squares = [];
    for (const k of kinds) for (const g of q.groups.filter(x => x.kind === k.kind)) for (let i = 0; i < g.squares; i++) squares.push({ ...g, cls: k.cls });
    const table = {
      caption: `People who arrived to stay, ${q.year}, by how they arrived (squares out of 100)`,
      columns: [{ key: "label", label: "Group" }, { key: "kind", label: "Visa", fmt: v => ({ permanent: "Permanent", temporary: "Temporary", citizen: "No visa (citizen)" })[v] },
        { key: "arrivals", label: "Arrivals", num: true }, { key: "squares", label: "Squares", num: true }, { key: "net", label: "Net (minus departures)", num: true }],
      rows: q.groups
    };
    const summary = `100 squares. ${q.permanent_squares} are people with a permanent visa, ${q.temporary_squares} temporary visas, and ${q.citizen_squares} Australian or New Zealand citizens.`;
    // which squares light up in each scene
    const lit = (scene, s) => scene === "citizen" ? s.kind === "citizen" : scene === "temporary" ? s.kind === "temporary" :
      scene === "permanent" ? s.kind === "permanent" : scene === "skilled" ? s.key === "perm_skilled" : false;
    function clsFor(scene, s) {
      if (scene === "report") return s.cls;
      if (scene === "all") return "f-context";
      if (lit(scene, s)) return "f-focus";
      return scene === "skilled" && s.kind === "permanent" ? "f-context" : "f-context-2";
    }
    function render(animate) {
      host.textContent = "";
      const w = widthOf(host);
      const side = w >= 560;
      const size = Math.min(side ? 320 : w - 8, 340);
      const cell = size / 10;
      const svg = makeSvg(host, side ? w : size, size, summary);
      const g = svg.append("g");
      const sel = g.selectAll("rect").data(squares).join("rect")
        .attr("x", (s, i) => (i % 10) * cell + 1).attr("y", (s, i) => Math.floor(i / 10) * cell + 1)
        .attr("width", cell - 2).attr("height", cell - 2).attr("rx", 2).attr("class", s => clsFor(sc.scene, s) + " sq")
        .attr("opacity", animate ? 0 : 1);
      hoverable(sel, s => ({ title: s.label, rows: [{ value: `${s.squares} in 100`, label: `${F.int(s.arrivals)} people` }] }));
      const groups = kinds.map(k => {
        const gs = q.groups.filter(x => x.kind === k.kind);
        return { ...k, n: gs.reduce((a, b) => a + b.squares, 0), parts: gs };
      });
      let legendRows = [];
      if (side) {
        const lg = svg.append("g").attr("transform", `translate(${size + 26},8)`);
        let yy = 0;
        groups.forEach(gr => {
          const blk = lg.append("g").attr("data-kind", gr.kind);
          blk.append("rect").attr("x", 0).attr("y", yy).attr("width", 14).attr("height", 14).attr("rx", 2).attr("class", gr.cls + " lg-sw");
          blk.append("text").attr("class", "lbl-strong").attr("x", 22).attr("y", yy + 12).text(`${gr.label}: ${gr.n}`);
          yy += 22;
          gr.parts.forEach(p => {
            blk.append("text").attr("class", "lbl-2").attr("data-key", p.key).attr("x", 22).attr("y", yy + 10).text(`${p.label} ${p.squares}`);
            yy += 18;
          });
          yy += 10;
          legendRows.push(blk);
        });
      } else {
        const box = el("div", { class: "chart-legend", "aria-hidden": "true", style: "flex-direction:column;gap:8px;margin-top:10px" });
        groups.forEach(gr => {
          const sw = el("span", { style: `display:inline-block;width:12px;height:12px;border-radius:2px;background:var(--${gr.cls.replace("f-", "")})` });
          box.appendChild(el("div", { "data-kind": gr.kind }, el("span", { class: "key", style: "font-weight:650;color:var(--ink)" }, sw, `${gr.label}: ${gr.n}`),
            el("div", { style: "padding-left:18px" }, gr.parts.map(p => `${p.label} ${p.squares}`).join(" · "))));
        });
        host.appendChild(box);
      }
      MBS.ui.keyNav(svg.node(), () => q.groups.map(gp => ({ node: sel.filter(s => s.key === gp.key).node(), title: gp.label,
        rows: [{ value: `${gp.squares} in 100`, label: `${F.int(gp.arrivals)} people` }] })), summary);
      sc.apply = (scene) => {
        sel.attr("class", s => clsFor(scene, s) + " sq");
        const on = k => scene === "report" || scene === "all" || (scene === "skilled" ? k === "permanent" : scene === k);
        legendRows.forEach(b => b.attr("opacity", on(b.attr("data-kind")) ? 1 : 0.4));
        host.querySelectorAll(".chart-legend [data-kind]").forEach(n => { n.style.opacity = on(n.getAttribute("data-kind")) ? "1" : "0.4"; });
      };
      sc.apply(sc.scene);
      if (!animate) return Promise.resolve();
      const t = sel.transition().delay((s, i) => i * 7).duration(220).attr("opacity", 1);
      return done(t);
    }
    return { render, table, summary, update: s => sc.set(s, true), get scene() { return sc.scene; } };
  }

  // ================================================================ net migration by visa group (skilled combined)
  function netByVisa(host, d, ctx) {
    const q = d.q3;
    const sc = scened(ctx);
    const G = k => q.groups.find(g => g.key === k);
    const ps = G("perm_skilled"), ts = G("temp_skilled");
    const rows = [
      { key: "skilled", label: "Skilled visas", net: ps.net + ts.net, parts: [{ label: "permanent", v: ps.net }, { label: "temporary", v: ts.net }], role: "focus" },
      ...q.groups.filter(g => g.key !== "perm_skilled" && g.key !== "temp_skilled").map(g => ({ key: g.key, label: g.label, net: g.net, role: g.key === "students" ? "comparison" : "context" }))
    ].sort((a, b) => b.net - a.net);
    const table = {
      caption: `Net overseas migration by visa group, ${q.year} (arrivals minus departures)`,
      columns: [{ key: "label", label: "Group" }, { key: "net", label: "Net", num: true }, { key: "share", label: "Share of net", num: true, fmt: v => F.pct1(v) }],
      rows: rows.map(r => ({ ...r, share: 100 * r.net / q.net_total })).concat([{ label: "Total", net: q.net_total, share: 100 }])
    };
    const summary = `Bar chart of net overseas migration by visa group in ${q.year}: ` + rows.map(r => `${r.label} ${F.int(r.net)}`).join(", ") + `. Total ${F.int(q.net_total)}.`;
    function render(animate) {
      host.textContent = "";
      const w = widthOf(host);
      const narrow = w < 520;
      const fs = narrow ? 12 : 13;
      const labW = d3.max(rows, r => textWidth(r.label, fs)) + 12;
      const rowH = narrow ? 30 : 32, bh = 18;
      const m = { t: 8, r: 62, b: 24, l: labW };
      const h = m.t + rows.length * rowH + m.b;
      const svg = makeSvg(host, w, h, summary);
      const x = d3.scaleLinear().domain([Math.min(0, d3.min(rows, r => r.net)) * 1.15, d3.max(rows, r => r.net)]).nice().range([m.l + 30, w - m.r]);
      const g = svg.append("g");
      const ticks = x.ticks(narrow ? 3 : 5);
      g.append("g").attr("class", "grid").selectAll("line").data(ticks).join("line").attr("x1", x).attr("x2", x).attr("y1", m.t).attr("y2", h - m.b);
      g.append("g").selectAll("text").data(ticks).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - 6).attr("text-anchor", "middle").text(F.short);
      g.append("line").attr("class", "baseline").attr("x1", x(0)).attr("x2", x(0)).attr("y1", m.t).attr("y2", h - m.b);
      const ts_ = [];
      const rowG = g.selectAll(".row").data(rows).join("g").attr("class", "row").attr("transform", (r, i) => `translate(0,${m.t + i * rowH})`);
      rowG.append("text").attr("class", r => r.role === "context" ? "lbl-2" : "lbl-strong").attr("x", m.l - 8).attr("y", bh - 2).attr("text-anchor", "end")
        .style("font-size", fs + "px").text(r => r.label);
      rowG.each(function (r) {
        const gg = d3.select(this);
        const cls = r.role === "focus" ? "f-focus" : r.role === "comparison" ? "f-comparison" : "f-context";
        if (r.parts) {
          let x0 = 0;
          r.parts.forEach((p, i) => {
            const a = x(x0), b = x(x0 + p.v);
            const pth = gg.append("path").attr("class", cls + " bar").attr("d", i === r.parts.length - 1 ? barPath(a + (i ? 1 : 0), b, 0, bh) : `M${a},0H${b - 1}V${bh}H${a}Z`);
            if (animate) pth.attr("opacity", 0).transition().delay(200 + i * 200).duration(400).attr("opacity", 1);
            x0 += p.v;
          });

        } else {
          const pth = gg.append("path").attr("class", cls + " bar").attr("d", barPath(x(0), x(animate ? 0 : r.net), 0, bh));
          if (animate) ts_.push(pth.transition().duration(DUR).ease(d3.easeCubicOut).attrTween("d", () => t => barPath(x(0), x(r.net * t), 0, bh)));
        }
        const vt = gg.append("text").attr("class", "lbl").attr("x", r.net >= 0 ? x(r.net) + 6 : x(r.net) - 6).attr("y", bh - 2)
          .attr("text-anchor", r.net >= 0 ? "start" : "end").text(F.short(r.net));
        if (r.parts) {
          // name each part inside its own segment when it fits
          let x0 = 0;
          r.parts.forEach(p => {
            const a = x(x0), b = x(x0 + p.v), txt = `${p.label} ${F.short(p.v)}`;
            if (b - a > textWidth(txt, 11) + 10) {
              gg.append("text").attr("class", "in-bar").attr("x", (a + b) / 2).attr("y", bh - 4.5).attr("text-anchor", "middle").text(txt);
            }
            x0 += p.v;
          });
        }
        gg.append("rect").attr("class", "hover-target").attr("x", 0).attr("width", w).attr("y", -6).attr("height", rowH);
      });
      hoverable(rowG.selectAll(".hover-target"), r => ({ title: r.label, rows: [{ value: F.int(r.net), label: "net (arrivals minus departures)" },
        { value: F.pct1(100 * r.net / q.net_total), label: "of net overseas migration" }].concat(r.parts ? r.parts.map(p => ({ value: F.int(p.v), label: p.label })) : []) }));
      MBS.ui.keyNav(svg.node(), () => rowG.nodes().map((nd, i) => ({ node: d3.select(nd).select(".hover-target").node(), title: rows[i].label,
        rows: [{ value: F.int(rows[i].net), label: "net" }] })), summary);
      sc.apply = (scene, anim) => {
        rowG.each(function (r) { dim(d3.select(this), scene === "report" || scene === "all" || r.role !== "context", anim, 0.45); });
      };
      sc.apply(sc.scene, false);
      return Promise.all(ts_.map(done));
    }
    return { render, table, summary, update: s => sc.set(s, true) };
  }

  // ================================================================ Q4: each plan's yearly net migration
  function planLines(host, d, ctx) {
    const q = d.q4;
    const xs = ["now", ...q.years];
    const plans = q.plans.filter(p => p.nom);
    const grn = q.plans.find(p => p.id === "grn");
    const on = q.plans.find(p => p.id === "on");
    let lit = (ctx && ctx.scene) || "all";
    const table = {
      caption: "Net overseas migration a year under each plan (One Nation years 1 to 3: our illustration, midpoint and range)",
      columns: [{ key: "year", label: "Year" }, ...plans.map(p => ({ key: p.id, label: p.name, num: true, fmt: (v, r) =>
        p.id === "on" && r.on_low != null ? `${F.int(v)} (${F.int(r.on_low)} to ${F.int(r.on_high)})` : F.int(v) }))],
      rows: q.years.map((y, i) => {
        const r = { year: y };
        plans.forEach(p => { r[p.id] = p.nom[i]; });
        if (i < 3) { r.on_low = on.nom_low[i]; r.on_high = on.nom_high[i]; }
        return r;
      })
    };
    table.rows.unshift({ year: `Now (${q.now.label})`, gov: q.now.v, coa: q.now.v, on: q.now.v });
    const summary = `Line chart of each plan from now (${F.int(q.now.v)}) to ${q.years[q.years.length - 1]}. ` +
      plans.map(p => `${p.name}: ${p.nom.map(F.int).join(", ")}`).join(". ") + `. Greens: no overall number.`;
    let api = {};
    function render(animate) {
      host.textContent = "";
      const w = widthOf(host);
      const narrow = w < 520;
      const h = narrow ? 300 : 340;
      const m = { t: 18, r: narrow ? 14 : 24, b: 28, l: 46 };
      const svg = makeSvg(host, w, h, summary);
      const x = d3.scalePoint().domain(xs).range([m.l + 8, w - m.r - 8]);
      const y = d3.scaleLinear().domain([-280000, 320000]).range([h - m.b, m.t]);
      const g = svg.append("g");
      yGrid(g, y, [-200000, -100000, 0, 100000, 200000, 300000], m.l, w - m.r, F.short);
      g.append("g").attr("class", "axis").selectAll("text").data(xs).join("text").attr("class", "tick-label")
        .attr("x", v => x(v)).attr("y", h - 8).attr("text-anchor", "middle")
        .text(v => v === "now" ? "Now" : narrow ? v.replace(/^20(\d\d)-(\d\d)$/, "’$1-$2") : v);
      g.append("line").attr("class", "baseline").attr("x1", m.l).attr("x2", w - m.r).attr("y1", y(0)).attr("y2", y(0));
      const band = d3.area().x(v => x(v.x)).y0(v => y(v.lo)).y1(v => y(v.hi));
      const bandData = [0, 1, 2].map(i => ({ x: q.years[i], lo: on.nom_low[i], hi: on.nom_high[i] }));
      const plansG = g.append("g");
      const bandPath = plansG.append("path").datum(bandData).attr("d", band).attr("data-plan", "on").attr("class", "band");
      const lineGen = d3.line().x(v => x(v.x)).y(v => y(v.v));
      const lines = plans.map(p => {
        const pts = [{ x: "now", v: q.now.v }, ...q.years.map((yy, i) => ({ x: yy, v: p.nom[i] }))];
        const gp = plansG.append("g").attr("data-plan", p.id);
        if (p.id === "on") {
          gp.append("path").datum(pts.slice(0, 4)).attr("d", lineGen).attr("class", "line dot-line pl");
          gp.append("path").datum(pts.slice(3)).attr("d", lineGen).attr("class", "line dash pl");
          gp.append("path").datum(pts.slice(0, 2)).attr("d", lineGen).attr("class", "line dash pl");
        } else {
          gp.append("path").datum(pts).attr("d", lineGen).attr("class", "line dash pl");
        }
        gp.selectAll("circle").data(pts.slice(1)).join("circle").attr("cx", v => x(v.x)).attr("cy", v => y(v.v)).attr("r", 4)
          .attr("class", "ring pd");
        return { p, gp, pts };
      });
      const nameAt = q.years[1];
      const names = g.append("g");
      const govV = plans.find(p => p.id === "gov").nom[1], coaV = plans.find(p => p.id === "coa").nom[1];
      names.append("text").attr("class", "lbl-strong nm").attr("data-plan", "gov").attr("x", x(nameAt)).attr("y", y(govV) - 10)
        .attr("text-anchor", "middle").text("Government");
      names.append("text").attr("class", "lbl-strong nm").attr("data-plan", "coa").attr("x", x(nameAt)).attr("y", y(coaV) + 20)
        .attr("text-anchor", "middle").text("Coalition");
      names.append("text").attr("class", "lbl-strong nm").attr("data-plan", "on").attr("x", x(nameAt)).attr("y", y(on.nom_low[1]) + 16)
        .attr("text-anchor", "middle").text(narrow ? "One Nation (our illustration)" : "One Nation (range: our illustration)");
      g.append("circle").attr("cx", x("now")).attr("cy", y(q.now.v)).attr("r", 5.5).attr("class", "f-comparison ring");
      g.append("text").attr("class", "lbl-strong").attr("x", x("now") + 2).attr("y", y(q.now.v) - 11).attr("text-anchor", "start").text(`Now: ${F.k(q.now.v)}`);
      const values = g.append("g");
      const note = g.append("g").attr("opacity", 0).attr("pointer-events", "none");
      const nw = Math.min(w - m.l - m.r - 16, 340);
      const noteLines = wrapText(grnShort(grn), nw - 24, 13);
      const ny = y(-20000);
      note.append("rect").attr("x", m.l + 8).attr("y", ny).attr("width", nw).attr("height", 34 + noteLines.length * 18).attr("rx", 8).attr("class", "f-surface").attr("stroke", "var(--border)");
      note.append("text").attr("class", "lbl-strong").attr("x", m.l + 18).attr("y", ny + 22).text("Greens: no overall number to draw");
      noteLines.forEach((ln, i) => note.append("text").attr("class", "lbl-2").attr("x", m.l + 18).attr("y", ny + 42 + i * 18).text(ln));
      function paint(state, anim) {
        lit = state;
        lines.forEach(({ p, gp }) => {
          const on_ = state === "all" || state === p.id;
          gp.selectAll(".pl").attr("class", function () { return this.getAttribute("class").replace(/ ?s-(focus|context)/g, "") + (on_ ? " s-focus" : " s-context"); })
            .attr("stroke-width", state === p.id ? 3 : 2);
          gp.selectAll(".pd").attr("class", "ring pd " + (on_ ? "f-focus" : "f-context"));
        });
        const bandOn = state === "all" || state === "on";
        bandPath.attr("fill", bandOn ? "url(#hatch-focus)" : "url(#hatch-context)").attr("opacity", bandOn ? 0.9 : 0.6);
        names.selectAll(".nm").attr("class", function () { return "nm " + ((state === "all" || state === this.getAttribute("data-plan")) ? "lbl-strong" : "lbl-3"); });
        values.selectAll("*").remove();
        const sp = plans.find(p => p.id === state);
        if (sp) {
          sp.nom.forEach((v, i) => {
            if (sp.id === "gov" && q.years[i] === nameAt) return;
            values.append("text").attr("class", "lbl-strong").attr("x", x(q.years[i])).attr("y", y(v) + (v < 0 ? 18 : -9))
              .attr("text-anchor", i === sp.nom.length - 1 ? "end" : "middle").text(F.short(v));
          });
        }
        names.select('[data-plan="gov"]').text(state === "gov" ? `Government: ${F.short(govV)}` : "Government");
        (anim && !MBS.util.reducedMotion() ? note.transition().duration(200) : note).attr("opacity", state === "grn" ? 1 : 0);
        if (ctx && ctx.onLit) ctx.onLit(state);
      }
      api.paint = paint;
      paint(lit, false);
      const colW = (x.step ? x.step() : 60);
      g.selectAll(".col").data(xs).join("rect").attr("class", "hover-target col").attr("x", v => x(v) - colW / 2).attr("width", colW)
        .attr("y", m.t).attr("height", h - m.t - m.b)
        .on("pointermove", (ev, v) => {
          if (v === "now") { MBS.ui.showTip(`Now (${q.now.label})`, [{ value: F.int(q.now.v), label: "more arrived than left" }], ev); return; }
          const i = q.years.indexOf(v);
          MBS.ui.showTip(v, plans.map(p => ({ value: p.id === "on" && i < 3 ? `${F.int(on.nom_low[i])} to ${F.int(on.nom_high[i])}` : F.int(p.nom[i]),
            label: p.name, color: COL.focus() })).concat([{ value: "No number", label: "Greens" }]), ev);
        })
        .on("pointerleave", () => MBS.ui.hideTip());
      MBS.ui.keyNav(svg.node(), () => g.selectAll(".col").nodes().map((nd, k) => {
        const v = xs[k];
        if (v === "now") return { node: nd, title: "Now", rows: [{ value: F.int(q.now.v) }] };
        const i = q.years.indexOf(v);
        return { node: nd, title: v, rows: plans.map(p => ({ value: p.id === "on" && i < 3 ? `${F.int(on.nom_low[i])} to ${F.int(on.nom_high[i])}` : F.int(p.nom[i]), label: p.name })) };
      }), summary);
      host.appendChild(el("p", { class: "chart-note", text: "Below 0, more people leave than arrive. Dashed lines are plans and forecasts; the hatched band is our illustration." }));
      if (animate) {
        plansG.attr("opacity", 0);
        return done(plansG.transition().duration(500).attr("opacity", 1));
      }
      return Promise.resolve();
    }
    function grnShort(g) {
      const m = /Humanitarian intake ([\d,]+) a year/.exec(g.note || "");
      return m ? `Their policy sets a humanitarian intake of ${m[1]} a year, not a total.` : "Their policy sets no total.";
    }
    function update(state) { lit = state; if (api.paint) api.paint(state, true); }
    return { render, table, summary, update, get lit() { return lit; } };
  }

  // ================================================================ rows-with-labels-above layout (Q5, Q6, Q11)
  function rowsFrame(host, n, opts) {
    const w = widthOf(host);
    const rowH = opts.rowH || 46;
    const m = { t: opts.top || 26, r: opts.right || 54, b: 26, l: opts.left || 8 };
    const h = m.t + n * rowH + m.b;
    return { w, h, m, rowH };
  }

  // ================================================================ Q5: population in 2030
  function popDots(host, d, ctx) {
    const q = d.q5;
    const rows = [...q.plans, { id: "ref", name: q.reference.name, v: q.reference.v, kind: "context" }];
    const table = {
      caption: "Population at 30 June 2030 under each plan (our model)",
      columns: [{ key: "name", label: "Plan" }, { key: "v", label: "Population, June 2030", num: true },
        { key: "range", label: "Range", num: true, fmt: (v, r) => r.low != null ? `${F.int(r.low)} to ${F.int(r.high != null ? r.high : r.v)}` : "–" },
        { key: "change", label: "Change from June 2026", num: true, fmt: v => F.signed(v) }],
      rows: rows.map(r => ({ ...r, range: r.low, change: r.v - q.today }))
    };
    table.rows.unshift({ name: "Today (June 2026, our estimate)", v: q.today, change: 0 });
    const summary = `Dot chart of the population in June 2030. Today: ${F.m1(q.today)} million. ` +
      rows.map(r => `${r.name}: ${F.m1(r.v)} million`).join(". ") + ".";
    function render(animate) {
      host.textContent = "";
      const minH = ctx && ctx.minH;
      const L = rowsFrame(host, rows.length, { top: 30, right: 60, rowH: minH ? Math.max(46, Math.floor((minH - 56) / rows.length)) : 46 });
      const { w, h, m, rowH } = L;
      const svg = makeSvg(host, w, h, summary);
      const lo = d3.min(rows, r => r.low != null ? r.low : r.v), hi = d3.max(rows, r => r.v);
      const x = d3.scaleLinear().domain([Math.min(lo, q.today) - 150000, hi + 100000]).nice().range([m.l + 4, w - m.r]);
      const g = svg.append("g");
      const ticks = x.ticks(w < 520 ? 4 : 6);
      g.append("g").attr("class", "grid").selectAll("line").data(ticks).join("line").attr("x1", x).attr("x2", x).attr("y1", m.t - 6).attr("y2", h - m.b);
      g.append("g").selectAll("text").data(ticks).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - 8).attr("text-anchor", "middle").text(v => `${(v / 1e6).toFixed(1)}m`);
      g.append("line").attr("class", "s-comparison").attr("stroke-width", 2).attr("x1", x(q.today)).attr("x2", x(q.today)).attr("y1", m.t - 8).attr("y2", h - m.b);
      g.append("text").attr("class", "lbl-strong").attr("x", x(q.today)).attr("y", m.t - 13).attr("text-anchor", x(q.today) < w * 0.3 ? "start" : "middle")
        .text(`Today: ${F.m1(q.today)} million`);
      const ts = [];
      rows.forEach((r, i) => {
        const yy = m.t + i * rowH;
        const cy = yy + rowH - 14;
        const gr = g.append("g");
        gr.append("text").attr("class", r.id === "ref" ? "lbl-2" : "lbl-strong").attr("x", m.l + 4).attr("y", cy - 14).text(r.name);
        gr.append("line").attr("class", "s-context").attr("stroke-width", 1).attr("x1", x(q.today)).attr("x2", x(r.v)).attr("y1", cy).attr("y2", cy);
        if (r.low != null && r.high != null) {
          gr.append("rect").attr("x", x(r.low)).attr("width", x(r.high) - x(r.low)).attr("y", cy - 7).attr("height", 14).attr("rx", 3)
            .attr("fill", "url(#hatch-focus)").attr("class", "hatch-bg");
        } else if (r.low != null) {
          gr.append("line").attr("class", "s-focus").attr("stroke-width", 2).attr("x1", x(r.low)).attr("x2", x(r.v)).attr("y1", cy).attr("y2", cy).attr("stroke-opacity", .5);
        }
        const c = gr.append("circle").attr("cy", cy).attr("r", 6).attr("class", (r.id === "ref" ? "f-context" : "f-focus") + " ring")
          .attr("cx", animate ? x(q.today) : x(r.v));
        const lab = gr.append("text").attr("class", "lbl").attr("y", cy + 4).attr("x", x(r.high || r.v) + 10).text(`${F.m1(r.v)}m`).attr("opacity", animate ? 0 : 1);
        if (animate) {
          ts.push(c.transition().duration(DUR).delay(i * 80).ease(d3.easeCubicOut).attr("cx", x(r.v)));
          lab.transition().delay(DUR).duration(200).attr("opacity", 1);
        }
        gr.append("rect").attr("class", "hover-target").attr("x", 0).attr("width", w).attr("y", yy).attr("height", rowH).datum(r);
      });
      hoverable(g.selectAll(".hover-target"), r => ({ title: r.name, rows: [{ value: F.int(r.v), label: "people in June 2030" }]
        .concat(r.low != null ? [{ value: `${F.int(r.low)} to ${F.int(r.high || r.v)}`, label: r.high ? "range (our illustration)" : "low case" }] : []) }));
      MBS.ui.keyNav(svg.node(), () => g.selectAll(".hover-target").nodes().map((nd, i) => ({ node: nd, title: rows[i].name, rows: [{ value: F.int(rows[i].v), label: "people" }] })), summary);
      return Promise.all(ts.map(done));
    }
    return { render, table, summary };
  }

  // ================================================================ Q6: homes needed against homes built
  function homesBars(host, d, ctx) {
    const q = d.q6;
    const sc = scened(ctx);
    const rows = q.plans;
    const table = {
      caption: `Homes needed a year for each plan's growth (our estimate, ${q.people_per_home} people per home), against homes built`,
      columns: [{ key: "name", label: "Plan" }, { key: "v", label: "Homes needed a year", num: true },
        { key: "range", label: "Range", num: true, fmt: (v, r) => r.low != null ? `${F.int(r.low)} to ${F.int(r.high != null ? r.high : r.v)}` : "–" }],
      rows: rows.map(r => ({ ...r, range: r.low }))
    };
    table.rows.push({ name: q.built_label, v: q.built }, { name: "Housing Accord target, a year", v: q.accord },
      { name: `Homes short since the ${q.shortfall_from}`, v: q.shortfall });
    const summary = `Bar chart of homes needed a year. ` + rows.map(r => `${r.name}: ${F.int(r.v)}`).join(". ") +
      `. Homes finished last year: ${F.int(q.built)}. Accord target: ${F.int(q.accord)} a year. About ${F.int(q.shortfall)} homes short since 2022.`;
    function render(animate) {
      host.textContent = "";
      legend(host, [{ shape: "rect", cls: "f-focus est", label: "Homes needed a year (our estimate)" },
        { shape: "line", cls: "s-comparison", label: `Finished last year: ${F.k(q.built)}` },
        { shape: "dash", cls: "s-comparison", label: `Accord target: ${F.k(q.accord)}` }]);
      const L = rowsFrame(host, rows.length, { top: 30, right: 24 });
      const { w, h, m, rowH } = L;
      const svg = makeSvg(host, w, h, summary);
      const lo = Math.min(0, d3.min(rows, r => r.low != null ? r.low : r.v));
      const x = d3.scaleLinear().domain([lo, Math.max(q.accord, d3.max(rows, r => r.high || r.v))]).nice().range([m.l + 4, w - m.r]);
      const g = svg.append("g");
      const ticks = x.ticks(w < 520 ? 4 : 6);
      g.append("g").attr("class", "grid").selectAll("line").data(ticks).join("line").attr("x1", x).attr("x2", x).attr("y1", m.t).attr("y2", h - m.b);
      g.append("g").selectAll("text").data(ticks).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - 8).attr("text-anchor", "middle").text(F.short);
      g.append("line").attr("class", "baseline").attr("x1", x(0)).attr("x2", x(0)).attr("y1", m.t).attr("y2", h - m.b);
      const ts = [];
      rows.forEach((r, i) => {
        const yy = m.t + i * rowH;
        const by = yy + 22, bh = 16;
        const lt = g.append("text").attr("x", m.l + 4).attr("y", yy + 15);
        lt.append("tspan").attr("class", r.context ? "lbl-2" : "lbl-strong").text(r.name);
        lt.append("tspan").attr("class", "lbl-2").text(`  ${F.k(r.v)} a year` + (r.low != null && r.high != null ? ` (range ${F.short(r.low)} to ${F.short(r.high)})` : ""));
        const cls = r.context ? "f-context" : r.kind === "illustration" ? "" : "f-focus est";
        const p = g.append("path").attr("class", cls).attr("d", barPath(x(0), x(animate ? 0 : r.v), by, bh));
        if (r.kind === "illustration") p.attr("fill", "url(#hatch-focus)");
        if (animate) ts.push(p.transition().duration(DUR).delay(i * 60).ease(d3.easeCubicOut)
          .attrTween("d", () => t => barPath(x(0), x(r.v * t), by, bh)));
        if (r.low != null && r.high != null) {
          const wg = g.append("g").attr("class", "s-ink").attr("stroke-width", 1.5);
          wg.append("line").attr("x1", x(r.low)).attr("x2", x(r.high)).attr("y1", by + bh / 2).attr("y2", by + bh / 2);
          wg.append("line").attr("x1", x(r.low)).attr("x2", x(r.low)).attr("y1", by + 2).attr("y2", by + bh - 2);
          wg.append("line").attr("x1", x(r.high)).attr("x2", x(r.high)).attr("y1", by + 2).attr("y2", by + bh - 2);
        }
        g.append("rect").attr("class", "hover-target").attr("x", 0).attr("width", w).attr("y", yy).attr("height", rowH).datum(r);
      });
      // benchmarks, labelled at the top
      const gBuilt = g.append("g");
      gBuilt.append("line").attr("class", "s-comparison").attr("stroke-width", 2.5).attr("x1", x(q.built)).attr("x2", x(q.built)).attr("y1", m.t - 10).attr("y2", h - m.b);
      gBuilt.append("text").attr("class", "lbl-strong").attr("x", x(q.built) - 4).attr("y", m.t - 14).attr("text-anchor", "end").text(`Built: ${F.k(q.built)}`);
      const gAccord = g.append("g");
      gAccord.append("line").attr("class", "s-comparison dash").attr("stroke-width", 2).attr("x1", x(q.accord)).attr("x2", x(q.accord)).attr("y1", m.t - 10).attr("y2", h - m.b);
      gAccord.append("text").attr("class", "lbl-2").attr("x", x(q.accord) + 4).attr("y", m.t - 14).attr("text-anchor", x(q.accord) > w - 110 ? "end" : "start").text("Accord target");
      hoverable(g.selectAll(".hover-target"), r => ({ title: r.name, rows: [{ value: F.int(r.v), label: "homes needed a year" }]
        .concat(r.low != null ? [{ value: `${F.int(r.low)} to ${F.int(r.high || r.v)}`, label: r.high != null ? "range (our illustration)" : "low case" }] : [])
        .concat([{ value: F.int(q.built), label: "homes finished last year", color: COL.comparison() }]) }));
      MBS.ui.keyNav(svg.node(), () => g.selectAll(".hover-target").nodes().map((nd, i) => ({ node: nd, title: rows[i].name, rows: [{ value: F.int(rows[i].v), label: "homes needed a year" }] })), summary);
      const callout = el("div", { class: "stat stat-callout" }, el("div", { class: "v", text: `About ${F.k(q.shortfall)}` }),
        el("div", { class: "l", text: `homes short since the ${q.shortfall_from}: the population grew faster than homes were finished` }));
      host.appendChild(el("div", { class: "stat-row" }, callout));
      sc.apply = (scene, anim) => {
        fade(gBuilt, scene !== "plans", anim);
        dim(gAccord, scene === "report" || scene === "shortfall", anim, 0.15);
        callout.style.opacity = scene === "plans" || scene === "built" ? "0.25" : "1";
        callout.classList.toggle("is-hot", scene === "shortfall");
      };
      sc.apply(sc.scene, false);
      return Promise.all(ts.map(done));
    }
    return { render, table, summary, update: s => sc.set(s, true) };
  }

  // ================================================================ Q7 and Q8: 24 job groups, sorted bars
  function sectorBars(host, d, mode, ctx) {
    const q7 = d.q7, q8 = d.q8;
    const sc = scened(ctx);
    const key = mode === "growth" ? "growth_pct" : "short_pct";
    const top = mode === "growth" ? q8.top : q7.top;
    const avg = mode === "growth" ? q8.all_growth_pct : q7.all_short_pct;
    const rows = q7.sectors.map(s => ({ ...s, star: mode !== "growth" && q7.low_assessed.includes(s.id) }));
    const startOrder = rows.slice().sort((a, b) => b.short_pct - a.short_pct).map(r => r.id);
    const endOrder = rows.slice().sort((a, b) => b[key] - a[key]).map(r => r.id);
    const unit = mode === "growth" ? "growth to 2030" : "of jobs short";
    const table = {
      caption: mode === "growth" ? "Projected growth in workers, May 2025 to May 2030, by job group" : "Share of each job group's workers in occupations on the 2025 shortage list",
      columns: [{ key: "name", label: "Job group" }, { key: key, label: mode === "growth" ? "Growth to 2030" : "Jobs short", num: true, fmt: v => mode === "growth" ? F.pct1(v) : F.pct0(v) },
        mode === "growth" ? { key: "short_pct", label: "Jobs short now", num: true, fmt: F.pct0 } : { key: "assessed_pct", label: "Jobs checked", num: true, fmt: F.pct0 },
        { key: "employed", label: "Workers (May 2025)", num: true }],
      rows: endOrder.map(id => rows.find(r => r.id === id))
    };
    table.rows.push({ name: "All jobs", [key]: avg, employed: null, short_pct: q7.all_short_pct, assessed_pct: q7.all_assessed_pct });
    const tops = top.map(id => rows.find(r => r.id === id));
    const summary = `Bar chart of 24 job groups sorted by ${unit}. Highest: ` + tops.map(r => `${r.name} ${mode === "growth" ? F.pct1(r[key]) : F.pct0(r[key])}`).join(", ") + `. All jobs: ${mode === "growth" ? F.pct1(avg) : F.pct0(avg)}.`;
    function render(animate) {
      host.textContent = "";
      if (mode === "growth") legend(host, [{ shape: "rect", cls: "f-focus", label: "Five fastest-growing" }, { shape: "rect", cls: "f-context", label: "Other job groups" },
        { shape: "dot", cls: "f-ink", label: "Most jobs short now" }]);
      const w = widthOf(host);
      const narrow = w < 520;
      const compact = ctx && ctx.compact;
      const fs = narrow ? 12 : 13;
      const labW = d3.max(rows, r => textWidth(r.name + (r.star ? " *" : ""), fs)) + 10;
      const rowH = compact ? 19 : narrow ? 21 : 22, bh = compact ? 12 : 13;
      const m = { t: 24, r: mode === "growth" ? 58 : 44, b: 22, l: labW };
      const h = m.t + rows.length * rowH + m.b;
      const svg = makeSvg(host, w, h, summary);
      const x = d3.scaleLinear().domain([0, mode === "growth" ? Math.max(20, d3.max(rows, r => r[key])) : 100]).range([m.l, w - m.r]);
      const g = svg.append("g");
      const ticks = mode === "growth" ? (narrow ? [0, 10, 20] : x.ticks(5)) : narrow ? [0, 50, 100] : [0, 25, 50, 75, 100];
      g.append("g").attr("class", "grid").selectAll("line").data(ticks).join("line").attr("x1", x).attr("x2", x).attr("y1", m.t).attr("y2", h - m.b);
      g.append("g").selectAll("text").data(ticks).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - 6).attr("text-anchor", "middle").text(v => `${v}%`);
      const yOf = order => id => m.t + order.indexOf(id) * rowH;
      const y0 = yOf(animate && mode === "growth" ? startOrder : endOrder), y1 = yOf(endOrder);
      const isTop = r => top.includes(r.id);
      const rowG = g.selectAll(".row").data(rows, r => r.id).join("g").attr("class", "row").attr("transform", r => `translate(0,${y0(r.id)})`);
      const labels = rowG.append("text").attr("x", m.l - 8).attr("y", bh - 2).attr("text-anchor", "end")
        .style("font-size", fs + "px").text(r => r.name + (r.star ? " *" : ""));
      const bars = rowG.append("path")
        .attr("d", r => barPath(x(0), x(animate && mode !== "growth" ? 0 : r[key]), 0, bh));
      const vals = rowG.filter(isTop).append("text").attr("class", "lbl").attr("x", r => x(r[key]) + 6).attr("y", bh - 2)
        .text(r => mode === "growth" ? F.pct1(r[key]) : F.pct0(r[key]));
      if (mode === "growth") {
        rowG.filter(r => r.short_pct >= q8.short_threshold).append("circle").attr("cx", w - 10).attr("cy", bh / 2).attr("r", 4).attr("class", "f-ink").style("fill", "var(--ink)");
        if (!narrow) g.append("text").attr("class", "lbl-3").attr("x", w - 4).attr("y", m.t - 10).attr("text-anchor", "end").text("Short now");
      }
      rowG.append("rect").attr("class", "hover-target").attr("x", 0).attr("width", w).attr("y", -4).attr("height", rowH);
      g.append("line").attr("class", "s-comparison").attr("stroke-width", 2).attr("x1", x(avg)).attr("x2", x(avg)).attr("y1", m.t - 6).attr("y2", h - m.b);
      g.append("text").attr("class", "lbl-strong").attr("x", x(avg) + (mode === "growth" ? 4 : -4)).attr("y", m.t - 10).attr("text-anchor", mode === "growth" ? "start" : "end")
        .text(`All jobs: ${mode === "growth" ? F.pct1(avg) : F.pct0(avg)}`);
      hoverable(rowG.selectAll(".hover-target"), r => ({ title: r.name, rows: [{ value: mode === "growth" ? F.pct1(r[key]) : F.pct0(r[key]), label: unit },
        { value: F.int(r.employed), label: "workers (May 2025)" }].concat(mode === "growth" ? [{ value: F.pct0(r.short_pct), label: "of jobs short now" }] : [{ value: F.pct0(r.assessed_pct), label: "of jobs checked" }]) }));
      MBS.ui.keyNav(svg.node(), () => endOrder.map(id => {
        const r = rows.find(z => z.id === id);
        return { node: rowG.filter(z => z.id === id).select(".hover-target").node(), title: r.name, rows: [{ value: mode === "growth" ? F.pct1(r[key]) : F.pct0(r[key]), label: unit }] };
      }), summary);
      if (mode !== "growth" && q7.low_assessed.length) {
        host.appendChild(el("p", { class: "chart-note", text: "* Fewer than half of these jobs were checked for shortages." }));
      }
      sc.apply = (scene) => {
        const hi = scene !== "all";
        bars.attr("class", r => (hi && isTop(r)) ? "f-focus" : "f-context");
        labels.attr("class", r => (hi && isTop(r)) ? "lbl-strong" : "lbl-2");
        vals.attr("opacity", hi ? 1 : 0);
      };
      sc.apply(sc.scene);
      if (!animate) return Promise.resolve();
      if (mode === "growth") {
        const t = rowG.transition().delay(250).duration(1100).ease(d3.easeCubicInOut).attr("transform", r => `translate(0,${y1(r.id)})`);
        return done(t);
      }
      const t = bars.transition().duration(DUR).delay((r, i) => i * 12).ease(d3.easeCubicOut).attrTween("d", r => tt => barPath(x(0), x(r[key] * tt), 0, bh));
      return done(t);
    }
    return { render, table, summary, update: s => sc.set(s, true), get scene() { return sc.scene; } };
  }

  // ================================================================ Q9 and Q10: per 100 workers needed
  function perHundred(host, d, mode, ctx) {
    const q = d.q9;
    const sc = scened(ctx);
    const rows = q.rows;
    const isVisa = mode === "visas";
    const key = isVisa ? "visas_per_100" : "trained_per_100";
    const byTrained = rows.slice().sort((a, b) => a.trained_per_100 - b.trained_per_100).map(r => r.id);
    const lit = scene => scene === "low" ? byTrained.slice(0, 2) : scene === "high" ? byTrained.slice(-3) :
      scene === "hi" ? [q.most_visas, q.lowest_trained] : null;
    const table = {
      caption: isVisa ? "Temporary skilled visas granted (2025-26) per 100 workers needed a year" : "People finishing training here each year per 100 workers needed a year (our estimate)",
      columns: [{ key: "name", label: "Job group" }, { key: "trained_per_100", label: "Trained here per 100 needed", num: true },
        { key: "visas_per_100", label: "Skilled visas per 100 needed", num: true }, { key: "need_per_year", label: "Workers needed a year", num: true },
        { key: "measured_share_pct", label: "Need where training is counted", num: true, fmt: F.pct0 }],
      rows
    };
    const summary = `Dot chart for ${rows.length} job groups, ${isVisa ? "skilled visas" : "people trained here"} per 100 workers needed: ` +
      rows.map(r => `${r.name} ${r[key]}`).join(", ") + ". A line marks 100: one for every worker needed.";
    function render(animate) {
      host.textContent = "";
      if (isVisa) legend(host, [{ shape: "dot", cls: "f-focus", label: "Skilled visas" }, { shape: "dot", cls: "f-context", label: "Trained here" }]);
      const w = widthOf(host);
      const narrow = w < 520;
      const fs = narrow ? 12 : 13;
      const labW = d3.max(rows, r => textWidth(r.name, fs)) + 12;
      const rowH = 36;
      const m = { t: 28, r: 30, b: 24, l: labW };
      const h = m.t + rows.length * rowH + m.b;
      const svg = makeSvg(host, w, h, summary);
      const max = d3.max(rows, r => Math.max(r.trained_per_100, r.visas_per_100));
      const x = d3.scaleLinear().domain([0, Math.max(150, max)]).nice().range([m.l, w - m.r]);
      const g = svg.append("g");
      const ticks = narrow ? x.ticks(3) : x.ticks(6);
      g.append("g").attr("class", "grid").selectAll("line").data(ticks).join("line").attr("x1", x).attr("x2", x).attr("y1", m.t).attr("y2", h - m.b);
      g.append("g").selectAll("text").data(ticks).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - 6).attr("text-anchor", "middle").text(v => v);
      g.append("line").attr("class", "s-comparison").attr("stroke-width", 2).attr("x1", x(100)).attr("x2", x(100)).attr("y1", m.t - 8).attr("y2", h - m.b);
      const refTxt = narrow ? "100 = one per worker needed" : "100 = one for every worker needed";
      const tw = textWidth(refTxt, 13);
      g.append("text").attr("class", "lbl-strong").attr("x", Math.max(4, Math.min(w - tw - 6, x(100) - tw / 2))).attr("y", m.t - 12).text(refTxt);
      const ts = [];
      const groups = [];
      rows.forEach((r, i) => {
        const cy = m.t + i * rowH + rowH / 2;
        const gr = g.append("g").attr("data-id", r.id);
        groups.push(gr);
        gr.append("text").attr("class", "lbl-strong").attr("x", m.l - 10).attr("y", cy + 4).attr("text-anchor", "end").style("font-size", fs + "px").text(r.name);
        if (isVisa) gr.append("circle").attr("cx", x(r.trained_per_100)).attr("cy", cy).attr("r", 5).attr("class", "f-context ring");
        const v = r[key];
        const stem = gr.append("line").attr("class", "s-focus").attr("stroke-width", 2).attr("x1", x(0)).attr("y1", cy).attr("y2", cy).attr("x2", animate ? x(0) : x(v)).attr("stroke-opacity", .45);
        const c = gr.append("circle").attr("cy", cy).attr("r", 6.5).attr("class", "f-focus ring").attr("cx", animate ? x(0) : x(v));
        const lx = x(v) + 10;
        const lab = gr.append("text").attr("class", "lbl-strong").attr("y", cy + 4).attr("x", lx).text(v).attr("opacity", animate ? 0 : 1);
        if (isVisa && Math.abs(x(r.trained_per_100) - lx) < 22 && r.trained_per_100 > v) lab.attr("x", x(v) - 10).attr("text-anchor", "end");
        if (animate) {
          ts.push(c.transition().duration(DUR).delay(i * 60).ease(d3.easeCubicOut).attr("cx", x(v)));
          stem.transition().duration(DUR).delay(i * 60).ease(d3.easeCubicOut).attr("x2", x(v));
          lab.transition().delay(DUR + i * 60).duration(200).attr("opacity", 1);
        }
        gr.append("rect").attr("class", "hover-target").attr("x", 0).attr("width", w).attr("y", cy - rowH / 2).attr("height", rowH).datum(r);
      });
      hoverable(g.selectAll(".hover-target"), r => ({ title: r.name, rows: [
        { value: String(r.visas_per_100), label: "skilled visas per 100 needed", color: isVisa ? COL.focus() : null },
        { value: String(r.trained_per_100), label: "trained here per 100 needed", color: isVisa ? COL.context() : COL.focus() },
        { value: F.int(r.need_per_year), label: "workers needed a year" }] }));
      MBS.ui.keyNav(svg.node(), () => g.selectAll(".hover-target").nodes().map((nd, i) => ({ node: nd, title: rows[i].name, rows: [{ value: String(rows[i][key]), label: "per 100 workers needed" }] })), summary);
      sc.apply = (scene, anim) => {
        const ids = lit(scene);
        groups.forEach(gr => dim(gr, !ids || ids.includes(gr.attr("data-id")), anim, 0.3));
      };
      sc.apply(sc.scene, false);
      return Promise.all(ts.map(done));
    }
    return { render, table, summary, update: s => sc.set(s, true) };
  }

  // ================================================================ Q11: in work, out of 100
  function outcomes(host, d, ctx) {
    const q = d.q11;
    const sc = scened(ctx);
    const rows = q.rows;
    const cls = { focus: "f-focus", comparison: "f-comparison", context: "f-context" };
    const table = {
      caption: `People aged ${q.ages} with a job, out of 100 (${q.period})`,
      columns: [{ key: "label", label: "Group" }, { key: "pct", label: "With a job, out of 100", num: true, fmt: F.one },
        { key: "participation_pct", label: "Working or looking, out of 100", num: true, fmt: F.one }, { key: "unemployment_pct", label: "Unemployment rate", num: true, fmt: F.pct1 }],
      rows
    };
    const summary = "Bar chart, out of 100 people aged 15 to 64 with a job: " + rows.map(r => `${r.label} ${F.one(r.pct)}`).join(", ") + ".";
    function render(animate) {
      host.textContent = "";
      const L = rowsFrame(host, rows.length, { top: 8, right: 70, rowH: 52 });
      const { w, h, m, rowH } = L;
      const svg = makeSvg(host, w, h, summary);
      const x = d3.scaleLinear().domain([0, 100]).range([m.l + 4, w - m.r]);
      const g = svg.append("g");
      const ts = [];
      const groups = [];
      rows.forEach((r, i) => {
        const yy = m.t + i * rowH, by = yy + 22, bh = 18;
        const gr = g.append("g").attr("data-key", r.key);
        groups.push(gr);
        gr.append("text").attr("class", r.role === "context" ? "lbl-2" : "lbl-strong").attr("x", m.l + 4).attr("y", yy + 15).text(r.label);
        gr.append("rect").attr("class", "track").attr("x", x(0)).attr("width", x(100) - x(0)).attr("y", by).attr("height", bh).attr("rx", 4);
        const p = gr.append("path").attr("class", cls[r.role]).attr("d", barPath(x(0), x(animate ? 0 : r.pct), by, bh));
        if (animate) ts.push(p.transition().duration(DUR).delay(i * 80).ease(d3.easeCubicOut).attrTween("d", () => t => barPath(x(0), x(r.pct * t), by, bh)));
        gr.append("text").attr("class", "lbl-strong").attr("x", x(100) + 8).attr("y", by + 13).text(`${Math.round(r.pct)} in 100`);
        gr.append("rect").attr("class", "hover-target").attr("x", 0).attr("width", w).attr("y", yy).attr("height", rowH).datum(r);
      });
      g.append("text").attr("class", "tick-label").attr("x", x(0)).attr("y", h - 8).text("0");
      g.append("text").attr("class", "tick-label").attr("x", x(100)).attr("y", h - 8).attr("text-anchor", "end").text("100");
      hoverable(g.selectAll(".hover-target"), r => ({ title: r.label, rows: [{ value: `${F.one(r.pct)} in 100`, label: "have a job" },
        { value: F.pct1(r.unemployment_pct), label: "unemployment rate" }] }));
      MBS.ui.keyNav(svg.node(), () => g.selectAll(".hover-target").nodes().map((nd, i) => ({ node: nd, title: rows[i].label, rows: [{ value: `${F.one(rows[i].pct)} in 100`, label: "have a job" }] })), summary);
      sc.apply = (scene, anim) => {
        const keep = scene === "top" ? ["skilled", "everyone"] : scene === "others" ? ["family", "humanitarian"] : null;
        groups.forEach(gr => dim(gr, !keep || keep.includes(gr.attr("data-key")), anim, 0.3));
      };
      sc.apply(sc.scene, false);
      return Promise.all(ts.map(done));
    }
    return { render, table, summary, update: s => sc.set(s, true) };
  }

  // ================================================================ Q12: state tiles
  function stateTiles(host, d, ctx) {
    const q = d.q12;
    const states = q.states.filter(s => s.code !== "AUS");
    const aus = q.states.find(s => s.code === "AUS");
    const max = states.reduce((a, b) => (b.people_per_home > a.people_per_home ? b : a));
    const codeOf = s => s === "max" ? max.code : s === "all" || s === "report" ? "AUS" : s;
    let sel = codeOf((ctx && (ctx.state || ctx.scene)) || "AUS");
    const lo = 1, hi = 4;
    const tcol = v => d3.interpolateViridis(1 - Math.max(0, Math.min(1, (v - lo) / (hi - lo))));
    const table = {
      caption: `People added for each new home finished, ${q.period_label}`,
      columns: [{ key: "name", label: "State or territory" }, { key: "people_per_home", label: "People added per new home", num: true, fmt: v => v.toFixed(2) },
        { key: "growth", label: "Population growth", num: true }, { key: "homes", label: "New homes finished", num: true }],
      rows: q.states.slice().sort((a, b) => b.people_per_home - a.people_per_home)
    };
    const summary = `Map of equal tiles, one per state and territory, coloured by people added per new home finished. Australia: ${aus.people_per_home.toFixed(2)}. ` +
      states.slice().sort((a, b) => b.people_per_home - a.people_per_home).map(s => `${s.name} ${s.people_per_home.toFixed(2)}`).join(", ") + ".";
    let api = {};
    function render() {
      host.textContent = "";
      const w = widthOf(host);
      const tile = Math.min(84, (w - 20) / 4.3);
      const gapT = 6;
      const gw = 4 * tile + 3 * gapT;
      const h = 4 * tile + 3 * gapT + 64;
      const svg = makeSvg(host, w, h, summary);
      const ox = (w - gw) / 2;
      const g = svg.append("g").attr("transform", `translate(${ox},0)`);
      const tiles = g.selectAll(".tile").data(states, s => s.code).join("g").attr("class", "tile")
        .attr("transform", s => `translate(${q.tiles[s.code][0] * (tile + gapT)},${q.tiles[s.code][1] * (tile + gapT)})`)
        .attr("tabindex", 0).attr("role", "button").attr("aria-label", s => `${s.name}: ${s.people_per_home.toFixed(1)} people added per new home. Select`)
        .style("cursor", "pointer");
      tiles.append("rect").attr("width", tile).attr("height", tile).attr("rx", 8).attr("fill", s => tcol(s.people_per_home));
      tiles.append("text").attr("x", 9).attr("y", 20).style("font-weight", 700).style("font-size", "13px")
        .style("fill", s => lum(tcol(s.people_per_home)) > 0.3 ? "#0b0b0b" : "#ffffff").text(s => s.code);
      tiles.append("text").attr("x", 9).attr("y", tile - 10).style("font-size", tile > 70 ? "20px" : "17px").style("font-weight", 650)
        .style("fill", s => lum(tcol(s.people_per_home)) > 0.3 ? "#0b0b0b" : "#ffffff").text(s => s.people_per_home.toFixed(1));
      const ring = g.append("rect").attr("class", "kbd-hi").attr("rx", 10).attr("width", tile + 8).attr("height", tile + 8).style("stroke-width", 3).attr("opacity", 0);
      const ly = 4 * tile + 3 * gapT + 22;
      const lw = Math.min(gw, 300), lx0 = (gw - lw) / 2;
      const gid = nextId("grad");
      const grad = svg.append("defs").append("linearGradient").attr("id", gid);
      d3.range(0, 1.01, 0.1).forEach(t => grad.append("stop").attr("offset", `${t * 100}%`).attr("stop-color", tcol(lo + t * (hi - lo))));
      const lg = g.append("g").attr("transform", `translate(${lx0},${ly})`);
      lg.append("rect").attr("width", lw).attr("height", 10).attr("rx", 3).attr("fill", `url(#${gid})`);
      const sx = d3.scaleLinear().domain([lo, hi]).range([0, lw]);
      [1, 2, 3, 4].forEach(v => lg.append("text").attr("class", "tick-label").attr("x", sx(v)).attr("y", 24).attr("text-anchor", "middle").text(v === 4 ? "4+" : v));
      lg.append("line").attr("x1", sx(q.household)).attr("x2", sx(q.household)).attr("y1", -4).attr("y2", 14).attr("stroke", "var(--ink)").attr("stroke-width", 2);
      lg.append("text").attr("class", "lbl-3").attr("x", sx(q.household)).attr("y", -8).attr("text-anchor", "middle").text(`${q.household} = average home`);
      lg.append("text").attr("class", "lbl-3").attr("x", lw / 2).attr("y", 38).attr("text-anchor", "middle").text("people added for each new home finished");
      function choose(code) {
        sel = code;
        const s = states.find(z => z.code === code);
        if (s) {
          ring.attr("opacity", 1).attr("x", q.tiles[code][0] * (tile + gapT) - 4).attr("y", q.tiles[code][1] * (tile + gapT) - 4);
        } else ring.attr("opacity", 0);
        tiles.attr("aria-pressed", z => String(z.code === code));
        if (ctx && ctx.onSelect) ctx.onSelect(code);
      }
      api.choose = choose;
      tiles.on("click", (ev, s) => choose(s.code)).on("keydown", (ev, s) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); choose(s.code); } });
      hoverable(tiles, s => ({ title: s.name, rows: [{ value: s.people_per_home.toFixed(2), label: "people added per new home" },
        { value: F.int(s.growth), label: "population growth" }, { value: F.int(s.homes), label: "new homes finished" }] }));
      if (sel !== "AUS") choose(sel); else ring.attr("opacity", 0);
      return Promise.resolve();
    }
    function update(s) { sel = codeOf(s); if (api.choose) api.choose(sel); }
    return { render, table, summary, update, get state() { return sel; } };
  }

  // ================================================================ Q13: four claim cards
  const VERDICT_LEVEL = { "Accurate": 4, "Mostly accurate": 3, "Partly accurate": 2, "Inaccurate": 1 };
  function claimCard(c) {
    const lvl = VERDICT_LEVEL[c.verdict];
    const meter = lvl ? el("span", { class: "meter", "aria-hidden": "true" }, [1, 2, 3, 4].map(i => el("i", { class: i <= lvl ? "on" : null }))) : null;
    const date = new Date(c.date + "T00:00:00");
    const when = isNaN(date) ? c.date : date.toLocaleDateString("en-AU", { day: "numeric", month: "long", year: "numeric" });
    return el("article", { class: "card" },
      el("p", { class: "side", text: c.side }),
      el("blockquote", { text: `“${c.claim}”` }),
      el("p", { class: "who" }, `${c.speaker}, ${when}. `, el("a", { href: c.url, target: "_blank", rel: "noopener", text: "Source" })),
      el("div", { class: "verdict" }, meter, c.verdict),
      el("details", null, el("summary", { text: "What the data shows" }), el("p", { text: c.shows }), c.caveat ? el("p", { text: `Note: ${c.caveat}` }) : null));
  }
  function claims(host, d) {
    const q = d.q13;
    const cards = q.featured.map(id => q.cards.find(c => c.id === id));
    const table = {
      caption: "The four claims shown, one per party",
      columns: [{ key: "side", label: "Party" }, { key: "speaker", label: "Who" }, { key: "claim", label: "Claim" }, { key: "verdict", label: "Verdict" }],
      rows: cards
    };
    const summary = `Four claim cards. ` + cards.map(c => `${c.side}, ${c.speaker}: ${c.verdict}`).join(". ") + ".";
    function render() {
      host.textContent = "";
      host.setAttribute("role", "group");
      host.setAttribute("aria-label", summary);
      host.classList.add("cards-host");
      host.appendChild(el("div", { class: "cards" }, cards.map(claimCard)));
      return Promise.resolve();
    }
    return { render, table, summary };
  }

  MBS.charts = Object.assign(MBS.charts || {}, {
    mcg, nomLine, waffle, netByVisa, planLines, popDots, homesBars,
    sectorShort: (h, d, ctx) => sectorBars(h, d, "short", ctx), sectorGrowth: (h, d, ctx) => sectorBars(h, d, "growth", ctx),
    trained: (h, d, ctx) => perHundred(h, d, "trained", ctx), visas: (h, d, ctx) => perHundred(h, d, "visas", ctx),
    outcomes, stateTiles, claims, claimCard
  });
})();
