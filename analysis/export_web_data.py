"""Bundle the pipeline's tables into the dashboard's data files, so the dashboard opens by double-click and works
offline (no server, no fetch).

Run from the Migration folder:  python3 analysis/export_web_data.py
(Run it last: it reads the outputs of every other build script. run_all.py does this.)

Outputs:
  docs/data/data.js           the 13-question story (loaded first, small)
  docs/data/data-explore.js   the four explore doors: jobs, states, the plan builder and all claim cards
  docs/data/data-methods.js   the Data and methods page: tables, dictionary, assumptions, analyses, sources
  docs/downloads/*.csv        copies of the tables behind the charts, for "download this data"
  analysis/web_export_checks.json  what was written, sizes, and the cross-checks below

Every number the dashboard shows comes from these files. Result lines are filled from them by templates in
docs/content/content.js; nothing is typed by hand. Where two tables hold the same figure, the script asserts
they agree before writing.
"""
import hashlib
import json
import math
import shutil

import numpy as np
import pandas as pd

import build_scenario_model as sm
from _common import HERE, ROOT, STATE_NAMES, STATES, TIDY

DASH = ROOT / "docs"
OUT = DASH / "data"
DL = DASH / "downloads"
MCG = 100_024
PLACES = ["AUS"] + STATES
PLACE_NAMES = {code: max((k for k, v in STATE_NAMES.items() if v == code), key=len) for code in PLACES}
FOCUS_RULE = (50.0, 60.0)   # Q9/Q10: most jobs short (>= 50%) and local training counted for >= 60% of the need

# Sources, APA 7th style. Release dates come from data_inventory.csv; where no exact date is known, year only.
SOURCES = {
    "abs_pop": {"short": "ABS, National, state and territory population, March 2026",
                "apa": "Australian Bureau of Statistics. (2026). National, state and territory population, March "
                       "2026 [Data set]. Released 17 September 2026.",
                "url": "https://www.abs.gov.au/statistics/people/population/national-state-and-territory-population"},
    "abs_hist": {"short": "ABS, Historical population, 2021",
                 "apa": "Australian Bureau of Statistics. (2024). Historical population, 2021 [Data set] (Tables "
                        "HPDC1 and HPDC7).",
                 "url": "https://www.abs.gov.au/statistics/people/population/historical-population"},
    "abs_om": {"short": "ABS, Overseas migration, 2024-25",
               "apa": "Australian Bureau of Statistics. (2025). Overseas migration, 2024-25 [Data set] (Table "
                      "34070DO004). Released 19 December 2025.",
               "url": "https://www.abs.gov.au/statistics/people/population/overseas-migration"},
    "abs_build": {"short": "ABS, Building activity, March 2026",
                  "apa": "Australian Bureau of Statistics. (2026). Building activity, Australia, March 2026 [Data "
                         "set] (Tables 34 and 38). Released 8 July 2026.",
                  "url": "https://www.abs.gov.au/statistics/industry/building-and-construction/building-activity-"
                         "australia"},
    "abs_census_hh": {"short": "ABS, 2021 Census QuickStats",
                      "apa": "Australian Bureau of Statistics. (2022). 2021 Census QuickStats: Australia.",
                      "url": "https://www.abs.gov.au/census/find-census-data/quickstats/2021/AUS"},
    "abs_mso": {"short": "ABS, Migrant settlement outcomes, 2026 (Census 2021 linked data)",
                "apa": "Australian Bureau of Statistics. (2026). Migrant settlement outcomes, 2026 [Data set] "
                       "(MSODC01). Released 22 September 2026.",
                "url": "https://www.abs.gov.au/statistics/people/people-and-communities/migrant-settlement-outcomes"},
    "jsa_osl": {"short": "Jobs and Skills Australia, 2025 Occupation Shortage List",
                "apa": "Jobs and Skills Australia. (2025). 2025 Occupation shortage list [Data set].",
                "url": "https://www.jobsandskills.gov.au/data/occupation-shortages-analysis/occupation-shortage-list"},
    "jsa_proj": {"short": "Jobs and Skills Australia, Employment projections, May 2025 to May 2035",
                 "apa": "Jobs and Skills Australia. (2025). Employment projections, May 2025 to May 2035 [Data set].",
                 "url": "https://www.jobsandskills.gov.au/data/employment-projections"},
    "jsa_ivi": {"short": "Jobs and Skills Australia, Internet Vacancy Index, August 2026",
                "apa": "Jobs and Skills Australia. (2026). Internet vacancy index, August 2026 [Data set].",
                "url": "https://www.jobsandskills.gov.au/data/internet-vacancy-index"},
    "ncver": {"short": "NCVER, Apprentices and trainees (DataBuilder)",
              "apa": "National Centre for Vocational Education Research. (2026). Apprentices and trainees "
                     "[Data set]. NCVER DataBuilder.",
              "url": "https://www.ncver.edu.au/research-and-statistics/data/databuilder"},
    "edu": {"short": "Department of Education, 2024 award course completions",
            "apa": "Department of Education. (2025). 2024 Section 14: Award course completions [Data set].",
            "url": "https://www.education.gov.au/higher-education-statistics"},
    "ha_bp0014": {"short": "Home Affairs, Temporary resident (skilled) visas, BP0014, to 30 June 2026",
                  "apa": "Department of Home Affairs. (2026). Temporary resident (skilled) visas granted and visa "
                         "holders, as at 30 June 2026 (BP0014) [Data set]. data.gov.au.",
                  "url": "https://data.gov.au/data/dataset/visa-temporary-work-skilled"},
    "ha_bp0019": {"short": "Home Affairs, Temporary visa holders, BP0019, 31 August 2026",
                  "apa": "Department of Home Affairs. (2026). Number of temporary visa holders in Australia at 31 "
                         "August 2026 (BP0019) [Data set]. data.gov.au.",
                  "url": "https://data.gov.au/data/dataset/temporary-entrants-visa-holders"},
    "budget": {"short": "Budget 2026-27, Budget Paper No. 3, Table A.5",
               "apa": "Australian Government. (2026). Budget 2026-27: Budget paper no. 3, Appendix A, Table A.5.",
               "url": "https://budget.gov.au/content/bp3/download/bp3_14_appendix_a.pdf"},
    "accord": {"short": "The Treasury, Delivering the National Housing Accord",
               "apa": "The Treasury. (n.d.). Delivering the National Housing Accord. Retrieved October 4, 2026.",
               "url": "https://treasury.gov.au/policy-topics/housing/accord"},
    "mcg": {"short": "Melbourne Cricket Club, MCG ticket information",
            "apa": "Melbourne Cricket Club. (n.d.). Ticket information. Retrieved October 4, 2026.",
            "url": "https://www.mcg.org.au/plan-a-visit/seating-and-ticket-information/ticket-information"},
    "model": {"short": "Our model (analysis/build_scenario_model.py)",
              "apa": "Migration by Skill. (2026). Scenario model, version 1 [Computer software]. "
                     "analysis/build_scenario_model.py.", "url": ""},
}


