/* Migration by Skill: charts for the report and the Models appendix. Same contract as charts.js:
   each returns {render(animate) -> Promise, table, summary}. The Models charts take MBS.explore.models (m). */
(function () {
  "use strict";
  const MBS = (window.MBS = window.MBS || {});
  const { el, textWidth } = MBS.util;
  const F = MBS.fmt;
  const H = MBS.chartHelpers;
  const { barPath, widthOf, makeSvg, hoverable, legend, done, COL } = H;
  const DUR = 850;

  // ================================================================ net overseas migration by state
  function nomByState(host, d) {
    const q = d.q12;
    const aus = q.states.find(s => s.code === "AUS");
    const rows = q.states.filter(s => s.code !== "AUS").map(s => ({ ...s, share: 100 * s.nom / aus.nom, popShare: 100 * s.population / aus.population }))
      .sort((a, b) => b.nom - a.nom);
    const top2 = rows.slice(0, 2).map(r => r.code);
    const table = {
      caption: `Net overseas migration by state and territory, ${q.period_label}`,
      columns: [{ key: "name", label: "State or territory" }, { key: "nom", label: "Net overseas migration", num: true },
        { key: "share", label: "Share of Australia's", num: true, fmt: F.pct1 }, { key: "popShare", label: "Share of population", num: true, fmt: F.pct1 }],
      rows: rows.concat([{ name: "Australia", nom: aus.nom, share: 100, popShare: 100 }])
    };
    const summary = "Bar chart of each state's share of net overseas migration, with its share of the population: " +
      rows.map(r => `${r.name} ${F.pct0(r.share)} of migration, ${F.pct0(r.popShare)} of people`).join("; ") + ".";
    function render(animate) {
      host.textContent = "";
      legend(host, [{ shape: "rect", cls: "f-focus", label: "Share of net overseas migration" }, { shape: "line", cls: "s-ink", label: "Share of Australia's population" }]);
      const w = widthOf(host);
      const narrow = w < 560;
      const labW = narrow ? 44 : d3.max(rows, r => textWidth(r.name, 13)) + 12;
      const rowH = 30, bh = 16;
      const m = { t: 6, r: narrow ? 92 : 190, b: 22, l: labW };
      const h = m.t + rows.length * rowH + m.b;
      const svg = makeSvg(host, w, h, summary);
      const x = d3.scaleLinear().domain([0, Math.max(35, d3.max(rows, r => Math.max(r.share, r.popShare)))]).nice().range([m.l, w - m.r]);
      const g = svg.append("g");
      const ticks = x.ticks(narrow ? 3 : 5);
      g.append("g").attr("class", "grid").selectAll("line").data(ticks).join("line").attr("x1", x).attr("x2", x).attr("y1", m.t).attr("y2", h - m.b);
      g.append("g").selectAll("text").data(ticks).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - 6).attr("text-anchor", "middle").text(v => `${v}%`);
      const ts = [];
      rows.forEach((r, i) => {
        const yy = m.t + i * rowH;
        const gr = g.append("g");
        const strong = top2.includes(r.code);
        gr.append("text").attr("class", strong ? "lbl-strong" : "lbl-2").attr("x", m.l - 8).attr("y", yy + bh - 2).attr("text-anchor", "end").text(narrow ? r.code : r.name);
        const p = gr.append("path").attr("class", strong ? "f-focus" : "f-context").attr("d", barPath(x(0), x(animate ? 0 : r.share), yy, bh));
        if (animate) ts.push(p.transition().duration(DUR).delay(i * 50).ease(d3.easeCubicOut).attrTween("d", () => t => barPath(x(0), x(r.share * t), yy, bh)));
        gr.append("line").attr("class", "s-ink").attr("stroke-width", 2.5).attr("x1", x(r.popShare)).attr("x2", x(r.popShare)).attr("y1", yy - 3).attr("y2", yy + bh + 3);
        gr.append("text").attr("class", strong ? "lbl-strong" : "lbl").attr("x", x(Math.max(r.share, r.popShare)) + 8).attr("y", yy + bh - 2)
          .text(narrow ? F.pct0(r.share) : `${F.int(r.nom)} (${F.pct0(r.share)})`);
        gr.append("rect").attr("class", "hover-target").attr("x", 0).attr("width", w).attr("y", yy - 6).attr("height", rowH).datum(r);
      });
      hoverable(g.selectAll(".hover-target"), r => ({ title: r.name, rows: [{ value: F.int(r.nom), label: "net overseas migration" },
        { value: F.pct1(r.share), label: "of Australia's net overseas migration", color: COL.focus() }, { value: F.pct1(r.popShare), label: "of Australia's population" }] }));
      MBS.ui.keyNav(svg.node(), () => g.selectAll(".hover-target").nodes().map((nd, i) => ({ node: nd, title: rows[i].name,
        rows: [{ value: F.pct1(rows[i].share), label: "of net overseas migration" }, { value: F.pct1(rows[i].popShare), label: "of the population" }] })), summary);
      return Promise.all(ts.map(done));
    }
    return { render, table, summary };
  }

  // ================================================================ claim verdicts by side (stacked)
  const VERDICTS = ["Accurate", "Mostly accurate", "Partly accurate", "Inaccurate", "Too early to tell", "Plan (what it implies)", "Can't test with our data"];
  const VCLS = ["v1", "v2", "v3", "v4", "v6", "v7", "v5"];
  const SIDES = ["Labor", "Coalition", "One Nation", "Greens", "Business", "Union"];
  function verdictsBySide(host, d, ctx) {
    const q = d.q13;
    const sides = SIDES.filter(s => q.counts_by_side[s]).concat(Object.keys(q.counts_by_side).filter(s => !SIDES.includes(s)));
    const present = VERDICTS.filter(v => sides.some(s => q.counts_by_side[s][v]));
    const rows = sides.map(s => ({ side: s, total: Object.values(q.counts_by_side[s]).reduce((a, b) => a + b, 0), ...q.counts_by_side[s] }));
    const table = {
      caption: "Claims checked, by side and verdict",
      columns: [{ key: "side", label: "Side" }, ...present.map(v => ({ key: v, label: v, num: true, fmt: x => x == null ? "0" : String(x) })), { key: "total", label: "Total", num: true }],
      rows
    };
    const summary = "Stacked bars of claim verdicts for each side: " + rows.map(r => `${r.side}: ${present.filter(v => r[v]).map(v => `${r[v]} ${v.toLowerCase()}`).join(", ")}`).join(". ") + ".";
    function render(animate) {
      host.textContent = "";
      const lg = el("div", { class: "chart-legend", "aria-hidden": "true" });
      present.forEach(v => lg.appendChild(el("span", { class: "key" }, el("span", { class: `sw ${VCLS[VERDICTS.indexOf(v)]}` }), v)));
      host.appendChild(lg);
      const w = widthOf(host);
      const labW = d3.max(rows, r => textWidth(r.side, 13)) + 12;
      const rowH = ctx && ctx.minH ? Math.max(36, Math.floor((ctx.minH - 60) / rows.length)) : 36, bh = Math.min(30, Math.round(rowH * 0.6));
      const m = { t: 6, r: 28, b: 22, l: labW };
      const h = m.t + rows.length * rowH + m.b;
      const svg = makeSvg(host, w, h, summary);
      const max = d3.max(rows, r => r.total);
      const x = d3.scaleLinear().domain([0, max]).range([m.l, w - m.r]);
      const g = svg.append("g");
      g.append("g").attr("class", "grid").selectAll("line").data(d3.range(0, max + 1)).join("line").attr("x1", x).attr("x2", x).attr("y1", m.t).attr("y2", h - m.b);
      g.append("g").selectAll("text").data(d3.range(0, max + 1)).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - 6).attr("text-anchor", "middle").text(v => v);
      const segs = [];
      rows.forEach((r, i) => {
        const yy = m.t + i * rowH;
        g.append("text").attr("class", "lbl-strong").attr("x", m.l - 8).attr("y", yy + bh / 2 + 4).attr("text-anchor", "end").text(r.side);
        let acc = 0;
        present.forEach(v => {
          const n = r[v] || 0;
          if (!n) return;
          const x0 = x(acc), x1 = x(acc + n);
          const cls = VCLS[VERDICTS.indexOf(v)];
          const seg = g.append("rect").attr("class", `vseg ${cls}`).attr("x", x0 + 1).attr("y", yy).attr("width", Math.max(0, x1 - x0 - 2)).attr("height", bh).attr("rx", 3)
            .datum({ side: r.side, v, n });
          if (animate) seg.attr("opacity", 0).transition().delay(i * 60).duration(400).attr("opacity", 1);
          segs.push(seg);
          if (x1 - x0 > 18) g.append("text").attr("class", `vlab ${cls}-ink`).attr("x", (x0 + x1) / 2).attr("y", yy + bh / 2 + 4).attr("text-anchor", "middle").text(n);
          acc += n;
        });
      });
      hoverable(g.selectAll(".vseg"), s => ({ title: s.side, rows: [{ value: String(s.n), label: s.v.toLowerCase() }] }));
      MBS.ui.keyNav(svg.node(), () => g.selectAll(".vseg").nodes().map(nd => { const s = d3.select(nd).datum(); return { node: nd, title: s.side, rows: [{ value: String(s.n), label: s.v }] }; }), summary);
      return Promise.resolve();
    }
    return { render, table, summary };
  }

  // ================================================================ Models A1: visas per 1,000 workers, short vs not
  function visaRates(host, d, ctx) {
    const a = ctx.m.a1;
    const rows = [
      { label: "On the shortage list", mean: a.visas_per_1000_workers_short, median: a.median_visas_per_1000_short, cls: "f-focus" },
      { label: "Not on the list", mean: a.visas_per_1000_workers_not_short, median: a.median_visas_per_1000_not_short, cls: "f-context" }];
    const table = { caption: "Temporary skilled visas granted 2025-26 per 1,000 workers",
      columns: [{ key: "label", label: "Occupations" }, { key: "mean", label: "All visas ÷ all workers", num: true, fmt: v => v.toFixed(2) }, { key: "median", label: "Typical occupation (median)", num: true, fmt: v => v.toFixed(2) }], rows };
    const summary = `Bars: ${a.visas_per_1000_workers_short} visas per 1,000 workers in short occupations against ${a.visas_per_1000_workers_not_short} in others. Medians ${a.median_visas_per_1000_short} and ${a.median_visas_per_1000_not_short}.`;
    function render(animate) {
      host.textContent = "";
      legend(host, [{ shape: "rect", cls: "f-focus", label: "All visas ÷ all workers" }, { shape: "dot", cls: "f-ink", label: "Typical occupation (median)" }]);
      const w = widthOf(host);
      const rowH = 64, bh = 26;
      const m = { t: 8, r: 52, b: 24, l: 8 };
      const h = m.t + rows.length * rowH + m.b;
      const svg = makeSvg(host, w, h, summary);
      const x = d3.scaleLinear().domain([0, Math.ceil(d3.max(rows, r => r.mean) + 1)]).range([m.l, w - m.r]);
      const g = svg.append("g");
      const ts = [];
      rows.forEach((r, i) => {
        const yy = m.t + i * rowH;
        g.append("text").attr("class", "lbl-strong").attr("x", m.l).attr("y", yy + 14).text(r.label);
        const p = g.append("path").attr("class", r.cls).attr("d", barPath(x(0), x(animate ? 0 : r.mean), yy + 22, bh));
        if (animate) ts.push(p.transition().duration(DUR).ease(d3.easeCubicOut).attrTween("d", () => t => barPath(x(0), x(r.mean * t), yy + 22, bh)));
        g.append("circle").attr("cx", x(r.median)).attr("cy", yy + 22 + bh / 2).attr("r", 5).attr("class", "f-ink ring");
        g.append("text").attr("class", "lbl-strong").attr("x", x(r.mean) + 8).attr("y", yy + 22 + bh / 2 + 5).style("font-size", "18px").text(r.mean.toFixed(1));
        g.append("rect").attr("class", "hover-target").attr("x", 0).attr("width", w).attr("y", yy).attr("height", rowH).datum(r);
      });
      g.append("g").selectAll("text").data(x.ticks(4)).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - 6).attr("text-anchor", "middle").text(v => v);
      hoverable(g.selectAll(".hover-target"), r => ({ title: r.label, rows: [{ value: r.mean.toFixed(2), label: "visas per 1,000 workers (all)" }, { value: r.median.toFixed(2), label: "typical occupation (median)" }] }));
      MBS.ui.keyNav(svg.node(), () => g.selectAll(".hover-target").nodes().map((nd, i) => ({ node: nd, title: rows[i].label, rows: [{ value: rows[i].mean.toFixed(2), label: "per 1,000 workers" }] })), summary);
      return Promise.all(ts.map(done));
    }
    return { render, table, summary };
  }

  // ================================================================ Models A2: share of visas vs share of workers
  function visaShares(host, d, ctx) {
    const a = ctx.m.a1;
    const rows = [{ label: "Share of temporary skilled visas", v: a.share_of_visas_to_short_occupations_pct, cls: "f-focus" },
      { label: "Share of workers", v: a.share_of_workers_in_short_occupations_pct, cls: "f-context" }];
    const table = { caption: "Occupations on the 2025 shortage list: share of visas and of workers", columns: [{ key: "label", label: "Measure" }, { key: "v", label: "Short occupations' share", num: true, fmt: F.pct1 }], rows };
    const summary = `${a.share_of_visas_to_short_occupations_pct}% of visas went to short occupations, which hold ${a.share_of_workers_in_short_occupations_pct}% of workers.`;
    function render(animate) {
      host.textContent = "";
      const w = widthOf(host);
      const rowH = 70, bh = 28;
      const m = { t: 6, r: 12, b: 24, l: 8 };
      const h = m.t + rows.length * rowH + m.b;
      const svg = makeSvg(host, w, h, summary);
      const x = d3.scaleLinear().domain([0, 100]).range([m.l, w - m.r]);
      const g = svg.append("g");
      const ts = [];
      rows.forEach((r, i) => {
        const yy = m.t + i * rowH;
        g.append("text").attr("class", "lbl-strong").attr("x", m.l).attr("y", yy + 14).text(r.label);
        g.append("rect").attr("class", "track").attr("x", x(0)).attr("width", x(100) - x(0)).attr("y", yy + 22).attr("height", bh).attr("rx", 4);
        const p = g.append("path").attr("class", r.cls).attr("d", barPath(x(0), x(animate ? 0 : r.v), yy + 22, bh));
        if (animate) ts.push(p.transition().duration(DUR).ease(d3.easeCubicOut).attrTween("d", () => t => barPath(x(0), x(r.v * t), yy + 22, bh)));
        g.append("text").attr("class", "lbl-strong").attr("x", x(r.v) + 8).attr("y", yy + 22 + bh / 2 + 6).attr("text-anchor", "start").style("font-size", "18px").text(F.pct0(r.v));
      });
      [0, 50, 100].forEach(v => g.append("text").attr("class", "tick-label").attr("x", x(v)).attr("y", h - 6).attr("text-anchor", v === 0 ? "start" : v === 100 ? "end" : "middle").text(`${v}%`));
      return Promise.all(ts.map(done));
    }
    return { render, table, summary };
  }

  // ================================================================ Models A3: every occupation
  function a1Scatter(host, d, ctx) {
    const R = ctx.m.a1_rows;
    const rows = R.rows.map(r => Object.fromEntries(R.columns.map((c, i) => [c, r[i]])));
    const table = { caption: `Temporary skilled visas per 1,000 workers and projected growth, ${rows.length} occupations`,
      columns: [{ key: "name", label: "Occupation" }, { key: "short", label: "On the shortage list", fmt: v => v ? "Yes" : "No" },
        { key: "growth", label: "Growth to 2030", num: true, fmt: F.pct1 }, { key: "per1000", label: "Visas per 1,000 workers", num: true, fmt: v => v.toFixed(2) },
        { key: "grants", label: "Visas granted", num: true }, { key: "employed", label: "Workers", num: true }],
      rows: rows.slice().sort((a, b) => b.per1000 - a.per1000) };
    const summary = `Scatter of ${rows.length} occupations: projected growth against visas per 1,000 workers. Occupations on the shortage list sit higher on average.`;
    function render(animate) {
      host.textContent = "";
      legend(host, [{ shape: "dot", cls: "f-focus", label: "On the shortage list" }, { shape: "dot", cls: "f-context", label: "Not on the list" }]);
      const w = widthOf(host);
      const h = Math.round(Math.min(360, Math.max(260, w * 0.62)));
      const m = { t: 26, r: 14, b: 34, l: 40 };
      const svg = makeSvg(host, w, h, summary);
      const gx = d3.extent(rows, r => r.growth);
      const x = d3.scaleLinear().domain([Math.min(-10, gx[0]), Math.max(30, gx[1])]).nice().range([m.l, w - m.r]);
      const y = d3.scaleLog().domain([1, d3.max(rows, r => r.per1000 + 1) * 1.1]).range([h - m.b, m.t]);
      const g = svg.append("g");
      const yt = [0, 1, 3, 10, 30, 100].filter(v => v + 1 <= y.domain()[1]);
      g.append("g").attr("class", "grid").selectAll("line").data(yt).join("line").attr("x1", m.l).attr("x2", w - m.r).attr("y1", v => y(v + 1)).attr("y2", v => y(v + 1));
      g.append("g").selectAll("text").data(yt).join("text").attr("class", "tick-label").attr("x", m.l - 6).attr("y", v => y(v + 1) + 4).attr("text-anchor", "end").text(v => v);
      const xt = x.ticks(5);
      g.append("g").attr("class", "grid").selectAll("line").data(xt).join("line").attr("x1", x).attr("x2", x).attr("y1", m.t).attr("y2", h - m.b);
      g.append("g").selectAll("text").data(xt).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - m.b + 16).attr("text-anchor", "middle").text(v => `${v}%`);
      g.append("text").attr("class", "lbl-3").attr("x", w - m.r).attr("y", h - 4).attr("text-anchor", "end").text("Projected growth in workers to 2030 →");
      g.append("text").attr("class", "lbl-3").attr("x", 2).attr("y", 12).text("Visas per 1,000 workers (log scale) ↑");
      const dots = g.append("g").selectAll("circle").data(rows.slice().sort((a, b) => a.short - b.short)).join("circle")
        .attr("cx", r => x(r.growth)).attr("cy", r => y(r.per1000 + 1)).attr("r", 4)
        .attr("class", r => (r.short ? "f-focus" : "f-context") + " ring dot-a1").attr("opacity", animate ? 0 : 0.85);
      if (animate) dots.transition().delay((r, i) => i * 2).duration(300).attr("opacity", 0.85);
      hoverable(dots, r => ({ title: r.name, rows: [{ value: r.per1000.toFixed(1), label: "visas per 1,000 workers" }, { value: F.pct1(r.growth), label: "growth to 2030" },
        { value: r.short ? "Yes" : "No", label: "on the shortage list" }] }));
      const top = rows.slice().sort((a, b) => b.per1000 - a.per1000).slice(0, 25);
      MBS.ui.keyNav(svg.node(), () => top.map(r => ({ node: dots.filter(z => z === r).node(), title: r.name, rows: [{ value: r.per1000.toFixed(1), label: "visas per 1,000 workers" }] })), summary);
      return Promise.resolve();
    }
    return { render, table, summary };
  }

  // ================================================================ Models A4: regression coefficients
  const TERM = { short_now: "On the shortage list", growth_5y_pct: "Growth to 2030 (per point)", skill_2: "Skill level 2 (vs 1)", skill_3: "Skill level 3 (vs 1)", skill_4: "Skill level 4 (vs 1)", skill_5: "Skill level 5 (vs 1)" };
  function coefPlot(host, d, ctx) {
    const reg = ctx.m.a1.regression;
    const rows = reg.terms.filter(t => t.term !== "intercept").map(t => ({ ...t, label: TERM[t.term] || t.term, pct: 100 * (Math.exp(t.coef) - 1) }));
    const table = { caption: `Regression of ${reg.outcome}, ${reg.standard_errors} standard errors, n = ${reg.n}, R² = ${reg.r2}`,
      columns: [{ key: "label", label: "Term" }, { key: "coef", label: "Coefficient", num: true, fmt: v => v.toFixed(3) }, { key: "ci95_low", label: "95% CI low", num: true, fmt: v => v.toFixed(3) },
        { key: "ci95_high", label: "95% CI high", num: true, fmt: v => v.toFixed(3) }, { key: "pct", label: "Effect", num: true, fmt: v => F.signed(Math.round(v)) + "%" }, { key: "p_approx", label: "p (approx.)", num: true, fmt: v => String(v) }],
      rows };
    const summary = "Coefficient plot: " + rows.map(r => `${r.label} ${r.coef.toFixed(2)} (95% CI ${r.ci95_low.toFixed(2)} to ${r.ci95_high.toFixed(2)})`).join("; ") + ".";
    function render() {
      host.textContent = "";
      const w = widthOf(host);
      const narrow = w < 520;
      const labW = d3.max(rows, r => textWidth(r.label, 13)) + 14;
      const rowH = 34;
      const m = { t: 22, r: narrow ? 56 : 84, b: 28, l: labW };
      const h = m.t + rows.length * rowH + m.b;
      const svg = makeSvg(host, w, h, summary);
      const lo = d3.min(rows, r => r.ci95_low), hi = d3.max(rows, r => r.ci95_high);
      const x = d3.scaleLinear().domain([Math.min(-0.2, lo) - 0.1, Math.max(0.2, hi) + 0.1]).nice().range([m.l, w - m.r]);
      const g = svg.append("g");
      const ticks = x.ticks(narrow ? 4 : 6);
      g.append("g").attr("class", "grid").selectAll("line").data(ticks).join("line").attr("x1", x).attr("x2", x).attr("y1", m.t).attr("y2", h - m.b);
      g.append("g").selectAll("text").data(ticks).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - m.b + 16).attr("text-anchor", "middle").text(v => v.toFixed(1));
      g.append("line").attr("class", "baseline").attr("x1", x(0)).attr("x2", x(0)).attr("y1", m.t - 8).attr("y2", h - m.b);
      g.append("text").attr("class", "lbl-3").attr("x", x(0) + 4).attr("y", m.t - 10).text("0 = no effect");
      rows.forEach((r, i) => {
        const cy = m.t + i * rowH + rowH / 2;
        const clear = r.ci95_low > 0 || r.ci95_high < 0;
        const focus = r.term === "short_now";
        g.append("text").attr("class", focus ? "lbl-strong" : "lbl-2").attr("x", m.l - 10).attr("y", cy + 4).attr("text-anchor", "end").text(r.label);
        g.append("line").attr("class", focus ? "s-focus" : "s-ink").attr("stroke-width", 2.5).attr("stroke-opacity", clear ? 1 : 0.45)
          .attr("x1", x(r.ci95_low)).attr("x2", x(r.ci95_high)).attr("y1", cy).attr("y2", cy);
        g.append("circle").attr("cx", x(r.coef)).attr("cy", cy).attr("r", 6).attr("class", (focus ? "f-focus" : clear ? "f-ink" : "f-context") + " ring");
        g.append("text").attr("class", focus ? "lbl-strong" : "lbl-2").attr("x", w - m.r + 8).attr("y", cy + 4)
          .text(r.term === "growth_5y_pct" ? `${F.signed(Math.round(r.pct * 10) / 10)}%` : `${F.signed(Math.round(r.pct))}%`);
        g.append("rect").attr("class", "hover-target").attr("x", 0).attr("width", w).attr("y", cy - rowH / 2).attr("height", rowH).datum(r);
      });
      g.append("text").attr("class", "lbl-3").attr("x", w - 2).attr("y", m.t - 10).attr("text-anchor", "end").text("effect");
      hoverable(g.selectAll(".hover-target"), r => ({ title: r.label, rows: [{ value: r.coef.toFixed(3), label: "coefficient" },
        { value: `${r.ci95_low.toFixed(3)} to ${r.ci95_high.toFixed(3)}`, label: "95% confidence interval" }, { value: `${F.signed(Math.round(r.pct))}%`, label: "visas per worker, other things equal" }] }));
      MBS.ui.keyNav(svg.node(), () => g.selectAll(".hover-target").nodes().map((nd, i) => ({ node: nd, title: rows[i].label, rows: [{ value: rows[i].coef.toFixed(3), label: "coefficient" }] })), summary);
      return Promise.resolve();
    }
    return { render, table, summary };
  }

  // ================================================================ Models A5: homes needed under each assumption
  const PLAN_KEY = { "Government (Labor)": "gov", "Coalition (Liberal-National)": "coa", "One Nation": "on", "Reference: latest year held flat (not a plan)": "ref" };
  const PLAN_NAME = { gov: "Government", coa: "Coalition", on: "One Nation", ref: "If the last 12 months continued" };
  function sensRows(m, measure) {
    const A = m.a2;
    const rows = A.rows.map(r => Object.fromEntries(A.columns.map((c, i) => [c, r[i]]))).filter(r => r.case === "central" && r.measure === measure);
    return ["gov", "coa", "on", "ref"].map(id => {
      const rs = rows.filter(r => PLAN_KEY[r.plan] === id);
      const central = rs.find(r => r.test === "central");
      const pph = rs.filter(r => r.test === "people_per_home").map(r => r.value);
      const bmd = rs.filter(r => r.test === "births_minus_deaths").map(r => r.value);
      const late = rs.find(r => r.test === "opposition_plans_start_2027_28");
      return { id, name: PLAN_NAME[id], central: central ? central.value : null, pphLo: Math.min(...pph), pphHi: Math.max(...pph),
        bmdLo: Math.min(...bmd), bmdHi: Math.max(...bmd), late: late && late.difference ? late.value : null };
    });
  }
  function sensitivity(host, d, ctx) {
    const rows = sensRows(ctx.m, "homes_needed_per_year");
    const built = d.q6.built;
    const table = { caption: "Homes needed a year under each plan when one assumption changes (our model)",
      columns: [{ key: "name", label: "Plan" }, { key: "central", label: "As published", num: true }, { key: "pph", label: "People per home 2.3 to 2.8", num: true, fmt: (v, r) => `${F.int(r.pphLo)} to ${F.int(r.pphHi)}` },
        { key: "bmd", label: "Births minus deaths ±10%", num: true, fmt: (v, r) => `${F.int(r.bmdLo)} to ${F.int(r.bmdHi)}` }, { key: "late", label: "Starts in 2027-28", num: true, fmt: v => v == null ? "–" : F.int(v) }],
      rows: rows.map(r => ({ ...r, pph: r.pphLo, bmd: r.bmdLo })) };
    const summary = "Homes needed a year: " + rows.map(r => `${r.name} ${F.int(r.central)} (people per home range ${F.int(r.pphLo)} to ${F.int(r.pphHi)})`).join("; ") + `. Homes finished last year: ${F.int(built)}.`;
    function render() {
      host.textContent = "";
      legend(host, [{ shape: "rect", cls: "f-focus est", label: "People per home 2.3 to 2.8" }, { shape: "dot", cls: "f-focus", label: "As published (2.5)" },
        { shape: "line", cls: "s-ink", label: "Births minus deaths ±10%" }, { shape: "line", cls: "s-comparison", label: `Built last year: ${F.k(built)}` }]);
      const w = widthOf(host);
      const rowH = 46, bh = 16;
      const m = { t: 6, r: 20, b: 24, l: 8 };
      const h = m.t + rows.length * rowH + m.b;
      const svg = makeSvg(host, w, h, summary);
      const x = d3.scaleLinear().domain([0, Math.max(built, d3.max(rows, r => r.pphHi)) * 1.08]).nice().range([m.l, w - m.r]);
      const g = svg.append("g");
      const ticks = x.ticks(w < 520 ? 4 : 6);
      g.append("g").attr("class", "grid").selectAll("line").data(ticks).join("line").attr("x1", x).attr("x2", x).attr("y1", m.t).attr("y2", h - m.b);
      g.append("g").selectAll("text").data(ticks).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - 6).attr("text-anchor", "middle").text(F.short);
      rows.forEach((r, i) => {
        const yy = m.t + i * rowH;
        const cy = yy + 30;
        g.append("text").attr("class", r.id === "ref" ? "lbl-2" : "lbl-strong").attr("x", m.l).attr("y", yy + 14).text(r.name);
        g.append("rect").attr("class", "f-focus est").attr("x", x(r.pphLo)).attr("width", Math.max(2, x(r.pphHi) - x(r.pphLo))).attr("y", cy - bh / 2).attr("height", bh).attr("rx", 4);
        g.append("line").attr("class", "s-ink").attr("stroke-width", 2).attr("x1", x(r.bmdLo)).attr("x2", x(r.bmdLo)).attr("y1", cy - bh / 2 - 3).attr("y2", cy + bh / 2 + 3);
        g.append("line").attr("class", "s-ink").attr("stroke-width", 2).attr("x1", x(r.bmdHi)).attr("x2", x(r.bmdHi)).attr("y1", cy - bh / 2 - 3).attr("y2", cy + bh / 2 + 3);
        g.append("circle").attr("cx", x(r.central)).attr("cy", cy).attr("r", 5.5).attr("class", (r.id === "ref" ? "f-context" : "f-focus") + " ring");
        g.append("rect").attr("class", "hover-target").attr("x", 0).attr("width", w).attr("y", yy).attr("height", rowH).datum(r);
      });
      g.append("line").attr("class", "s-comparison").attr("stroke-width", 2.5).attr("x1", x(built)).attr("x2", x(built)).attr("y1", m.t).attr("y2", h - m.b);
      hoverable(g.selectAll(".hover-target"), r => ({ title: r.name, rows: [{ value: F.int(r.central), label: "homes a year, as published" },
        { value: `${F.int(r.pphLo)} to ${F.int(r.pphHi)}`, label: "at 2.8 to 2.3 people per home" }, { value: `${F.int(r.bmdLo)} to ${F.int(r.bmdHi)}`, label: "births minus deaths ±10%" },
        { value: F.int(built), label: "homes finished last year", color: COL.comparison() }] }));
      MBS.ui.keyNav(svg.node(), () => g.selectAll(".hover-target").nodes().map((nd, i) => ({ node: nd, title: rows[i].name, rows: [{ value: `${F.int(rows[i].pphLo)} to ${F.int(rows[i].pphHi)}`, label: "homes a year" }] })), summary);
      return Promise.resolve();
    }
    return { render, table, summary };
  }

  // ================================================================ Models A6: a later start for the opposition plans
  function lateStart(host, d, ctx) {
    const rows = sensRows(ctx.m, "population_june_2030").filter(r => r.id !== "ref");
    const table = { caption: "Population at June 2030 if the opposition plans start in 2027-28 (our model)",
      columns: [{ key: "name", label: "Plan" }, { key: "central", label: "Starting 2026-27", num: true }, { key: "late", label: "Starting 2027-28", num: true, fmt: v => v == null ? "No change (in government)" : F.int(v) },
        { key: "diff", label: "Difference", num: true, fmt: v => v ? F.signed(v) : "0" }],
      rows: rows.map(r => ({ ...r, diff: r.late == null ? 0 : r.late - r.central })) };
    const summary = "Population in June 2030: " + rows.map(r => `${r.name} ${F.int(r.central)}` + (r.late ? `, or ${F.int(r.late)} starting a year later` : "")).join("; ") + ".";
    function render() {
      host.textContent = "";
      legend(host, [{ shape: "dot", cls: "f-focus", label: "Plan starts in 2026-27" }, { shape: "dot", cls: "f-comparison", label: "Starts a year later" }]);
      const w = widthOf(host);
      const rowH = 54;
      const m = { t: 8, r: 24, b: 26, l: 8 };
      const h = m.t + rows.length * rowH + m.b;
      const svg = makeSvg(host, w, h, summary);
      const vals = rows.flatMap(r => [r.central, r.late || r.central]);
      const x = d3.scaleLinear().domain([d3.min(vals) - 150000, d3.max(vals) + 150000]).nice().range([m.l, w - m.r]);
      const g = svg.append("g");
      const ticks = x.ticks(w < 520 ? 3 : 5);
      g.append("g").attr("class", "grid").selectAll("line").data(ticks).join("line").attr("x1", x).attr("x2", x).attr("y1", m.t).attr("y2", h - m.b);
      g.append("g").selectAll("text").data(ticks).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - 6).attr("text-anchor", "middle").text(v => `${(v / 1e6).toFixed(2)}m`);
      rows.forEach((r, i) => {
        const yy = m.t + i * rowH, cy = yy + 34;
        g.append("text").attr("class", "lbl-strong").attr("x", m.l).attr("y", yy + 14).text(r.name + (r.late ? `: ${F.signed(r.late - r.central)} people` : ": in government, no delay"));
        if (r.late) {
          g.append("line").attr("class", "s-ink").attr("stroke-width", 2).attr("x1", x(r.central)).attr("x2", x(r.late)).attr("y1", cy).attr("y2", cy);
          g.append("circle").attr("cx", x(r.late)).attr("cy", cy).attr("r", 6).attr("class", "f-comparison ring");
        }
        g.append("circle").attr("cx", x(r.central)).attr("cy", cy).attr("r", 6).attr("class", "f-focus ring");
      });
      return Promise.resolve();
    }
    return { render, table, summary };
  }

  // ================================================================ Models A7: the browser model checks itself against the pipeline
  function selfCheckData() {
    const M = MBS.explore.model;
    const ids = { "Government (Labor)": "gov", "Coalition (Liberal-National)": "coa", "One Nation": "on", "Reference: latest year held flat (not a plan)": "ref" };
    const out = [];
    for (const [plan, cs, place, pop, homes, wa] of M.expected) {
      const pre = M.presets.find(p => p.id === `${ids[plan]}_${cs}`);
      if (!pre) continue;
      const r = MBS.model.run(pre.nom, place);
      out.push({ measure: "Population, June 2030", plan, cs, place, diff: r.pop_2030 - pop });
      out.push({ measure: "Homes needed a year", plan, cs, place, diff: r.homes_per_year - homes });
      out.push({ measure: "Working-age people added", plan, cs, place, diff: r.working_age_4y - wa });
    }
    return out;
  }
  function selfCheck(host) {
    const pts = selfCheckData();
    const worst = d3.max(pts, p => Math.abs(p.diff)) || 0;
    const within = pts.filter(p => Math.abs(p.diff) <= 1).length;
    const measures = Array.from(new Set(pts.map(p => p.measure)));
    const table = { caption: "Browser model minus pipeline, every plan, case and place",
      columns: [{ key: "measure", label: "Measure" }, { key: "n", label: "Results", num: true }, { key: "worst", label: "Largest difference", num: true, fmt: v => v.toFixed(2) }],
      rows: measures.map(ms => { const p = pts.filter(z => z.measure === ms); return { measure: ms, n: p.length, worst: d3.max(p, z => Math.abs(z.diff)) }; }) };
    const summary = `${within} of ${pts.length} results agree within one; the largest difference is ${worst.toFixed(2)}.`;
    function render() {
      host.textContent = "";
      host.appendChild(el("div", { class: "stat-row stat-row-tight" },
        el("div", { class: "stat" }, el("div", { class: "v", text: `${within} of ${pts.length}` }), el("div", { class: "l", text: "results agree within one person or home" })),
        el("div", { class: "stat" }, el("div", { class: "v", text: worst.toFixed(2) }), el("div", { class: "l", text: "largest difference (rounding)" }))));
      const w = widthOf(host);
      const labW = d3.max(measures, s => textWidth(s, 13)) + 14;
      const rowH = 44;
      const m = { t: 14, r: 20, b: 28, l: labW };
      const h = m.t + measures.length * rowH + m.b;
      const svg = makeSvg(host, w, h, summary);
      const x = d3.scaleLinear().domain([-1, 1]).range([m.l, w - m.r]);
      const g = svg.append("g");
      [-1, -0.5, 0, 0.5, 1].forEach(v => {
        g.append("line").attr("class", v === 0 ? "baseline" : "grid-line").attr("x1", x(v)).attr("x2", x(v)).attr("y1", m.t).attr("y2", h - m.b);
        g.append("text").attr("class", "tick-label").attr("x", x(v)).attr("y", h - 8).attr("text-anchor", "middle").text(v === 0 ? "0" : (v > 0 ? "+" : "−") + Math.abs(v).toFixed(1));
      });
      const rnd = d3.randomLcg(42);
      measures.forEach((ms, i) => {
        const cy = m.t + i * rowH + rowH / 2;
        g.append("text").attr("class", "lbl-strong").attr("x", m.l - 10).attr("y", cy + 4).attr("text-anchor", "end").text(ms);
        g.append("g").selectAll("circle").data(pts.filter(p => p.measure === ms)).join("circle")
          .attr("cx", p => x(Math.max(-1, Math.min(1, p.diff)))).attr("cy", () => cy + (rnd() - 0.5) * (rowH - 16)).attr("r", 3.5).attr("class", "f-focus").attr("opacity", 0.7);
      });
      return Promise.resolve();
    }
    return { render, table, summary, get worst() { return worst; }, get count() { return pts.length; } };
  }

  // ================================================================ Models A8: the pipeline
  function pipeline(host, d, ctx) {
    const P = ctx.m.pipeline;
    const boxes = [
      { big: F.int(P.source_files), l: "source files", s: "ABS, Jobs and Skills Australia, Home Affairs, NCVER, Education, Treasury" },
      { big: F.int(P.scripts), l: "Python scripts", s: `${F.int(P.steps_logged)} steps with row counts logged` },
      { big: F.int(P.tables_documented), l: "tables documented", s: `${F.int(P.columns_documented)} columns, each with its source and kind of number` },
      { big: F.int(P.figures), l: "charts", s: `${F.int(P.downloads)} tables to download; every chart has a table view` }];
    const table = { caption: "From source files to charts", columns: [{ key: "l", label: "Stage" }, { key: "big", label: "Count", num: true }, { key: "s", label: "Detail" }], rows: boxes };
    const summary = "Pipeline: " + boxes.map(b => `${b.big} ${b.l}`).join(", then ") + ".";
    function render() {
      host.textContent = "";
      host.setAttribute("role", "img");
      host.setAttribute("aria-label", summary);
      host.appendChild(el("ol", { class: "pipeline" }, boxes.map(b => el("li", null,
        el("span", { class: "pl-big", text: b.big }), el("span", { class: "pl-l", text: b.l }), el("span", { class: "pl-s", text: b.s })))));
      return Promise.resolve();
    }
    return { render, table, summary };
  }

  Object.assign(MBS.charts, { nomByState, verdictsBySide, visaRates, visaShares, a1Scatter, coefPlot, sensitivity, lateStart, selfCheck, pipeline });
  MBS.selfCheckData = selfCheckData;
})();
