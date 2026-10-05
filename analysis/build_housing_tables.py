"""Housing capacity: dwelling approvals, commencements and completions by state, set against population growth.

Run from the Migration folder:  python3 analysis/build_housing_tables.py
Run build_population_tables.py first (this script reads analysis/population_years_by_state.csv).

Inputs (ABS):
  87520034.xlsx           Building Activity, Australia, Table 34: dwelling units commenced, states (quarterly)
  87520038.xlsx           Building Activity, Australia, Table 38: dwelling units completed, states (quarterly)
  Dwellings-approved.zip  Building Approvals, Australia (8731): Table 6 (Australia), Table 7 (states, trend and
                          seasonally adjusted) and Table 9 (states, original) (monthly)

Outputs:
  tidy/abs_dwellings_commenced_completed_by_state.csv  quarterly, original / seasonally adjusted / trend
  tidy/abs_dwellings_approved_by_state.csv             monthly, original / seasonally adjusted / trend
  analysis/housing_vs_population_by_state.csv          12-month flows of homes against population growth, by state
  analysis/housing_targets.csv                         the national housing target, as a reference line
  analysis/housing_checks.json                         reconciliation checks

Notes:
  * Building Activity tables 34 and 38 have no Australia column, so Australia (original series only) is the sum of
    the eight states and territories, flagged derived=True. Seasonally adjusted and trend series are not added up.
  * Completions are gross: homes demolished are not subtracted, so the net addition to the stock is smaller.
  * No household size is assumed anywhere. People added per home completed is a plain ratio of two official counts.
"""
import json

import numpy as np
import pandas as pd

from _common import (HERE, ROOT, STATES, TIDY, dictionary_rows, read_abs_timeseries, state_code,
                     update_dictionary, write_table, zip_member)

ACTIVITY = {"Commenced": ROOT / "87520034.xlsx", "Completed": ROOT / "87520038.xlsx"}
APPROVALS_ZIP = ROOT / "Dwellings-approved.zip"
APPROVAL_TABLES = {"6": "8731006.xlsx", "7": "8731007.xlsx", "9": "8731009.xlsx"}
POPULATION = HERE / "population_years_by_state.csv"
SRC_BA = "ABS, Building Activity, Australia, March quarter 2026 (cat. 8752.0), Tables 34 and 38"
SRC_AP = "ABS, Building Approvals, Australia, August 2026 (cat. 8731.0), Tables 6, 7 and 9"
SRC_POP = "ABS, National, state and territory population, March 2026 (cat. 3101.0), via population_years_by_state"
SRC_ACCORD = ("Australian Government, The Treasury (n.d.), Delivering the National Housing Accord, "
              "https://treasury.gov.au/policy-topics/housing/accord (checked 4 Oct 2026)")
BUILDING = {"Houses": "Houses", "Total (Type of Building)": "All dwellings",
            "Dwellings excluding houses": "Dwellings excluding houses"}
WORK = {"New": "New", "Total (Type of Work)": "All work"}
SECTOR = {"Private Sector": "Private", "Public Sector": "Public", "Total Sectors": "All sectors"}


def yyyymm(d):
    return pd.to_datetime(d).dt.strftime("%Y-%m")


def activity():
    """Dwelling units commenced and completed by state, quarterly (Building Activity tables 34 and 38)."""
    out = []
    for act, path in ACTIVITY.items():
        df = read_abs_timeseries(path)
        parts = df["series"].str.split(" ; ", expand=True)
        assert parts.shape[1] == 5, f"unexpected series label layout in {path.name}"
        df = df.assign(quarter=yyyymm(df["date"]), activity=act, state=parts[1].map(state_code),
                       building_type=parts[2].map(BUILDING), type_of_work=parts[3].map(WORK),
                       sector=parts[4].map(SECTOR), dwellings=df["value"], derived=False)
        assert df[["state", "building_type", "type_of_work", "sector"]].notna().all().all(), path.name
        out.append(df)
    df = pd.concat(out, ignore_index=True)
    keys = ["quarter", "activity", "building_type", "type_of_work", "sector", "series_type"]
    orig = df[df["series_type"].eq("Original")]
    full = orig.groupby(keys)["state"].nunique().eq(len(STATES))
    aus = orig.groupby(keys)["dwellings"].sum()[full].reset_index()
    aus = aus.assign(state="AUS", series_id="", derived=True)
    cols = keys[:1] + ["state"] + keys[1:] + ["dwellings", "series_id", "derived"]
    df = pd.concat([df[cols], aus[cols]], ignore_index=True)
    order = {s: i for i, s in enumerate(STATES + ["AUS"])}
    return df.sort_values(keys[:1] + ["state"] + keys[1:], key=lambda s: s.map(order) if s.name == "state" else s,
                          ignore_index=True)