def rnd(x, n=0):
    """Round for JSON: ints for n=0, floats otherwise; None for missing."""
    if x is None or (isinstance(x, float) and math.isnan(x)) or pd.isna(x):
        return None
    return int(round(float(x))) if n == 0 else round(float(x), n)


def label_month(p):
    return pd.Period(p, "M").strftime("%B %Y")


def fy_label(year_end):
    return f"{year_end - 1}-{str(year_end)[2:]}"


def largest_remainder(values, total, fixed=None):
    """Whole-number shares of `total` that add up exactly; `fixed` = {key: n} assigned first (conventional
    rounding for the group the result line talks about), the rest by largest remainder."""
    fixed = fixed or {}
    out = dict(fixed)
    rest = {k: v for k, v in values.items() if k not in fixed}
    left = total - sum(fixed.values())
    s = sum(rest.values())
    raw = {k: v / s * left for k, v in rest.items()}
    floors = {k: int(math.floor(v)) for k, v in raw.items()}
    short = left - sum(floors.values())
    for k in sorted(raw, key=lambda k: raw[k] - floors[k], reverse=True)[:short]:
        floors[k] += 1
    out.update(floors)
    return out


# ---------------------------------------------------------------- story
def pop_quarterly():
    p = pd.read_csv(TIDY / "abs_population_quarterly_by_state.csv")
    p["q"] = pd.PeriodIndex(p["quarter"], freq="M")
    return p


def q1_q2(p, checks):
    a = p[p["state"].eq("AUS")].sort_values("q").set_index("q")
    a["nom12"] = a["nom"].rolling(4).sum()
    last = a.index.max()
    nom = float(a.loc[last, "nom12"])
    ev = pd.read_csv(HERE / "everyday_comparisons.csv").set_index("item")
    assert int(ev.loc["Net overseas migration, latest 12 months", "value"]) == round(nom)
    q1 = {"nom": rnd(nom), "period_end": str(last), "period_label": f"the year to {label_month(last)}",
          "mcg_capacity": MCG, "mcgs": round(nom / MCG, 2), "per_day": rnd(nom / 365),
          "pop_latest": rnd(a.loc[last, "erp"]), "growth_12m": rnd(a["growth"].iloc[-4:].sum()),
          "sources": ["abs_pop", "mcg"]}

    lr = pd.read_csv(HERE / "population_long_run_australia.csv")
    early = lr[(lr["year"] >= 1950) & (lr["year"] <= 1981)]
    series = []
    for r in early.itertuples():
        cal = "31 December" in r.nom_reference
        series.append({"x": r.year + (1.0 if cal else 0.5), "v": rnd(r.nom),
                       "label": str(r.year) if cal else fy_label(r.year), "kind": "calendar" if cal else "financial"})
    roll = a[a["nom12"].notna()]
    for q, r in roll.iterrows():
        series.append({"x": round(q.year + q.month / 12, 4), "v": rnd(r["nom12"]),
                       "label": f"Year to {q.strftime('%b %Y')}", "kind": "rolling"})
    s = pd.DataFrame(series)
    pk = s.loc[s["v"].idxmax()]
    lo = s.loc[s["v"].idxmin()]
    fy21 = lr.loc[lr["year"].eq(2021)].iloc[0]
    fy23 = lr.loc[lr["year"].eq(2023)].iloc[0]
    per1000 = lr.set_index("year")["nom_per_1000_pop"]
    # the 12 months to June 2021 in the quarterly series should equal the 2020-21 financial-year figure
    j21 = float(a.loc[pd.Period("2021-06", "M"), "nom12"])
    checks["q2_fy2020_21_vs_rolling_june_2021"] = [rnd(fy21["nom"]), rnd(j21)]
    assert abs(j21 - fy21["nom"]) < 50
    since = per1000[(per1000.index < 2023)]
    higher_before = since[since >= per1000[2023]]
    q2 = {"series": series, "peak": {"v": rnd(pk["v"]), "label": pk["label"], "x": pk["x"]},
          "low": {"v": rnd(lo["v"]), "label": lo["label"], "x": lo["x"]},
          "latest": {"v": rnd(nom), "label": f"Year to {last.strftime('%b %Y')}", "x": series[-1]["x"]},
          "fy_2020_21": rnd(fy21["nom"]), "fy_2022_23": rnd(fy23["nom"]),
          "per1000_2022_23": round(float(per1000[2023]), 1), "per1000_1949": round(float(per1000[1949]), 1),
          "per1000_1950": round(float(per1000[1950]), 1),
          "per1000_last_higher_year": int(higher_before.index.max()),
          "per1000_last_higher": round(float(higher_before.iloc[-1]), 1),
          "fall_from_peak_pct": round(100 * (1 - nom / pk["v"]), 1),
          "sources": ["abs_pop", "abs_hist"]}
    return q1, q2, last


