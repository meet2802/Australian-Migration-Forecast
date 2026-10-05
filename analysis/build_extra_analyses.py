"""Two extra analyses for the dashboard's researcher layer.

A1. Do visas go where the shortages are?
    Across occupations (ANZSCO unit groups), compare temporary skilled visa grants per 1,000 workers with whether the
    occupation is on the 2025 shortage list and how fast it is projected to grow. Rank correlations (Spearman) and a
    regression of log(1 + visas per 1,000 workers) on shortage status, projected growth and skill level, with
    heteroskedasticity-robust (HC1) standard errors. Descriptive only: it shows where visas went, not why.

A2. How sensitive is the scenario model to its assumptions?
    Re-runs analysis/build_scenario_model.py's arithmetic with other values for people per home (2.3 to 2.8), the
    working-age share of migrants, births minus deaths, and a later start for the opposition plans.

Run from the Migration folder:  python3 analysis/build_extra_analyses.py
(Run build_occupation_table.py and build_scenario_model.py first. run_all.py does this.)

Outputs:
  analysis/visas_vs_shortages.csv          one row per occupation in the A1 analysis
  analysis/visas_vs_shortages_summary.json A1 results: shares, medians, correlations, regression
  analysis/model_sensitivity.csv           A2: each test, setting, plan and measure, against the central result
  analysis/extra_analyses_checks.json
Uses only numpy and pandas (no scipy or statsmodels), so it runs wherever the rest of the pipeline runs.
"""
import json
import math

import numpy as np
import pandas as pd

import build_scenario_model as sm
from _common import HERE, dictionary_rows, log_rows, update_dictionary, write_table

CODE = "unit_group_code"
S_OCC = "analysis/occupation_skills_national.csv (JSA projections and 2025 shortage list; Home Affairs BP0014)"
D, E, C = "Derived (our calculation)", "Estimate (our model)", "Classification"


# ---------------------------------------------------------------- A1
def norm_p(z):
    """Two-sided p-value from the normal distribution (large-sample approximation)."""
    return math.erfc(abs(z) / math.sqrt(2))


def spearman(x, y):
    """Spearman's rank correlation (average ranks for ties) with a large-sample p-value."""
    d = pd.DataFrame({"x": x, "y": y}).dropna()
    rx, ry = d["x"].rank(), d["y"].rank()
    rho = float(np.corrcoef(rx, ry)[0, 1])
    n = len(d)
    t = rho * math.sqrt((n - 2) / max(1e-12, 1 - rho ** 2))
    return {"rho": round(rho, 3), "n": n, "p_approx": float(f"{norm_p(t):.2g}")}


def ols_hc1(y, X, names):
    """Ordinary least squares with HC1 robust standard errors."""
    X = np.column_stack([np.ones(len(y)), X])
    n, k = X.shape
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    resid = y - X @ beta
    meat = (X * resid[:, None] ** 2).T @ X
    cov = xtx_inv @ meat @ xtx_inv * n / (n - k)
    se = np.sqrt(np.diag(cov))
    r2 = 1 - (resid @ resid) / ((y - y.mean()) @ (y - y.mean()))
    rows = []
    for name, b, s in zip(["intercept"] + names, beta, se):
        z = b / s
        rows.append({"term": name, "coef": round(float(b), 4), "se_hc1": round(float(s), 4),
                     "ci95_low": round(float(b - 1.96 * s), 4), "ci95_high": round(float(b + 1.96 * s), 4),
                     "p_approx": float(f"{norm_p(z):.2g}")})
    return {"n": int(n), "r2": round(float(r2), 3), "terms": rows}


