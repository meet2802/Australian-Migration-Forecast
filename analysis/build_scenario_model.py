"""Version 1 scenario model: what each plan's migration path means for population, working-age people and homes,
nationally and by state, plus what One Nation's stated cut to temporary skilled visa holders could mean by sector.

A deliberately simple, transparent model: plain arithmetic on official data, no behaviour or feedback loops. Economic
effects (GDP per person, the budget, wages) come from published research and sit beside it
(tidy/research_economic_effects.csv), as agreed for the hybrid method.

Decided on 4 October 2026: Meet asked for the choices best for the project, so every assumption is ours. Each one is
written to analysis/scenario_assumptions.csv with its source, why we chose it and the option we did not take.

Run from the Migration folder:  python3 analysis/build_scenario_model.py
(Run build_population_tables.py, build_housing_tables.py, build_policy_inputs.py and build_named_sector_tables.py
first.)

Inputs: analysis/scenario_nom_paths.csv, tidy/abs_population_quarterly_by_state.csv,
analysis/housing_vs_population_by_state.csv, analysis/named_sector_summary_national.csv,
tidy/bp0019_temporary_visa_holders.csv, and 'ABS Graph 4.1 arrivals by age and sex 2024-25 (transcribed).csv'
(the data table behind Graph 4.1 of ABS Overseas Migration 2024-25, read from the release page on 4 October 2026 and
checked against the published total, median and mode).

Outputs:
  tidy/abs_overseas_arrivals_by_age_2024_25.csv  arrivals by single year of age and sex
  analysis/scenario_assumptions.csv               every assumption, with source and the alternative not taken
  analysis/scenario_population.csv                plan x case x place x year: NOM, births minus deaths, moves
                                                  between states, growth, population, working-age people, homes
  analysis/scenario_summary.csv                   plan x case x place: four-year totals and yearly averages
  analysis/scenario_housing_context.csv           homes completed against homes needed for past growth, for context
  analysis/scenario_skilled_exposure.csv          by sector: temporary skilled visa holders, and One Nation's stated
                                                  cut if it fell evenly across jobs (our illustration)
  analysis/scenario_checks.json
"""
import json

import numpy as np
import pandas as pd

from _common import HERE, ROOT, STATES, TIDY, dictionary_rows, update_dictionary, write_table

YEARS = ["2026-27", "2027-28", "2028-29", "2029-30"]
GOV, COA, ON = "Government (Labor)", "Coalition (Liberal-National)", "One Nation"
REF = "Reference: latest year held flat (not a plan)"
PLACES = ["AUS"] + STATES
PEOPLE_PER_HOME = 2.5            # ABS, Census 2021 QuickStats, Australia: average number of people per household
ACCORD_PER_YEAR = 240_000        # National Housing Accord: 1.2 million homes over five years from July 2024
ARRIVALS_2024_25 = 568_370       # ABS Overseas Migration 2024-25: overseas migrant arrivals (34070DO004)
ON_SKILLED_CUT = 103_000         # One Nation's own split: temporary skilled visa holders and dependants
AGE_FILE = ROOT / "ABS Graph 4.1 arrivals by age and sex 2024-25 (transcribed).csv"
S_ABS_POP = "ABS, National, state and territory population, March 2026 (tidy/abs_population_quarterly_by_state.csv)"
S_ABS_AGE = ("ABS, Overseas Migration 2024-25, Graph 4.1 'Overseas migrant arrivals - age and sex' (data table read "
             "from the release page on 4 Oct 2026)")
S_HOUSE = "ABS Building Activity, March quarter 2026 (analysis/housing_vs_population_by_state.csv)"
S_CENSUS = "ABS, 2021 Census QuickStats, Australia: average number of people per household"
S_PATHS = "analysis/scenario_nom_paths.csv (each plan's sources are listed there)"
S_HA = "Home Affairs, BP0019 temporary visa holders and BP0014 temporary skilled visas"
A, E, D, C = ("Assumption (ours)", "Estimate (our model)", "Derived (our calculation)", "Classification")