def q3(checks):
    v = pd.read_csv(HERE / "nom_by_visa_group.csv")
    fy = v["financial_year"].max()
    g = v[v["state"].eq("AUS") & v["financial_year"].eq(fy)]
    tot = float(g.loc[g["row_type"].eq("total"), "arrivals"].iloc[0])
    grp = g[g["row_type"].eq("group")].set_index("visa_group")
    res = g[g["row_type"].eq("residual")]
    assert res.empty or float(res["arrivals"].sum()) == 0, "unassigned arrivals"
    plain = {  # visa_group -> (key, plain label, kind)
        "Skilled (permanent)": ("perm_skilled", "Skilled", "permanent"),
        "Family": ("perm_family", "Family", "permanent"),
        "Special eligibility & humanitarian": ("perm_humanitarian", "Humanitarian and special", "permanent"),
        "Other (permanent)": ("perm_other", "Other permanent", "permanent"),
        "Student": ("students", "Students", "temporary"),
        "Working holiday": ("working_holiday", "Working holiday", "temporary"),
        "Visitors": ("visitors", "Visitors", "temporary"),
        "Skilled (temporary)": ("temp_skilled", "Temporary skilled workers", "temporary"),
        "Other (temporary)": ("temp_other", "Other temporary", "temporary"),
        "Australian citizens (no visa)": ("aus_citizens", "Australians coming home", "citizen"),
        "New Zealand citizens (subclass 444)": ("nz_citizens", "New Zealanders", "citizen"),
    }
    assert set(grp.index) == set(plain), set(grp.index) ^ set(plain)
    arr = {plain[k][0]: float(grp.loc[k, "arrivals"]) for k in plain}
    assert abs(sum(arr.values()) - tot) < 1
    perm = sum(x for k, x in arr.items() if k.startswith("perm_"))
    perm_sub = g.loc[g["visa_group"].eq("Total permanent visas"), "arrivals"]
    assert abs(float(perm_sub.iloc[0]) - perm) < 1
    blocks = {"permanent": perm, **{k: x for k, x in arr.items() if not k.startswith("perm_")}}
    perm_sq = int(round(100 * perm / tot))
    sq = largest_remainder(blocks, 100, fixed={"permanent": perm_sq})
    perm_split = largest_remainder({k: x for k, x in arr.items() if k.startswith("perm_")}, perm_sq)
    groups = []
    for vg, (key, label, kind) in plain.items():
        groups.append({"key": key, "label": label, "kind": kind, "arrivals": rnd(arr[key]),
                       "squares": perm_split[key] if kind == "permanent" else sq[key],
                       "per100": round(100 * arr[key] / tot, 1)})
    order = ["perm_skilled", "perm_family", "perm_humanitarian", "perm_other", "students", "working_holiday",
             "visitors", "temp_skilled", "temp_other", "aus_citizens", "nz_citizens"]
    groups.sort(key=lambda d: order.index(d["key"]))
    assert sum(d["squares"] for d in groups) == 100
    temp = sum(arr[k] for k in arr if plain_kind(plain, k) == "temporary")
    cit = sum(arr[k] for k in arr if plain_kind(plain, k) == "citizen")
    checks["q3_squares"] = {d["key"]: d["squares"] for d in groups}
    temp_pub = float(g.loc[g["visa_group"].eq("Total temporary visas"), "arrivals"].iloc[0])
    checks["q3_temporary_groups_vs_published_subtotal"] = [rnd(temp), rnd(temp_pub)]
    assert abs(temp - temp_pub) <= 20, "temporary groups should match the published subtotal within ABS rounding"
    # net migration (arrivals minus departures) by the same groups: who adds to net overseas migration
    net_tot = float(g.loc[g["row_type"].eq("total"), "net"].iloc[0])
    net = {plain[k][0]: float(grp.loc[k, "net"]) for k in plain}
    assert abs(sum(net.values()) - net_tot) <= 20, "net by group should add to the total within ABS rounding"
    for d in groups:
        d["net"] = rnd(net[d["key"]])
        d["net_share_pct"] = round(100 * net[d["key"]] / net_tot, 1)
    skilled_net = net["perm_skilled"] + net["temp_skilled"]
    checks["q3_net"] = {"total": rnd(net_tot), "skilled": rnd(skilled_net),
                        "skilled_share_pct": round(100 * skilled_net / net_tot, 2)}
    return {"year": fy, "arrivals": rnd(tot), "permanent": rnd(perm), "temporary": rnd(temp), "citizens": rnd(cit),
            "temporary_published": rnd(temp_pub),
            "net_total": rnd(net_tot), "skilled_net": rnd(skilled_net),
            "skilled_net_share_pct": round(100 * skilled_net / net_tot, 2),
            "permanent_squares": perm_sq, "permanent_per100": round(100 * perm / tot, 1),
            "temporary_squares": sum(d["squares"] for d in groups if d["kind"] == "temporary"),
            "citizen_squares": sum(d["squares"] for d in groups if d["kind"] == "citizen"),
            "groups": groups,
            "guess_options": [[0, 25], [26, 50], [51, 75], [76, 100]],
            "sources": ["abs_om"]}


def plain_kind(plain, key):
    return next(kind for (k, _, kind) in plain.values() if k == key)