def a1():
    o = pd.read_csv(HERE / "occupation_skills_national.csv", dtype={CODE: str})
    log_rows("A1: read the occupation table", o, "occupation_skills_national.csv")
    o = o[o[CODE].str.fullmatch(r"\d{4}")]
    log_rows("A1: kept four-digit unit groups", o)
    o = o[~o["not_further_defined"].astype(str).eq("True") & o["in_jsa_projections"].astype(str).eq("True")]
    log_rows("A1: dropped 'not further defined' codes and codes without projections", o)
    o = o[o["employed_may2025"].gt(0) & o["projected_growth_5y_pct"].notna()]
    log_rows("A1: kept occupations with workers and a growth projection", o)
    # a few unit groups span skill levels ("2, 3"): use the highest skill (lowest number) listed
    o["skill_level"] = o["skill_level"].astype(str).str.extract(r"(\d)")[0].astype(float)
    o = o[o["skill_level"].notna()]
    o["short"] = o["shortage_now"].map({"Short now": 1, "Not short now": 0})
    all_occ = o.copy()
    o = o[o["short"].notna()].copy()
    log_rows("A1: kept occupations rated on the 2025 shortage list", o, note="'Not assessed' occupations left out")
    o["visas_per_1000_workers"] = 1000 * o["visa_grants_primary"] / o["employed_may2025"]
    out = o[[CODE, "occupation", "skill_level", "shortage_now", "short", "projected_growth_5y_pct", "employed_may2025",
             "visa_grants_primary", "visas_per_1000_workers"]].copy()
    out["short"] = out["short"].astype(int)
    out["visas_per_1000_workers"] = out["visas_per_1000_workers"].round(2)
    out["rank_visas_per_1000"] = out["visas_per_1000_workers"].rank(ascending=False, method="min").astype(int)
    # a stable two-key sort, so ties come out in the same order on every computer
    out = out.sort_values(["visas_per_1000_workers", CODE], ascending=[False, True], kind="mergesort").reset_index(drop=True)

    tot_v, tot_w = o["visa_grants_primary"].sum(), o["employed_may2025"].sum()
    sh = o[o["short"].eq(1)]
    share_visas_short = 100 * sh["visa_grants_primary"].sum() / tot_v
    share_workers_short = 100 * sh["employed_may2025"].sum() / tot_w
    na = all_occ[all_occ["short"].isna()]
    by_skill = (o.groupby("skill_level").agg(occupations=(CODE, "size"), visa_grants=("visa_grants_primary", "sum"),
                                             workers=("employed_may2025", "sum")).reset_index())
    by_skill["visas_per_1000_workers"] = (1000 * by_skill["visa_grants"] / by_skill["workers"]).round(2)

    y = np.log1p(o["visas_per_1000_workers"].to_numpy())
    skill = pd.get_dummies(o["skill_level"].astype(int), prefix="skill", drop_first=True, dtype=float)
    X = np.column_stack([o["short"].to_numpy(float), o["projected_growth_5y_pct"].to_numpy(float), skill.to_numpy()])
    names = ["short_now", "growth_5y_pct"] + list(skill.columns)
    reg = ols_hc1(y, X, names)
    sub = o[o["skill_level"].le(3)]
    skill3 = pd.get_dummies(sub["skill_level"].astype(int), prefix="skill", drop_first=True, dtype=float)
    reg3 = ols_hc1(np.log1p(sub["visas_per_1000_workers"].to_numpy()),
                   np.column_stack([sub["short"].to_numpy(float), sub["projected_growth_5y_pct"].to_numpy(float),
                                    skill3.to_numpy()]), ["short_now", "growth_5y_pct"] + list(skill3.columns))
    b_short = next(t for t in reg["terms"] if t["term"] == "short_now")
    b_grow = next(t for t in reg["terms"] if t["term"] == "growth_5y_pct")
    summary = {
        "question": "Do temporary skilled visas go to occupations that are short of workers or growing fast?",
        "unit": "ANZSCO unit group (four-digit occupation)",
        "occupations": int(len(o)), "occupations_not_rated_left_out": int(len(na)),
        "visa_measure": "Temporary skilled visas granted to main applicants, 2025-26, per 1,000 workers (May 2025)",
        "visa_grants_in_analysis": int(tot_v),
        "share_of_visas_to_short_occupations_pct": round(share_visas_short, 1),
        "share_of_workers_in_short_occupations_pct": round(share_workers_short, 1),
        "visas_per_1000_workers_short": round(1000 * sh["visa_grants_primary"].sum() / sh["employed_may2025"].sum(), 2),
        "visas_per_1000_workers_not_short": round(1000 * o.loc[o["short"].eq(0), "visa_grants_primary"].sum()
                                                  / o.loc[o["short"].eq(0), "employed_may2025"].sum(), 2),
        "median_visas_per_1000_short": round(float(sh["visas_per_1000_workers"].median()), 2),
        "median_visas_per_1000_not_short": round(float(o.loc[o["short"].eq(0), "visas_per_1000_workers"].median()), 2),
        "occupations_with_no_visas_pct": round(100 * float(o["visa_grants_primary"].eq(0).mean()), 1),
        "spearman_visas_vs_short": spearman(o["visas_per_1000_workers"], o["short"]),
        "spearman_visas_vs_growth": spearman(o["visas_per_1000_workers"], o["projected_growth_5y_pct"]),
        "regression": {"outcome": "log(1 + visas per 1,000 workers)", "standard_errors": "HC1 (robust)",
                       "skill_level_reference": "skill level 1", **reg},
        "regression_skill_1_to_3": {"outcome": "log(1 + visas per 1,000 workers)", "standard_errors": "HC1 (robust)",
                                    **reg3},
        "short_effect_pct": round(100 * (math.exp(b_short["coef"]) - 1), 1),
        "short_effect_pct_ci95": [round(100 * (math.exp(b_short["ci95_low"]) - 1), 1),
                                  round(100 * (math.exp(b_short["ci95_high"]) - 1), 1)],
        "growth_effect_pct_per_point": round(100 * (math.exp(b_grow["coef"]) - 1), 1),
        "by_skill_level": by_skill.to_dict("records"),
        "plain_words": None,
        "limits": ["Descriptive: it shows where visas went in one year, not what caused it.",
                   "Shortage status is yes or no; it does not measure the size of a shortage.",
                   "Some occupations are not eligible for temporary skilled visas, which the skill-level terms only "
                   "partly capture.",
                   "Occupations not rated on the 2025 list are left out."],
    }
    grow_sig = b_grow["ci95_low"] > 0 or b_grow["ci95_high"] < 0
    summary["plain_words"] = (
        f"{summary['share_of_visas_to_short_occupations_pct']:.0f}% of temporary skilled visas went to jobs on the "
        f"shortage list, which hold {summary['share_of_workers_in_short_occupations_pct']:.0f}% of workers in the jobs "
        f"rated. Short jobs got {summary['visas_per_1000_workers_short']:.1f} visas per 1,000 workers, other jobs "
        f"{summary['visas_per_1000_workers_not_short']:.1f}. "
        + ("Faster projected growth also went with more visas, once shortages and skill level are allowed for."
           if grow_sig else "Projected growth made no clear difference once shortages and skill level are allowed for."))
    summary["growth_effect_clear"] = bool(grow_sig)
    return out, summary