def approvals():
    """Dwelling units approved, monthly. Table 9: states and Australia, original, by building type.
    Table 7: states, trend (and seasonally adjusted where ABS publishes it), all dwellings.
    Table 6: Australia, original / seasonally adjusted / trend, by building type and sector."""
    out, overlap = [], {}
    for table, f in APPROVAL_TABLES.items():
        df = read_abs_timeseries(zip_member(APPROVALS_ZIP, f))
        parts = df["series"].str.split(" ; ")
        rows = []
        for lab in parts:
            st, bld, sec = None, "All dwellings", "All sectors"
            for p in lab[1:]:
                if state_code(p):
                    st = state_code(p)
                elif p in BUILDING:
                    bld = BUILDING[p]
                elif p in SECTOR:
                    sec = SECTOR[p]
                else:
                    raise ValueError(f"unknown label part {p!r} in table {table}")
            rows.append((st or "AUS", bld, sec))
        lab = pd.DataFrame(rows, columns=["state", "building_type", "sector"], index=df.index)
        df = pd.concat([df, lab], axis=1).assign(month=yyyymm(df["date"]), dwellings=df["value"],
                                                 source_table=f"8731.0 Table {table}")
        if table == "7":   # states only; Table 9 already has the original series
            overlap["7"] = df[df["series_type"].eq("Original")]
            df = df[~df["series_type"].eq("Original")]
        if table == "6":   # Australia; Table 9 already has the original all-sector series
            drop = df["series_type"].eq("Original") & df["sector"].eq("All sectors")
            overlap["6"] = df[drop]
            df = df[~drop]
        out.append(df)
    df = pd.concat(out, ignore_index=True)
    t9 = df[df["source_table"].eq("8731.0 Table 9")].set_index(["month", "state", "building_type"])["dwellings"]
    diffs = {}
    for table, o in overlap.items():
        o = o.set_index(["month", "state", "building_type"])["dwellings"]
        diffs["table" + table + "_original_vs_table9_max_abs"] = float((o - t9.reindex(o.index)).abs().max())
        diffs["table" + table + "_original_rows_compared"] = int(t9.reindex(o.index).notna().sum())
    cols = ["month", "state", "building_type", "sector", "series_type", "dwellings", "series_id", "source_table"]
    df = df[cols]
    dup = df.duplicated(["month", "state", "building_type", "sector", "series_type"])
    assert not dup.any(), "approval series overlap between tables"
    order = {s: i for i, s in enumerate(STATES + ["AUS"])}
    df = df.sort_values(["month", "state", "building_type", "sector", "series_type"],
                        key=lambda s: s.map(order) if s.name == "state" else s, ignore_index=True)
    return df, diffs