def q4_q5_q6(q1, checks):
    paths = pd.read_csv(HERE / "scenario_nom_paths.csv")
    pol = pd.read_csv(TIDY / "policy_migration_positions.csv")
    srcmap = pol.drop_duplicates("source_key").set_index("source_key")
    summ = pd.read_csv(HERE / "scenario_summary.csv")
    pop = pd.read_csv(HERE / "scenario_population.csv")
    aus = summ[summ["place"].eq("AUS")].set_index(["plan", "case"])
    years = sm.YEARS

    def src(keys):
        out = []
        for k in str(keys).split(";"):
            k = k.strip()
            if k in srcmap.index:
                r = srcmap.loc[k]
                out.append({"key": k, "text": r["source"], "url": r["source_url"], "published": r["published"]})
        return out

    pop_aus = pop[pop["place"].eq("AUS")]
    cut = pol[pol["plan"].eq(sm.ON) & pol["measure"].eq("Temporary visa holders (party modelling, total)")]
    assert len(cut) == 1
    on_cut = -rnd(cut["value"].iloc[0])

    def yearly(plan, case):
        g = pop_aus[(pop_aus["plan"].eq(plan)) & (pop_aus["case"].eq(case))].set_index("financial_year")
        return [rnd(g.loc[y, "nom"]) for y in years]

    gov = paths[paths["plan"].eq(sm.GOV)].set_index("period")
    coa = paths[paths["plan"].eq(sm.COA)].iloc[0]
    on = paths[paths["plan"].eq(sm.ON)].set_index("period")
    grn = paths[paths["plan"].eq("Greens")].iloc[0]
    plans = [
        {"id": "gov", "name": "Government", "party": "Labor", "full": sm.GOV, "kind": "forecast",
         "status": gov.loc["2026-27", "status"], "nom": yearly(sm.GOV, "central"),
         "current_year_forecast": rnd(gov.loc["2025-26", "nom"]),
         "note": "Budget forecast for 2026-27 and 2027-28, then projection", "sources": src("bp3")},
        {"id": "coa", "name": "Coalition", "party": "Liberal-National", "full": sm.COA, "kind": "plan",
         "status": coa["status"], "nom": yearly(sm.COA, "central"), "nom_low": yearly(sm.COA, "low"),
         "reported_range": [rnd(coa["nom_low"]), rnd(coa["nom_high"])],
         "note": coa["basis"], "sources": src(coa["source_key"])},
        {"id": "on", "name": "One Nation", "party": "One Nation", "full": sm.ON, "kind": "plan",
         "status": on.loc["Year 4 onward", "status"], "nom": yearly(sm.ON, "central"),
         "nom_low": yearly(sm.ON, "low"), "nom_high": yearly(sm.ON, "high"),
         "illustration_years": [years[i] for i in range(3)], "party_cut": on_cut,
         "illustration_status": on.loc["Year 1", "status"],
         "note_years_1_3": on.loc["Year 1", "basis"], "note_year_4": on.loc["Year 4 onward", "basis"],
         "sources": src(on.loc["Year 1", "source_key"]) + src(on.loc["Year 4 onward", "source_key"])},
        {"id": "grn", "name": "Greens", "party": "Greens", "full": "Greens", "kind": "none",
         "status": grn["status"], "nom": None, "note": grn["basis"], "sources": src(grn["source_key"])},
    ]
    ref = sm.REF
    q4 = {"years": years, "now": {"v": q1["nom"], "label": q1["period_label"], "fy": "2025-26"},
          "plans": plans, "reference_nom": yearly(ref, "central"),
          "first_year": {"gov": plans[0]["nom"][0], "on": plans[2]["nom"][0]},
          "sources": ["budget", "abs_pop"]}
    assert plans[0]["nom"] == [245000, 225000, 225000, 225000]

    def s(plan, case, col):
        return rnd(aus.loc[(plan, case), col])

    today = s(sm.GOV, "central", "population_june_2026_est")
    q5rows = [
        {"id": "gov", "name": "Government", "v": s(sm.GOV, "central", "population_june_2030"), "kind": "estimate"},
        {"id": "coa", "name": "Coalition", "v": s(sm.COA, "central", "population_june_2030"),
         "low": s(sm.COA, "low", "population_june_2030"), "kind": "estimate"},
        {"id": "on", "name": "One Nation", "v": s(sm.ON, "central", "population_june_2030"),
         "low": s(sm.ON, "low", "population_june_2030"), "high": s(sm.ON, "high", "population_june_2030"),
         "kind": "illustration"},
    ]
    refv = s(ref, "central", "population_june_2030")
    vals = [r["v"] for r in q5rows]
    gap = max(vals) - min(vals)
    q5 = {"today": today, "today_label": "30 June 2026 (our estimate)", "year": 2030, "plans": q5rows,
          "reference": {"name": "If the last 12 months continued", "v": refv},
          "min": min(vals), "max": max(vals), "gap": gap, "gap_mcgs": round(gap / MCG, 1),
          "min_plan": min(q5rows, key=lambda r: r["v"])["name"], "max_plan": max(q5rows, key=lambda r: r["v"])["name"],
          "sources": ["model", "abs_pop", "budget"]}

    ctx = pd.read_csv(HERE / "scenario_housing_context.csv")
    since = ctx[ctx["window"].str.startswith("Since the borders") & ctx["place"].eq("AUS")].iloc[0]
    last12 = ctx[ctx["window"].eq("Latest 12 months") & ctx["place"].eq("AUS")].iloc[0]
    built = s(sm.GOV, "central", "homes_completed_reference_per_year")
    assert built == rnd(last12["homes_completed"])
    q6rows = [
        {"id": "gov", "name": "Government", "v": s(sm.GOV, "central", "homes_needed_per_year"), "kind": "estimate"},
        {"id": "coa", "name": "Coalition", "v": s(sm.COA, "central", "homes_needed_per_year"),
         "low": s(sm.COA, "low", "homes_needed_per_year"), "kind": "estimate"},
        {"id": "on", "name": "One Nation", "v": s(sm.ON, "central", "homes_needed_per_year"),
         "low": s(sm.ON, "low", "homes_needed_per_year"), "high": s(sm.ON, "high", "homes_needed_per_year"),
         "kind": "illustration"},
        {"id": "ref", "name": "If the last 12 months continued", "v": s(ref, "central", "homes_needed_per_year"),
         "kind": "estimate", "context": True},
    ]
    keeps_up = [r["name"] for r in q6rows if r["v"] <= built]
    q6 = {"plans": q6rows, "built": built, "built_label": f"Homes finished in the year to "
                                                         f"{label_month(last12['to_quarter'])}",
          "accord": sm.ACCORD_PER_YEAR, "people_per_home": sm.PEOPLE_PER_HOME,
          "all_plans_below_built": all(r["v"] <= built for r in q6rows if not r.get("context")),
          "plans_keeping_up": keeps_up,
          "shortfall": -rnd(since["homes_completed_minus_needed"]), "shortfall_from": "March quarter 2022",
          "shortfall_to": label_month(since["to_quarter"]),
          "shortfall_growth": rnd(since["population_growth"]), "shortfall_homes_completed": rnd(since["homes_completed"]),
          "sources": ["model", "abs_build", "accord", "abs_census_hh"]}
    checks["q6_shortfall"] = q6["shortfall"]

    b, last_q, h_last = sm.base()
    _, shares, _ = sm.age_profile()
    slider = {"start_pop": rnd(b.loc["AUS", "erp_june_2026_est"]),
              "natural_increase": rnd(b.loc["AUS", "natural_increase"]),
              "people_per_home": sm.PEOPLE_PER_HOME, "working_age_share": round(shares["15-64"], 4),
              "built": built, "accord": sm.ACCORD_PER_YEAR, "years": len(years), "min": -250000, "max": 600000,
              "step": 5000, "start": 225000,
              "marks": [{"name": p["name"], "v": p["nom"][-1]} for p in plans if p["nom"]]}
    assert slider["start_pop"] == today
    return q4, q5, q6, slider, b, shares


def sectors_national():
    n = pd.read_csv(HERE / "named_sector_summary_national.csv")
    sec = n[n["row_type"].eq("Named sector")].copy()
    allj = n[n["row_type"].eq("Total")].iloc[0]
    return n, sec, allj


def q7_q8(sec, allj):
    rows = []
    for r in sec.itertuples():
        rows.append({"id": r.sector_id, "name": r.short_name, "full": r.sector_name, "group": r.sector_group,
                     "short_pct": rnd(r.jobs_in_shortage_pct, 1), "assessed_pct": rnd(r.jobs_assessed_pct, 1),
                     "growth_pct": rnd(r.projected_growth_5y_pct, 1),
                     "short_and_growing_pct": rnd(r.jobs_short_and_growing_faster_pct, 1),
                     "employed": rnd(r.employed_may2025), "projected_2030": rnd(r.projected_may2030),
                     "need_per_year": rnd(r.new_workers_needed_per_year_est)})
    by_short = sorted(rows, key=lambda d: -d["short_pct"])
    by_growth = sorted(rows, key=lambda d: -d["growth_pct"])
    top_short = by_short[:4]
    top_growth = by_growth[:5]
    q7 = {"sectors": rows, "all_short_pct": rnd(allj["jobs_in_shortage_pct"], 1),
          "all_assessed_pct": rnd(allj["jobs_assessed_pct"], 1),
          "top": [d["id"] for d in top_short],
          "top_min_pct": min(d["short_pct"] for d in top_short),
          "low_assessed": [d["id"] for d in rows if d["assessed_pct"] < 50],
          "sources": ["jsa_osl", "jsa_proj"]}
    q8 = {"all_growth_pct": rnd(allj["projected_growth_5y_pct"], 1),
          "top": [d["id"] for d in top_growth],
          "top_short_count": sum(d["short_pct"] >= 50 for d in top_growth),
          "short_threshold": 50, "sources": ["jsa_proj", "jsa_osl"]}
    return q7, q8


