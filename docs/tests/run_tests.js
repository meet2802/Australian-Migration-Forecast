/* Migration by Skill: headless tests. Must pass 100% before any release.
   Checks the story (every chapter, step and chart scene), the simulator (its arithmetic and its charts), the report
   (key numbers, findings, every exhibit with its table, About panel, source and CSV), the interactive tools, the
   Models appendix (including the live self-check), the brief and the methods page; that the numbers match the
   pipeline's tables; that the plan model reproduces the pipeline; and that no em dash appears anywhere.
   Run from docs/tests:  npm install   then   node run_tests.js */
"use strict";
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const DASH = path.resolve(__dirname, "..");
const ROOT = path.resolve(DASH, "..");
let pass = 0, fail = 0;
const fails = [];
function ok(cond, name, detail) {
  if (cond) pass += 1;
  else { fail += 1; fails.push(`${name}${detail !== undefined ? ": " + detail : ""}`); }
}
function near(a, b, tol) { return Math.abs(Number(a) - Number(b)) <= (tol == null ? 0.5 : tol); }
const words = s => String(s).trim().split(/\s+/).filter(Boolean).length;
const bad = t => /undefined|NaN|null|\{|\}/.test(t);
const sleep = ms => new Promise(r => setTimeout(r, ms));

// ---------------------------------------------------------------- CSV reader (quoted fields, commas, newlines)
function readCsv(rel) {
  const p = path.join(ROOT, rel);
  if (!fs.existsSync(p)) return null;
  const txt = fs.readFileSync(p, "utf8");
  const rows = [];
  let row = [], field = "", q = false;
  for (let i = 0; i < txt.length; i++) {
    const c = txt[i];
    if (q) {
      if (c === '"' && txt[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') q = false;
      else field += c;
    } else if (c === '"') q = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; }
    else if (c !== "\r") field += c;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  const head = rows.shift();
  return rows.filter(r => r.length === head.length).map(r => Object.fromEntries(head.map((h, i) => [h, r[i]])));
}

async function load(page, ready) {
  const errors = [];
  const vc = new VirtualConsole();
  vc.on("jsdomError", e => errors.push(String(e && e.message || e)));
  vc.on("error", e => errors.push(String(e)));
  const url = "file://" + path.join(DASH, page);
  const dom = await JSDOM.fromFile(path.join(DASH, page), {
    url, runScripts: "dangerously", resources: "usable", pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      w.Element.prototype.scrollIntoView = function () {};
      w.HTMLElement.prototype.focus = function () {};
      w.scrollTo = function () {};
      w.print = function () {};
    }
  });
  await new Promise(res => dom.window.addEventListener("load", res));
  for (let i = 0; i < 80 && ready && !ready(dom.window); i++) await sleep(50);
  await sleep(300);
  return { dom, w: dom.window, d: dom.window.document, errors };
}

async function main() {
  // ================================================================ index: story, simulator, report
  const { w, d, errors } = await load("index.html", win => win.document.querySelector("#models-grid .exhibit") && win.document.querySelector("#ex17-tool .search"));
  const M = w.MBS, D = M.data, C = M.content, F = M.fmt;
  ok(errors.length === 0, "index.html loads without script errors", errors.join(" | "));

  // ---------------------------------------------------------------- frame: nav, guide, theme
  ok(d.querySelectorAll(".topbar .nav a").length === 6, "Top bar links: Story, Simulator, Report, Models, Brief, Methods");
  ok(!!d.querySelector(".skip-link[href='#report']"), "Skip link straight to the report");
  const guide = d.getElementById("welcome-modal");
  ok(!!guide && !guide.hidden, "Welcome guide opens with the page");
  ok(guide && guide.getAttribute("role") === "dialog" && guide.getAttribute("aria-modal") === "true", "Welcome guide is a labelled dialog");
  ok(guide && guide.querySelectorAll(".modal-list li").length >= 6, "Welcome guide explains each part of the page");
  ok(guide && guide.querySelectorAll(".modal-list .badge").length === 4, "Welcome guide shows the four kinds of numbers");
  d.getElementById("guide-close").click();
  ok(guide.hidden, "Start exploring closes the guide");
  await sleep(250);
  d.getElementById("help-btn").click();
  ok(!guide.hidden, "The ? button reopens the guide");
  guide.dispatchEvent(new w.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
  ok(guide.hidden, "Escape closes the guide");
  const tt = d.querySelector(".topbar .theme-toggle");
  ok(!!tt && !tt.closest("details"), "Light/dark switch sits in the top bar, outside the menu");
  if (tt) {
    const before = tt.getAttribute("aria-pressed");
    tt.click();
    ok(d.documentElement.getAttribute("data-theme") === (before === "true" ? "light" : "dark"), "Light/dark switch changes the theme");
    ok(tt.getAttribute("aria-pressed") !== before, "Light/dark switch reports its state");
    tt.click();
  }

  // ---------------------------------------------------------------- the opening
  const h1 = d.getElementById("hero-h");
  ok(h1 && h1.getAttribute("aria-label").startsWith(F.about(D.q1.per_day)), "Opening: headline says how many a day", h1 && h1.getAttribute("aria-label"));
  ok(d.querySelector(".hero-num").textContent.replace(/,/g, "") === String(Math.round(D.q1.per_day)), "Opening: the big number is the people a day");
  ok(d.querySelectorAll(".hero-dots circle").length === Math.round(D.q1.per_day), "Opening: one dot per person a day", d.querySelectorAll(".hero-dots circle").length);
  ok(d.querySelector(".hero-note").textContent.includes(F.int(D.q1.nom)), "Opening: note gives the exact 12-month figure");

  // ---------------------------------------------------------------- the story: chapters, steps, scenes
  const chs = C.chapters;
  ok(chs.length === 8, "Story: eight chapters", chs.length);
  for (const ch of chs) {
    const sec = d.getElementById(ch.id);
    ok(!!sec, `${ch.id}: chapter exists`);
    if (!sec) continue;
    const title = sec.querySelector(".opener-title").textContent, stat = sec.querySelector(".opener-big").textContent, lab = sec.querySelector(".opener-lab").textContent;
    ok(title.length > 5 && !bad(title) && words(title) <= 8, `${ch.id}: opener question filled (8 words or fewer)`, title);
    ok(stat.length > 0 && !bad(stat) && words(stat) <= 3, `${ch.id}: opener big number filled`, stat);
    ok(lab.length > 10 && !bad(lab), `${ch.id}: opener label filled`, lab);
    if (ch.claims) {
      ok(sec.querySelectorAll(".card").length === 4, `${ch.id}: four claim cards`);
      ok(!bad(sec.querySelector(".claims-intro").textContent), `${ch.id}: intro filled`);
      continue;
    }
    const steps = sec.querySelectorAll(".step");
    ok(steps.length === ch.steps.length, `${ch.id}: every step drawn`, `${steps.length} of ${ch.steps.length}`);
    steps.forEach((st, i) => {
      const t = st.textContent;
      ok(t.length > 20 && !bad(t) && words(t) <= 45, `${ch.id} step ${i + 1}: text filled (45 words or fewer)`, `${words(t)}: ${t}`);
    });
    // walk every step: the right chart shows, in the right scene
    for (let i = 0; i < ch.steps.length; i++) {
      M.story.activate(ch.id, i);
      const st = ch.steps[i];
      const lay = M.story.layers[ch.id][st.layer];
      ok(lay.fig.classList.contains("is-on") && lay.fig.getAttribute("aria-hidden") === "false", `${ch.id} step ${i + 1}: its chart is shown`);
      ok(Object.values(M.story.layers[ch.id]).filter(l => l.fig.classList.contains("is-on")).length === 1, `${ch.id} step ${i + 1}: only one chart shown`);
      ok(d.querySelectorAll(`#${ch.id} .step.is-active`).length === 1 && d.querySelector(`#${ch.id} .step[data-i="${i}"]`).classList.contains("is-active"), `${ch.id} step ${i + 1}: the step is marked active`);
      const svg = lay.host.querySelector("svg[role='img']");
      ok(!!svg && svg.getAttribute("aria-label").length > 20 && svg.querySelectorAll("path, rect, circle, line").length > 3, `${ch.id} step ${i + 1}: chart drawn with a label`);
    }
    for (const lay of Object.values(M.story.layers[ch.id])) {
      ok(lay.fig.querySelector(".layer-title").textContent.length > 10 && !bad(lay.fig.querySelector(".layer-title").textContent), `${ch.id} ${lay.key}: chart title`);
      ok(lay.fig.querySelectorAll(".badge").length >= 1, `${ch.id} ${lay.key}: number-type badge`);
    }
  }
  // scenes that change what's drawn
  M.story.activate("ch1", 1);
  await sleep(450);
  const nomG = d.querySelectorAll("#ch1-nom svg > g > g[opacity]");
  ok(Array.from(nomG).some(g => g.getAttribute("opacity") === "1" && /more left/.test(g.textContent)), "ch1: the 2020-21 step labels the year more people left");
  M.story.activate("ch1", 3);
  await sleep(450);
  ok(/−47%|−\d+%/.test(Array.from(d.querySelectorAll("#ch1-nom svg > g > g[opacity='1']")).map(g => g.textContent).join(" ")), "ch1: the 'now' step shows the fall from the record");
  M.story.activate("ch2", 4);
  const lit = d.querySelectorAll("#ch2-waffle rect.sq.f-focus").length;
  ok(lit === D.q3.groups.find(g => g.key === "perm_skilled").squares, "ch2: the skilled step lights only permanent skilled squares", lit);
  M.story.activate("ch2", 1);
  ok(d.querySelectorAll("#ch2-waffle rect.sq.f-focus").length === D.q3.citizen_squares, "ch2: the citizens step lights the citizens");
  M.story.activate("ch3", 1);
  ok(/Government: 225k/.test(d.querySelector("#ch3-plans svg").textContent), "ch3: lighting the Government plan labels its value without a clash");
  M.story.activate("ch4", 4);
  ok(d.querySelector("#ch4-tiles .tile[aria-pressed='true']") && d.querySelector("#ch4-tiles .tile[aria-pressed='true']").textContent.includes("NT"), "ch4: the last step rings the highest state");
  M.story.activate("ch5", 0);
  ok(d.querySelectorAll("#ch5-short path.f-focus").length === 0, "ch5: the first step shows every group in grey");
  M.story.activate("ch5", 1);
  ok(d.querySelectorAll("#ch5-short path.f-focus").length === D.q7.top.length, "ch5: the second step lights the top groups");
  const ch3 = d.querySelector("#ch3 .step[data-i='5']").textContent;
  ok(ch3.includes(F.m1(D.q5.min)) && ch3.includes(F.m1(D.q5.max)) && ch3.includes(String(Math.round(D.q5.gap_mcgs))), "ch3: population step gives the range and the MCG gap", ch3);
  ok(d.querySelector("#ch4 .step[data-i='2']").textContent.includes(F.k(D.q6.shortfall)), "ch4: the shortfall step says the homes behind");
  ok(d.querySelectorAll(".bl-card").length === 3 && Array.from(d.querySelectorAll(".bl-card")).every(c => !bad(c.textContent)), "Bottom line: three filled cards");

  // ---------------------------------------------------------------- the simulator
  const S = D.sim;
  const nbv = readCsv("analysis/nom_by_visa_group.csv").filter(r => r.state === "AUS" && r.financial_year === S.year);
  const net = k => +nbv.find(r => r.visa_group === k).net;
  const tot = +nbv.find(r => r.row_type === "total").net;
  ok(near(S.skilled_share_pct, 100 * (net("Skilled (permanent)") + net("Skilled (temporary)")) / tot, 0.01), "Simulator: skilled share matches the ABS table", S.skilled_share_pct);
  ok(near(D.q3.net_total, tot) && near(D.q3.skilled_net, net("Skilled (permanent)") + net("Skilled (temporary)")), "Net migration by visa matches the ABS table");
  const mo = readCsv("analysis/migrant_outcomes_by_stream.csv");
  ok(S.employment_recent_pct === D.q11.skilled_recent_pct, "Simulator: employment rate is the recent skilled migrants' rate");
  const a1s = JSON.parse(fs.readFileSync(path.join(ROOT, "analysis/visas_vs_shortages_summary.json"), "utf8"));
  ok(S.short_share_of_visas_pct === a1s.share_of_visas_to_short_occupations_pct, "Simulator: today's share to short jobs comes from the visas analysis");
  const r = M.sim.compute(225000, S.skilled_share_pct);
  const workers = 225000 * S.skilled_share_pct / 100 * S.working_age_share * S.employment_recent_pct / 100;
  ok(near(r.workers, workers, 0.01) && near(r.todayShort, workers * S.short_share_of_visas_pct / 100, 0.01) && near(r.firstShort, workers, 0.01), "Simulator: arithmetic follows the agreed method");
  ok(near(r.groups.reduce((a, g) => a + g.today, 0), workers, 0.5) && near(r.groups.reduce((a, g) => a + g.first, 0), workers, 0.5), "Simulator: both mixes share out every skilled worker");
  ok(r.groups.filter(g => g.short_pct === 0).every(g => g.first === 0), "Simulator: skills-first sends nobody to groups with no short jobs");
  ok(near(r.matchSize, 225000 * S.short_share_of_visas_pct / 100, 0.01), "Simulator: the matching size is right");
  ok(M.sim.compute(0, S.skilled_share_pct).workers === 0, "Simulator: zero migration gives zero skilled workers");
  const sh = d.querySelector(".sim-headline").textContent;
  ok(sh.includes(F.int(S.start)) && sh.includes(F.about(r.todayShort)) && sh.includes(F.about(r.firstShort)), "Simulator: headline shows both mixes", sh);
  ok(d.querySelectorAll("#simulator .sim-stats .stat").length === 4, "Simulator: four figures");
  ok(d.querySelectorAll("#simulator .sim-fig svg[role='img']").length === 2, "Simulator: two charts drawn");
  ok(d.querySelectorAll("#sim-groups-table tbody tr").length === S.sectors.length, "Simulator: group table has every job group");
  ok(d.querySelectorAll("#sim-measured-table tbody tr").length === S.measured.length, "Simulator: training table has the measured groups");
  M.sim.set({ size: 130000 });
  await sleep(120);
  ok(d.querySelector(".sim-headline").textContent.includes("130,000"), "Simulator: changing the size updates the headline");
  M.sim.set({ mix: "today" });
  await sleep(120);
  ok(d.querySelector("[data-mix='today']").getAttribute("aria-pressed") === "true", "Simulator: the mix switch reports its state");
  ok(/today's mix/.test(d.querySelector("#sim-measured-table caption").textContent), "Simulator: the training chart follows the mix");
  ok(d.getElementById("sim-size").getAttribute("aria-valuetext").includes("130,000"), "Simulator: slider reads its value aloud");

  // ---------------------------------------------------------------- the report: key numbers and findings
  ok(d.querySelectorAll(".kpi").length === C.report.kpis.length && Array.from(d.querySelectorAll(".kpi")).every(k => !bad(k.textContent)), "Report: key numbers filled");
  const finds = d.querySelectorAll(".findings li");
  ok(finds.length >= 7, "Report: key findings", finds.length);
  ok(Array.from(finds).every(li => !bad(li.textContent) && !!d.getElementById(li.querySelector("a").getAttribute("href").slice(1))), "Report: every finding links to an exhibit that exists");
  ok(d.querySelectorAll(".report-toc a").length === C.report.sections.length, "Report: contents list every section");

  // ---------------------------------------------------------------- every exhibit
  const dl = fs.readdirSync(path.join(DASH, "downloads"));
  const allEx = C.exhibits.concat(C.models);
  for (const ex of allEx) {
    const art = d.getElementById(ex.id);
    ok(!!art, `${ex.id}: exhibit exists`);
    if (!art) continue;
    const t = art.querySelector(".ex-title").textContent;
    ok(t.length > 8 && !bad(t) && words(t) <= 16, `${ex.id}: takeaway title filled (16 words or fewer)`, `${words(t)}: ${t}`);
    ok(!bad(art.querySelector(".ex-sub").textContent), `${ex.id}: subtitle filled`);
    ok(art.querySelectorAll(".ex-foot .badge").length >= 1, `${ex.id}: number-type badge`);
    if (ex.csv) ok(dl.includes(ex.csv) && !!art.querySelector(`a[href='downloads/${ex.csv}']`), `${ex.id}: CSV link to a file that exists`, ex.csv);
    if (ex.tool) {
      ok(!art.querySelector(".tool-wait"), `${ex.id}: tool built`);
      continue;
    }
    const host = art.querySelector(".chart-host");
    const svg = host.querySelector("svg[role='img']");
    const label = svg ? svg.getAttribute("aria-label") : host.getAttribute("aria-label");
    ok(!!(svg || host.querySelector(".cards, .pipeline")), `${ex.id}: chart drawn`);
    ok(label && label.length > 20 && !bad(label), `${ex.id}: chart has screen-reader text`, label);
    const table = d.querySelector(`#${ex.id}-table table`);
    ok(table && table.querySelectorAll("tbody tr").length > 0 && !/undefined|NaN/.test(table.textContent), `${ex.id}: table view has rows`);
    const info = d.getElementById(`${ex.id}-info`);
    const ps = info ? Array.from(info.querySelectorAll("h3 + p")).map(p => p.textContent) : [];
    ok(ps.length >= 4 && ps.slice(0, 4).every(x => x.length > 10 && !/undefined|NaN/.test(x)), `${ex.id}: About panel has four filled parts`, ps.join(" / "));
  }
  ok(d.getElementById("ex1").querySelector(".ex-title").textContent.includes(F.k(D.q1.nom)), "Exhibit 1: title says the 12-month figure");
  ok(d.getElementById("ex9").querySelector(".ex-title").textContent.includes(F.k(D.q6.shortfall)), "Exhibit 9: title says the homes behind");
  ok(d.getElementById("ex7").querySelector(".ex-title").textContent.includes((D.q5.gap / 1e6).toFixed(1)), "Exhibit 7: title says the gap by 2030");
  ok(d.querySelectorAll("#ex3 svg rect.sq").length === 100, "Exhibit 3: 100 squares drawn");
  ok(d.querySelectorAll("#ex19 .card").length === 4, "Exhibit 19: four claim cards");
  d.querySelector("#ex6-chips [data-plan='coa']").click();
  ok(d.querySelector("#ex6-chips [data-plan='coa']").getAttribute("aria-pressed") === "true", "Exhibit 6: plan buttons light one plan");

  // ---------------------------------------------------------------- tools
  const T = M.report.tools;
  ok(T.job && T.state && T.plans && T.claims, "Report: all four tools built");
  const ji = d.getElementById("job-input");
  ji.value = "electrician"; ji.dispatchEvent(new w.Event("input"));
  ok(d.querySelectorAll("#job-input-list li").length > 0, "Find your job: search finds electricians");
  ji.dispatchEvent(new w.KeyboardEvent("keydown", { key: "Enter" }));
  await sleep(80);
  ok(/Electricians/.test(d.querySelector("#ex17 .job-card").textContent), "Find your job: card shows the job");
  ok(!bad(d.querySelector("#ex17 .job-card").textContent), "Find your job: card has no template errors");
  T.state.set({ state: "WA" });
  await sleep(80);
  const stTxt = d.querySelector("#ex11 .tool-out").textContent;
  ok(stTxt.includes("Western Australia") && stTxt.includes(F.int(D.q12.states.find(s => s.code === "WA").population)), "Your state: Western Australia's numbers", stTxt.slice(0, 160));
  ok(!bad(stTxt), "Your state: no template errors");
  T.plans.set({ plan: "on_central", state: "NSW" });
  await sleep(80);
  const plTxt = d.querySelector("#ex8 .tool-out").textContent;
  ok(plTxt.includes("New South Wales") && /our illustration/.test(plTxt) && !bad(plTxt), "Build your own plan: One Nation preset for NSW, with its caveat");
  const ends = [...d.querySelectorAll("#ex8 .end-label")].map(n => n.getAttribute("data-label"));
  ok(ends.length === 4 && ends.every(t => /: \d+\.\d\dm$/.test(t)) && ends.some(t => t.startsWith("One Nation (midpoint)")) && ends.some(t => t.startsWith("Last 12 months")),
    "Build your own plan: every population line is named where it ends", ends.join(" | "));
  const claimCards = () => d.querySelectorAll("#ex20 .tool .cards .card").length;
  ok(claimCards() === 6, "All claims: six shown at first", claimCards());
  d.querySelector("#ex20 .show-all").click();
  ok(claimCards() === M.explore.claims.length, "All claims: show all lists every claim", claimCards());
  T.claims.set({ side: "Greens" });
  ok(claimCards() === M.explore.claims.filter(c => c.side === "Greens").length, "All claims: side filter works");

  // ---------------------------------------------------------------- Models appendix
  const sc = M.selfCheckData();
  const worst = Math.max(...sc.map(p => Math.abs(p.diff)));
  ok(sc.length === 3 * readCsv("analysis/scenario_summary.csv").length && worst <= 1, `Models: live self-check covers every result and agrees within 1`, `${sc.length} results, worst ${worst}`);
  ok(d.getElementById("exA7").textContent.includes(`${sc.length} of ${sc.length}`), "Models: self-check exhibit reports the count");
  ok(d.querySelectorAll("#exA3 circle.dot-a1").length === M.explore.models.a1_rows.rows.length && M.explore.models.a1_rows.rows.length === a1s.occupations, "Models: scatter has every occupation in the analysis");
  ok(d.getElementById("exA8").textContent.includes(String(readCsv("docs/figures.csv").length)), "Models: pipeline counts the charts in figures.csv");

  // ---------------------------------------------------------------- numbers match the pipeline
  const pq = readCsv("tidy/abs_population_quarterly_by_state.csv").filter(r => r.state === "AUS");
  const noms = pq.map(r => +r.nom);
  const roll = noms.map((v, i) => i >= 3 ? noms[i] + noms[i - 1] + noms[i - 2] + noms[i - 3] : null);
  ok(near(D.q1.nom, roll[roll.length - 1]), "Q1: latest 12-month NOM matches the ABS table", `${D.q1.nom} vs ${roll[roll.length - 1]}`);
  ok(near(D.q1.mcgs, D.q1.nom / 100024, 0.006), "Q1: MCG count matches 100,024 per MCG");
  const peak = Math.max(...roll.filter(v => v != null));
  ok(near(D.q2.peak.v, peak), "Q2: record matches the ABS quarterly series", `${D.q2.peak.v} vs ${peak}`);
  const lr = readCsv("analysis/population_long_run_australia.csv");
  ok(near(D.q2.fy_2020_21, +lr.find(x => x.year === "2021").nom), "Q2: 2020-21 matches the long-run table");
  const vg = nbv;
  ok(near(D.q3.arrivals, +vg.find(x => x.row_type === "total").arrivals), "Q3: total arrivals match");
  ok(near(D.q3.permanent, +vg.find(x => x.visa_group === "Total permanent visas").arrivals), "Q3: permanent arrivals match");
  ok(D.q3.groups.reduce((a, g) => a + g.squares, 0) === 100, "Q3: squares add to 100");
  const paths = readCsv("analysis/scenario_nom_paths.csv");
  const gov = paths.filter(x => x.plan === "Government (Labor)" && x.period !== "2025-26").map(x => +x.nom);
  ok(JSON.stringify(D.q4.plans[0].nom) === JSON.stringify(gov), "Q4: Government path matches the Budget table");
  const summ = readCsv("analysis/scenario_summary.csv").filter(x => x.place === "AUS");
  const SS = (plan, c, col) => +summ.find(x => x.plan === plan && x.case === c)[col];
  ok(near(D.q5.plans[0].v, SS("Government (Labor)", "central", "population_june_2030")), "Q5: Government 2030 population matches");
  ok(near(D.q5.plans[2].low, SS("One Nation", "low", "population_june_2030")), "Q5: One Nation low case matches");
  ok(near(D.q5.today, SS("Government (Labor)", "central", "population_june_2026_est")), "Q5: start population matches");
  ok(near(D.q6.plans[0].v, SS("Government (Labor)", "central", "homes_needed_per_year")), "Q6: homes needed match");
  const hc = readCsv("analysis/scenario_housing_context.csv").find(x => x.place === "AUS" && x.window.startsWith("Since the borders"));
  ok(near(D.q6.shortfall, -hc.homes_completed_minus_needed), "Q6: shortfall matches the housing context table");
  const sec = readCsv("analysis/named_sector_summary_national.csv").filter(x => x.row_type === "Named sector");
  ok(sec.length === 24 && D.q7.sectors.length === 24, "Q7: 24 job groups");
  ok(sec.every(x => { const s = D.q7.sectors.find(y => y.id === x.sector_id); return s && near(s.short_pct, +x.jobs_in_shortage_pct, 0.05) && near(s.growth_pct, +x.projected_growth_5y_pct, 0.05); }),
    "Q7/Q8: shortage and growth shares match for every job group");
  ok(D.q9.rows.every(x => { const s = sec.find(y => y.sector_id === x.id); return near(x.trained_per_100, +s.local_training_per_100_needed) && near(x.visas_per_100, +s.visa_grants_per_100_needed); }),
    "Q9/Q10: per-100 values match");
  ok(S.sectors.every(x => { const s = sec.find(y => y.sector_id === x.id); return near(x.need, +s.new_workers_needed_per_year_est) && near(x.visa_grants, +s.visa_grants_primary); }), "Simulator: job groups match the sector table");
  const mt = mo.filter(x => x.arrival_group === "Total");
  ok(near(D.q11.rows[0].pct, +mt.find(x => x.population === "Permanent Skilled migrants").employment_to_population_pct, 0.05), "Q11: skilled employment rate matches");
  ok(near(D.q11.rows[1].pct, +mt.find(x => x.population === "Total population").employment_to_population_pct, 0.05), "Q11: everyone's rate matches");
  const hv = readCsv("analysis/housing_vs_population_by_state.csv");
  const last = hv.reduce((a, x) => (x.year_ending > a ? x.year_ending : a), "");
  ok(D.q12.states.every(s => near(s.people_per_home, +hv.find(x => x.state === s.code && x.year_ending === last).people_added_per_home_completed, 0.005)), "Q12: people per home match for every state");
  const fc = readCsv("analysis/fact_check_cards.csv");
  const testable = fc.filter(x => ["Accurate", "Mostly accurate", "Partly accurate", "Inaccurate"].includes(x.verdict));
  ok(D.q13.testable === testable.length && D.q13.accurate_or_mostly === testable.filter(x => /^(Accurate|Mostly accurate)$/.test(x.verdict)).length, "Q13: claim counts match");
  ok(Object.values(D.q13.counts_by_side).reduce((a, c) => a + Object.values(c).reduce((x, y) => x + y, 0), 0) === fc.length, "Claims by side add up to every claim");
  const vv = readCsv("analysis/visas_vs_shortages.csv");
  ok(vv.length === M.explore.models.a1_rows.rows.length, "Models: occupation rows match the analysis table");

  // ---------------------------------------------------------------- the plan model reproduces the pipeline
  const all = readCsv("analysis/scenario_summary.csv");
  const plans = { "Government (Labor)": "gov", "Coalition (Liberal-National)": "coa", "One Nation": "on", "Reference: latest year held flat (not a plan)": "ref" };
  let worstM = 0, n = 0;
  for (const x of all) {
    const pre = M.explore.model.presets.find(p => p.id === `${plans[x.plan]}_${x.case}`);
    const res = M.model.run(pre.nom, x.place);
    worstM = Math.max(worstM, Math.abs(res.pop_2030 - x.population_june_2030), Math.abs(res.homes_per_year - x.homes_needed_per_year),
      Math.abs(res.working_age_4y - x.working_age_people_added_via_nom_4y));
    n += 1;
  }
  ok(n === all.length && worstM <= 1, `Plan model reproduces all ${all.length} plan, case and place results within 1`, `worst gap ${worstM}`);

  // ---------------------------------------------------------------- whole page checks
  ok(!d.body.textContent.includes("—"), "No em dashes on the page");
  const srcFiles = ["content/content.js", "js/core.js", "js/charts.js", "js/charts-report.js", "js/shell.js", "js/story.js", "js/sim.js", "js/explore.js", "js/report.js",
    "js/guide.js", "js/main.js", "js/brief.js", "js/methods.js", "js/model.js", "index.html", "methods.html", "brief.html", "css/style.css"];
  ok(srcFiles.every(f => !fs.readFileSync(path.join(DASH, f), "utf8").includes("—")), "No em dashes in the dashboard's source files");
  ok(Array.from(d.querySelectorAll("button")).every(b => (b.textContent.trim() || b.getAttribute("aria-label"))), "Every button has a name");
  ok(Array.from(d.querySelectorAll("svg[role='img']")).every(s => s.getAttribute("aria-label")), "Every chart image has a label");
  ok(Array.from(d.querySelectorAll("a[target='_blank']")).every(a => /noopener/.test(a.getAttribute("rel") || "")), "External links open safely");
  const ids = Array.from(d.querySelectorAll("[id]")).map(n => n.id);
  const dup = ids.filter((x, i) => ids.indexOf(x) !== i);
  ok(dup.length === 0, "No repeated element ids", Array.from(new Set(dup)).slice(0, 10).join(", "));
  ok(Array.from(d.querySelectorAll("a[href^='#']")).every(a => { const h = a.getAttribute("href").slice(1).split("?")[0]; return !h || !!d.getElementById(h); }), "Every in-page link has a target");
  ok(dl.length >= 20, "Downloads folder has the tables", dl.length);

  // ================================================================ methods page
  const mp = await load("methods.html");
  ok(mp.errors.length === 0, "methods.html loads without script errors", mp.errors.join(" | "));
  for (const id of ["numbers", "figures", "tables", "dictionary", "assumptions", "rows", "a1", "a2", "limits", "sources", "ai", "inventory"]) {
    ok(!!mp.d.getElementById(id), `Methods: section ${id}`);
  }
  ok(mp.d.querySelectorAll(".topbar .nav a").length === 6, "Methods: same top bar as the dashboard");
  ok(mp.w.MBS.methods.dictionary.rows.length > 1000, "Methods: column dictionary loaded");
  ok(mp.d.querySelectorAll("#sources .refs p").length > 20, "Methods: reference list", mp.d.querySelectorAll("#sources .refs p").length);
  ok(mp.w.MBS.methods.row_counts.length > 50, "Methods: row counts at each step");
  ok(mp.d.querySelectorAll("#figures tbody tr").length === readCsv("docs/figures.csv").length, "Methods: figures table lists every chart");
  ok(!mp.d.body.textContent.includes("—"), "Methods: no em dashes");

  // ================================================================ brief
  const bp = await load("brief.html");
  ok(bp.errors.length === 0, "brief.html loads without script errors", bp.errors.join(" | "));
  ok(bp.d.querySelectorAll(".b-page").length === 2, "Brief: two pages");
  ok(bp.d.querySelectorAll(".b-fig svg[role='img']").length === 4, "Brief: four figures drawn");
  ok(bp.d.querySelectorAll(".b-kpi").length === 4 && Array.from(bp.d.querySelectorAll(".b-kpi")).every(k => !bad(k.textContent)), "Brief: four key numbers");
  ok(bp.d.querySelectorAll(".b-findings li").length >= 5, "Brief: what the data says");
  ok(bp.d.querySelectorAll(".b-points li").length === 4 && !bad(bp.d.querySelector(".b-points").textContent), "Brief: what it means, four points");
  ok(bp.d.querySelectorAll(".b-refs p").length >= 10, "Brief: APA sources");
  ok(!bp.d.body.textContent.includes("—") && !bad(bp.d.querySelector(".b-pages").textContent), "Brief: no em dashes or template errors");
  ok(!/\b(should|must) (vote|support|elect)\b/i.test(bp.d.body.textContent), "Brief: no party endorsements");

  // ================================================================ figures list
  const figs = readCsv("docs/figures.csv");
  ok(figs && figs.length >= 25 && figs.every(f => ["draft", "approved", "locked"].includes(f.status)), "figures.csv lists every chart with a status", figs && figs.length);

  // ================================================================ report
  const total = pass + fail;
  console.log(`\nMigration by Skill tests: ${pass} of ${total} passed (${Math.round((100 * pass) / total)}%).`);
  if (fails.length) { console.log("\nFailed:"); fails.forEach(f => console.log(" - " + f)); }
  process.exit(fail ? 1 : 0);
}
main().catch(e => { console.error(e); process.exit(2); });