# ---------------------------------------------------------------- A2
def run_model(people_per_home=None, working_age_share=None, natural_scale=1.0, late_start=False):
    paths = pd.read_csv(HERE / "scenario_nom_paths.csv")
    _, shares, _ = sm.age_profile()
    b, _, _ = sm.base()
    b = b.copy()
    b["natural_increase"] = b["natural_increase"] * natural_scale
    cases = sm.nom_cases(paths, b.loc["AUS", "homes_completed_12m"], b.loc["AUS", "nom_12m"])
    if late_start:
        # the opposition plans start a year later, after the next election: 2026-27 follows the Budget path, and
        # each plan's year 1 moves to 2027-28 (One Nation's fourth year falls after 2029-30)
        gov1 = float(cases[cases["plan"].eq(sm.GOV) & cases["financial_year"].eq(sm.YEARS[0])]["nom_aus"].iloc[0])
        new = []
        for (plan, case), g in cases.groupby(["plan", "case"], sort=False):
            g = g.set_index("financial_year").reindex(sm.YEARS)
            vals = g["nom_aus"].tolist()
            if plan in (sm.COA, sm.ON):
                vals = [gov1] + vals[:-1]
            new += [(plan, case, y, v) for y, v in zip(sm.YEARS, vals)]
        cases = pd.DataFrame(new, columns=["plan", "case", "financial_year", "nom_aus"])
    saved = sm.PEOPLE_PER_HOME
    try:
        if people_per_home:
            sm.PEOPLE_PER_HOME = people_per_home
        pop = sm.project(cases, b, working_age_share or shares["15-64"])
        summ = sm.summarise(pop)
    finally:
        sm.PEOPLE_PER_HOME = saved
    return summ[summ["place"].eq("AUS")].set_index(["plan", "case"]), shares["15-64"]


def a2():
    base, was = run_model()
    measures = {"population_june_2030": "Population at 30 June 2030",
                "homes_needed_per_year": "Homes needed a year for the growth",
                "working_age_people_added_via_nom_4y": "Working-age people added through migration, four years"}
    tests = [("people_per_home", v, {"people_per_home": v}, ["homes_needed_per_year"]) for v in (2.3, 2.4, 2.6, 2.7, 2.8)]
    tests += [("working_age_share", round(v, 3), {"working_age_share": v}, ["working_age_people_added_via_nom_4y"])
              for v in (0.80, 0.86)]
    tests += [("births_minus_deaths", s, {"natural_scale": s}, ["population_june_2030", "homes_needed_per_year"])
              for s in (0.9, 1.1)]
    tests += [("opposition_plans_start_2027_28", "yes", {"late_start": True},
               ["population_june_2030", "homes_needed_per_year"])]
    rows = []
    for plan, case in base.index:
        for m in measures:
            rows.append({"test": "central", "setting": "as published", "plan": plan, "case": case, "measure": m,
                         "value": base.loc[(plan, case), m], "central_value": base.loc[(plan, case), m]})
    for test, setting, kw, ms in tests:
        res, _ = run_model(**kw)
        for plan, case in res.index:
            for m in ms:
                rows.append({"test": test, "setting": setting, "plan": plan, "case": case, "measure": m,
                             "value": res.loc[(plan, case), m], "central_value": base.loc[(plan, case), m]})
    out = pd.DataFrame(rows)
    out["value"] = out["value"].round().astype("Int64")
    out["central_value"] = out["central_value"].round().astype("Int64")
    out["difference"] = (out["value"] - out["central_value"]).astype("Int64")
    out["measure_label"] = out["measure"].map(measures)
    out["setting"] = out["setting"].astype(str)
    out = out[["test", "setting", "plan", "case", "measure", "measure_label", "value", "central_value", "difference"]]
    return out, was