def q9_q10(sec, allj):
    short_min, cover_min = FOCUS_RULE
    pick = sec[(sec["jobs_in_shortage_pct"] >= short_min)
               & (sec["training_measured_share_of_need_pct"] >= cover_min)].copy()
    pick = pick.sort_values("local_training_per_100_needed")
    rows = [{"id": r.sector_id, "name": r.short_name, "trained_per_100": rnd(r.local_training_per_100_needed),
             "visas_per_100": rnd(r.visa_grants_per_100_needed), "need_per_year": rnd(r.new_workers_needed_per_year_est),
             "trained_effective": rnd(r.local_training_effective), "need_measured": rnd(r.need_where_training_measured),
             "measured_share_pct": rnd(r.training_measured_share_of_need_pct),
             "visa_grants": rnd(r.visa_grants_primary), "short_pct": rnd(r.jobs_in_shortage_pct, 1)}
            for r in pick.itertuples()]
    lowest = min(rows, key=lambda d: d["trained_per_100"])
    most_v = max(rows, key=lambda d: d["visas_per_100"])
    least_v = min(rows, key=lambda d: d["visas_per_100"])
    excluded = sec[~sec["sector_id"].isin(pick["sector_id"])][["sector_id", "short_name"]]
    return {"rows": rows, "rule": {"short_min_pct": short_min, "training_counted_min_pct": cover_min},
            "excluded": excluded["short_name"].tolist(),
            "lowest_trained": lowest["id"], "most_visas": most_v["id"], "fewest_visas": least_v["id"],
            "all_trained_per_100": rnd(allj["local_training_per_100_needed"]),
            "all_visas_per_100": rnd(allj["visa_grants_per_100_needed"]),
            "sources_q9": ["ncver", "edu", "jsa_proj"], "sources_q10": ["ha_bp0014", "jsa_proj"]}


def q11():
    m = pd.read_csv(HERE / "migrant_outcomes_by_stream.csv")
    t = m[m["arrival_group"].eq("Total")].set_index("population")
    pick = [("skilled", "Skilled visa migrants", "Permanent Skilled migrants", "focus"),
            ("everyone", "Everyone in Australia", "Total population", "comparison"),
            ("family", "Family visa migrants", "Permanent Family migrants", "context"),
            ("humanitarian", "Humanitarian visa migrants", "Permanent Humanitarian migrants", "context")]
    rows = [{"key": k, "label": lab, "pct": rnd(t.loc[pop, "employment_to_population_pct"], 1),
             "participation_pct": rnd(t.loc[pop, "participation_pct"], 1),
             "unemployment_pct": rnd(t.loc[pop, "unemployment_rate_pct"], 1), "role": role}
            for k, lab, pop, role in pick]
    rec = m[m["population"].eq("Permanent Skilled migrants") & m["arrival_group"].eq("Arrived within 5 years")].iloc[0]
    return {"rows": rows, "ages": "15 to 64", "period": "Census 2021",
            "skilled_recent_pct": rnd(rec["employment_to_population_pct"], 1),
            "sources": ["abs_mso"]}


def q12(sec_state, short_names, checks):
    h = pd.read_csv(HERE / "housing_vs_population_by_state.csv", dtype={"year_ending": str})
    last = h["year_ending"].max()
    g = h[h["year_ending"].eq(last)].set_index("state")
    states = []
    for code in PLACES:
        r = g.loc[code]
        ss = sec_state[sec_state["state"].eq(code)] if code != "AUS" else None
        top = []
        if ss is not None and len(ss):
            t = ss.sort_values("jobs_in_state_shortage_pct", ascending=False).head(3)
            top = [{"id": x.sector_id, "name": short_names[x.sector_id],
                    "short_pct": rnd(x.jobs_in_state_shortage_pct, 1)}
                   for x in t.itertuples()]
        states.append({"code": code, "name": PLACE_NAMES[code], "people_per_home": rnd(r["people_added_per_home_completed"], 2),
                       "growth": rnd(r["population_growth_12m"]), "homes": rnd(r["dwellings_completed_12m"]),
                       "nom": rnd(r["nom_12m"]), "population": rnd(r["erp_end"]), "top_short": top})
    aus = next(s for s in states if s["code"] == "AUS")
    calc = round(aus["growth"] / aus["homes"], 2)
    checks["q12_aus_people_per_home"] = [aus["people_per_home"], calc]
    assert abs(calc - aus["people_per_home"]) < 0.011
    return {"states": states, "period_label": f"the year to {label_month(last)}", "household": sm.PEOPLE_PER_HOME,
            "tiles": {"WA": [0, 1], "NT": [1, 0], "SA": [1, 1], "QLD": [2, 0], "NSW": [2, 1], "VIC": [2, 2],
                      "ACT": [3, 1], "TAS": [2, 3]},
            "sources": ["abs_build", "abs_pop", "jsa_osl"]}


def claims_all():
    f = pd.read_csv(HERE / "fact_check_cards.csv")
    testable = {"Accurate", "Mostly accurate", "Partly accurate", "Inaccurate"}
    cards = []
    for r in f.itertuples():
        cards.append({"id": r.card_id, "side": r.side, "speaker": r.speaker, "date": r.date_said, "claim": r.claim,
                      "type": r.claim_type, "topic": r.topic, "verdict": r.verdict,
                      "shows": r.what_the_data_shows, "caveat": None if pd.isna(r.caveats) else r.caveats,
                      "source": r.claim_source, "url": r.claim_url,
                      "tables": None if pd.isna(r.evidence_tables) else r.evidence_tables,
                      "checked_on": r.checked_on, "testable": r.verdict in testable})
    return cards


def q13(cards):
    parties = ["Labor", "Coalition", "One Nation", "Greens"]
    feat = []
    for p in parties:
        c = [x for x in cards if x["side"] == p and x["testable"]]
        # rule: each party's most recent claim we could test; a tie goes to the one listed first
        c.sort(key=lambda x: (x["date"], -cards.index(x)), reverse=True)
        feat.append(c[0]["id"])
    t = [x for x in cards if x["testable"]]
    good = [x for x in t if x["verdict"] in ("Accurate", "Mostly accurate")]
    counts = {}
    for x in cards:
        counts.setdefault(x["side"], {}).setdefault(x["verdict"], 0)
        counts[x["side"]][x["verdict"]] += 1
    return {"featured": feat, "total": len(cards), "testable": len(t), "accurate_or_mostly": len(good),
            "rule": "For each party, its most recent claim we could test (a tie goes to the one listed first).",
            "verdict_scale": ["Accurate", "Mostly accurate", "Partly accurate", "Inaccurate"],
            "not_testable": ["Too early to tell", "Plan (what it implies)", "Can't test with our data"],
            "counts_by_side": counts, "sources": []}


