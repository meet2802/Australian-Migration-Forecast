/* Migration by Skill: the two-page briefing. A4 pages on screen and in print: key numbers, what the data says,
   four charts, what it means for skilled migration planning (in skills terms only, no party is endorsed), limits and
   sources (APA 7th). Every number comes from data/data.js through the same templates as the dashboard. */
(function () {
  "use strict";
  const MBS = (window.MBS = window.MBS || {});
  const { el } = MBS.util;
  const F = MBS.fmt;
  const C = () => MBS.content;
  const Hh = () => MBS.content.helpers;

  function kpi(v, l, type) {
    return el("div", { class: "b-kpi" }, el("p", { class: "b-kpi-v", text: v }), el("p", { class: "b-kpi-l", text: l }), MBS.ui.badges([type]));
  }
  function fig(n, title, sub, chartFn, d, ctx, types, sources) {
    const host = el("div", { class: "chart-host" });
    const box = el("figure", { class: "b-fig" },
      el("p", { class: "b-fig-n", text: `Figure ${n}` }),
      el("figcaption", { class: "b-fig-t", text: title }),
      el("p", { class: "b-fig-s", text: sub }),
      host,
      el("div", { class: "b-fig-foot" }, MBS.ui.badges(types), MBS.ui.sourceLine(sources)));
    box._draw = () => { if (typeof chartFn === "function") chartFn(host); else MBS.charts[chartFn](host, d, ctx).render(false); };
    return box;
  }

  // size against mix at three sizes: skilled workers reaching short jobs (our illustration)
  function sizeMix(host) {
    const d = MBS.data, S = d.sim;
    const rows = S.presets.map(v => { const r = MBS.sim.compute(v, S.skilled_share_pct, d); return { v, today: r.todayShort, first: r.firstShort }; });
    host.textContent = "";
    MBS.chartHelpers.legend(host, [{ shape: "rect", cls: "f-context", label: "Today's mix" }, { shape: "rect", fill: "url(#hatch-focus)", label: "Skills-first (our illustration)" }]);
    const w = MBS.chartHelpers.widthOf(host);
    const groupH = 58, bh = 18, m = { t: 6, r: 64, b: 22, l: 70 };
    const h = m.t + rows.length * groupH + m.b;
    const svg = MBS.chartHelpers.makeSvg(host, w, h, "Skilled workers a year reaching short jobs at three sizes of net overseas migration: " +
      rows.map(r => `${F.int(r.v)}: today's mix ${F.about(r.today)}, skills-first ${F.about(r.first)}`).join("; ") + ".");
    const x = d3.scaleLinear().domain([0, d3.max(rows, r => r.first) * 1.05]).nice().range([m.l, w - m.r]);
    const g = svg.append("g");
    g.append("g").attr("class", "grid").selectAll("line").data(x.ticks(4)).join("line").attr("x1", x).attr("x2", x).attr("y1", m.t).attr("y2", h - m.b);
    g.append("g").selectAll("text").data(x.ticks(4)).join("text").attr("class", "tick-label").attr("x", x).attr("y", h - 6).attr("text-anchor", "middle").text(F.short);
    rows.forEach((r, i) => {
      const yy = m.t + i * groupH;
      g.append("text").attr("class", "lbl-strong").attr("x", m.l - 8).attr("y", yy + bh + 4).attr("text-anchor", "end").text(F.int(r.v));
      g.append("path").attr("class", "f-context").attr("d", MBS.chartHelpers.barPath(x(0), x(r.today), yy, bh));
      g.append("text").attr("class", "lbl").attr("x", x(r.today) + 6).attr("y", yy + bh - 4).text(F.about(r.today));
      g.append("path").attr("fill", "url(#hatch-focus)").attr("class", "hatch-cell").attr("d", MBS.chartHelpers.barPath(x(0), x(r.first), yy + bh + 3, bh));
      g.append("text").attr("class", "lbl-strong").attr("x", x(r.first) + 6).attr("y", yy + 2 * bh - 1).text(F.about(r.first));
    });
    return null;
  }

  function references(keys) {
    const S = MBS.data.sources;
    return keys.map(k => S[k]).filter(Boolean).map(s => s.apa).sort();
  }

  function build() {
    const d = MBS.data, Ct = C(), H = Hh();
    MBS.ui.ensureDefs();
    const app = document.getElementById("app");
    app.textContent = "";
    const now = new Date();
    const prepared = now.toLocaleDateString("en-AU", { month: "long", year: "numeric" });
    const g = H.biggestGap(d);
    const r225 = MBS.sim.compute(d.sim.start, d.sim.skilled_share_pct, d);
    const r300 = MBS.sim.compute(d.sim.presets[d.sim.presets.length - 1], d.sim.skilled_share_pct, d);
    const skilled = d.q11.rows.find(x => x.key === "skilled"), everyone = d.q11.rows.find(x => x.key === "everyone");

    const bar = el("div", { class: "b-toolbar" },
      el("a", { class: "brand", href: "index.html" }, MBS.shell ? MBS.shell.logo() : null, el("span", null, Ct.meta.title)),
      el("span", { class: "spacer" }),
      el("a", { class: "btn", href: "index.html" }, el("span", { class: "lbl-long" }, "Back to the dashboard"), el("span", { class: "lbl-short" }, "Dashboard")),
      el("button", { class: "btn btn-primary", type: "button", onclick: () => window.print() }, el("span", { class: "lbl-long" }, "Print or save as PDF"), el("span", { class: "lbl-short" }, "Print / PDF")));

    const findings = Ct.report.findings.map(fd => fd.text(d)).filter(Boolean).slice(0, 6);
    const page1 = el("section", { class: "b-page", "aria-label": "Page 1" },
      el("header", { class: "b-head" },
        el("p", { class: "b-kicker", text: `${Ct.meta.title} · Briefing · ${prepared}` }),
        el("h1", { class: "b-title", text: Ct.meta.tagline }),
        el("p", { class: "b-sub", text: `What official data says about migration, skills and housing in Australia. Data to ${F.yearTo("Year to " + monthShort(d.data_to)).replace("year to ", "")}.` })),
      el("div", { class: "b-kpis" },
        kpi(F.int(d.q1.nom), `net overseas migration, ${d.q1.period_label}; down ${F.pct0(d.q2.fall_from_peak_pct)} from the record`, "official"),
        kpi(F.pct1(d.q3.skilled_net_share_pct), `of net overseas migration came on skilled visas, ${d.q3.year}`, "official"),
        kpi(`${(d.q5.gap / 1e6).toFixed(1)}m`, "people separate the plans by June 2030", "estimate"),
        kpi(F.k(d.q6.shortfall), "homes short of population growth since 2022", "estimate")),
      el("h2", { class: "b-h2", text: "What the data says" }),
      el("ol", { class: "b-findings" }, findings.map(t => el("li", null, MBS.rich(t)))),
      el("div", { class: "b-figs" },
        fig(1, `Down ${F.pct0(d.q2.fall_from_peak_pct)} from the record`, "Net overseas migration a year since 1950", "nomLine", d, undefined, ["official"], d.q2.sources),
        fig(2, "The parties' plans split from year one", "Net overseas migration a year under each plan", "planLines", d, undefined, ["official", "forecast", "illustration"], d.q4.sources)),
      el("h2", { class: "b-h2", text: "Limits" }),
      el("ul", { class: "b-limits" },
        el("li", { text: "Forecasts and projections can be wrong; official migration figures are revised as more travel records arrive." }),
        el("li", { text: "Skilled visas are a small share of all arrivals, and people can change jobs after they arrive." }),
        el("li", { text: "The scenario model and simulator are simple arithmetic with no feedback from the economy; they are illustrations, not forecasts." }),
        el("li", { text: "One Nation gave no size for its net-negative years, so that range is our illustration from the party's own figures." })),
      el("p", { class: "b-page-foot", text: `Draft for review · ${Ct.meta.title}, version ${d.version} · Page 1 of 2` }));

    const page2 = el("section", { class: "b-page", "aria-label": "Page 2" },
      el("div", { class: "b-figs" },
        fig(3, `${Ct.helpers.cap(Ct.WORD[g.id])}: ${g.trained_per_100} trained and ${g.visas_per_100} skilled visas per 100 needed`, "Temporary skilled visas (blue) and people trained here (grey) per 100 workers needed a year", "visas", d, undefined, ["estimate"], d.q9.sources_q10.concat(d.q9.sources_q9)),
        fig(4, "Mix matters as much as size", "Skilled workers a year reaching jobs on the shortage list, by size of net overseas migration", sizeMix, d, undefined, ["illustration"], d.sim.sources)),
      el("h2", { class: "b-h2", text: "What this means for skilled migration planning" }),
      el("ul", { class: "b-points" },
        el("li", null, MBS.rich(`**Size and skill are separate levers.** About ${F.pct0(d.sim.short_share_of_visas_pct)} of temporary skilled visas go to jobs on the shortage list. In our illustration, aiming every skilled place at short jobs sends about ${F.about(r225.firstShort)} skilled workers a year to them at ${F.int(d.sim.start)}, against ${F.about(r300.todayShort)} at ${F.int(d.sim.presets[d.sim.presets.length - 1])} with today's mix.`)),
        el("li", null, MBS.rich(`**The gaps are specific.** ${Ct.helpers.cap(Ct.WORD[g.id])} has the largest gap we can measure: ${g.trained_per_100} trained here and ${g.visas_per_100} skilled visas for every 100 workers needed a year.`)),
        el("li", null, MBS.rich(`**Housing is a shared constraint.** The population has grown faster than homes were finished since the ${d.q6.shortfall_from}: about ${F.k(d.q6.shortfall)} homes behind, whichever plan is chosen next.`)),
        el("li", null, MBS.rich(`**Skilled migrants mostly work.** ${F.round0(skilled.pct)} in 100 skilled visa migrants aged ${d.q11.ages} have a job, against ${F.round0(everyone.pct)} in 100 overall (${d.q11.period}). This measures any job, not the job they were selected for.`))),
      el("h2", { class: "b-h2", text: "Sources" }),
      el("div", { class: "b-refs" }, references(["abs_pop", "abs_hist", "abs_om", "abs_build", "abs_mso", "jsa_osl", "jsa_proj", "ha_bp0014", "ncver", "edu", "budget", "abs_census_hh"])
        .map(t => el("p", { text: t }))),
      el("p", { class: "b-page-foot", text: `Skills, not nationality: this work looks at jobs, skills and places, never at where people come from. Made by ${Ct.meta.author}. Full report, tables and methods: the Migration by Skill dashboard. Page 2 of 2` }));

    app.appendChild(bar);
    app.appendChild(el("main", { class: "b-pages", id: "main" }, page1, page2));
    document.querySelectorAll(".b-fig").forEach(f => f._draw());
  }
  function monthShort(p) { const [y, m] = p.split("-"); return `${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][+m - 1]} ${y}`; }
  MBS.buildBrief = build;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build); else build();
})();