def age_profile():
    a = pd.read_csv(AGE_FILE, dtype={"age": str})
    a["age_years"] = a["age"].str.replace("+", "", regex=False).astype(int)
    a["males"] = (a["males_000"] * 1000).round().astype(int)
    a["females"] = (a["females_000"] * 1000).round().astype(int)
    a["persons"] = a["males"] + a["females"]
    total = int(a["persons"].sum())
    assert abs(total - ARRIVALS_2024_25) < 1_000, f"transcribed ages add to {total}, not about {ARRIVALS_2024_25}"
    cum = a["persons"].cumsum() / total
    checks = {"total_vs_abs": [total, ARRIVALS_2024_25], "median_age (ABS says 26)": int(a.loc[cum.ge(0.5).idxmax(),
                                                                                                   "age_years"]),
              "modal_age (ABS says 23)": int(a.loc[a["persons"].idxmax(), "age_years"]),
              "sex_ratio (ABS says 98)": round(100 * a["males"].sum() / a["females"].sum(), 1)}
    shares = {band: float(a.loc[a["age_years"].between(lo, hi), "persons"].sum() / total)
              for band, (lo, hi) in {"0-14": (0, 14), "15-64": (15, 64), "65+": (65, 200)}.items()}
    tidy = a[["age", "males", "females", "persons"]].assign(period="2024-25")
    return tidy, shares, checks


def base():
    p = pd.read_csv(TIDY / "abs_population_quarterly_by_state.csv")
    p["q"] = pd.PeriodIndex(p["quarter"], freq="M")
    last = p["q"].max()
    cols = ["natural_increase", "nom", "net_interstate_migration"]
    l12 = p[p["q"] > last - 12].groupby("state")[cols].sum()
    l36 = p[p["q"] > last - 36].groupby("state")["nom"].sum()
    same_q = p[p["q"] == last - 9].set_index("state")[cols].sum(axis=1)   # June quarter a year earlier
    erp = p[p["q"] == last].set_index("state")["erp"]
    h = pd.read_csv(HERE / "housing_vs_population_by_state.csv", dtype={"year_ending": str})
    h_last = h["year_ending"].max()
    homes = h[h["year_ending"].eq(h_last)].set_index("state")["dwellings_completed_12m"]
    out = pd.DataFrame({"natural_increase": l12["natural_increase"], "net_interstate_migration":
                        l12["net_interstate_migration"], "nom_12m": l12["nom"],
                        "nom_share": l36 / l36["AUS"], "erp_last": erp, "june_qtr_growth_est": same_q,
                        "homes_completed_12m": homes}).reindex(PLACES)
    out.loc["AUS", "net_interstate_migration"] = 0.0
    out["erp_june_2026_est"] = out["erp_last"] + out["june_qtr_growth_est"]
    return out, str(last), h_last


def nom_cases(paths, homes_aus, nom_12m_aus):
    """National NOM by plan, case and year (2026-27 = plan year 1)."""
    rows = []
    gov = paths[paths["plan"].eq(GOV)].set_index("period")["nom"]
    for y in YEARS:
        rows.append((GOV, "central", y, float(gov[y])))
    coa = paths[paths["plan"].eq(COA)].iloc[0]
    for y in YEARS:
        rows.append((COA, "central", y, float(homes_aus)))
        rows.append((COA, "low", y, float(coa["nom_low"])))
    on = paths[paths["plan"].eq(ON)].set_index("period")
    for i, y in enumerate(YEARS, start=1):
        r = on.loc[f"Year {i}"] if i <= 3 else on.loc["Year 4 onward"]
        rows += [(ON, "central", y, float(r["nom"])), (ON, "low", y, float(r["nom_low"])),
                 (ON, "high", y, float(r["nom_high"]))]
    for y in YEARS:
        rows.append((REF, "central", y, float(nom_12m_aus)))
    return pd.DataFrame(rows, columns=["plan", "case", "financial_year", "nom_aus"])


