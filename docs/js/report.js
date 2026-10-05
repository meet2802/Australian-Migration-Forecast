/* Migration by Skill: the report. Executive summary (key numbers and findings), numbered exhibits in a two-column
   grid (takeaway title, chart, source, About, Table, CSV), interactive exhibits, Appendix A (models) and Appendix B
   (data and methods). Charts draw as they come near the screen. */
(function () {
  "use strict";
  const MBS = (window.MBS = window.MBS || {});
  const { el, reducedMotion } = MBS.util;
  const F = MBS.fmt;
  const R = { charts: {}, tools: {} };
  MBS.report = R;
  const canAnimate = () => typeof window.IntersectionObserver === "function" && !reducedMotion();

  // explore data arrives after the page is drawn: run callbacks once it is here
  const waiting = [];
  MBS.whenExplore = fn => { if (MBS.explore && MBS.explore.models) fn(); else waiting.push(fn); };
  MBS.exploreReady = () => { while (waiting.length) waiting.shift()(); };

  const exNum = id => id.replace(/^ex/, "");

  // ---------------------------------------------------------------- one exhibit card
  function exhibit(ex, d, m) {
    const arg = m ? Object.assign({}, d, m) : d;
    const id = ex.id;
    const infoId = `${id}-info`, tableId = `${id}-table`, descId = `${id}-desc`;
    const art = el("article", { class: `exhibit span-${ex.span}${ex.tool ? " exhibit-tool" : ""}`, id, "aria-labelledby": `${id}-h` });
    art.appendChild(el("p", { class: "ex-num", text: `Exhibit ${exNum(id)}` }));
    art.appendChild(el("h4", { class: "ex-title", id: `${id}-h`, tabindex: "-1", text: ex.title(arg) }));
    art.appendChild(el("p", { class: "ex-sub", text: ex.sub(arg) }));
    const foot = el("div", { class: "ex-foot" }, MBS.ui.badges(ex.types), el("span", { class: "spacer" }));
    if (ex.tool) {
      const body = el("div", { class: "tool", id: `${id}-tool` }, el("p", { class: "tool-wait", text: "Loading the data for this tool…" }));
      art.appendChild(body);
      if (ex.csv) foot.appendChild(csvLink(ex.csv));
      art.appendChild(foot);
      const src = MBS.ui.sourceLine(ex.sources(arg));
      if (src) art.appendChild(el("p", { class: "ex-source" }, src));
      MBS.whenExplore(() => {
        body.textContent = "";
        R.tools[ex.tool] = MBS.tools[ex.tool](body);
      });
      return art;
    }
    const host = el("div", { class: "chart-host" });
    const ctx = Object.assign({}, m ? { m } : null, ex.minH ? { minH: ex.minH } : null,
      ex.chart === "stateTiles" ? { onSelect: code => tilePicked(code, d) } : null, ex.chart === "planLines" ? { onLit: lit => litChips(id, lit) } : null);
    const chart = MBS.charts[ex.chart](host, d, ctx);
    R.charts[id] = { chart, host, width: 0, rendered: false };
    if (ex.plans) art.appendChild(planChips(id, d));
    if (ex.chart === "stateTiles") art.appendChild(el("p", { class: "tile-pick", id: "tile-pick", "aria-live": "polite", text: "Tap a tile to load that state into Exhibit 11." }));
    art.appendChild(el("figure", { class: "chart", "aria-describedby": descId }, host));
    art.appendChild(el("p", { class: "sr-only", id: descId, text: chart.summary }));
    const info = ex.info ? (typeof ex.info === "string" ? MBS.content.INFO[ex.info] : ex.info) : null;
    if (info) foot.appendChild(MBS.ui.infoToggle(infoId));
    foot.appendChild(MBS.ui.tableToggle(tableId));
    if (ex.csv) foot.appendChild(csvLink(ex.csv));
    art.appendChild(foot);
    const src = MBS.ui.sourceLine(ex.sources(arg));
    if (src) art.appendChild(el("p", { class: "ex-source" }, src));
    if (info) {
      art.appendChild(MBS.ui.infoPanel(infoId, { why: info.why(arg), how: info.how(arg), shows: info.shows(arg), limits: info.limits(arg),
        sources: info.sources ? info.sources(arg) : null, link: info.link ? info.link(arg) : null }));
    }
    art.appendChild(MBS.ui.tableView(tableId, chart.table));
    MBS.shell.lazy(art, () => draw(id, canAnimate()));
    return art;
  }
  function draw(id, animate) {
    const c = R.charts[id];
    if (!c) return;
    c.rendered = true;
    c.width = c.host.clientWidth;
    c.chart.render(animate);
  }
  function csvLink(file) {
    return el("a", { class: "icon-btn", href: `downloads/${file}`, download: file, title: `Download ${file}` },
      el("span", { class: "dl", "aria-hidden": "true" }, "↓"), "CSV");
  }
  function planChips(id, d) {
    const items = [["all", "All plans"], ...d.q4.plans.map(p => [p.id, p.name])];
    return el("div", { class: "chips", role: "group", "aria-label": "Light up one plan", id: `${id}-chips` },
      items.map(([pid, label]) => el("button", { class: "chip", type: "button", "data-plan": pid, "aria-pressed": String(pid === "all"),
        onclick: () => { const c = R.charts[id]; if (!c.rendered) draw(id, false); c.chart.update(pid); } }, label)));
  }
  function litChips(id, lit) {
    document.querySelectorAll(`#${id}-chips .chip`).forEach(c => c.setAttribute("aria-pressed", String(c.getAttribute("data-plan") === lit)));
  }
  function tilePicked(code, d) {
    const s = d.q12.states.find(x => x.code === code);
    const p = document.getElementById("tile-pick");
    if (p && s) {
      p.textContent = "";
      p.append(`${s.name}: ${F.one(s.people_per_home)} people per new home, ${F.int(s.growth)} more people, ${F.int(s.homes)} homes finished. `,
        el("a", { href: "#ex11", text: "More in Exhibit 11" }), ".");
    }
    if (R.tools.state && s) R.tools.state.set({ state: code });
  }

  // ---------------------------------------------------------------- executive summary
  function execSummary(d) {
    const C = MBS.content.report;
    return el("section", { class: "exec", "aria-labelledby": "exec-h" },
      el("h3", { class: "exec-title", id: "exec-h", text: "Executive summary" }),
      el("div", { class: "kpis" }, C.kpis.map(k => el("div", { class: "kpi" },
        el("p", { class: "kpi-label", text: k.label }),
        el("p", { class: "kpi-value", text: k.value(d) }),
        el("p", { class: "kpi-sub", text: k.sub(d) }),
        MBS.ui.badges([k.type])))),
      el("h4", { class: "findings-title", text: "Key findings" }),
      el("ol", { class: "findings" }, C.findings.map(fd => {
        const t = fd.text(d);
        if (!t) return null;
        return el("li", null, el("p", null, MBS.rich(t)), el("a", { class: "find-link", href: `#${fd.ex}` }, `Exhibit ${exNum(fd.ex)}`, el("span", { "aria-hidden": "true" }, " →")));
      })));
  }

  // ---------------------------------------------------------------- sections
  function sectionHead(s) {
    return el("header", { class: "rsec-head" },
      el("span", { class: "rsec-n", "aria-hidden": "true", text: String(s.n) }),
      el("div", null, el("h3", { class: "rsec-title", id: `${s.id}-h`, text: s.title }), el("p", { class: "rsec-blurb", text: s.blurb })));
  }
  function modelsSection(s, d) {
    const grid = el("div", { class: "ex-grid", id: "models-grid" }, el("p", { class: "tool-wait span-12", text: "Loading the models…" }));
    MBS.whenExplore(() => {
      grid.textContent = "";
      const m = MBS.explore.models;
      for (const ex of MBS.content.models) grid.appendChild(exhibit(ex, d, m));
    });
    return el("section", { class: "rsec rsec-models", id: s.id, "aria-labelledby": `${s.id}-h` }, sectionHead(s), grid);
  }
  function dataSection(s, d) {
    const files = Array.from(new Set(MBS.content.exhibits.concat(MBS.content.models).map(e => e.csv).filter(Boolean))).sort();
    const now = new Date();
    const today = `${now.toLocaleDateString("en-US", { month: "long" })} ${now.getDate()}, ${now.getFullYear()}`;
    const name = MBS.content.meta.author.trim().split(/\s+/);
    const author = name.length > 1 ? `${name[name.length - 1]}, ${name.slice(0, -1).map(n => n[0] + ".").join(" ")}` : name[0];
    const here = location.href.split("#")[0];
    return el("section", { class: "rsec", id: s.id, "aria-labelledby": `${s.id}-h` }, sectionHead(s),
      el("div", { class: "ex-grid" },
        el("article", { class: "exhibit span-4 data-card" },
          el("h4", { class: "ex-title", text: "Data and methods" }),
          el("p", null, "Every table, every column's meaning and source, each assumption, the row counts at each step, the limits and the full reference list."),
          el("p", null, el("a", { class: "btn btn-primary", href: "methods.html" }, "Open Data and methods", el("span", { "aria-hidden": "true" }, "→")))),
        el("article", { class: "exhibit span-4 data-card" },
          el("h4", { class: "ex-title", text: "Download the tables" }),
          el("ul", { class: "dl-list" }, files.map(f => el("li", null, el("a", { href: `downloads/${f}`, download: f, text: f }))))),
        el("article", { class: "exhibit span-4 data-card" },
          el("h4", { class: "ex-title", text: "Cite this work" }),
          el("p", { class: "cite", text: `${author} (2026). ${MBS.content.meta.title}: Who moves to Australia, the jobs we need and what each party plans [Interactive data story and report, version ${d.version}]. Retrieved ${today}, from ${here}` }),
          el("p", null, el("a", { class: "btn", href: "brief.html" }, "Two-page brief for print")))));
  }

  function build(main) {
    const d = MBS.data, C = MBS.content;
    const R0 = C.report;
    const sec = el("section", { class: "report", id: "report", "aria-labelledby": "report-h" });
    sec.appendChild(el("div", { class: "report-head" }, el("div", { class: "wrap-wide" },
      el("p", { class: "sec-kicker", text: "For analysts, journalists and policy readers" }),
      el("h2", { class: "sec-title", id: "report-h", tabindex: "-1", text: R0.title }),
      el("p", { class: "sec-lede", text: R0.lede }),
      el("nav", { class: "report-toc", "aria-label": "Report sections" }, R0.sections.map(s => el("a", { href: `#${s.id}` }, el("span", { class: "toc-n", text: String(s.n) }), s.title.replace(/^Appendix [AB]: /, "")))))));
    const body = el("div", { class: "wrap-wide report-body" });
    sec.appendChild(body);
    body.appendChild(execSummary(d));
    for (const s of R0.sections) {
      if (s.id === "models") { body.appendChild(modelsSection(s, d)); continue; }
      if (s.id === "sec-data") { body.appendChild(dataSection(s, d)); continue; }
      const grid = el("div", { class: "ex-grid" }, C.exhibits.filter(e => e.section === s.id).map(e => exhibit(e, d)));
      body.appendChild(el("section", { class: "rsec", id: s.id, "aria-labelledby": `${s.id}-h` }, sectionHead(s), grid));
    }
    main.appendChild(sec);
    window.addEventListener("resize", MBS.util.debounce(() => {
      for (const [id, c] of Object.entries(R.charts)) {
        if (!c.rendered) continue;
        const w = c.host.clientWidth;
        if (Math.abs(w - c.width) < 8) continue;
        c.width = w;
        const lit = c.chart.lit;
        c.chart.render(false);
        if (lit && c.chart.update) c.chart.update(lit);
      }
    }, 220));
  }
  R.draw = draw;
  MBS.buildReport = build;
})();