# ---------------------------------------------------------------- explore
def explore(b, shares, sec_nat, sec_state, cards, checks):
    o = pd.read_csv(HERE / "occupation_skills_national.csv", dtype={"unit_group_code": str})
    o = o[o["unit_group_code"].str.fullmatch(r"\d{4}")].copy()
    occ_sec = pd.read_csv(HERE / "named_sector_occupations.csv", dtype={"unit_group_code": str})
    main_sec = (occ_sec.sort_values("share_of_code_pct", ascending=False).drop_duplicates("unit_group_code")
                .set_index("unit_group_code")["sector_id"])
    o["sector_id"] = o["unit_group_code"].map(main_sec)
    occ_cols = {
        "code": "unit_group_code", "name": "occupation", "skill": "skill_level", "nfd": "not_further_defined",
        "sector": "sector_id", "short": "shortage_now", "osl": "osl_2025_rating", "growth_pct": "projected_growth_5y_pct",
        "growth_band": "growth_band", "employed": "employed_may2025", "proj_2030": "projected_may2030",
        "need": "new_workers_needed_per_year_est", "growth_per_year": "projected_growth_per_year",
        "retire": "retirements_per_year_est", "moves": "career_moves_net_loss_per_year_est",
        "earn": "median_weekly_earnings", "age55": "share_aged_55_plus_pct", "ads": "job_ads_latest",
        "ads_ago": "job_ads_year_ago", "appr_done": "apprentice_completions", "visa_grants": "visa_grants_primary",
        "visa_holders": "visa_holders_primary", "visa_per_1000": "visa_primary_per_1000_workers",
        "grp": "comparison_group", "grp_name": "comparison_group_name", "train_cover": "local_training_coverage",
        "grp_need": "group_new_workers_needed_per_year_est", "grp_trained": "group_local_training_effective",
        "grp_trained_100": "group_local_training_per_100_needed", "grp_visa_100": "group_visa_grants_per_100_needed",
    }
    num = {"growth_pct": 1, "age55": 1, "visa_per_1000": 1, "grp_trained_100": 0, "grp_visa_100": 0}
    rows = []
    for r in o.itertuples(index=False):
        rr = r._asdict()
        row = []
        for k, c in occ_cols.items():
            v = rr[c]
            if k in ("nfd",):
                row.append(bool(v))
            elif isinstance(v, str):
                row.append(v)
            elif k == "skill":
                row.append(rnd(v))
            else:
                row.append(rnd(v, num.get(k, 0)))
        rows.append(row)
    occupations = {"columns": list(occ_cols), "rows": rows}

    # job ads: national three-month average, one point a quarter for the last ten years
    iv = pd.read_csv(TIDY / "jsa_ivi_occupation4_state_monthly.csv.gz", dtype={"anzsco_code": str})
    iv = iv[iv["state"].eq("AUS") & iv["anzsco_code"].str.fullmatch(r"\d{4}")]
    lastm = pd.Period(iv["month"].max(), "M")
    months = [str(lastm - 3 * i) for i in range(40, -1, -1)]
    ivp = iv[iv["month"].isin(months)].pivot_table(index="anzsco_code", columns="month", values="job_ads_3m_avg")
    ivp = ivp.reindex(columns=months)
    ads = {code: [rnd(x) for x in vals] for code, vals in zip(ivp.index, ivp.values)}
    checks["job_ads_series"] = {"occupations": len(ads), "first": months[0], "last": months[-1]}

    os_ = pd.read_csv(HERE / "occupation_skills_state.csv", dtype={"unit_group_code": str})
    os_ = os_[os_["unit_group_code"].str.fullmatch(r"\d{4}")]
    st_cols = {"code": "unit_group_code", "state": "state", "osl": "osl_2025_state_rating",
               "employed": "employed_state_est", "visa_grants": "visa_grants_primary",
               "visa_holders": "visa_holders_primary", "ads": "job_ads_latest", "ads_ago": "job_ads_year_ago",
               "appr_done": "apprentice_completions"}
    st_rows = []
    for r in os_.itertuples(index=False):
        rr = r._asdict()
        st_rows.append([rr[c] if isinstance(rr[c], str) else rnd(rr[c]) for c in st_cols.values()])
    occ_state = {"columns": list(st_cols), "rows": st_rows}

    sectors = []
    for r in sec_nat.itertuples():
        sectors.append({"id": r.sector_id, "name": r.short_name, "full": r.sector_name, "group": r.sector_group,
                        "employed": rnd(r.employed_may2025), "short_pct": rnd(r.jobs_in_shortage_pct, 1),
                        "assessed_pct": rnd(r.jobs_assessed_pct, 1), "growth_pct": rnd(r.projected_growth_5y_pct, 1),
                        "need": rnd(r.new_workers_needed_per_year_est),
                        "trained_100": rnd(r.local_training_per_100_needed),
                        "trained_cover_pct": rnd(r.training_measured_share_of_need_pct),
                        "visa_100": rnd(r.visa_grants_per_100_needed), "visa_grants": rnd(r.visa_grants_primary),
                        "visa_per_1000": rnd(r.visa_grants_per_1000_workers, 1),
                        "ads": rnd(r.job_ads_latest), "ads_change_pct": rnd(r.job_ads_change_12m_pct, 1),
                        "age55": rnd(r.share_aged_55_plus_pct, 1), "industry": r.main_industry_plain_name,
                        "industry_share_pct": rnd(r.main_industry_share_pct, 1)})
    sec_st = []
    for r in sec_state.itertuples():
        sec_st.append([r.sector_id, r.state, rnd(r.employed_state_est), rnd(r.jobs_in_state_shortage_pct, 1),
                       rnd(r.jobs_assessed_pct, 1), rnd(r.visa_grants_primary), rnd(r.job_ads_latest),
                       rnd(r.job_ads_change_12m_pct, 1)])

    p = pop_quarterly()
    p = p[p["q"] >= pd.Period("1999-06", "M")].sort_values(["state", "q"])
    hq = pd.read_csv(HERE / "housing_vs_population_by_state.csv", dtype={"year_ending": str})
    states = {}
    for code in PLACES:
        x = p[p["state"].eq(code)].copy()
        x["nom12"] = x["nom"].rolling(4).sum()
        x["growth12"] = x["growth"].rolling(4).sum()
        x = x[x["q"] >= pd.Period("2001-06", "M")]
        hh = hq[hq["state"].eq(code) & (hq["year_ending"] >= "2001-06")].sort_values("year_ending")
        states[code] = {
            "name": PLACE_NAMES[code],
            "pop": [[str(q), rnd(e), rnd(n12), rnd(g12)] for q, e, n12, g12 in
                    zip(x["q"], x["erp"], x["nom12"], x["growth12"])],
            "homes": [[ye, rnd(c), rnd(g), rnd(pp, 2)] for ye, c, g, pp in
                      zip(hh["year_ending"], hh["dwellings_completed_12m"], hh["population_growth_12m"],
                          hh["people_added_per_home_completed"])],
        }

    model = {"years": sm.YEARS, "people_per_home": sm.PEOPLE_PER_HOME, "working_age_share": round(shares["15-64"], 6),
             "accord": sm.ACCORD_PER_YEAR,
             "places": {code: {"start_pop": float(b.loc[code, "erp_june_2026_est"]),
                               "natural_increase": float(b.loc[code, "natural_increase"]),
                               "interstate": float(b.loc[code, "net_interstate_migration"]),
                               "nom_share": round(float(b.loc[code, "nom_share"]), 8),
                               "homes_built": float(b.loc[code, "homes_completed_12m"])} for code in PLACES}}
    pop_s = pd.read_csv(HERE / "scenario_population.csv")
    presets = []
    for (plan, case), g in pop_s[pop_s["place"].eq("AUS")].groupby(["plan", "case"], sort=False):
        g = g.set_index("financial_year").reindex(sm.YEARS)
        pid = {sm.GOV: "gov", sm.COA: "coa", sm.ON: "on", sm.REF: "ref"}[plan]
        presets.append({"id": f"{pid}_{case}", "plan": pid, "case": case, "nom": [rnd(v) for v in g["nom"]]})
    model["presets"] = presets
    summ = pd.read_csv(HERE / "scenario_summary.csv")
    model["expected"] = [[r.plan, r.case, r.place, rnd(r.population_june_2030), rnd(r.homes_needed_per_year),
                          rnd(r.working_age_people_added_via_nom_4y)] for r in summ.itertuples()]
    return {"occupations": occupations, "job_ads": {"months": months, "series": ads}, "occ_state": occ_state,
            "sectors": sectors, "sector_state": {"columns": ["sector", "state", "employed", "short_pct",
                                                              "assessed_pct", "visa_grants", "ads", "ads_change_pct"],
                                                  "rows": sec_st},
            "states": states, "model": model, "claims": cards,
            "all_jobs": {"growth_pct": None}}


