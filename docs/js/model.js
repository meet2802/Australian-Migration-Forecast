/* Migration by Skill: the scenario model in the browser. The same arithmetic as analysis/build_scenario_model.py,
   so the plan builder and the slider give the pipeline's numbers for the party presets (checked by the tests).
   For each year: growth = national NOM x the place's share + births minus deaths + net moves from other states;
   homes needed = growth / people per home; working-age people added = NOM x the share of arrivals aged 15 to 64. */
(function () {
  "use strict";
  const MBS = (window.MBS = window.MBS || {});

  // nom: national net overseas migration for each plan year; place: "AUS" or a state code
  function run(nom, place, opts) {
    const M = MBS.explore.model;
    const p = M.places[place || "AUS"];
    const pph = (opts && opts.peoplePerHome) || M.people_per_home;
    const was = (opts && opts.workingAgeShare) || M.working_age_share;
    let pop = p.start_pop;
    const years = M.years.map((fy, i) => {
      const n = nom[i] * p.nom_share;
      const growth = n + p.natural_increase + p.interstate;
      const start = pop;
      pop += growth;
      return { fy, nom: n, natural_increase: p.natural_increase, interstate: p.interstate, growth, start, end: pop,
        homes_needed: growth / pph, working_age: n * was };
    });
    const sum = k => years.reduce((a, y) => a + y[k], 0);
    return {
      place: place || "AUS", years, start_pop: p.start_pop, pop_2030: pop, growth_4y: sum("growth"),
      homes_per_year: sum("homes_needed") / years.length, working_age_4y: sum("working_age"),
      built: p.homes_built, accord: place === "AUS" || !place ? M.accord : null, people_per_home: pph
    };
  }

  // national-only version for the story slider (needs only the small story data file)
  function national(nomPerYear, peoplePerHome) {
    const S = MBS.data.slider;
    const pph = peoplePerHome || S.people_per_home;
    const growth = nomPerYear + S.natural_increase;
    return { pop_2030: S.start_pop + S.years * growth, homes_per_year: growth / pph,
      working_age_4y: S.years * nomPerYear * S.working_age_share, built: S.built, accord: S.accord };
  }

  MBS.model = { run, national };
})();
