/* Migration by Skill: the skills gap simulator ("size vs mix", method A agreed 5 October 2026). Our illustration:
   skilled workers a year = net overseas migration x skilled share x working-age share x employment rate of recent
   skilled migrants. Today's mix: the share of skilled visas that go to short jobs today, spread across job groups
   like 2025-26 temporary skilled visas. Skills-first: every skilled place goes to a short job, spread across job
   groups by workers needed a year x the share of the group's jobs on the shortage list. */
(function () {
  "use strict";
  const MBS = (window.MBS = window.MBS || {});
  const { el, textWidth } = MBS.util;
  const F = MBS.fmt;
  const H = () => MBS.chartHelpers;

  // ---------------------------------------------------------------- the model
  function compute(size, sharePct, d) {
    const S = (d || MBS.data).sim;
    const migrants = Math.max(0, size) * sharePct / 100;
    const workers = migrants * S.working_age_share * S.employment_recent_pct / 100;
    const todayShort = workers * S.short_share_of_visas_pct / 100;
    const firstShort = workers;
    const totV = S.sectors.reduce((a, s) => a + s.visa_grants, 0);
    const shortNeed = s => s.need * s.short_pct / 100;
    const totShort = S.sectors.reduce((a, s) => a + shortNeed(s), 0);
    const groups = S.sectors.map(s => {
      const today = workers * s.visa_grants / totV;
      const first = workers * shortNeed(s) / totShort;
      return { ...s, today, first, today100: 100 * today / s.need, first100: 100 * first / s.need, measured: S.measured.includes(s.id) };
    });
    return { size, sharePct, migrants, workers, todayShort, firstShort, groups,
      matchSize: size * S.short_share_of_visas_pct / 100, workersPer100: S.working_age_share * S.employment_recent_pct };
  }
  MBS.sim = { compute };

  // ---------------------------------------------------------------- chart: skilled workers per 100 needed, each job group
  function groupsChart(host, r) {
    host.textContent = "";
    const rows = r.groups.slice().sort((a, b) => b.short_pct - a.short_pct || b.need - a.need);
    H().legend(host, [{ shape: "dot", cls: "f-context", label: "Today's mix" }, { shape: "dot", cls: "f-focus", label: "Skills-first" }]);
    const w = H().widthOf(host);
    const narrow = w < 520;
    const fs = narrow ? 12 : 13;
    const labW = d3.max(rows, g => textWidth(g.name, fs)) + 12;
    const rowH = 21;
    const m = { t: 22, r: 40, b: 24, l: labW };
    const h = m.t + rows.length * rowH + m.b;
    const summary = `Skilled workers per 100 workers needed a year, by job group: today's mix against skills-first. ` +
      rows.slice(0, 6).map(g => `${g.name}: ${Math.round(g.today100)} against ${Math.round(g.first100)}`).join("; ") + ".";
    const svg = H().makeSvg(host, w, h, summary);
    const max = Math.max(10, d3.max(rows, g => Math.max(g.today100, g.first100)));
    const x = d3.scaleLinear().domain([0, max]).nice().range([m.l, w - m.r]);
    const g = svg.append("g");
    const ticks = x.ticks(narrow ? 3 : 5);
    g.append("g").attr("class", "grid").selectAll("line").data(ticks).join("line").attr("x1", x).attr("x2", x).attr("y1", m.t).attr("y2", h - m.b);
    g.append("g").selectAll("text").data(ticks).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - 6).attr("text-anchor", "middle").text(v => v);
    const firstNot = rows.findIndex(z => z.short_pct < 50);
    if (firstNot > 0) {
      const yb = m.t + firstNot * rowH - 3;
      g.append("line").attr("class", "baseline").attr("x1", 0).attr("x2", w).attr("y1", yb).attr("y2", yb).attr("stroke-dasharray", "3 3");
      g.append("text").attr("class", "lbl-3").attr("x", w - 2).attr("y", m.t - 8).attr("text-anchor", "end").text("Most jobs short ↓");
      g.append("text").attr("class", "lbl-3").attr("x", w - 2).attr("y", yb + 12).attr("text-anchor", "end").text("Most jobs not short ↓");
    }
    rows.forEach((z, i) => {
      const cy = m.t + i * rowH + rowH / 2;
      const short = z.short_pct >= 50;
      g.append("text").attr("class", short ? "lbl-strong" : "lbl-2").attr("x", m.l - 8).attr("y", cy + 4).attr("text-anchor", "end").style("font-size", fs + "px").text(z.name);
      g.append("line").attr("class", "s-context").attr("stroke-width", 2).attr("x1", x(z.today100)).attr("x2", x(z.first100)).attr("y1", cy).attr("y2", cy);
      g.append("circle").attr("cx", x(z.today100)).attr("cy", cy).attr("r", 4.5).attr("class", "f-context ring");
      g.append("circle").attr("cx", x(z.first100)).attr("cy", cy).attr("r", 4.5).attr("class", "f-focus ring");
      g.append("rect").attr("class", "hover-target").attr("x", 0).attr("width", w).attr("y", cy - rowH / 2).attr("height", rowH).datum(z);
    });
    H().hoverable(g.selectAll(".hover-target"), z => ({ title: z.name, rows: [
      { value: F.about(z.today), label: `workers a year, today's mix (${Math.round(z.today100)} per 100 needed)`, color: H().COL.context() },
      { value: F.about(z.first), label: `workers a year, skills-first (${Math.round(z.first100)} per 100 needed)`, color: H().COL.focus() },
      { value: F.int(z.need), label: "workers needed a year" }, { value: F.pct0(z.short_pct), label: "of the group's jobs short" }] }));
    MBS.ui.keyNav(svg.node(), () => g.selectAll(".hover-target").nodes().map((nd, i) => ({ node: nd, title: rows[i].name,
      rows: [{ value: String(Math.round(rows[i].today100)), label: "per 100 needed, today's mix" }, { value: String(Math.round(rows[i].first100)), label: "per 100 needed, skills-first" }] })), summary);
    return { caption: "Skilled workers a year by job group under each mix (our illustration)",
      columns: [{ key: "name", label: "Job group" }, { key: "short_pct", label: "Jobs short", num: true, fmt: F.pct0 }, { key: "need", label: "Workers needed a year", num: true },
        { key: "today", label: "Today's mix", num: true }, { key: "first", label: "Skills-first", num: true },
        { key: "today100", label: "Per 100 needed, today", num: true, fmt: v => String(Math.round(v)) }, { key: "first100", label: "Per 100 needed, skills-first", num: true, fmt: v => String(Math.round(v)) }],
      rows };
  }

  // ---------------------------------------------------------------- chart: where training is counted, trained + skilled vs 100
  function measuredChart(host, r, mix, d) {
    host.textContent = "";
    const train = Object.fromEntries((d || MBS.data).q9.rows.map(z => [z.id, z.trained_per_100]));
    const rows = r.groups.filter(z => z.measured).map(z => ({ ...z, trained: train[z.id], skilled: mix === "first" ? z.first100 : z.today100 }))
      .sort((a, b) => (a.trained + a.skilled) - (b.trained + b.skilled));
    H().legend(host, [{ shape: "rect", cls: "f-context", label: "Trained here (our estimate)" },
      { shape: "rect", fill: "url(#hatch-focus)", label: `Skilled workers, ${mix === "first" ? "skills-first" : "today's mix"} (our illustration)` }]);
    const w = H().widthOf(host);
    const fs = w < 520 ? 12 : 13;
    const labW = d3.max(rows, z => textWidth(z.name, fs)) + 12;
    const rowH = 30, bh = 16;
    const m = { t: 22, r: 56, b: 24, l: labW };
    const h = m.t + rows.length * rowH + m.b;
    const summary = `Trained here plus skilled workers per 100 needed, ${mix === "first" ? "skills-first" : "today's mix"}: ` + rows.map(z => `${z.name} ${Math.round(z.trained + z.skilled)}`).join(", ") + ". 100 means one for every worker needed.";
    const svg = H().makeSvg(host, w, h, summary);
    const x = d3.scaleLinear().domain([0, Math.max(150, d3.max(rows, z => z.trained + z.skilled))]).nice().range([m.l, w - m.r]);
    const g = svg.append("g");
    const ticks = x.ticks(w < 520 ? 3 : 6);
    g.append("g").attr("class", "grid").selectAll("line").data(ticks).join("line").attr("x1", x).attr("x2", x).attr("y1", m.t).attr("y2", h - m.b);
    g.append("g").selectAll("text").data(ticks).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - 6).attr("text-anchor", "middle").text(v => v);
    rows.forEach((z, i) => {
      const yy = m.t + i * rowH;
      g.append("text").attr("class", "lbl-strong").attr("x", m.l - 8).attr("y", yy + bh - 3).attr("text-anchor", "end").style("font-size", fs + "px").text(z.name);
      g.append("rect").attr("class", "f-context").attr("x", x(0)).attr("y", yy).attr("width", Math.max(0, x(z.trained) - x(0) - 1)).attr("height", bh).attr("rx", 2);
      g.append("rect").attr("fill", "url(#hatch-focus)").attr("class", "hatch-cell").attr("x", x(z.trained)).attr("y", yy).attr("width", Math.max(0, x(z.trained + z.skilled) - x(z.trained))).attr("height", bh).attr("rx", 2);
      g.append("text").attr("class", "lbl-strong").attr("x", x(z.trained + z.skilled) + 6).attr("y", yy + bh - 3).text(Math.round(z.trained + z.skilled));
      g.append("rect").attr("class", "hover-target").attr("x", 0).attr("width", w).attr("y", yy - 6).attr("height", rowH).datum(z);
    });
    g.append("line").attr("class", "s-comparison").attr("stroke-width", 2).attr("x1", x(100)).attr("x2", x(100)).attr("y1", m.t - 8).attr("y2", h - m.b);
    g.append("text").attr("class", "lbl-strong").attr("x", x(100) + 4).attr("y", m.t - 10).text("100 = one for every worker needed");
    H().hoverable(g.selectAll(".hover-target"), z => ({ title: z.name, rows: [{ value: String(z.trained), label: "trained here per 100 needed" },
      { value: String(Math.round(z.skilled)), label: "skilled workers per 100 needed" }, { value: String(Math.round(z.trained + z.skilled)), label: "together" }] }));
    MBS.ui.keyNav(svg.node(), () => g.selectAll(".hover-target").nodes().map((nd, i) => ({ node: nd, title: rows[i].name, rows: [{ value: String(Math.round(rows[i].trained + rows[i].skilled)), label: "per 100 needed" }] })), summary);
    return { caption: `Trained here and skilled workers per 100 workers needed a year, ${mix === "first" ? "skills-first" : "today's mix"}`,
      columns: [{ key: "name", label: "Job group" }, { key: "trained", label: "Trained here", num: true }, { key: "skilled", label: "Skilled workers", num: true, fmt: v => String(Math.round(v)) },
        { key: "total", label: "Together", num: true, fmt: v => String(Math.round(v)) }], rows: rows.map(z => ({ ...z, total: z.trained + z.skilled })) };
  }

  // ---------------------------------------------------------------- the section
  function build(main) {
    const d = MBS.data, S = d.sim, C = MBS.content.sim;
    const st = { size: S.start, share: S.skilled_share_pct, mix: "first" };
    const sizeOut = el("output", { class: "sim-val", for: "sim-size" });
    const shareOut = el("output", { class: "sim-val", for: "sim-share" });
    const size = el("input", { type: "range", id: "sim-size", min: S.min, max: S.max, step: S.step, value: st.size, oninput: e => set({ size: +e.target.value }) });
    const share = el("input", { type: "range", id: "sim-share", min: "5", max: "60", step: "0.5", value: st.share, oninput: e => set({ share: +e.target.value }) });
    const presets = el("div", { class: "chips", role: "group", "aria-label": "Set the size" },
      S.presets.map(v => el("button", { class: "chip", type: "button", "data-v": String(v), onclick: () => set({ size: v }) }, F.int(v))));
    const shareReset = el("button", { class: "chip", type: "button", onclick: () => set({ share: S.skilled_share_pct }) }, `Today: ${F.pct1(S.skilled_share_pct)}`);
    const mixBtns = el("div", { class: "seg", role: "group", "aria-label": "Mix for the training chart" },
      [["today", "Today's mix"], ["first", "Skills-first"]].map(([k, l]) => el("button", { type: "button", "data-mix": k, onclick: () => set({ mix: k }) }, l)));
    const headline = el("p", { class: "sim-headline", "aria-live": "polite" });
    const stats = el("div", { class: "stat-row sim-stats" });
    const gHost = el("div", { class: "chart-host" }), mHost = el("div", { class: "chart-host" });
    const gTable = el("div", { class: "table-view", id: "sim-groups-table", hidden: true });
    const mTable = el("div", { class: "table-view", id: "sim-measured-table", hidden: true });
    const sec = el("section", { class: "sim", id: "simulator", "aria-labelledby": "sim-h" },
      el("div", { class: "wrap-wide" },
        el("header", { class: "sec-head" },
          el("p", { class: "sec-kicker", text: C.kicker }),
          el("h2", { id: "sim-h", class: "sec-title", tabindex: "-1", text: C.title }),
          el("p", { class: "sec-lede", text: C.intro })),
        el("div", { class: "sim-grid" },
          el("div", { class: "sim-controls" },
            el("div", { class: "ctl" },
              el("label", { for: "sim-size", class: "ctl-label" }, el("span", null, "1. Size: net overseas migration a year"), sizeOut),
              size, presets, el("p", { class: "ctl-note", text: C.presetNote(d) })),
            el("div", { class: "ctl" },
              el("label", { for: "sim-share", class: "ctl-label" }, el("span", null, "2. Skilled share of that migration"), shareOut),
              share, el("div", { class: "chips" }, shareReset)),
            el("div", { class: "ctl" },
              el("p", { class: "ctl-label" }, el("span", null, "3. Mix for the training chart")), mixBtns),
            el("details", { class: "sim-how" }, el("summary", null, "How it works, and its limits"),
              el("ol", null, C.steps(d).map(t => el("li", null, MBS.rich(t)))),
              el("p", { class: "ctl-note" }, el("strong", null, "Limits. ")),
              el("ul", null, C.limits.map(t => el("li", { text: t }))),
              el("p", { class: "ctl-note" }, MBS.ui.sourceLine(S.sources)))),
          el("div", { class: "sim-out" },
            headline, stats,
            el("figure", { class: "card sim-fig" },
              el("figcaption", { class: "card-title" }, "Skilled workers per 100 needed, by job group"),
              el("p", { class: "card-sub", text: "Each job group's skilled workers a year, per 100 workers it needs a year: today's mix against skills-first" }),
              gHost, el("div", { class: "card-foot" }, MBS.ui.badges(["illustration"]), el("span", { class: "spacer" }), MBS.ui.tableToggle("sim-groups-table")), gTable),
            el("figure", { class: "card sim-fig" },
              el("figcaption", { class: "card-title" }, "Where we can count training: does it reach 100?"),
              el("p", { class: "card-sub", text: "Trained here plus skilled workers, per 100 workers needed a year" }),
              mHost, el("div", { class: "card-foot" }, MBS.ui.badges(["estimate", "illustration"]), el("span", { class: "spacer" }), MBS.ui.tableToggle("sim-measured-table")), mTable)))));
    main.appendChild(sec);
    let raf = 0;
    function set(p) {
      Object.assign(st, p);
      if (raf) return;
      const run = () => { raf = 0; draw(); };
      raf = window.requestAnimationFrame ? requestAnimationFrame(run) : (setTimeout(run, 0), 1);
    }
    function stat(v, l, cls) { return el("div", { class: `stat ${cls || ""}` }, el("div", { class: "v", text: v }), el("div", { class: "l", text: l })); }
    function draw() {
      const r = compute(st.size, st.share, d);
      size.value = st.size; share.value = st.share;
      sizeOut.textContent = F.int(st.size);
      shareOut.textContent = F.pct1(st.share);
      size.setAttribute("aria-valuetext", `${F.int(st.size)} a year`);
      share.setAttribute("aria-valuetext", `${F.pct1(st.share)} skilled`);
      presets.querySelectorAll(".chip").forEach(b => b.setAttribute("aria-pressed", String(+b.getAttribute("data-v") === st.size)));
      shareReset.setAttribute("aria-pressed", String(Math.abs(st.share - S.skilled_share_pct) < 0.01));
      mixBtns.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(b.getAttribute("data-mix") === st.mix)));
      headline.textContent = "";
      headline.append(...MBS.rich(st.size <= 0 ? "With no net migration, no skilled workers arrive through the program." :
        `At ${F.int(st.size)} a year, today's mix sends about **${F.about(r.todayShort)} skilled workers** a year to short jobs. Skills-first sends **${F.about(r.firstShort)}**. ` +
        `Skills-first would match today's number with about ${F.about(r.matchSize)} a year.`));
      stats.textContent = "";
      stats.append(stat(F.about(r.migrants), "skilled migrants a year, with partners and children"),
        stat(F.about(r.workers), `skilled workers a year (about ${Math.round(r.workersPer100)} per 100 migrants)`),
        stat(F.about(r.todayShort), "reach short jobs, today's mix", "stat-context"),
        stat(F.about(r.firstShort), "reach short jobs, skills-first", "stat-focus"));
      MBS.ui.fillTable(gTable, groupsChart(gHost, r));
      MBS.ui.fillTable(mTable, measuredChart(mHost, r, st.mix, d));
    }
    MBS.shell.lazy(sec, draw, "400px 0px");
    window.addEventListener("resize", MBS.util.debounce(() => { if (gHost.firstChild) draw(); }, 250));
    MBS.sim.set = set;
    MBS.sim.state = st;
  }
  MBS.buildSim = build;
})();