def main():
    occ, summ = a1()
    sens, was = a2()
    built = int(sm.base()[0].loc["AUS", "homes_completed_12m"])
    h = sens[sens["measure"].eq("homes_needed_per_year") & sens["test"].isin(["central", "people_per_home"])]
    plans = h[h["case"].eq("central")]
    summ_sens = {
        "people_per_home_range": [2.3, 2.8], "homes_completed_reference": built,
        "homes_needed_range_by_plan": {p: [int(g["value"].min()), int(g["value"].max())]
                                       for p, g in plans.groupby("plan")},
        "every_central_plan_below_completions_across_range": bool((plans["value"] <= built).all()),
        "late_start_population_2030_difference": {
            p: int(g["difference"].iloc[0]) for p, g in sens[sens["test"].eq("opposition_plans_start_2027_28")
                                                            & sens["measure"].eq("population_june_2030")
                                                            & sens["case"].eq("central")].groupby("plan")},
    }
    outs = {HERE / "visas_vs_shortages.csv": occ, HERE / "model_sensitivity.csv": sens}
    written = {p.name: write_table(d, p).name for p, d in outs.items()}
    summ["checked_by"] = "analysis/build_extra_analyses.py"
    (HERE / "visas_vs_shortages_summary.json").write_text(json.dumps(summ, indent=1, default=str))
    checks = {"files_written": written, "a1_occupations": summ["occupations"], "a1_plain_words": summ["plain_words"],
              "a1_spearman_growth": summ["spearman_visas_vs_growth"], "a1_spearman_short": summ["spearman_visas_vs_short"],
              "a2": summ_sens, "working_age_share_central": round(was, 4),
              "rows": {p.name: len(d) for p, d in outs.items()}}
    (HERE / "extra_analyses_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))

    m = {
        CODE: ("ANZSCO unit group code", S_OCC, "", C),
        "occupation": ("Occupation (unit group)", S_OCC, "", C),
        "skill_level": ("ANZSCO skill level, 1 (degree) to 5; where a unit group spans levels, the highest skill (lowest "
                        "number)", S_OCC, "", C),
        "shortage_now": ("On the 2025 shortage list (Short now) or rated not short (Not short now)", S_OCC, "2025", C),
        "short": ("1 = short now, 0 = not short now", S_OCC, "2025", D),
        "projected_growth_5y_pct": ("Projected growth in workers, May 2025 to May 2030, %", S_OCC, "2025 to 2030",
                                    "Forecast (JSA)"),
        "employed_may2025": ("Workers, May 2025", S_OCC, "May 2025", "Official estimate (JSA)"),
        "visa_grants_primary": ("Temporary skilled visas granted to main applicants", S_OCC, "2025-26",
                                "Official data (Home Affairs)"),
        "visas_per_1000_workers": ("visa_grants_primary per 1,000 workers", "", "", D),
        "rank_visas_per_1000": ("Rank by visas per 1,000 workers (1 = most)", "", "", D),
        "test": ("Which assumption was changed (central = as published)", "This project", "", C),
        "setting": ("The value tried", "This project", "", C),
        "plan": ("Plan, or the reference line", "analysis/scenario_nom_paths.csv", "", C),
        "case": ("central, low or high", "analysis/scenario_nom_paths.csv", "", C),
        "measure": ("Result column from analysis/scenario_summary.csv", "", "", C),
        "measure_label": ("The result in plain words", "", "", C),
        "value": ("The result with the changed assumption (Australia)", "analysis/build_scenario_model.py", "", E),
        "central_value": ("The published central result", "analysis/scenario_summary.csv", "", E),
        "difference": ("value - central_value", "", "", E),
    }
    rows = []
    for p, d in outs.items():
        rows += dictionary_rows(f"analysis/{written[p.name]}", d, m)
    rl = HERE / "row_counts.csv"
    rlm = {"script": ("Build script", "This project", "", C), "step_no": ("Order of the step in the script", "", "", C),
           "step": ("What the step does", "", "", C), "table": ("File or table at that step", "", "", C),
           "rows": ("Rows after the step", "", "", D), "columns": ("Columns after the step", "", "", D),
           "note": ("Note on the step", "", "", C)}
    rows += dictionary_rows("analysis/row_counts.csv", pd.DataFrame(columns=list(rlm)), rlm)
    update_dictionary(rows)
    _ = rl


if __name__ == "__main__":
    main()