# ---------------------------------------------------------------- methods
DOWNLOADS = [
    ("tidy/abs_population_quarterly_by_state.csv", "Population, births minus deaths, migration and moves between "
     "states, every quarter since 1981, by state", ["q1", "q2", "q12", "your_state"]),
    ("analysis/population_long_run_australia.csv", "Population and net overseas migration since 1860", ["q2"]),
    ("analysis/nom_by_visa_group.csv", "Arrivals, departures and net migration by visa group, 2004-05 to 2024-25",
     ["q3"]),
    ("analysis/scenario_nom_paths.csv", "Each party's migration numbers, with sources and status", ["q4", "plans"]),
    ("analysis/scenario_population.csv", "Our model: each plan's population, homes and working-age people by year "
     "and state", ["q5", "q6", "plans"]),
    ("analysis/scenario_summary.csv", "Our model: four-year totals by plan and state", ["q5", "q6", "plans"]),
    ("analysis/scenario_assumptions.csv", "Every assumption in our model, with sources", ["q5", "q6", "plans"]),
    ("analysis/scenario_housing_context.csv", "Homes finished against homes needed for past growth", ["q6", "q12"]),
    ("analysis/housing_vs_population_by_state.csv", "Homes approved, started and finished against population "
     "growth, by state", ["q12", "your_state"]),
    ("analysis/named_sectors.csv", "The 24 job groups and the occupations in each", ["q7", "q8", "q9", "q10"]),
    ("analysis/named_sector_summary_national.csv", "The 24 job groups: shortages, growth, training and visas",
     ["q7", "q8", "q9", "q10"]),
    ("analysis/named_sector_summary_state.csv", "The 24 job groups by state", ["q12", "your_state"]),
    ("analysis/occupation_skills_national.csv", "Every occupation: shortage, growth, workers needed, training, "
     "visas and job ads", ["your_job"]),
    ("analysis/occupation_skills_state.csv", "Every occupation by state", ["your_job"]),
    ("analysis/migrant_outcomes_by_stream.csv", "Jobs and incomes of permanent migrants by visa stream "
     "(Census 2021)", ["q11"]),
    ("analysis/fact_check_cards.csv", "All 19 claims, verdicts and what the data shows", ["q13", "claims"]),
    ("analysis/everyday_comparisons.csv", "Headline numbers as full MCGs and people a day", ["q1"]),
    ("analysis/visas_vs_shortages.csv", "Extra analysis: do visas go where the shortages are? (by occupation)",
     ["q10", "methods"]),
    ("analysis/model_sensitivity.csv", "Extra analysis: how much the model's results move with its assumptions",
     ["q5", "q6", "methods"]),
    ("analysis/data_dictionary.csv", "What every column means, with its source and number type", ["methods"]),
]


def simulator(d3, d11, sectors, measured_ids, working_age_share, checks):
    """Inputs for the skills gap simulator (method A, 'size vs mix', agreed 5 October 2026). Our illustration:
    skilled workers a year = net overseas migration x skilled share x working-age share x employment rate of recent
    skilled migrants; today's mix follows 2025-26 temporary skilled visas, skills-first follows short jobs."""
    a1p = HERE / "visas_vs_shortages_summary.json"
    a1 = json.loads(a1p.read_text()) if a1p.exists() else {}
    rows = [{"id": s["id"], "name": s["name"], "need": s["need"], "short_pct": s["short_pct"],
             "visa_grants": s["visa_grants"], "trained_100": s["trained_100"],
             "trained_cover_pct": s["trained_cover_pct"]} for s in sectors]
    sim = {"year": d3["year"], "nom_total": d3["net_total"], "skilled_net": d3["skilled_net"],
           "skilled_share_pct": d3["skilled_net_share_pct"], "working_age_share": working_age_share,
           "employment_recent_pct": d11["skilled_recent_pct"],
           "short_share_of_visas_pct": a1.get("share_of_visas_to_short_occupations_pct"),
           "a1_occupations": a1.get("occupations"), "sectors": rows, "measured": measured_ids,
           "presets": [130000, 225000, 300000], "min": 0, "max": 400000, "step": 5000, "start": 225000,
           "sources": ["abs_om", "abs_mso", "ha_bp0014", "jsa_osl", "jsa_proj"]}
    workers_per_100 = working_age_share * d11["skilled_recent_pct"]
    checks["simulator"] = {"skilled_share_pct": sim["skilled_share_pct"], "workers_per_100_skilled": round(workers_per_100, 2),
                           "short_share_of_visas_pct": sim["short_share_of_visas_pct"], "sectors": len(rows)}
    return sim


def models_block(me):
    """Data for the Models appendix: the visas-and-shortages regression (one row per occupation), the sensitivity
    runs, and counts that describe the pipeline itself."""
    a1p = HERE / "visas_vs_shortages_summary.json"
    a1 = json.loads(a1p.read_text()) if a1p.exists() else None
    vv = HERE / "visas_vs_shortages.csv"
    rows = []
    if vv.exists():
        v = pd.read_csv(vv, dtype={"unit_group_code": str})
        rows = [[r.unit_group_code, r.occupation, rnd(r.skill_level), int(r.short), rnd(r.projected_growth_5y_pct, 1),
                 rnd(r.employed_may2025), rnd(r.visa_grants_primary), rnd(r.visas_per_1000_workers, 2)]
                for r in v.itertuples(index=False)]
    a2 = me["analyses"].get("a2") or []
    a2_cols = ["test", "setting", "plan", "case", "measure", "value", "central_value", "difference"]
    dic_rows = me["dictionary"]["rows"]
    pipeline = {"source_files": len(me["inventory"]),
                "scripts": len({r["script"] for r in me["row_counts"]}),
                "steps_logged": len(me["row_counts"]),
                "tables_documented": len({r[0] for r in dic_rows}),
                "columns_documented": len(dic_rows),
                "downloads": len(me["tables"]),
                "figures": len(me["figures"])}
    return {"a1": a1, "a1_rows": {"columns": ["code", "name", "skill", "short", "growth", "employed", "grants",
                                              "per1000"], "rows": rows},
            "a2": {"columns": a2_cols, "rows": [[r.get(c) for c in a2_cols] for r in a2]},
            "pipeline": pipeline}


