/* Migration by Skill: every word on the page. The story (hero, chapters, steps), the simulator, the report
   (key numbers, findings, exhibits) and the welcome guide. Every number comes from MBS.data or MBS.explore
   (written by analysis/export_web_data.py) through the templates below; nothing here is typed by hand.
   Rules: headlines are punchy but say exactly what the data says; parties are described the same way; no em dashes. */
(function () {
  "use strict";
  const MBS = (window.MBS = window.MBS || {});
  const f = () => MBS.fmt;

  // One or two plain words for each job group, for sentences.
  const WORD = {
    nurses: "nurses", doctors: "doctors", other_health: "other health jobs", aged_disability: "aged care",
    child_care: "child care", teaching: "teaching", community: "community services", police_security: "police and security",
    construction: "construction", mechanics_metal: "mechanics", engineering: "engineering", farming: "farming",
    mining: "mining", manufacturing: "manufacturing", tech: "tech", science: "science", hospitality: "hospitality",
    transport: "transport", retail: "retail", business: "business", office: "office jobs", arts_media: "arts and media",
    personal_services: "personal services", cleaning_labouring: "cleaning and labouring"
  };
  // "___ jobs" for growth headlines
  const JOBS = {
    nurses: "Nursing jobs", doctors: "Doctor jobs", other_health: "Other health jobs", aged_disability: "Aged care jobs",
    child_care: "Child care jobs", teaching: "Teaching jobs", community: "Community services jobs", police_security: "Police and security jobs",
    construction: "Construction jobs", mechanics_metal: "Mechanic jobs", engineering: "Engineering jobs", farming: "Farming jobs",
    mining: "Mining jobs", manufacturing: "Manufacturing jobs", tech: "Tech jobs", science: "Science jobs", hospitality: "Hospitality jobs",
    transport: "Transport jobs", retail: "Retail jobs", business: "Business jobs", office: "Office jobs", arts_media: "Arts and media jobs",
    personal_services: "Personal services jobs", cleaning_labouring: "Cleaning and labouring jobs"
  };
  // Worker words for "For every 100 ___ needed".
  const WORKERS = {
    aged_disability: "aged care workers", doctors: "doctors", nurses: "nurses", teaching: "teachers",
    construction: "construction workers", child_care: "child care workers", mechanics_metal: "mechanics",
    other_health: "health workers", engineering: "engineers", mining: "mining workers"
  };
  const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
  const list = a => (a.length < 2 ? a.join("") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1]);
  const byId = (rows, id) => rows.find(r => r.id === id);
  const grp = (d, k) => d.q3.groups.find(g => g.key === k);
  const plan = (d, id) => d.q4.plans.find(p => p.id === id);
  const statesOnly = d => d.q12.states.filter(s => s.code !== "AUS");
  const ausState = d => d.q12.states.find(s => s.code === "AUS");
  const maxPph = d => statesOnly(d).reduce((a, b) => (b.people_per_home > a.people_per_home ? b : a));
  const tempPermRatio = d => Math.round(d.q3.temporary_published / d.q3.permanent);
  const skilledNet = d => d.q3.skilled_net;
  const studentsNet = d => grp(d, "students").net;
  const homesPlans = d => d.q6.plans.filter(p => !p.context);
  const topStates = d => statesOnly(d).slice().sort((a, b) => b.nom - a.nom);
  const top2Share = d => { const t = topStates(d); return 100 * (t[0].nom + t[1].nom) / ausState(d).nom; };
  const shortName = s => ({ "New South Wales": "NSW", "Victoria": "Victoria", "Queensland": "Queensland" })[s.name] || s.name;
  const trainedSorted = d => d.q9.rows.slice().sort((a, b) => a.trained_per_100 - b.trained_per_100);
  const growthRatio = d => byId(d.q7.sectors, d.q8.top[0]).growth_pct / d.q8.all_growth_pct;
  const untestable = d => d.q13.total - d.q13.testable;
  const biggestGap = d => d.q9.rows.slice().sort((a, b) => (a.trained_per_100 + a.visas_per_100) - (b.trained_per_100 + b.visas_per_100))[0];

  const TYPES = {
    official: { label: "Official data", note: "Published by a government agency" },
    forecast: { label: "Forecast or plan", note: "A forecast, target or party plan: not law, not yet happened" },
    estimate: { label: "Our estimate", note: "Worked out by this project from official data" },
    illustration: { label: "Our illustration", note: "A what-if or a range we drew; not an official figure or a forecast" }
  };

  // ---------------------------------------------------------------- the (i) panels, shared by story and report
  const INFO = {
    q1: {
      why: () => "A full MCG is a crowd most Australians can picture.",
      how: d => `Net overseas migration is people arriving to stay a year or more, minus people leaving for a year or more. This is the total for ${d.q1.period_label}, divided by the MCG's capacity of ${f().int(d.q1.mcg_capacity)}.`,
      shows: d => `${f().int(d.q1.nom)} more people arrived than left. Counting births minus deaths too, the population grew by ${f().int(d.q1.growth_12m)}.`,
      limits: () => "It counts anyone who stays 12 of the next 16 months, so students and temporary workers are included. The ABS revises recent figures as more travel records come in."
    },
    q2: {
      why: () => "A long line shows whether today's number is unusual.",
      how: () => "Calendar years to 1971, then financial years to 1981, then the 12 months to each quarter from 1982.",
      shows: d => `Today's figure is ${f().pct0(d.q2.fall_from_peak_pct)} below the peak. Counted by financial year, the record was ${f().int(d.q2.fy_2022_23)} in 2022-23. Per person, 2022-23 (${f().one(d.q2.per1000_2022_23)} per 1,000 people) was the highest since ${d.q2.per1000_last_higher_year}, close to 1949 and 1950 (about ${f().round0(d.q2.per1000_1949)} per 1,000).`,
      limits: d => `The ABS changed how it counts migration in 2006, so older years are not exactly comparable. In 2020-21, with the borders closed, ${f().int(-d.q2.fy_2020_21)} more people left than arrived.`
    },
    q3: {
      why: () => "Out of 100 makes the mix easy to see at a glance.",
      how: d => `Each square is 1 in 100 of the ${f().int(d.q3.arrivals)} people who arrived to stay in ${d.q3.year}, grouped by how they arrived. Squares are rounded to whole numbers.`,
      shows: d => `${f().int(d.q3.permanent)} came on permanent visas and ${f().int(d.q3.temporary_published)} on temporary visas (students: ${f().int(grp(d, "students").arrivals)}). ${f().int(d.q3.citizens)} were Australians coming home or New Zealanders.`,
      limits: () => "This counts arrivals only, not people leaving. Many temporary visa holders later get a permanent visa while already here, which this chart does not show."
    },
    net: {
      why: () => "Arrivals alone overstate some groups: many students and visitors also leave. Net counts both.",
      how: d => `Arrivals minus departures for each visa group in ${d.q3.year}, from the ABS. Groups add up to total net overseas migration of ${f().int(d.q3.net_total)}.`,
      shows: d => `Skilled visas (permanent ${f().int(grp(d, "perm_skilled").net)}, temporary ${f().int(grp(d, "temp_skilled").net)}) added ${f().int(skilledNet(d))}, or ${f().pct1(d.q3.skilled_net_share_pct)} of the total. Students added ${f().int(studentsNet(d))}. More Australians left than came home (${f().int(grp(d, "aus_citizens").net)}).`,
      limits: () => "Skilled visa counts include partners and children. People are counted under the visa they held when they crossed the border, not any visa they get later."
    },
    states: {
      why: () => "Sorted bars show where net overseas migration lands.",
      how: d => `Net overseas migration in ${d.q12.period_label}, by state and territory (ABS).`,
      shows: d => topStates(d).map(s => `${s.name} ${f().int(s.nom)}`).join(", ") + ".",
      limits: () => "Migrants can move between states after they arrive; this counts the state where they first settle."
    },
    q4: {
      why: () => "Every plan on one chart, in the same units, makes them easy to compare.",
      how: d => {
        const coa = plan(d, "coa"), on = plan(d, "on");
        return `Net overseas migration a year, every plan starting in ${d.q4.years[0]}. Government: the Budget forecast. Coalition: its rule (no more migrants than homes built) applied to last year's ${f().int(coa.nom[0])} homes. One Nation: its ${f().int(on.nom[3])} cap after three years of more people leaving than arriving.`;
      },
      shows: d => {
        const on = plan(d, "on");
        return `For One Nation's first three years we drew a range from ${f().int(on.nom_low[0])} to ${f().int(on.nom_high[0])} a year, using the party's own figure of ${f().int(on.party_cut)} fewer temporary visa holders. The Greens give no overall number.`;
      },
      limits: () => "Plans are not law. One Nation gave no size for its net-negative years, so the hatched range is our illustration, not a party figure. The Coalition's final number is not set.",
      sources: d => {
        const seen = new Set();
        return d.q4.plans.flatMap(p => p.sources.map(s => ({ text: `${p.name}: ${s.text}`, url: s.url })))
          .filter(s => (seen.has(s.url) ? false : seen.add(s.url)));
      }
    },
    q5: {
      why: () => "One dot per plan shows how far apart the plans end up.",
      how: d => `Our model adds each plan's migration, plus births minus deaths (${f().int(d.slider.natural_increase)} a year), to an estimated ${f().int(d.q5.today)} people in June 2026.`,
      shows: d => {
        const r = id => d.q5.plans.find(p => p.id === id);
        return `Government ${f().int(r("gov").v)}. Coalition ${f().int(r("coa").v)}. One Nation ${f().int(r("on").v)} (range ${f().int(r("on").low)} to ${f().int(r("on").high)}). If the last 12 months continued: ${f().int(d.q5.reference.v)}.`;
      },
      limits: d => "A simple model: births, deaths and departures do not react to the economy. The scale does not start at zero, so gaps look bigger than on a full scale." +
        (d.q5.sensitivity ? ` If the opposition plans started a year later, after the next election, the 2030 population would be about ${f().k(d.q5.sensitivity.late_start_difference.coa)} higher for the Coalition and ${f().k(d.q5.sensitivity.late_start_difference.on)} higher for One Nation.` : ""),
      link: () => ({ href: "#models", text: "How sensitive is the model? (Models)" })
    },
    q6: {
      why: () => "Comparing homes needed with homes built shows whether building keeps pace.",
      how: d => `Homes needed = each plan's yearly population growth divided by ${d.q6.people_per_home} people per home (the average household in the 2021 Census). Homes built = ${d.q6.built_label.charAt(0).toLowerCase() + d.q6.built_label.slice(1)}.`,
      shows: d => `From the ${d.q6.shortfall_from} to ${d.q6.shortfall_to}, the population grew by ${f().int(d.q6.shortfall_growth)}, needing about ${f().int(d.q6.shortfall_growth / d.q6.people_per_home)} homes. ${f().int(d.q6.shortfall_homes_completed)} were finished, about ${f().int(d.q6.shortfall)} too few.`,
      limits: d => {
        const sn = d.q6.sensitivity;
        return "New homes are counted without taking away homes knocked down. New arrivals may live in bigger or smaller households than average. Prices, location and the type of home matter too." +
          (sn ? ` With ${sn.people_per_home_range[0]} to ${sn.people_per_home_range[1]} people per home, the Government plan needs ${f().k(sn.homes_needed_range.gov[0])} to ${f().k(sn.homes_needed_range.gov[1])} homes a year; ${sn.all_below_built ? "every plan stays below" : "some plans go above"} last year's ${f().int(d.q6.built)}.` : "");
      },
      link: () => ({ href: "#models", text: "How sensitive is the model? (Models)" })
    },
    q7: {
      why: () => "Sorted bars make the biggest shortages easy to spot.",
      how: () => "For each of 24 job groups: the share of its workers whose occupation is on the 2025 shortage list from Jobs and Skills Australia.",
      shows: d => d.q7.top.map(id => byId(d.q7.sectors, id)).map(s => `${s.name} ${f().pct0(s.short_pct)}`).join(", ") + `. All jobs: ${f().pct0(d.q7.all_short_pct)}.`,
      limits: d => {
        const low = d.q7.low_assessed.map(id => byId(d.q7.sectors, id));
        return "An occupation is either on the list or not, so this is not the size of the gap." +
          (low.length ? ` Fewer than half of the jobs in ${list(low.map(s => s.name.toLowerCase()))} were checked, so their shares may be too low (marked *).` : "");
      }
    },
    q8: {
      why: () => "Re-sorting the same bars shows which groups will grow, not just which are short now.",
      how: () => "Jobs and Skills Australia's projected growth in the number of workers, May 2025 to May 2030. 'Short now' means most of the group's jobs are on the 2025 shortage list.",
      shows: d => d.q8.top.map(id => byId(d.q7.sectors, id)).map(s => `${s.name} ${f().pct1(s.growth_pct)}`).join(", ") + `. All jobs: ${f().pct1(d.q8.all_growth_pct)}.`,
      limits: () => "These are projections from an economic model, not promises. Policy, the economy and new technology can change them."
    },
    q9: {
      why: () => "'Per 100 needed' puts small and large job groups on the same scale.",
      how: () => "Workers needed a year = new jobs + retirements + people moving to other jobs (our estimate from Jobs and Skills Australia and ABS data). Trained here = apprentices and graduates finishing each year, counting only those who work in their field.",
      shows: d => `Shown: the ${d.q9.rows.length} job groups where most jobs are short and we can count training for at least ${d.q9.rule.training_counted_min_pct}% of the need. ` +
        d.q9.rows.map(r => `${r.name} ${r.trained_per_100}`).join(", ") + ".",
      limits: () => "Training is only counted for some occupations. Migrants and people changing careers also fill jobs, and not everyone who finishes training stays in the job."
    },
    q10: {
      why: () => "The same scale as the training chart lets you compare visas with local training.",
      how: () => "Temporary skilled visas granted to main applicants in 2025-26, per 100 workers needed a year in that job group.",
      shows: d => d.q9.rows.map(r => `${r.name} ${r.visas_per_100}`).join(", ") + `. All jobs: ${d.q9.all_visas_per_100}.` +
        (d.q9.a1 ? ` Across ${d.q9.a1.occupations} occupations: ${d.q9.a1.plain_words}` : ""),
      link: () => ({ href: "#models", text: "Go deeper: do visas go where the shortages are? (Models)" }),
      limits: () => "Only temporary skilled visas are counted: permanent skilled visas, and students or working holiday makers who work, are not. Visa holders can change jobs after they arrive."
    },
    q11: {
      why: () => "'Out of 100' makes groups of different sizes easy to compare.",
      how: () => "People aged 15 to 64 with a job, from the 2021 Census linked to visa records. Migrants are permanent migrants who arrived from 2000 on.",
      shows: d => d.q11.rows.map(r => `${r.label}: ${f().one(r.pct)} in 100`).join(". ") + `. Skilled migrants who arrived in the last five years: ${f().one(d.q11.skilled_recent_pct)} in 100.`,
      limits: () => "This shows having a job, not whether it is the job they were picked for. The Census was in August 2021, during Covid lockdowns. 'Everyone' includes migrants."
    },
    q12: {
      why: () => "Equal-sized tiles let small states count as much as big ones.",
      how: d => `Population growth in ${d.q12.period_label} divided by new homes finished in that year.`,
      shows: d => {
        const over = statesOnly(d).filter(s => s.people_per_home > d.q12.household).map(s => f().theName(s.name));
        return `Below ${d.q12.household} (the average household), building kept up with growth last year. Above it, growth ran ahead of building: ${list(over)}.`;
      },
      limits: () => "One year can swing a lot, especially in small states. It leaves out the existing shortfall, homes knocked down, and where in the state people live."
    },
    verdicts: {
      why: () => "Stacked bars show at a glance how each side's claims fared, including the ones that couldn't be tested.",
      how: () => "Each claim is checked against official data with the same rule for every side: accurate within 5%, mostly accurate within 15%, partly accurate within 35%, otherwise inaccurate.",
      shows: d => Object.entries(d.q13.counts_by_side).map(([s, c]) => `${s}: ${Object.entries(c).map(([v, n]) => `${n} ${v.toLowerCase()}`).join(", ")}`).join(". ") + ".",
      limits: () => "We collected a sample of recent claims, not every claim. A claim we can't test is not a judgement on it."
    },
    q13: {
      why: () => "One claim per party, checked the same way, keeps it fair.",
      how: d => `We check what each claim says against official data: accurate within 5%, mostly accurate within 15%, partly accurate within 35%. ${d.q13.rule}`,
      shows: d => `We collected ${d.q13.total} claims from Labor, the Coalition, One Nation, the Greens, business and unions. ${d.q13.testable} could be tested; the rest were plans, too early, or need data we don't have.`,
      limits: () => "We check the numbers, not motives, and not whether a policy is a good idea. A claim we can't test is not a judgement on it."
    }
  };

  // ---------------------------------------------------------------- hero
  const hero = {
    kicker: "Migration by Skill · Australia",
    number: d => f().about(d.q1.per_day),
    line: "more people arrive than leave. Every day.",
    question: "But are they the skills we need?",
    note: d => `Net overseas migration, ${d.q1.period_label}: ${f().int(d.q1.nom)} (ABS). That's about ${f().about(d.q1.per_day)} a day.`,
    dots: "Each dot is one person, net, in a single day.",
    lede: "A data story in eight short chapters, a simulator, then the full report with every chart, table and source."
  };

  // ---------------------------------------------------------------- the story: eight chapters
  // layers: the charts a chapter's sticky graphic can show; steps: the text cards, each naming a layer and a state.
  const chapters = [
    {
      id: "ch1", n: 1, kicker: "How many", title: d => `Is ${f().k(d.q1.nom)} a lot?`,
      stat: d => f().one(d.q1.mcgs), statLabel: () => "full MCGs of people added through migration in a year",
      layers: {
        nom: { chart: "nomLine", title: "Net overseas migration a year since 1950", types: ["official"], sources: d => d.q2.sources, info: "q2" },
        mcg: { chart: "mcg", title: "The last 12 months, in full MCGs", types: ["official"], sources: d => d.q1.sources, info: "q1" }
      },
      steps: [
        { layer: "nom", state: "all", text: () => "This is net overseas migration since 1950: people who arrive to stay a year or more, **minus those who leave**." },
        { layer: "nom", state: "low", text: d => `In 2020-21, with the borders shut, **${f().int(-d.q2.fy_2020_21)} more people left than arrived**.` },
        { layer: "nom", state: "peak", text: d => `Then the rebound: **a record ${f().int(d.q2.peak.v)}** in the ${f().yearTo(d.q2.peak.label)}.` },
        { layer: "nom", state: "now", text: d => `Now it's **${f().int(d.q2.latest.v)}**: down ${f().pct0(d.q2.fall_from_peak_pct)} from the record.` },
        { layer: "mcg", state: null, text: d => `That's still **${f().one(d.q1.mcgs)} full MCGs** a year, or about **${f().about(d.q1.per_day)} people a day**.` }
      ]
    },
    {
      id: "ch2", n: 2, kicker: "Who", title: "Who's actually coming?",
      stat: d => `${grp(d, "perm_skilled").squares} in 100`, statLabel: d => `arrivals in ${d.q3.year} came on a permanent skilled visa`,
      layers: {
        waffle: { chart: "waffle", title: d => `Every 100 people who arrived to stay in ${d.q3.year}`, types: ["official"], sources: d => d.q3.sources, info: "q3" },
        net: { chart: "netByVisa", title: d => `Net overseas migration by visa, ${d.q3.year} (arrivals minus departures)`, types: ["official"], sources: d => d.q3.sources, info: "net" }
      },
      steps: [
        { layer: "waffle", state: "all", text: d => `Picture every **100 people** who arrived to stay in ${d.q3.year}.` },
        { layer: "waffle", state: "citizen", text: d => `**${d.q3.citizen_squares}** were Australians coming home or New Zealanders.` },
        { layer: "waffle", state: "temporary", text: d => `**${d.q3.temporary_squares}** came on temporary visas: ${grp(d, "students").squares} students, ${grp(d, "working_holiday").squares} working holiday makers, ${grp(d, "visitors").squares} visitors and ${grp(d, "temp_skilled").squares} skilled workers.` },
        { layer: "waffle", state: "permanent", text: d => `Just **${d.q3.permanent_squares}** held a permanent visa.` },
        { layer: "waffle", state: "skilled", text: d => `And only **${grp(d, "perm_skilled").squares} in 100** came on a permanent skilled visa.` },
        { layer: "net", state: "students", text: d => studentsNet(d) > skilledNet(d)
          ? `Count the people leaving too, and students added **${f().k(studentsNet(d))}** to net migration: more than every skilled visa combined (${f().k(skilledNet(d))}).`
          : `Count the people leaving too, and skilled visas added **${f().k(skilledNet(d))}** to net migration; students added ${f().k(studentsNet(d))}.` }
      ]
    },
    {
      id: "ch3", n: 3, kicker: "The plans", title: "What do the parties want?",
      stat: d => `${(d.q5.gap / 1e6).toFixed(1)} million`, statLabel: () => "people apart by 2030, depending on whose plan wins",
      layers: {
        plans: { chart: "planLines", title: "Net overseas migration a year under each plan", types: ["official", "forecast", "illustration"], sources: d => d.q4.sources, info: "q4" },
        pop: { chart: "popDots", title: "Population at 30 June 2030 under each plan (our model)", types: ["estimate", "illustration"], sources: d => d.q5.sources, info: "q5" }
      },
      steps: [
        { layer: "plans", state: "all", text: d => `Each line is a party's plan for net overseas migration, year by year to ${d.q4.years[d.q4.years.length - 1]}.` },
        { layer: "plans", state: "gov", text: d => { const g = plan(d, "gov"); return `**Government:** the Budget forecast. ${f().k(g.nom[0])} next year, then ${f().k(g.nom[1])} a year.`; } },
        { layer: "plans", state: "coa", text: d => `**Coalition:** no more migrants than homes built. At last year's building, about ${f().k(plan(d, "coa").nom[0])} a year.` },
        { layer: "plans", state: "on", text: d => `**One Nation:** more people leaving than arriving for three years, then a ${f().k(plan(d, "on").nom[3])} cap. It gives no size for those years, so the shaded range is our illustration.` },
        { layer: "plans", state: "grn", text: () => "**Greens:** a humanitarian intake, but no overall number, so there's no line to draw." },
        { layer: "pop", state: "all", text: d => `By June 2030, that's **${f().m1(d.q5.min)} to ${f().m1(d.q5.max)} million people**: a gap of ${(d.q5.gap / 1e6).toFixed(1)} million, or ${f().round0(d.q5.gap_mcgs)} full MCGs.` }
      ]
    },
    {
      id: "ch4", n: 4, kicker: "Homes", title: "Can we house everyone?",
      stat: d => f().k(d.q6.shortfall), statLabel: () => "homes short of population growth since 2022",
      layers: {
        homes: { chart: "homesBars", title: d => `Homes needed a year for each plan's growth, against homes finished`, types: ["estimate", "official", "forecast", "illustration"], sources: d => d.q6.sources, info: "q6" },
        tiles: { chart: "stateTiles", title: d => `People added for each new home finished, ${d.q12.period_label}`, types: ["official"], sources: d => d.q12.sources, info: "q12" }
      },
      steps: [
        { layer: "homes", state: "plans", text: d => { const h = homesPlans(d).map(p => p.v); return `At ${d.q6.people_per_home} people per home, the plans need **${f().k(Math.min(...h))} to ${f().k(Math.max(...h))} new homes a year**.`; } },
        { layer: "homes", state: "built", text: d => `Last year, **${f().int(d.q6.built)} homes** were finished: ${d.q6.all_plans_below_built ? "more than any plan needs" : "fewer than some plans need"}.` },
        { layer: "homes", state: "shortfall", text: d => `But since the ${d.q6.shortfall_from}, the population grew faster than homes were finished: **about ${f().k(d.q6.shortfall)} homes behind**.` },
        { layer: "tiles", state: "all", text: () => "And it's not even. Each tile is a state or territory: **the darker the tile, the more people per new home**." },
        { layer: "tiles", state: "max", text: d => { const m = maxPph(d); return `In ${f().theName(m.name)}, the population grew by **${f().one(m.people_per_home)} people for every new home** finished. Nationally: ${f().one(ausState(d).people_per_home)}.`; } }
      ]
    },
    {
      id: "ch5", n: 5, kicker: "Shortages", title: "Which jobs can't find workers?",
      stat: d => `${Math.round(d.q7.all_short_pct / 10)} in 10`, statLabel: () => "workers are in jobs on the national shortage list",
      layers: {
        short: { chart: "sectorShort", title: "Share of each job group's jobs on the 2025 shortage list", types: ["official"], sources: d => d.q7.sources, info: "q7" },
        growth: { chart: "sectorGrowth", title: "Projected growth in workers, May 2025 to May 2030", types: ["forecast"], sources: d => d.q8.sources, info: "q8" }
      },
      steps: [
        { layer: "short", state: "all", text: () => "**24 job groups**, sorted by the share of their jobs on the 2025 shortage list." },
        { layer: "short", state: "top", text: d => `**${cap(list(d.q7.top.map(id => WORD[id])))}**: about ${Math.round(d.q7.top_min_pct / 10)} in 10 of their jobs are short.` },
        { layer: "growth", state: "sort", text: () => "Now **re-sort the same groups** by expected growth to 2030." },
        { layer: "growth", state: "top", text: d => { const s = byId(d.q7.sectors, d.q8.top[0]); return `**${JOBS[s.id]} grow fastest**: up ${f().pct1(s.growth_pct)} by 2030, ${f().one(growthRatio(d))} times the average. ${cap(f().word(d.q8.top_short_count))} of the five fastest-growing groups are short now.`; } }
      ]
    },
    {
      id: "ch6", n: 6, kicker: "Training and visas", title: "Who fills the gaps?",
      stat: d => { const hi = byId(d.q9.rows, d.q9.most_visas), lo = byId(d.q9.rows, d.q9.lowest_trained); return `${hi.visas_per_100} vs ${lo.visas_per_100}`; },
      statLabel: d => `skilled visas per 100 workers needed: ${WORD[d.q9.most_visas]} against ${WORD[d.q9.lowest_trained]}`,
      layers: {
        trained: { chart: "trained", title: "People finishing training here per 100 workers needed a year", types: ["estimate"], sources: d => d.q9.sources_q9, info: "q9" },
        visas: { chart: "visas", title: "Temporary skilled visas per 100 workers needed a year", types: ["estimate"], sources: d => d.q9.sources_q10, info: "q10" }
      },
      steps: [
        { layer: "trained", state: "all", text: d => `${cap(f().word(d.q9.rows.length))} job groups where most jobs are short and we can count local training. **The orange line at 100** means one trained for every worker needed.` },
        { layer: "trained", state: "low", text: d => { const t = trainedSorted(d); return `${cap(WORD[t[0].id])} trains just **${t[0].trained_per_100} for every 100 workers it needs**. ${cap(WORD[t[1].id])}: ${t[1].trained_per_100}.`; } },
        { layer: "trained", state: "high", text: d => { const t = trainedSorted(d).slice(-3).reverse(); return `Others train well above 100 and are still short: ${list(t.map(r => `${WORD[r.id]} **${r.trained_per_100}**`))}.`; } },
        { layer: "visas", state: "hi", text: d => { const hi = byId(d.q9.rows, d.q9.most_visas), lo = byId(d.q9.rows, d.q9.lowest_trained); return `Skilled visas tell a different story: **${WORD[hi.id]} get ${hi.visas_per_100} per 100 needed**. ${cap(WORD[lo.id])}: ${lo.visas_per_100}.`; } },
        { layer: "visas", state: "all", text: d => d.q9.a1 ? `Across ${d.q9.a1.occupations} occupations, **${Math.round(d.q9.a1.share_of_visas_to_short_occupations_pct)}% of temporary skilled visas** went to jobs on the shortage list, which hold ${Math.round(d.q9.a1.share_of_workers_in_short_occupations_pct)}% of workers.` : "Visas and training tell different stories for each job group." }
      ]
    },
    {
      id: "ch7", n: 7, kicker: "Outcomes", title: "Do skilled migrants find work?",
      stat: d => `${f().round0(d.q11.rows.find(r => r.key === "skilled").pct)} in 100`, statLabel: d => `skilled migrants aged ${d.q11.ages} have a job`,
      layers: {
        out: { chart: "outcomes", title: d => `People aged ${d.q11.ages} with a job, out of 100 (${d.q11.period})`, types: ["official"], sources: d => d.q11.sources, info: "q11" }
      },
      steps: [
        { layer: "out", state: "top", text: d => { const r = k => d.q11.rows.find(x => x.key === k); return `**${f().round0(r("skilled").pct)} in 100** skilled migrants aged ${d.q11.ages} have a job. Across everyone in Australia: ${f().round0(r("everyone").pct)}.`; } },
        { layer: "out", state: "others", text: d => { const r = k => d.q11.rows.find(x => x.key === k); return `Family (${f().round0(r("family").pct)}) and humanitarian migrants (${f().round0(r("humanitarian").pct)}) are less likely to work. **Their visas aren't chosen for job skills.**`; } }
      ]
    },
    {
      id: "ch8", n: 8, kicker: "Fact check", title: "So, who's right?",
      stat: d => `${d.q13.accurate_or_mostly} of ${d.q13.testable}`, statLabel: () => "claims we could test were accurate or mostly accurate",
      claims: true,
      intro: d => `We checked **${d.q13.total} claims** from every side against the same official data. ${d.q13.testable} could be tested, and **${d.q13.accurate_or_mostly} were accurate or mostly accurate**. The other ${untestable(d)} were plans, too early to judge, or need data nobody publishes yet.`
    }
  ];

  // ---------------------------------------------------------------- the bottom line
  const bottomLine = {
    title: "The bottom line",
    items: [
      { big: d => `${Math.round(d.q3.skilled_net_share_pct)}%`, text: d => `of net overseas migration in ${d.q3.year} came on a skilled visa. The rest were students, working holiday makers, visitors, families, refugees and New Zealanders.` },
      { big: d => { const g = biggestGap(d); return `${g.trained_per_100} + ${g.visas_per_100}`; }, text: d => { const g = biggestGap(d); return `${cap(WORD[g.id])}: ${g.trained_per_100} trained here and ${g.visas_per_100} skilled visas for every 100 workers needed. The biggest gap we can measure.`; } },
      { big: d => f().k(d.q6.shortfall), text: () => "homes short of population growth since 2022. Every plan starts from this gap." }
    ]
  };

  // ---------------------------------------------------------------- the simulator (method A: size vs mix)
  const sim = {
    kicker: "Your turn",
    title: "Size vs mix",
    intro: "Pick a size for net overseas migration and see how many skilled workers would reach jobs on the shortage list: with today's mix of skilled visas, or a skills-first mix.",
    presetNote: d => `For scale: ${f().int(plan(d, "gov").nom[1])} is the Government's Budget forecast for ${d.q4.years[1]}, ${f().int(plan(d, "on").nom[3])} is One Nation's cap, and the last 12 months were ${f().int(d.q1.nom)}.`,
    steps: d => {
      const S = d.sim;
      return [
        `**Skilled share:** ${f().pct1(S.skilled_share_pct)} of net overseas migration came on skilled visas in ${S.year} (${f().int(S.skilled_net)} of ${f().int(S.nom_total)}, including partners and children).`,
        `**Workers:** ${f().pct0(100 * S.working_age_share)} of migrants are of working age and ${S.employment_recent_pct} in 100 recent skilled migrants have a job, so about ${Math.round(S.working_age_share * S.employment_recent_pct)} workers for every 100 skilled migrants.`,
        `**Today's mix:** ${f().pct0(S.short_share_of_visas_pct)} of temporary skilled visas go to jobs on the shortage list (our analysis of ${S.a1_occupations} occupations), spread across job groups as visas are today.`,
        "**Skills-first:** every skilled place goes to a job on the shortage list, spread across job groups by how many short jobs each needs to fill."
      ];
    },
    limits: [
      "Skilled visas are only one source of workers: students, working holiday makers, partners and people changing careers fill jobs too.",
      "People can change jobs after they arrive.",
      "Temporary skilled visa patterns stand in for permanent ones, which aren't published by job group.",
      "Rates are held at today's levels; in reality they move with the economy.",
      "National only for now. A version by state could come later."
    ]
  };

  // ---------------------------------------------------------------- the report
  const report = {
    title: "The report",
    lede: "Every chart from the story and more, as numbered exhibits with a takeaway title, the table behind it, how it was made and its data.",
    kpis: [
      { label: "Net overseas migration", value: d => f().int(d.q1.nom), sub: d => `${d.q1.period_label}; down ${f().pct0(d.q2.fall_from_peak_pct)} from the record`, type: "official" },
      { label: "Skilled visas' share", value: d => f().pct1(d.q3.skilled_net_share_pct), sub: d => `of net overseas migration, ${d.q3.year}`, type: "official" },
      { label: "Population, June 2030", value: d => `${f().m1(d.q5.min)}m to ${f().m1(d.q5.max)}m`, sub: () => "depending on the plan (our model)", type: "estimate" },
      { label: "Homes behind since 2022", value: d => f().k(d.q6.shortfall), sub: () => "population growth against homes finished", type: "estimate" },
      { label: "Workers in short jobs", value: d => f().pct1(d.q7.all_short_pct), sub: () => "on the 2025 shortage list", type: "official" },
      { label: "Aged care, trained per 100 needed", value: d => String(byId(d.q9.rows, "aged_disability").trained_per_100), sub: d => `and ${byId(d.q9.rows, "aged_disability").visas_per_100} skilled visas per 100`, type: "estimate" }
    ],
    findings: [
      { text: d => `Net overseas migration is **${f().int(d.q2.latest.v)}** a year, down ${f().pct0(d.q2.fall_from_peak_pct)} from the record in the ${f().yearTo(d.q2.peak.label)}.`, ex: "ex2" },
      { text: d => `Temporary visas outnumber permanent ones **${tempPermRatio(d)} to 1** among arrivals; ${grp(d, "perm_skilled").squares} in 100 arrivals held a permanent skilled visa.`, ex: "ex3" },
      { text: d => `Skilled visas made up **${f().pct1(d.q3.skilled_net_share_pct)}** of net migration in ${d.q3.year}; students added ${f().k(studentsNet(d))}, more than all skilled visas combined.`, ex: "ex4" },
      { text: d => `By June 2030 the parties' plans end **${(d.q5.gap / 1e6).toFixed(1)} million people** apart.`, ex: "ex7" },
      { text: d => `Today's building ${d.q6.all_plans_below_built ? "outpaces every plan's needs" : "falls short of some plans"}, but the country is about **${f().k(d.q6.shortfall)} homes behind** since 2022.`, ex: "ex9" },
      { text: d => `${cap(list(d.q7.top.map(id => WORD[id])))}: about **${Math.round(d.q7.top_min_pct / 10)} in 10 jobs short**.`, ex: "ex12" },
      { text: d => { const g = biggestGap(d); return `${cap(WORD[g.id])} trains **${g.trained_per_100}** and gets **${g.visas_per_100}** skilled visas per 100 workers needed: the biggest gap we can measure.`; }, ex: "ex14" },
      { text: d => d.q9.a1 ? `**${Math.round(d.q9.a1.share_of_visas_to_short_occupations_pct)}%** of temporary skilled visas go to short jobs, which hold ${Math.round(d.q9.a1.share_of_workers_in_short_occupations_pct)}% of workers; projected growth ${d.q9.a1.growth_effect_clear ? "also matters" : "makes no clear difference"}.` : "", ex: "exA1" }
    ],
    sections: [
      { id: "sec-arrivals", n: 1, title: "Arrivals", blurb: "How many, who, and where they settle." },
      { id: "sec-plans", n: 2, title: "Party plans", blurb: "Each plan's numbers, and what they mean by 2030." },
      { id: "sec-homes", n: 3, title: "Homes and states", blurb: "Homes needed against homes built, state by state." },
      { id: "sec-jobs", n: 4, title: "Jobs and skills", blurb: "Shortages, growth, training, visas and outcomes." },
      { id: "sec-claims", n: 5, title: "Claims", blurb: "Every side, checked against the same data." },
      { id: "models", n: "A", title: "Appendix A: Models", blurb: "The data science under the hood: a regression, a sensitivity test, and a model that checks itself." },
      { id: "sec-data", n: "B", title: "Appendix B: Data and methods", blurb: "Sources, downloads, and how to cite this work." }
    ]
  };

  // ---------------------------------------------------------------- report exhibits (takeaway titles are punchy, and exact)
  const exhibits = [
    { id: "ex1", section: "sec-arrivals", chart: "mcg", span: 5, types: ["official"], info: "q1", sources: d => d.q1.sources,
      title: d => `${f().k(d.q1.nom)} more arrived than left: about ${f().about(d.q1.per_day)} a day`,
      sub: d => `Net overseas migration, ${d.q1.period_label}, in full MCGs (${f().int(d.q1.mcg_capacity)} each)`, csv: "everyday_comparisons.csv" },
    { id: "ex2", section: "sec-arrivals", chart: "nomLine", span: 7, types: ["official"], info: "q2", sources: d => d.q2.sources,
      title: d => `Down ${f().pct0(d.q2.fall_from_peak_pct)} from the record ${f().k(d.q2.peak.v)}`,
      sub: () => "Net overseas migration a year since 1950 (12 months to each quarter from 1982)", csv: "population_long_run_australia.csv" },
    { id: "ex3", section: "sec-arrivals", chart: "waffle", span: 6, types: ["official"], info: "q3", sources: d => d.q3.sources,
      title: d => `Temporary visas outnumber permanent ${tempPermRatio(d)} to 1`,
      sub: d => `Every 100 people who arrived to stay in ${d.q3.year}, by visa`, csv: "nom_by_visa_group.csv" },
    { id: "ex4", section: "sec-arrivals", chart: "netByVisa", span: 6, types: ["official"], info: "net", sources: d => d.q3.sources,
      title: d => studentsNet(d) > skilledNet(d) ? "Students added more than all skilled visas combined" : `Skilled visas added ${f().k(skilledNet(d))}`,
      sub: d => `Net overseas migration by visa group, ${d.q3.year} (arrivals minus departures)`, csv: "nom_by_visa_group.csv" },
    { id: "ex5", section: "sec-arrivals", chart: "nomByState", span: 12, types: ["official"], info: "states", sources: d => ["abs_pop"],
      title: d => { const t = topStates(d); return `${f().pct0(top2Share(d))} of net arrivals went to ${shortName(t[0])} and ${shortName(t[1])}`; },
      sub: d => `Net overseas migration by state and territory, ${d.q12.period_label}`, csv: "abs_population_quarterly_by_state.csv" },

    { id: "ex6", section: "sec-plans", chart: "planLines", span: 7, types: ["official", "forecast", "illustration"], info: "q4", sources: d => d.q4.sources,
      title: d => { const g = plan(d, "gov"); return `Year one: from +${f().k(g.nom[0])} to more people leaving than arriving`; },
      sub: () => "Net overseas migration a year under each plan", csv: "scenario_nom_paths.csv", plans: true },
    { id: "ex7", section: "sec-plans", chart: "popDots", span: 5, minH: 400, types: ["estimate", "illustration"], info: "q5", sources: d => d.q5.sources,
      title: d => `The plans end ${(d.q5.gap / 1e6).toFixed(1)} million people apart by 2030`,
      sub: () => "Population at 30 June 2030 under each plan (our model)", csv: "scenario_summary.csv" },
    { id: "ex8", section: "sec-plans", tool: "plans", span: 12, types: ["estimate", "forecast", "illustration"], sources: () => ["model", "abs_pop", "budget"],
      title: () => "Build your own plan", sub: () => "Set net overseas migration for each year and see population and homes to 2030, for Australia or a state", csv: "scenario_summary.csv" },

    { id: "ex9", section: "sec-homes", chart: "homesBars", span: 6, types: ["estimate", "official", "forecast", "illustration"], info: "q6", sources: d => d.q6.sources,
      title: d => d.q6.all_plans_below_built ? `Building outpaces every plan, but we're ${f().k(d.q6.shortfall)} homes behind` : `Some plans need more homes than we build, and we're ${f().k(d.q6.shortfall)} behind`,
      sub: () => "Homes needed a year for each plan's growth, against homes finished", csv: "scenario_housing_context.csv" },
    { id: "ex10", section: "sec-homes", chart: "stateTiles", span: 6, types: ["official"], info: "q12", sources: d => d.q12.sources,
      title: d => { const m = maxPph(d); return `${m.code}: ${f().one(m.people_per_home)} people per new home, ${f().one(m.people_per_home / ausState(d).people_per_home)} times the national rate`; },
      sub: d => `People added for each new home finished, ${d.q12.period_label}`, csv: "housing_vs_population_by_state.csv" },
    { id: "ex11", section: "sec-homes", tool: "state", span: 12, types: ["official", "estimate"], sources: () => ["abs_pop", "abs_build", "jsa_osl"],
      title: () => "Your state at a glance", sub: () => "Population, migration, homes and shortages for any state or territory", csv: "housing_vs_population_by_state.csv" },

    { id: "ex12", section: "sec-jobs", chart: "sectorShort", span: 6, types: ["official"], info: "q7", sources: d => d.q7.sources,
      title: d => `${cap(list(d.q7.top.map(id => WORD[id])))}: ${Math.round(d.q7.top_min_pct / 10)} in 10 jobs short`,
      sub: () => "Share of each job group's workers in occupations on the 2025 shortage list", csv: "named_sector_summary_national.csv" },
    { id: "ex13", section: "sec-jobs", chart: "sectorGrowth", span: 6, types: ["forecast"], info: "q8", sources: d => d.q8.sources,
      title: d => `${JOBS[d.q8.top[0]]} to grow ${f().one(growthRatio(d))} times faster than average`,
      sub: () => "Projected growth in workers, May 2025 to May 2030", csv: "named_sector_summary_national.csv" },
    { id: "ex14", section: "sec-jobs", chart: "trained", span: 6, types: ["estimate"], info: "q9", sources: d => d.q9.sources_q9,
      title: d => { const r = byId(d.q9.rows, d.q9.lowest_trained); return `${cap(WORD[r.id])}: ${r.trained_per_100} trained here for every 100 needed`; },
      sub: () => "People finishing training each year per 100 workers needed a year (our estimate)", csv: "named_sector_summary_national.csv" },
    { id: "ex15", section: "sec-jobs", chart: "visas", span: 6, types: ["estimate"], info: "q10", sources: d => d.q9.sources_q10,
      title: d => { const hi = byId(d.q9.rows, d.q9.most_visas), lo = byId(d.q9.rows, d.q9.lowest_trained); return `${cap(WORD[hi.id])} get ${hi.visas_per_100} skilled visas per 100 needed; ${WORD[lo.id]} gets ${lo.visas_per_100}`; },
      sub: () => "Temporary skilled visas granted 2025-26 per 100 workers needed a year", csv: "named_sector_summary_national.csv" },
    { id: "ex16", section: "sec-jobs", chart: "outcomes", span: 5, types: ["official"], info: "q11", sources: d => d.q11.sources,
      title: d => { const r = k => d.q11.rows.find(x => x.key === k); return `${f().round0(r("skilled").pct)} in 100 skilled migrants work, against ${f().round0(r("everyone").pct)} overall`; },
      sub: d => `People aged ${d.q11.ages} with a job, out of 100 (${d.q11.period})`, csv: "migrant_outcomes_by_stream.csv" },
    { id: "ex17", section: "sec-jobs", tool: "job", span: 7, types: ["official", "estimate"], sources: () => ["jsa_osl", "jsa_proj", "jsa_ivi", "ha_bp0014"],
      title: () => "Find your job", sub: () => "Any occupation: shortage status, growth to 2030, job ads, training and visas", csv: "occupation_skills_national.csv" },

    { id: "ex18", section: "sec-claims", chart: "verdictsBySide", span: 5, minH: 330, types: ["official"], info: "verdicts", sources: () => [],
      title: d => `${untestable(d)} of ${d.q13.total} claims couldn't be tested against the data`,
      sub: d => `Verdicts on ${d.q13.total} claims, by side`, csv: "fact_check_cards.csv" },
    { id: "ex19", section: "sec-claims", chart: "claims", span: 7, types: ["official"], info: "q13", sources: () => [],
      title: d => `We tested ${d.q13.testable} claims. ${d.q13.accurate_or_mostly} held up.`,
      sub: () => "The most recent testable claim from each party", csv: "fact_check_cards.csv" },
    { id: "ex20", section: "sec-claims", tool: "claims", span: 12, types: ["official"], sources: () => [],
      title: d => `All ${d.q13.total} claims`, sub: () => "Filter by side, verdict or topic", csv: "fact_check_cards.csv" }
  ];

  // ---------------------------------------------------------------- Appendix A: models (need the explore data)
  const models = [
    { id: "exA1", chart: "visaRates", span: 4, types: ["estimate"], sources: () => ["ha_bp0014", "jsa_osl", "jsa_proj"],
      title: m => `Short-listed jobs get ${f().one(m.a1.visas_per_1000_workers_short / m.a1.visas_per_1000_workers_not_short)} times the skilled visas per worker`,
      sub: m => `Temporary skilled visas granted 2025-26 per 1,000 workers, ${m.a1.occupations} occupations`, csv: "visas_vs_shortages.csv",
      info: {
        why: () => "Two bars answer the first question: do visas lean towards short jobs at all?",
        how: m => `${m.a1.visa_measure}. Occupations split by whether they are on the 2025 shortage list. Mean: total visas ÷ total workers in each group. Median: the middle occupation.`,
        shows: m => `Mean ${m.a1.visas_per_1000_workers_short} per 1,000 workers in short jobs against ${m.a1.visas_per_1000_workers_not_short} in other jobs. Medians ${m.a1.median_visas_per_1000_short} and ${m.a1.median_visas_per_1000_not_short}. ${m.a1.occupations_with_no_visas_pct}% of occupations had no temporary skilled visas.`,
        limits: m => m.a1.limits[0]
      } },
    { id: "exA2", chart: "visaShares", span: 4, types: ["estimate"], sources: () => ["ha_bp0014", "jsa_osl", "jsa_proj"],
      title: m => `${Math.round(m.a1.share_of_visas_to_short_occupations_pct)}% of skilled visas go to jobs holding ${Math.round(m.a1.share_of_workers_in_short_occupations_pct)}% of workers`,
      sub: () => "Occupations on the 2025 shortage list: their share of visas and of workers", csv: "visas_vs_shortages.csv",
      info: {
        why: () => "If visas followed jobs evenly, the two bars would match. The gap is the lean towards shortages.",
        how: m => `Across ${m.a1.occupations} occupations rated on the 2025 list: visas granted to short occupations ÷ all visas, and workers in short occupations ÷ all workers.`,
        shows: m => `${m.a1.share_of_visas_to_short_occupations_pct}% of visas against ${m.a1.share_of_workers_in_short_occupations_pct}% of workers.`,
        limits: m => m.a1.limits[2]
      } },
    { id: "exA3", chart: "a1Scatter", span: 4, types: ["estimate"], sources: () => ["ha_bp0014", "jsa_osl", "jsa_proj"],
      title: m => m.a1.growth_effect_clear ? "Shortages and growth both track where visas go" : "Shortage status, not growth, tracks where visas go",
      sub: () => "Each dot is an occupation: growth to 2030 against visas per 1,000 workers", csv: "visas_vs_shortages.csv",
      info: {
        why: () => "Every occupation at once shows whether the averages hide anything.",
        how: () => "Horizontal: Jobs and Skills Australia's projected growth to 2030. Vertical: temporary skilled visas per 1,000 workers, on a log scale (0 is drawn at the bottom). Blue: on the shortage list.",
        shows: m => `Rank correlation with shortage status ${m.a1.spearman_visas_vs_short.rho}; with growth ${m.a1.spearman_visas_vs_growth.rho} (n = ${m.a1.spearman_visas_vs_growth.n}).`,
        limits: m => m.a1.limits[1]
      } },
    { id: "exA4", chart: "coefPlot", span: 6, types: ["estimate"], sources: () => ["ha_bp0014", "jsa_osl", "jsa_proj"],
      title: m => `On the shortage list: about ${Math.round(m.a1.short_effect_pct)}% more visas per worker, other things equal`,
      sub: m => `Regression of log(1 + visas per 1,000 workers), n = ${m.a1.regression.n}, R² = ${m.a1.regression.r2}. Bars are 95% confidence intervals (robust)`, csv: "visas_vs_shortages.csv",
      info: {
        why: () => "A regression separates shortages from growth and skill level, which move together.",
        how: m => `Ordinary least squares with ${m.a1.regression.standard_errors} standard errors. Terms: on the shortage list (yes or no), projected growth (per percentage point), and skill level (compared with level 1).`,
        shows: m => `Shortage coefficient ${m.a1.regression.terms.find(t => t.term === "short_now").coef.toFixed(3)} (95% CI ${m.a1.short_effect_pct_ci95[0]}% to ${m.a1.short_effect_pct_ci95[1]}% more visas per worker). Growth: ${m.a1.growth_effect_clear ? "a clear effect" : "no clear effect"}. Skill levels 4 and 5 get far fewer visas, as most aren't eligible.`,
        limits: m => m.a1.limits[0]
      } },
    { id: "exA5", chart: "sensitivity", span: 6, types: ["estimate", "illustration"], sources: () => ["model", "abs_pop", "abs_build", "abs_census_hh"],
      title: d => d.q6.sensitivity && d.q6.sensitivity.all_below_built ? `At ${d.q6.sensitivity.people_per_home_range[0]} to ${d.q6.sensitivity.people_per_home_range[1]} people per home, every plan still fits today's building` : "Homes needed move with household size",
      sub: () => "Homes needed a year under each plan when one assumption changes (our model)", csv: "model_sensitivity.csv",
      info: {
        why: () => "A model is only as good as its assumptions. Changing them one at a time shows which ones matter.",
        how: () => "People per home from 2.3 to 2.8 (2.5 is the 2021 Census average); births minus deaths 10% lower or higher; opposition plans starting a year later. Each run changes one assumption.",
        shows: d => d.q6.sensitivity ? `Government: ${f().int(d.q6.sensitivity.homes_needed_range.gov[0])} to ${f().int(d.q6.sensitivity.homes_needed_range.gov[1])} homes a year across the people-per-home range.` : "",
        limits: () => "Each assumption is changed on its own; real changes can come together."
      } },
    { id: "exA6", chart: "lateStart", span: 6, types: ["estimate", "illustration"], sources: () => ["model", "abs_pop", "budget"],
      title: d => d.q5.sensitivity ? `A year's delay adds up to ${f().k(Math.max(...Object.values(d.q5.sensitivity.late_start_difference)))} people by 2030` : "Timing matters",
      sub: () => "Population at June 2030 if the opposition plans start in 2027-28 instead of 2026-27 (our model)", csv: "model_sensitivity.csv",
      info: {
        why: () => "An opposition can't change migration until after an election, so its plan may start later.",
        how: () => "Same model; the Coalition and One Nation plans begin a year later, with the latest 12 months held for the year in between.",
        shows: d => d.q5.sensitivity ? `Coalition +${f().int(d.q5.sensitivity.late_start_difference.coa)}; One Nation +${f().int(d.q5.sensitivity.late_start_difference.on)}.` : "",
        limits: () => "Election timing is uncertain; this shows one plausible delay."
      } },
    { id: "exA7", chart: "selfCheck", span: 6, types: ["estimate"], sources: () => ["model"],
      title: m => "Two languages, one answer: the browser model matches the Python pipeline",
      sub: () => "Our in-browser model against the pipeline's results, every plan, case and place (difference in people or homes)", csv: "scenario_summary.csv",
      info: {
        why: () => "The plan builder and simulator run in your browser. This checks them, live, against the Python pipeline.",
        how: () => "On page load, the browser model reruns every plan, case and state, and compares population, homes needed and working-age people with the pipeline's table.",
        shows: () => "Every difference is within one person or home (rounding).",
        limits: () => "It proves the two implementations agree, not that the assumptions are right; the sensitivity tests cover that."
      } },
    { id: "exA8", chart: "pipeline", span: 12, types: ["official", "estimate"], sources: () => [],
      title: m => `From ${m.pipeline.source_files} source files to ${m.pipeline.figures} charts`,
      sub: () => "How the numbers get from official releases to this page", csv: "data_dictionary.csv",
      info: {
        why: () => "Every number on this page can be traced back to a source file.",
        how: m => `${m.pipeline.scripts} Python scripts read the source files, log row counts at ${m.pipeline.steps_logged} steps, and document ${m.pipeline.columns_documented} columns in ${m.pipeline.tables_documented} tables. One script writes the data behind this page.`,
        shows: m => `${m.pipeline.downloads} tables can be downloaded; every chart has a table view and a source line.`,
        limits: () => "Source releases are checked by hand when they change; the pipeline doesn't fetch new data by itself."
      } }
  ];

  // ---------------------------------------------------------------- welcome guide
  const guide = {
    lede: "A data story, a simulator and a full report about who moves to Australia, the skills we need and what each party plans. Here's how it works:",
    items: [
      ["Scroll the story.", "Eight short chapters. The chart changes as the text scrolls past it."],
      ["Hover or tap", "any bar, line or dot for its exact number. On a keyboard, press Tab to reach a chart, then use the arrow keys."],
      ["The labels on each chart", "say what kind of numbers you're looking at:", true],
      ["Your turn:", "the simulator. Pick a size and a mix of skilled migration and see how many workers reach short jobs."],
      ["The report", "has every chart as a numbered exhibit. **About** explains how it was made and its limits, **Table** shows every number, **CSV** downloads the data."],
      ["Models", "shows the regression, the sensitivity tests and the model's live self-check. **Brief** is a two-page summary that prints to PDF."],
      ["The Dark and Light button", "switches the colours. The **?** button opens this guide again."]
    ]
  };

  MBS.content = {
    meta: {
      title: "Migration by Skill",
      tagline: "Not how many. Which skills, where, and why.",
      subtitle: "Who moves to Australia, the jobs we need, and what each party plans: a data story, a simulator and a full report.",
      author: "Meet Sharma",
      status: "Numbers are checked against the data; the charts are not yet approved."
    },
    types: TYPES, INFO, hero, chapters, bottomLine, sim, report, exhibits, models, guide, WORD, WORKERS, JOBS,
    helpers: { cap, list, byId, grp, plan, maxPph, ausState, topStates, biggestGap, studentsNet, skilledNet }
  };
})();