def project(cases, b, working_age_share):
    rows = []
    for (plan, case), g in cases.groupby(["plan", "case"], sort=False):
        g = g.set_index("financial_year").reindex(YEARS)
        for place in PLACES:
            pop = b.loc[place, "erp_june_2026_est"]
            for i, y in enumerate(YEARS, start=1):
                nom = g.loc[y, "nom_aus"] * b.loc[place, "nom_share"]
                ni, nim = b.loc[place, "natural_increase"], b.loc[place, "net_interstate_migration"]
                growth = nom + ni + nim
                start, pop = pop, pop + growth
                homes = b.loc[place, "homes_completed_12m"]
                rows.append({"plan": plan, "case": case, "place": place, "financial_year": y, "plan_year": i,
                             "nom": nom, "natural_increase": ni, "net_interstate_migration": nim,
                             "population_growth": growth, "population_start": start, "population_end": pop,
                             "working_age_people_added_via_nom": nom * working_age_share,
                             "homes_needed_for_growth": growth / PEOPLE_PER_HOME,
                             "homes_completed_reference": homes,
                             "homes_completed_minus_needed": homes - growth / PEOPLE_PER_HOME,
                             "accord_pace_per_year": ACCORD_PER_YEAR if place == "AUS" else np.nan})
    return pd.DataFrame(rows)


def summarise(pop):
    g = pop.groupby(["plan", "case", "place"], sort=False)
    s = g.agg(nom_4y=("nom", "sum"), population_growth_4y=("population_growth", "sum"),
              population_june_2026_est=("population_start", "first"), population_june_2030=("population_end", "last"),
              working_age_people_added_via_nom_4y=("working_age_people_added_via_nom", "sum"),
              homes_needed_4y=("homes_needed_for_growth", "sum"),
              homes_completed_reference_per_year=("homes_completed_reference", "first")).reset_index()
    s["homes_needed_per_year"] = s["homes_needed_4y"] / len(YEARS)
    s["homes_completed_minus_needed_per_year"] = s["homes_completed_reference_per_year"] - s["homes_needed_per_year"]
    s["people_added_per_home_completed"] = (s["population_growth_4y"] / len(YEARS)) / s[
        "homes_completed_reference_per_year"]
    gov = s[s["plan"].eq(GOV)].set_index("place")["population_june_2030"]
    s["population_june_2030_vs_government"] = s["population_june_2030"] - s["place"].map(gov)
    return s


def housing_context():
    """Homes completed against homes needed for past population growth (same 2.5 people per home), for context."""
    p = pd.read_csv(TIDY / "abs_population_quarterly_by_state.csv")
    p["q"] = pd.PeriodIndex(p["quarter"], freq="M")
    d = pd.read_csv(TIDY / "abs_dwellings_commenced_completed_by_state.csv")
    d = d[d["activity"].eq("Completed") & d["building_type"].eq("All dwellings") & d["sector"].eq("All sectors")
          & d["series_type"].eq("Original")].copy()
    d["q"] = pd.PeriodIndex(d["quarter"], freq="M")
    last = min(p["q"].max(), d["q"].max())
    windows = {"Latest 12 months": last - 9, "Since the borders reopened (from the March quarter 2022)":
               pd.Period("2022-03", "M"), "Five years": last - 57}
    rows = []
    for label, start in windows.items():
        g = p[(p["q"] >= start) & (p["q"] <= last)].groupby("state")["growth"].sum()
        h = d[(d["q"] >= start) & (d["q"] <= last)].groupby("state")["dwellings"].sum()
        for place in PLACES:
            needed = g[place] / PEOPLE_PER_HOME
            rows.append({"window": label, "from_quarter": str(start), "to_quarter": str(last), "place": place,
                         "population_growth": g[place], "homes_needed_for_growth": needed,
                         "homes_completed": h[place], "homes_completed_minus_needed": h[place] - needed,
                         "people_added_per_home_completed": g[place] / h[place]})
    return pd.DataFrame(rows)


