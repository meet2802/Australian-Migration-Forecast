/* Migration by Skill: the Data and methods page. Built from data/data-methods.js (tables, dictionary, assumptions,
   row counts, the two extra analyses, the inventory) plus the story and explore data for sources. */
(function () {
  "use strict";
  const MBS = (window.MBS = window.MBS || {});
  const { el } = MBS.util;
  const F = MBS.fmt;

  function table(caption, columns, rows, opts) {
    const box = el("div", { class: "table-view", style: opts && opts.max ? `max-height:${opts.max}px` : null });
    MBS.ui.fillTable(box, { caption, columns, rows });
    return box;
  }
  function section(id, title, ...kids) {
    return el("section", { id, "aria-labelledby": `${id}-h` }, el("h2", { id: `${id}-h`, text: title }), ...kids);
  }
  function p(text) { return el("p", { text }); }

  function apaDate(d) {
    const t = new Date(d + "T00:00:00");
    if (isNaN(t)) return "n.d.";
    return `${t.getFullYear()}, ${t.toLocaleDateString("en-US", { month: "long" })} ${t.getDate()}`;
  }
  function apaAuthor(name) {
    const n = String(name).replace(/\s*\((party)\)\s*/i, "").replace(/\s*\(.*\)\s*$/, "").trim();
    const parts = n.split(/\s+/);
    if (parts.length < 2 || /^(One Nation|Australian Greens|ACTU|Australian Workers' Union)$/i.test(n)) return n;
    const and = n.split(/\s+and\s+/);
    if (and.length > 1) return and.map(apaAuthor).join(", & ");
    return `${parts[parts.length - 1]}, ${parts.slice(0, -1).map(x => x[0] + ".").join(" ")}`;
  }

  function references() {
    const refs = new Map();
    const add = (text, url) => { const k = url || text; if (!refs.has(k)) refs.set(k, { text, url }); };
    for (const s of Object.values(MBS.data.sources)) if (s.apa) add(s.apa, s.url);
    for (const pl of MBS.data.q4.plans) for (const s of pl.sources) {
      const m = /^(.*?) \((\d{4})(?:, ([^)]*))?\), (.*)$/.exec(s.text);
      add(m ? `${m[1]}. (${m[2]}${m[3] ? ", " + m[3] : ""}). ${m[4]}.` : `${s.text}.`, s.url);
    }
    if (MBS.explore) for (const c of MBS.explore.claims) add(`${apaAuthor(c.speaker)} (${apaDate(c.date)}). ${c.source}.`, c.url);
    return Array.from(refs.values()).sort((a, b) => a.text.localeCompare(b.text));
  }

  function build() {
    MBS.ui.initTheme();
    MBS.ui.ensureDefs();
    const M = MBS.methods, D = MBS.data, C = MBS.content;
    const app = document.getElementById("app");
    app.textContent = "";
    app.appendChild(MBS.shell.header({ page: "methods" }));
    const names = { numbers: "Kinds of numbers", figures: "Figures", tables: "Downloads", dictionary: "Column dictionary", assumptions: "Assumptions", rows: "Row counts", a1: "Visas and shortages", a2: "Model sensitivity", limits: "Limits", sources: "Sources", ai: "How AI helped", inventory: "Source files" };
    app.appendChild(el("div", { class: "methods-head" }, el("div", { class: "wrap-wide" },
      el("p", { class: "sec-kicker", style: "color:var(--band-accent)", text: "Appendix B" }),
      el("h1", { class: "sec-title", text: "Data and methods" }),
      el("p", { class: "sec-lede", text: "Everything behind the dashboard: the tables, what every column means, each assumption, how many rows each step kept, two extra analyses, the limits and the sources." }),
      el("p", { class: "draft-note" }, el("strong", null, "Draft for review."), `Version ${D.version}. Data to ${F.yearTo("Year to " + mon(D.data_to)).replace("year to ", "")}. ${C.meta.status}`),
      el("nav", { class: "methods-nav", "aria-label": "On this page" }, Object.entries(names).map(([id, t]) => el("a", { href: `#${id}`, text: t }))))));
    const main = el("main", { class: "wrap-wide methods", id: "main" });
    app.appendChild(main);

    // kinds of numbers
    main.appendChild(section("numbers", "Kinds of numbers",
      p("Every chart carries a badge saying what kind of numbers it shows. Inside charts, the line style says the same thing: solid for official data, dashed for forecasts and plans, lighter for our estimates where they sit beside official data, and hatched for our illustrations."),
      el("ul", null, Object.entries(C.types).map(([k, t]) => el("li", null, el("span", { class: "badge", style: "margin-right:8px" }, MBS.ui.typeSwatch(k), t.label), t.note))),
      p("Colours carry one meaning each across the whole dashboard: grey for context, blue for the focus, orange for a comparison point, a purple-to-yellow scale (viridis) for continuous values on the state map, and one blue ramp for claim verdicts. Red and green are not used.")));

    // figures
    main.appendChild(section("figures", "Figures",
      p("Every chart, its data and its review status. Charts stay drafts until approved, then locked."),
      table("Figures", [{ key: "figure_id", label: "Figure" }, { key: "question", label: "Question or view" }, { key: "chart_form", label: "Chart" },
        { key: "data_tables", label: "Data" }, { key: "number_types", label: "Kinds of numbers" }, { key: "status", label: "Status" }, { key: "notes", label: "Notes" }], M.figures)));

    // downloads
    main.appendChild(section("tables", "Tables you can download",
      p("Copies of the tables behind the charts, as CSV files. Column meanings are in the dictionary below and in data_dictionary.csv."),
      table("Downloads", [{ key: "file", label: "File", fmt: v => v }, { key: "what", label: "What it holds" }, { key: "rows", label: "Rows", num: true },
        { key: "columns", label: "Columns", num: true }, { key: "kb", label: "Size (KB)", num: true }], M.tables)));
    main.querySelectorAll("#tables tbody tr").forEach((tr, i) => {
      const th = tr.querySelector("th");
      const f = M.tables[i].file;
      th.textContent = "";
      th.appendChild(el("a", { href: `downloads/${f}`, download: f, text: f }));
    });

    // dictionary
    const dcols = M.dictionary.columns;
    const drows = M.dictionary.rows.map(r => Object.fromEntries(dcols.map((c, i) => [c, r[i]])));
    const dbox = el("div");
    const search = el("input", { type: "search", placeholder: "Search columns, e.g. shortage, homes, visa", "aria-label": "Search the column dictionary" });
    const draw = () => {
      const q = search.value.toLowerCase().trim();
      const hit = drows.filter(r => !q || Object.values(r).join(" ").toLowerCase().includes(q));
      dbox.textContent = "";
      dbox.appendChild(el("p", { class: "q-num", text: `${hit.length} of ${drows.length} columns${hit.length > 60 ? " (first 60 shown)" : ""}` }));
      dbox.appendChild(table("Column dictionary", [{ key: "table", label: "Table" }, { key: "column", label: "Column" }, { key: "meaning", label: "Meaning" },
        { key: "source", label: "Source" }, { key: "period", label: "Period" }, { key: "number_type", label: "Kind of number" }], hit.slice(0, 60), { max: 520 }));
    };
    search.addEventListener("input", draw);
    main.appendChild(section("dictionary", "What each column means", p("Every column in every table the project builds, with its source, period and the kind of number it is. The downloadable tables are a subset."), search, dbox));
    draw();

    // assumptions
    main.appendChild(section("assumptions", "Assumptions in our model",
      p("The scenario model is plain arithmetic on official data: each plan's net overseas migration, plus births minus deaths and moves between states, gives population; population growth divided by people per home gives homes needed. Every assumption is listed with the option we did not take."),
      table("Assumptions", [{ key: "assumption", label: "Assumption" }, { key: "value", label: "Value" }, { key: "unit", label: "Unit" },
        { key: "number_type", label: "Kind" }, { key: "why", label: "Why" }, { key: "alternative_not_taken", label: "Not taken" }, { key: "source", label: "Source" }], M.assumptions)));

    // row counts
    const byScript = {};
    for (const r of M.row_counts) (byScript[r.script] = byScript[r.script] || []).push(r);
    main.appendChild(section("rows", "Rows at each step",
      p("How many rows each build script read, kept and wrote. Every output table is logged; the scripts behind the story also log their reading, filtering and joining steps."),
      Object.entries(byScript).map(([sname, rows]) => el("details", null, el("summary", { text: `${sname} (${rows.length} steps)` }),
        table(sname, [{ key: "step_no", label: "Step", num: true }, { key: "step", label: "What it does" }, { key: "table", label: "File" },
          { key: "rows", label: "Rows", num: true, fmt: v => F.int(+v) }, { key: "columns", label: "Columns", num: true }, { key: "note", label: "Note" }], rows)))));

    // A1
    const a1 = M.analyses.a1;
    if (a1) {
      const terms = a1.regression.terms.map(t => ({ ...t, term: ({ intercept: "Intercept", short_now: "Short now (1 = yes)", growth_5y_pct: "Projected growth to 2030 (per percentage point)", skill_2: "Skill level 2 (vs 1)", skill_3: "Skill level 3 (vs 1)", skill_4: "Skill level 4 (vs 1)", skill_5: "Skill level 5 (vs 1)" })[t.term] || t.term }));
      main.appendChild(section("a1", "Extra analysis 1: do visas go where the shortages are?",
        el("p", { class: "lead", style: "font-size:18px", text: a1.plain_words }),
        p(`Unit: ${a1.unit}. ${a1.occupations} occupations rated on the 2025 shortage list (${a1.occupations_not_rated_left_out} not rated were left out). Measure: ${a1.visa_measure}.`),
        el("ul", null,
          el("li", { text: `Share of visas to jobs on the shortage list: ${a1.share_of_visas_to_short_occupations_pct}%. Share of workers in those jobs: ${a1.share_of_workers_in_short_occupations_pct}%.` }),
          el("li", { text: `Visas per 1,000 workers: ${a1.visas_per_1000_workers_short} in short jobs, ${a1.visas_per_1000_workers_not_short} in other jobs. Medians: ${a1.median_visas_per_1000_short} and ${a1.median_visas_per_1000_not_short}.` }),
          el("li", { text: `Rank correlation (Spearman) of visas per 1,000 workers with shortage status: ${a1.spearman_visas_vs_short.rho}; with projected growth: ${a1.spearman_visas_vs_growth.rho} (n = ${a1.spearman_visas_vs_growth.n}).` }),
          el("li", { text: `${a1.occupations_with_no_visas_pct}% of these occupations had no temporary skilled visas in 2025-26.` })),
        el("h3", { text: "Regression" }),
        p(`Outcome: ${a1.regression.outcome}. Ordinary least squares with ${a1.regression.standard_errors} standard errors; n = ${a1.regression.n}, R² = ${a1.regression.r2}. P-values use a large-sample normal approximation.`),
        table("Regression of log(1 + visas per 1,000 workers)", [{ key: "term", label: "Term" }, { key: "coef", label: "Coefficient", num: true, fmt: v => v.toFixed(3) },
          { key: "se_hc1", label: "Robust SE", num: true, fmt: v => v.toFixed(3) }, { key: "ci95_low", label: "95% CI low", num: true, fmt: v => v.toFixed(3) },
          { key: "ci95_high", label: "95% CI high", num: true, fmt: v => v.toFixed(3) }, { key: "p_approx", label: "p (approx.)", num: true, fmt: v => String(v) }], terms),
        p(`Being on the shortage list goes with (1 + visas per 1,000 workers) about ${Math.round(a1.short_effect_pct)}% higher (95% CI ${a1.short_effect_pct_ci95[0]}% to ${a1.short_effect_pct_ci95[1]}%), holding growth and skill level fixed. Restricted to skill levels 1 to 3 (n = ${a1.regression_skill_1_to_3.n}), the shortage coefficient is ${a1.regression_skill_1_to_3.terms.find(t => t.term === "short_now").coef.toFixed(3)}.`),
        table("Visas by skill level", [{ key: "skill_level", label: "Skill level", fmt: v => String(v) }, { key: "occupations", label: "Occupations", num: true },
          { key: "visa_grants", label: "Visas granted", num: true }, { key: "workers", label: "Workers", num: true }, { key: "visas_per_1000_workers", label: "Visas per 1,000 workers", num: true, fmt: v => v.toFixed(2) }], a1.by_skill_level),
        el("h3", { text: "Limits" }), el("ul", null, a1.limits.map(t => el("li", { text: t }))),
        el("p", null, "Data: ", el("a", { href: "downloads/visas_vs_shortages.csv", download: "visas_vs_shortages.csv", text: "visas_vs_shortages.csv" }), " (one row per occupation).")));
    }

    // A2
    const a2 = M.analyses.a2;
    if (a2) {
      const planName = { "Government (Labor)": "Government", "Coalition (Liberal-National)": "Coalition", "One Nation": "One Nation", "Reference: latest year held flat (not a plan)": "If the last 12 months continued" };
      const testName = { central: "As published", people_per_home: "People per home", working_age_share: "Working-age share of migrants", births_minus_deaths: "Births minus deaths (× central)", opposition_plans_start_2027_28: "Opposition plans start in 2027-28" };
      const rows = a2.filter(r => r.case === "central").map(r => ({ ...r, plan: planName[r.plan] || r.plan, test: testName[r.test] || r.test }));
      main.appendChild(section("a2", "Extra analysis 2: how sensitive is the model?",
        p("We re-ran the scenario model changing one assumption at a time. Central cases only; the full table, with low and high cases, is in model_sensitivity.csv."),
        table("Model results when one assumption changes (Australia, central cases)", [{ key: "test", label: "Change" }, { key: "setting", label: "Setting" }, { key: "plan", label: "Plan" },
          { key: "measure_label", label: "Result" }, { key: "value", label: "Value", num: true }, { key: "central_value", label: "As published", num: true }, { key: "difference", label: "Difference", num: true, fmt: v => F.signed(v) }], rows, { max: 520 }),
        el("p", null, "Data: ", el("a", { href: "downloads/model_sensitivity.csv", download: "model_sensitivity.csv", text: "model_sensitivity.csv" }), ".")));
    }

    // limits
    main.appendChild(section("limits", "Limits",
      el("ul", null, [
        "Forecasts and projections (Treasury, Jobs and Skills Australia) can be wrong; the economy, policy and technology change.",
        "Official migration figures arrive with a lag and are revised as more travel records come in.",
        "Skilled visas are a small share of all arrivals: most people arrive on student, working holiday, visitor or family visas, or are citizens coming home.",
        "People change jobs after they arrive, so a visa granted for one occupation does not mean the person stays in it.",
        "The shortage list says whether an occupation is short, not how short. Some occupations were not rated.",
        "Local training is counted only where apprenticeships or university courses map to an occupation.",
        "The scenario model is simple arithmetic with no feedback: births, deaths, departures and building do not react to the plans.",
        "Homes finished are gross: homes knocked down are not subtracted. 2.5 people per home is the 2021 Census average, not the household size of new arrivals.",
        `One Nation gave no size for its net-negative years; the range shown is our illustration from the party's own ${F.int(D.q4.plans.find(x => x.id === "on").party_cut)} figure.`,
        "Migrant job outcomes come from the 2021 Census, taken during Covid lockdowns.",
        "We check what claims say, not motives, and not whether a policy is a good idea."
      ].map(t => el("li", { text: t })))));

    // sources
    main.appendChild(section("sources", "Sources (APA 7th)", el("div", { class: "refs" }, references().map(r => el("p", null, r.text, " ", r.url ? el("a", { href: r.url, target: "_blank", rel: "noopener", text: r.url }) : null)))));

    // AI
    main.appendChild(section("ai", "How AI helped",
      p("Claude, an AI model made by Anthropic, helped write the data pipeline and this dashboard's code, ran checks of every figure against the source tables, and drafted wording. Every number comes from the cited sources through the scripts in the analysis folder, which anyone can re-run. The project's author reviews each chart and each sentence before it is approved; the figures list shows what is still a draft.")));

    // inventory
    main.appendChild(section("inventory", "Source files",
      el("details", null, el("summary", { text: `Every source file in the project folder (${M.inventory.length})` }),
        table("Source files", [{ key: "file", label: "File" }, { key: "source", label: "Source" }, { key: "what_it_is", label: "What it is" }, { key: "status", label: "Status" }, { key: "checked_on", label: "Checked" }], M.inventory, { max: 600 }))));

    app.appendChild(MBS.shell.footer());
    if (location.hash) { const t = document.getElementById(location.hash.slice(1)); if (t) t.scrollIntoView(); }
  }
  function mon(p) { const [y, m] = p.split("-"); return `${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][+m - 1]} ${y}`; }
  MBS.buildMethods = build;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build); else build();
})();