def rolling_sum(df, period_col, n, step, value_col):
    """Sum of the last n periods per state (periods are YYYY-MM, step months apart).
    NaN unless all n periods are present."""
    out = []
    for st, g in df.groupby("state", sort=False):
        d = pd.to_datetime(g[period_col] + "-01")
        k = (d.dt.year * 12 + d.dt.month - 1).to_numpy()
        s = pd.Series(g[value_col].to_numpy(), index=k)
        full = np.arange(k.min(), k.max() + 1, step)
        assert set(k) <= set(full), f"{st}: periods are not {step} months apart"
        r = s.reindex(full).rolling(n, min_periods=n).sum()
        ye = ["%04d-%02d" % (x // 12, x % 12 + 1) for x in full]
        out.append(pd.DataFrame({"state": st, "year_ending": ye, value_col: r.to_numpy()}))
    return pd.concat(out, ignore_index=True)


def housing_vs_population(act, appr):
    base = act[act["series_type"].eq("Original") & act["building_type"].eq("All dwellings")
               & act["type_of_work"].eq("All work") & act["sector"].eq("All sectors")]
    flows = []
    for a, name in [("Commenced", "dwellings_commenced_12m"), ("Completed", "dwellings_completed_12m")]:
        x = base[base["activity"].eq(a)].rename(columns={"dwellings": name})
        flows.append(rolling_sum(x, "quarter", 4, 3, name).set_index(["state", "year_ending"]))
    houses = act[act["series_type"].eq("Original") & act["building_type"].eq("Houses")
                 & act["sector"].eq("All sectors") & act["activity"].eq("Completed")]
    houses = houses.rename(columns={"dwellings": "new_houses_completed_12m"})
    flows.append(rolling_sum(houses, "quarter", 4, 3, "new_houses_completed_12m").set_index(["state", "year_ending"]))
    ap = appr[appr["series_type"].eq("Original") & appr["building_type"].eq("All dwellings")
              & appr["sector"].eq("All sectors") & appr["source_table"].eq("8731.0 Table 9")]
    ap = ap.rename(columns={"dwellings": "dwellings_approved_12m"})
    flows.append(rolling_sum(ap, "month", 12, 1, "dwellings_approved_12m").set_index(["state", "year_ending"]))
    flows = pd.concat(flows, axis=1).reset_index()

    pop = pd.read_csv(POPULATION, dtype={"year_ending": str})
    pop = pop.rename(columns={"growth": "population_growth_12m", "nom": "nom_12m"})
    df = pop[["year_ending", "financial_year", "state", "erp_start", "erp_end", "population_growth_12m", "nom_12m"]]
    df = df.merge(flows, on=["state", "year_ending"], how="left")
    hcols = ["dwellings_approved_12m", "dwellings_commenced_12m", "dwellings_completed_12m"]
    df = df[df[hcols].notna().any(axis=1)].copy()
    per_1000 = lambda v: (1000 * v / df["erp_start"]).round(2)
    df["approved_per_1000_pop"] = per_1000(df["dwellings_approved_12m"])
    df["completed_per_1000_pop"] = per_1000(df["dwellings_completed_12m"])
    comp = df["dwellings_completed_12m"].where(df["dwellings_completed_12m"] > 0)
    df["people_added_per_home_completed"] = (df["population_growth_12m"] / comp).round(2)
    df["nom_per_home_completed"] = (df["nom_12m"] / comp).round(2)
    df["new_houses_share_of_completed_pct"] = (100 * df["new_houses_completed_12m"] / comp).round(1)
    order = {s: i for i, s in enumerate(STATES + ["AUS"])}
    df = df.sort_values(["state", "year_ending"], key=lambda s: s.map(order) if s.name == "state" else s)
    cols = ["year_ending", "financial_year", "state", "dwellings_approved_12m", "dwellings_commenced_12m",
            "dwellings_completed_12m", "new_houses_completed_12m", "new_houses_share_of_completed_pct",
            "population_growth_12m", "nom_12m", "erp_start", "erp_end", "approved_per_1000_pop",
            "completed_per_1000_pop", "people_added_per_home_completed", "nom_per_home_completed"]
    return df[cols].reset_index(drop=True)


def targets():
    return pd.DataFrame([{
        "target": "National Housing Accord", "homes": 1_200_000, "period_start": "2024-07",
        "period_end": "2029-06", "homes_per_year": 240_000,
        "status": "Policy target agreed by National Cabinet on 16 August 2023 (not law)",
        "what_it_counts": "New well-located homes. The Treasury page does not say which ABS measure tracks it; "
                          "this project compares it with ABS dwelling completions (assumption)",
        "source": SRC_ACCORD}])


def main():
    act = activity()
    appr, overlap_checks = approvals()
    hp = housing_vs_population(act, appr)
    tg = targets()
    outs = {TIDY / "abs_dwellings_commenced_completed_by_state.csv": act,
            TIDY / "abs_dwellings_approved_by_state.csv": appr,
            HERE / "housing_vs_population_by_state.csv": hp,
            HERE / "housing_targets.csv": tg}
    for path, df in outs.items():
        write_table(df, path)

    t9all = appr[appr["source_table"].eq("8731.0 Table 9")]
    t9 = t9all[t9all["building_type"].eq("All dwellings")]
    t9_states = t9[t9["state"].isin(STATES)].groupby("month")["dwellings"].sum()
    t9_aus = t9[t9["state"].eq("AUS")].set_index("month")["dwellings"]
    wide = t9all.pivot_table(index=["month", "state"], columns="building_type", values="dwellings")
    parts_gap = (wide["All dwellings"] - wide["Houses"] - wide["Dwellings excluding houses"]).reset_index(name="gap")

    def gap_summary(gap, months):
        nz = months[gap != 0]
        return {"months_affected": int(len(set(nz))), "max_abs": float(np.abs(gap).max()),
                "first_month": min(nz) if len(nz) else None, "last_month": max(nz) if len(nz) else None}

    def at(state, ye, col):
        v = hp.loc[hp["state"].eq(state) & hp["year_ending"].eq(ye), col]
        return None if v.empty or pd.isna(v.iloc[0]) else float(v.iloc[0])

    latest = hp.dropna(subset=["dwellings_completed_12m"])["year_ending"].max()
    checks = {
        "activity_series_per_file": {a: int(act[act["activity"].eq(a) & ~act["derived"]]
                                            .groupby(["state", "building_type", "type_of_work", "sector",
                                                      "series_type"]).ngroups) for a in ACTIVITY},
        "activity_latest_quarter": act["quarter"].max(),
        "approvals_latest_month": appr["month"].max(),
        "approvals_table9_australia_minus_sum_of_states (ABS published; old months only)":
            gap_summary((t9_aus - t9_states).to_numpy(), t9_aus.index.to_numpy()),
        "approvals_overlap_with_table9": overlap_checks,
        "approvals_table9_total_minus_houses_minus_other (ABS published; old months only)":
            gap_summary(parts_gap["gap"].to_numpy(), parts_gap["month"].to_numpy()),
        "analysis_latest_year_ending": latest,
        "year_to_latest": {st: {"approved": at(st, latest, "dwellings_approved_12m"),
                                "commenced": at(st, latest, "dwellings_commenced_12m"),
                                "completed": at(st, latest, "dwellings_completed_12m"),
                                "population_growth": at(st, latest, "population_growth_12m"),
                                "people_added_per_home_completed": at(st, latest, "people_added_per_home_completed")}
                           for st in STATES + ["AUS"]},
        "australia_completed_by_financial_year": {
            fy: at("AUS", str(int(fy[:4]) + 1) + "-06", "dwellings_completed_12m")
            for fy in ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]},
        "accord_pace_per_year": 240_000,
        "australia_people_added_per_home_completed_by_financial_year": {
            fy: at("AUS", str(int(fy[:4]) + 1) + "-06", "people_added_per_home_completed")
            for fy in ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]},
        "rows": {p.name: len(df) for p, df in outs.items()},
    }
    (HERE / "housing_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))

    O = "Official data (ABS)"
    m = {
        "quarter": ("Quarter, labelled by its last month (YYYY-MM; 2026-03 = March quarter 2026)", SRC_BA, "", "Classification"),
        "month": ("Month (YYYY-MM)", SRC_AP, "", "Classification"),
        "state": ("State or territory code; AUS = Australia", "", "", "Classification"),
        "activity": ("Commenced (building work started) or Completed", SRC_BA, "", "Classification"),
        "building_type": ("Houses, Dwellings excluding houses (units, apartments, townhouses) or All dwellings",
                          "ABS", "", "Classification"),
        "type_of_work": ("New = new residential building only; All work = also dwellings created by alterations, "
                         "additions and conversions", SRC_BA, "", "Classification"),
        "sector": ("Who the work is for: Private, Public or All sectors", "ABS", "", "Classification"),
        "series_type": ("Original, Seasonally Adjusted or Trend (ABS)", "ABS", "", "Classification"),
        "dwellings": ("Number of dwelling units in the period (quarter or month)", "ABS", "", O),
        "series_id": ("ABS series ID (blank for derived Australia rows)", "ABS", "", "Classification"),
        "derived": ("True for Australia rows calculated here as the sum of the eight states and territories "
                    "(original series only)", SRC_BA, "", "Classification"),
        "source_table": ("8731.0 table the series comes from", SRC_AP, "", "Classification"),
        "year_ending": ("Last month of the 12-month period (YYYY-MM)", "", "", "Classification"),
        "financial_year": ("Financial year, for 12-month periods ending in June", "", "", "Classification"),
        "dwellings_approved_12m": ("Dwelling units approved in the 12 months (original, all dwellings, all sectors)",
                                   SRC_AP, "12 months to year_ending", O),
        "dwellings_commenced_12m": ("Dwelling units commenced in the 12 months (original, all dwellings, all work, "
                                    "all sectors; Australia = sum of states)", SRC_BA, "12 months to year_ending", O),
        "dwellings_completed_12m": ("Dwelling units completed in the 12 months (gross: demolitions not subtracted; "
                                    "Australia = sum of states)", SRC_BA, "12 months to year_ending", O),
        "new_houses_completed_12m": ("New houses completed in the 12 months (all sectors)", SRC_BA,
                                     "12 months to year_ending", O),
        "new_houses_share_of_completed_pct": ("New houses as a share of all dwellings completed. The rest are units, "
                                              "apartments and townhouses, plus homes created by alterations",
                                              SRC_BA, "12 months to year_ending", "Calculated from official data"),
        "population_growth_12m": ("Change in estimated resident population over the 12 months", SRC_POP,
                                  "12 months to year_ending", "Official data (ABS)"),
        "nom_12m": ("Net overseas migration over the 12 months", SRC_POP, "12 months to year_ending",
                    "Official data (ABS; recent quarters are preliminary)"),
        "erp_start": ("Estimated resident population at the start of the 12 months", SRC_POP, "", "Official data (ABS)"),
        "erp_end": ("Estimated resident population at the end of the 12 months", SRC_POP, "", "Official data (ABS)"),
        "approved_per_1000_pop": ("Dwellings approved per 1,000 residents (population at the start)", "",
                                  "12 months to year_ending", "Calculated from official data"),
        "completed_per_1000_pop": ("Dwellings completed per 1,000 residents (population at the start)", "",
                                   "12 months to year_ending", "Calculated from official data"),
        "people_added_per_home_completed": ("Population growth divided by dwellings completed. Higher = homes "
                                            "falling further behind population. No household size is assumed", "",
                                            "12 months to year_ending", "Calculated from official data"),
        "nom_per_home_completed": ("Net overseas migration divided by dwellings completed. Overseas migration is "
                                   "one part of growth; natural increase and interstate moves are the rest", "",
                                   "12 months to year_ending", "Calculated from official data"),
        "target": ("Name of the target", SRC_ACCORD, "", "Classification"),
        "homes": ("Homes the target aims for over its whole period", SRC_ACCORD, "2024-07 to 2029-06",
                  "Policy target (not law)"),
        "period_start": ("First month of the target period", SRC_ACCORD, "", "Classification"),
        "period_end": ("Last month of the target period", SRC_ACCORD, "", "Classification"),
        "homes_per_year": ("Even yearly pace needed to reach the target (homes / 5)", SRC_ACCORD, "",
                           "Calculated from a policy target"),
        "status": ("Legal status of the target", SRC_ACCORD, "", "Classification"),
        "what_it_counts": ("What the target counts and how this project compares it", SRC_ACCORD, "", "Classification"),
        "source": ("Where the figure comes from", "", "", "Classification"),
    }
    rows = []
    for path, df in outs.items():
        prefix = "tidy/" if path.parent == TIDY else "analysis/"
        rows += dictionary_rows(prefix + path.name, df, m)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