def skilled_exposure():
    sec = pd.read_csv(HERE / "named_sector_summary_national.csv")
    sec = sec[sec["row_type"].eq("Named sector")]
    b = pd.read_csv(TIDY / "bp0019_temporary_visa_holders.csv", dtype=str)
    b["visa_holders"] = pd.to_numeric(b["visa_holders"])
    sk = b[b["visa_category"].eq("Temporary Resident (Skilled Employment)")]
    snap = "2026-06-30"   # the same date as the BP0014 occupation snapshot used for each sector
    base_all = int(sk.loc[sk["snapshot_date"].eq(snap), "visa_holders"].sum())
    share = ON_SKILLED_CUT / base_all
    out = sec[["sector_id", "sector_name", "short_name", "employed_may2025", "visa_holders_primary"]].copy()
    out["visa_holders_per_1000_workers"] = 1000 * out["visa_holders_primary"] / out["employed_may2025"]
    out["share_of_all_holders_pct"] = 100 * out["visa_holders_primary"] / out["visa_holders_primary"].sum()
    out["one_nation_cut_if_even"] = out["visa_holders_primary"] * share
    out["one_nation_cut_per_1000_workers"] = 1000 * out["one_nation_cut_if_even"] / out["employed_may2025"]
    out = out.sort_values("visa_holders_primary", ascending=False).reset_index(drop=True)
    return out, share, base_all, snap


def assumptions(b, last_q, h_last, shares, cut_share, cut_base, snap, paths):
    coa = paths[paths["plan"].eq(COA)].iloc[0]
    rows = [
        ("start", "Every plan starts on 1 July 2026 (plan year 1 = 2026-27)", "2026-27", "", "All plans",
         "This project", A, "Compares the plans on the same footing",
         "Start the opposition plans after the next federal election (due by 2028)"),
        ("horizon", "Four years, 2026-27 to 2029-30", "4", "years", "All plans", "This project", A,
         "Matches the Budget's forward estimates, the longest official NOM path", "A ten-year horizon"),
        ("gov_path", "Government NOM follows the 2026-27 Budget", "245,000 then 225,000", "people a year", GOV,
         S_PATHS, "Forecast (Treasury)", "The government's own published path", "None"),
        ("coalition_central", "Coalition cap = homes completed in the previous year, using the latest ABS 12 months, "
         "held flat", f"{int(b.loc['AUS', 'homes_completed_12m']):,}", "people a year", COA, S_HOUSE, A,
         "Applies the party's stated rule to official data",
         f"The ABC's estimated range ({int(coa['nom_low']):,} to {int(coa['nom_high']):,}); its low end is the "
         "'low' case"),
        ("one_nation_path", "One Nation: our labelled range for the three net-negative years, then the 130,000 cap",
         "-127,667 (range -255,333 to 0), then 130,000 (high case 230,000)", "people a year", ON, S_PATHS, A,
         "Built only from the party's own 766,000 figure (decided 4 Oct 2026)", "Leave the years blank"),
        ("reference", "Reference line: NOM in the latest 12 months held flat (not a plan)",
         f"{int(b.loc['AUS', 'nom_12m']):,}", "people a year", REF, S_ABS_POP, A,
         "Shows what the plans change compared with now", "None"),
        ("births_deaths", "Births minus deaths stay at the latest 12 months in every state",
         f"{int(b.loc['AUS', 'natural_increase']):,} nationally", "people a year", "All plans", S_ABS_POP, A,
         "Recent official figure; it changes slowly", "Use the Budget's population projections"),
        ("interstate", "Moves between states stay at the latest 12 months", "by state", "people a year",
         "All plans (states)", S_ABS_POP, A, "Recent official figure", "Hold them at zero"),
        ("state_shares", "Each state gets the share of NOM it had over the last three years (also for negative NOM)",
         "NSW 30%, VIC 29%, QLD 18%, WA 14%", "share of NOM", "All plans (states)", S_ABS_POP, A,
         "Smooths out single-year swings", "Use the latest year only"),
        ("start_population", f"Population at 30 June 2026 = official population at {last_q} plus the June quarter "
         "a year earlier", f"{int(b.loc['AUS', 'erp_june_2026_est']):,}", "people", "All plans", S_ABS_POP, E,
         "The June 2026 figure is not published until December 2026", "Start from March 2026 instead"),
        ("household_size", "Homes needed = population growth / 2.5 people per home, in every state",
         f"{PEOPLE_PER_HOME}", "people per home", "All plans", S_CENSUS, "Official data (ABS Census 2021)",
         "The average household (official). New arrivals may live in bigger or smaller households than average, so "
         "treat homes needed as a rough guide",
         "State household sizes (not in our data yet)"),
        ("homes_completed", f"Homes completed stay at the latest ABS 12 months (year to {h_last})",
         f"{int(b.loc['AUS', 'homes_completed_12m']):,} nationally", "homes a year", "All plans", S_HOUSE, A,
         "A neutral benchmark; the Housing Accord pace (240,000 a year) is shown alongside", "Use the Accord pace"),
        ("working_age", "Net migrants have the same age mix as 2024-25 arrivals", f"{100 * shares['15-64']:.1f}% "
         "aged 15 to 64", "share", "All plans", S_ABS_AGE, A,
         "ABS publishes arrivals by age on the release page but not departures", "Leave working-age people out"),
        ("one_nation_skilled", "One Nation's cut of 103,000 temporary skilled visa holders and dependants falls evenly "
         "across jobs (our illustration)", f"{100 * cut_share:.1f}% of {cut_base:,} holders at {snap}", "share",
         ON, f"{S_HA}; tidy/policy_migration_positions.csv", A,
         "The party gives a total but not which jobs; an even spread is the neutral starting point",
         "Assume the cut falls on particular jobs"),
    ]
    return pd.DataFrame(rows, columns=["assumption_id", "assumption", "value", "unit", "applies_to", "source",
                                       "number_type", "why", "alternative_not_taken"])