def md5(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def methods(checks):
    DL.mkdir(parents=True, exist_ok=True)
    tables = []
    missing = []
    for rel, what, used in DOWNLOADS:
        src = ROOT / rel
        if not src.exists():
            missing.append(rel)
            continue
        dst = DL / src.name
        shutil.copyfile(src, dst)
        d = pd.read_csv(src, low_memory=False)
        tables.append({"file": src.name, "path": rel, "what": what, "rows": len(d), "columns": len(d.columns),
                       "used_in": used, "kb": round(src.stat().st_size / 1024)})
    keep = {t["file"] for t in tables} | {"README.txt"}
    for f in DL.iterdir():
        if f.name not in keep:
            f.unlink()
    (DL / "README.txt").write_text(
        "Copies of the tables behind the Migration by Skill dashboard, written by analysis/export_web_data.py.\n"
        "Column meanings, sources and number types are in data_dictionary.csv.\n")
    dic = pd.read_csv(HERE / "data_dictionary.csv", dtype=str, keep_default_na=False)
    assum = pd.read_csv(HERE / "scenario_assumptions.csv", dtype=str, keep_default_na=False)
    rc = HERE / "row_counts.csv"
    rows_log = pd.read_csv(rc, dtype=str, keep_default_na=False).to_dict("records") if rc.exists() else []
    a1 = HERE / "visas_vs_shortages_summary.json"
    a2 = HERE / "model_sensitivity.csv"
    analyses = {"a1": json.loads(a1.read_text()) if a1.exists() else None,
                "a2": pd.read_csv(a2).to_dict("records") if a2.exists() else None}
    figs = DASH / "figures.csv"
    figures = pd.read_csv(figs, dtype=str, keep_default_na=False).to_dict("records") if figs.exists() else []
    inv = ROOT / "data_inventory.csv"
    inventory = []
    if inv.exists():
        iv = pd.read_csv(inv, dtype=str, keep_default_na=False)
        inventory = iv[["file", "source", "what_it_is", "status", "checked_on"]].to_dict("records")
    checks["downloads"] = len(tables)
    checks["downloads_missing"] = missing
    if missing:
        print("WARNING: not yet built, so not in downloads:", missing)
    return {"tables": tables, "dictionary": {"columns": list(dic.columns), "rows": dic.values.tolist()},
            "assumptions": assum.to_dict("records"), "row_counts": rows_log, "analyses": analyses,
            "inventory": inventory, "figures": figures}


# ---------------------------------------------------------------- write
def write_js(path, name, obj):
    body = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    path.write_text(f"/* Written by analysis/export_web_data.py. Do not edit by hand. */\n"
                    f"window.MBS = window.MBS || {{}};\nwindow.MBS.{name} = {body};\n", encoding="utf-8")
    return {"file": f"docs/data/{path.name}", "kb": round(path.stat().st_size / 1024, 1), "md5": md5(path)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    checks = {}
    p = pop_quarterly()
    q1, q2, last = q1_q2(p, checks)
    d3 = q3(checks)
    q4, q5, q6, slider, b, shares = q4_q5_q6(q1, checks)
    sec_nat_all, sec, allj = sectors_national()
    q7, q8 = q7_q8(sec, allj)
    q910 = q9_q10(sec, allj)
    d11 = q11()
    sec_state = pd.read_csv(HERE / "named_sector_summary_state.csv")
    d12 = q12(sec_state, dict(zip(sec["sector_id"], sec["short_name"])), checks)
    cards = claims_all()
    d13 = q13(cards)
    a1p, a2p = HERE / "visas_vs_shortages_summary.json", HERE / "extra_analyses_checks.json"
    if a1p.exists():
        a1 = json.loads(a1p.read_text())
        q910["a1"] = {k: a1[k] for k in ("occupations", "share_of_visas_to_short_occupations_pct",
                                         "share_of_workers_in_short_occupations_pct", "visas_per_1000_workers_short",
                                         "visas_per_1000_workers_not_short", "plain_words", "growth_effect_clear")}
    if a2p.exists():
        a2 = json.loads(a2p.read_text())["a2"]
        ids = {sm.GOV: "gov", sm.COA: "coa", sm.ON: "on", sm.REF: "ref"}
        q6["sensitivity"] = {"people_per_home_range": a2["people_per_home_range"],
                             "homes_needed_range": {ids[k]: v for k, v in a2["homes_needed_range_by_plan"].items()},
                             "all_below_built": a2["every_central_plan_below_completions_across_range"]}
        q5["sensitivity"] = {"late_start_difference": {ids[k]: v for k, v in
                                                       a2["late_start_population_2030_difference"].items()}}
    story = {"version": "1.0-draft", "data_to": str(last), "places": PLACE_NAMES, "sources": SOURCES,
             "q1": q1, "q2": q2, "q3": d3, "q4": q4, "q5": q5, "q6": q6, "slider": slider, "q7": q7, "q8": q8,
             "q9": q910, "q11": d11, "q12": d12,
             "q13": {**d13, "cards": [c for c in cards if c["id"] in d13["featured"]]}}
    ex = explore(b, shares, sec_nat_all[sec_nat_all["row_type"].eq("Named sector")], sec_state, cards, checks)
    ex["all_jobs"] = {"growth_pct": q8["all_growth_pct"], "short_pct": q7["all_short_pct"]}
    story["sim"] = simulator(d3, d11, ex["sectors"], [r["id"] for r in q910["rows"]],
                             ex["model"]["working_age_share"], checks)
    me = methods(checks)
    ex["models"] = models_block(me)
    checks["models"] = {"a1_rows": len(ex["models"]["a1_rows"]["rows"]), "a2_rows": len(ex["models"]["a2"]["rows"]),
                        "pipeline": ex["models"]["pipeline"]}
    written = [write_js(OUT / "data.js", "data", story), write_js(OUT / "data-explore.js", "explore", ex),
               write_js(OUT / "data-methods.js", "methods", me)]
    checks["written"] = written
    checks["story_values"] = {
        "q1_nom": q1["nom"], "q1_mcgs": q1["mcgs"], "q1_per_day": q1["per_day"],
        "q2_peak": [q2["peak"]["v"], q2["peak"]["label"]], "q2_low": [q2["low"]["v"], q2["low"]["label"]],
        "q3_permanent_squares": d3["permanent_squares"], "q4_first_year": q4["first_year"],
        "q5_range": [q5["min"], q5["max"], q5["gap"], q5["gap_mcgs"]], "q6_shortfall": q6["shortfall"],
        "q7_top": q7["top"], "q8_top": q8["top"], "q9_rows": [(r["id"], r["trained_per_100"], r["visas_per_100"])
                                                             for r in q910["rows"]],
        "q11": [(r["key"], r["pct"]) for r in d11["rows"]], "q13": [d13["featured"], d13["testable"],
                                                                   d13["accurate_or_mostly"]]}
    (HERE / "web_export_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))


if __name__ == "__main__":
    main()