def main():
    paths = pd.read_csv(HERE / "scenario_nom_paths.csv")
    ages, shares, age_checks = age_profile()
    b, last_q, h_last = base()
    cases = nom_cases(paths, b.loc["AUS", "homes_completed_12m"], b.loc["AUS", "nom_12m"])
    pop = project(cases, b, shares["15-64"])
    summ = summarise(pop)
    expo, cut_share, cut_base, snap = skilled_exposure()
    ctx = housing_context()
    assum = assumptions(b, last_q, h_last, shares, cut_share, cut_base, snap, paths)

    ints = ["nom", "natural_increase", "net_interstate_migration", "population_growth", "population_start",
            "population_end", "working_age_people_added_via_nom", "homes_needed_for_growth",
            "homes_completed_reference", "homes_completed_minus_needed", "accord_pace_per_year"]
    for c in ints:
        pop[c] = pop[c].round().astype("Int64")
    for c in ["nom_4y", "population_growth_4y", "population_june_2026_est", "population_june_2030",
              "working_age_people_added_via_nom_4y", "homes_needed_4y", "homes_completed_reference_per_year",
              "homes_needed_per_year", "homes_completed_minus_needed_per_year", "population_june_2030_vs_government"]:
        summ[c] = summ[c].round().astype("Int64")
    summ["people_added_per_home_completed"] = summ["people_added_per_home_completed"].round(2)
    for c in ["one_nation_cut_if_even"]:
        expo[c] = expo[c].round().astype("Int64")
    for c in ["visa_holders_per_1000_workers", "share_of_all_holders_pct", "one_nation_cut_per_1000_workers"]:
        expo[c] = expo[c].round(1)
    for c in ["population_growth", "homes_needed_for_growth", "homes_completed", "homes_completed_minus_needed"]:
        ctx[c] = ctx[c].round().astype("Int64")
    ctx["people_added_per_home_completed"] = ctx["people_added_per_home_completed"].round(2)

    outs = {TIDY / "abs_overseas_arrivals_by_age_2024_25.csv": ages, HERE / "scenario_assumptions.csv": assum,
            HERE / "scenario_population.csv": pop, HERE / "scenario_summary.csv": summ,
            HERE / "scenario_skilled_exposure.csv": expo, HERE / "scenario_housing_context.csv": ctx}
    written = {p.name: write_table(d, p).name for p, d in outs.items()}

    aus = summ[summ["place"].eq("AUS")].set_index(["plan", "case"])
    st_sum = pop[pop["place"].ne("AUS")].groupby(["plan", "case", "financial_year"])["nom"].sum()
    au = pop[pop["place"].eq("AUS")].set_index(["plan", "case", "financial_year"])["nom"]
    checks = {
        "files_written": written,
        "age_table_checks": age_checks,
        "age_shares_of_arrivals_pct": {k: round(100 * v, 1) for k, v in shares.items()},
        "latest_population_quarter": last_q, "homes_completed_year_ending": h_last,
        "state_nom_shares_pct": {k: round(100 * v, 2) for k, v in b["nom_share"].items()},
        "state_nom_add_to_national (largest gap)": int((st_sum - au.reindex(st_sum.index)).abs().max()),
        "population_june_2026_est": int(b.loc["AUS", "erp_june_2026_est"]),
        "one_nation_skilled_cut_share_pct": round(100 * cut_share, 1),
        "housing_context_australia": ctx[ctx["place"].eq("AUS")].drop(columns="place").to_dict("records"),
        "national_results": aus[["nom_4y", "population_growth_4y", "population_june_2030",
                                 "population_june_2030_vs_government", "working_age_people_added_via_nom_4y",
                                 "homes_needed_per_year", "homes_completed_minus_needed_per_year"]]
                            .reset_index().to_dict("records"),
        "rows": {p.name: len(d) for p, d in outs.items()},
    }
    (HERE / "scenario_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))

    m = {
        "age": ("Age in single years (100+ = 100 and over)", S_ABS_AGE, "2024-25", C),
        "males": ("Male overseas migrant arrivals (published in thousands to two decimals)", S_ABS_AGE, "2024-25",
                  "Official data (ABS), transcribed"),
        "females": ("Female overseas migrant arrivals (published in thousands to two decimals)", S_ABS_AGE, "2024-25",
                    "Official data (ABS), transcribed"),
        "persons": ("males + females", S_ABS_AGE, "2024-25", D),
        "period": ("Financial year of the arrivals", S_ABS_AGE, "", C),
        "assumption_id": ("Short id of the assumption", "This project", "", C),
        "assumption": ("The assumption in plain words", "This project", "", C),
        "value": ("The value used", "See source", "", C),
        "unit": ("Unit of the value", "", "", C),
        "applies_to": ("Which plans or places it applies to", "", "", C),
        "source": ("Where the value comes from", "", "", C),
        "number_type": ("What kind of number the value is: assumption, forecast, estimate or official data", "", "",
                        C),
        "why": ("Why we chose it", "This project", "", C),
        "alternative_not_taken": ("The main option we did not take", "This project", "", C),
        "plan": ("Plan, or the reference line (latest year held flat, not a plan). The Greens state no overall "
                 "number, so they are not modelled", S_PATHS, "", C),
        "case": ("central, low or high (low/high only where the plan or reporting gives a range)", S_PATHS, "", C),
        "place": ("AUS or a state or territory code", "", "", C),
        "financial_year": ("Financial year (July to June)", "", "", C),
        "plan_year": ("Year of the plan (1 = 2026-27)", "", "", C),
        "nom": ("Net overseas migration in the year (states: the national figure x the state's share)", S_PATHS, "",
                E),
        "natural_increase": ("Births minus deaths, held at the latest 12 months", S_ABS_POP, "Year to March 2026", A),
        "net_interstate_migration": ("Net moves from other states, held at the latest 12 months (0 for Australia)",
                                     S_ABS_POP, "Year to March 2026", A),
        "population_growth": ("nom + natural_increase + net_interstate_migration", "", "", E),
        "population_start": ("Population at the start of the year (30 June 2026 is our estimate)", S_ABS_POP, "", E),
        "population_end": ("Population at the end of the year (30 June)", "", "", E),
        "working_age_people_added_via_nom": ("nom x the share of 2024-25 arrivals aged 15 to 64", S_ABS_AGE, "", E),
        "homes_needed_for_growth": ("population_growth / 2.5 people per home (negative = fewer homes needed)",
                                    S_CENSUS, "", E),
        "homes_completed_reference": ("Homes completed in the latest 12 months, held flat as a benchmark", S_HOUSE,
                                      "Year to March 2026", "Official data (ABS), used as a benchmark"),
        "homes_completed_minus_needed": ("homes_completed_reference - homes_needed_for_growth (positive = more "
                                         "homes completed than the growth needs; ignores the existing shortfall, "
                                         "demolitions and empty homes)", "", "", E),
        "accord_pace_per_year": ("National Housing Accord pace, 240,000 homes a year (a target, not law; Australia "
                                 "only)", "National Housing Accord (agreed 16 Aug 2023)", "", "Target (not law)"),
        "nom_4y": ("NOM over the four years", "", "2026-27 to 2029-30", E),
        "population_growth_4y": ("Population growth over the four years", "", "2026-27 to 2029-30", E),
        "population_june_2026_est": ("Estimated population at 30 June 2026 (the starting point)", S_ABS_POP, "", E),
        "population_june_2030": ("Population at 30 June 2030", "", "", E),
        "working_age_people_added_via_nom_4y": ("Working-age people (15 to 64) added through migration over the "
                                                "four years", S_ABS_AGE, "", E),
        "homes_needed_4y": ("Homes needed for the four years' growth at 2.5 people per home", S_CENSUS, "", E),
        "homes_completed_reference_per_year": ("Homes completed in the latest 12 months (benchmark)", S_HOUSE, "",
                                               "Official data (ABS), used as a benchmark"),
        "homes_needed_per_year": ("homes_needed_4y / 4", "", "", E),
        "homes_completed_minus_needed_per_year": ("Benchmark completions minus homes needed, a year", "", "", E),
        "people_added_per_home_completed": ("Population growth a year / benchmark completions (2.5 = in step with "
                                            "the average household)", "", "", E),
        "population_june_2030_vs_government": ("population_june_2030 minus the government plan's figure", "", "", E),
        "sector_id": ("Named sector id", "analysis/named_sectors.csv", "", C),
        "sector_name": ("Named sector", "analysis/named_sectors.csv", "", C),
        "short_name": ("Shorter label for charts", "analysis/named_sectors.csv", "", C),
        "employed_may2025": ("Employed persons, May 2025", "JSA, Employment projections (via the sector table)",
                             "May 2025", "Official estimate (JSA)"),
        "visa_holders_primary": ("Main applicants holding a temporary skilled visa", S_HA, "Snapshot 2026-06-30",
                                 "Official data (Home Affairs)"),
        "visa_holders_per_1000_workers": ("visa_holders_primary per 1,000 employed", "", "", D),
        "share_of_all_holders_pct": ("Sector's share of all main applicants with a job recorded, %", "", "", D),
        "one_nation_cut_if_even": ("Main applicants who would go if One Nation's 103,000 cut (holders and "
                                   "dependants) fell evenly across jobs. Our illustration, not a party figure",
                                   f"{S_HA}; tidy/policy_migration_positions.csv", "", E),
        "one_nation_cut_per_1000_workers": ("one_nation_cut_if_even per 1,000 employed in the sector", "", "", E),
        "window": ("Period the context covers", "This project", "", C),
        "from_quarter": ("First quarter in the window (YYYY-MM)", "", "", "Date"),
        "to_quarter": ("Last quarter in the window (YYYY-MM)", "", "", "Date"),
        "homes_completed": ("Homes completed in the window (gross: homes knocked down are not subtracted)",
                            "ABS Building Activity (tidy/abs_dwellings_commenced_completed_by_state.csv)", "",
                            "Official data (ABS)"),
    }
    rows = []
    for p, d in outs.items():
        prefix = "tidy/" if p.parent == TIDY else "analysis/"
        rows += dictionary_rows(prefix + written[p.name], d, m)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
