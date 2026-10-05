"""Industry tables: JSA employment projections by industry, JSA industry profiles, and
temporary skilled visas by sponsor industry, joined at ANZSIC division level.
The 'sector_' file names are older and mean industries here. The sectors the dashboard names (groups of occupations,
such as 'Aged and disability care') are built by build_named_sector_tables.py.

Run from the Migration folder:  python3 analysis/build_sector_tables.py

Inputs: employment_projections_-_may_2025_to_may_2035.xlsx (Tables 1 and 5),
industry_data_-_february_2026.xlsx (Tables 1 to 4), tidy/skilled_grants_industry_state.csv,
tidy/skilled_holders_industry_state.csv.
Outputs in tidy/: jsa_projections_industry_division.csv, jsa_projections_industry_group.csv,
  jsa_industry_overview_feb2026.csv, jsa_industry_employment_quarterly.csv,
  jsa_industry_employment_by_sector_feb2026.csv, jsa_industry_top_occupations.csv
Outputs in analysis/: sector_skills_national.csv, sector_skills_state.csv, sector_checks.json
"""
import json
import re

import numpy as np
import pandas as pd

from _common import (DIVISIONS, HERE, INDUSTRY_PLAIN, ROOT, TIDY, STATES, dictionary_rows, state_code,
                     update_dictionary, write_table)

PROJ = ROOT / "employment_projections_-_may_2025_to_may_2035.xlsx"
IND = ROOT / "industry_data_-_february_2026.xlsx"
S_PROJ = "JSA, Employment projections May 2025 to May 2035 (Tables 1 and 5)"
S_IND = "JSA, Industry data February 2026 (industry profiles)"
S_HA = "Home Affairs, BP0014 temporary resident (skilled) visas, by sponsor industry"
D = "Derived (our calculation)"


def _key(name):
    k = re.sub(r"[^a-z]", "", str(name).lower())
    return k[:-8] if k.endswith("services") and k != "otherservices" else k


DIV_BY_KEY = {_key(v): c for c, v in DIVISIONS.items()}


def division_code(name):
    return DIV_BY_KEY.get(_key(name))


def projections():
    t1 = pd.read_excel(PROJ, sheet_name="Table_1 Industry Division", header=None, skiprows=9).iloc[:, :14]
    t1.columns = ["level", "code", "industry", "e25", "e30", "e35", "s25", "s30", "s35", "c5", "c5p", "c10", "c10p", "x"]
    t1 = t1[t1["code"].astype(str).isin(DIVISIONS)]
    div = pd.DataFrame({
        "anzsic_division": t1["code"], "industry": t1["industry"].str.strip(),
        "employed_may2025": (t1["e25"] * 1000).round(), "projected_may2030": (t1["e30"] * 1000).round(),
        "projected_may2035": (t1["e35"] * 1000).round(), "projected_growth_5y": (t1["c5"] * 1000).round(),
        "projected_growth_5y_pct": (t1["c5p"] * 100).round(1), "projected_growth_10y": (t1["c10"] * 1000).round(),
        "projected_growth_10y_pct": (t1["c10p"] * 100).round(1)})
    t5 = pd.read_excel(PROJ, sheet_name="Table_5 Industry Group", header=None, skiprows=9).iloc[:, :11]
    t5.columns = ["level", "nfd", "code", "industry", "e25", "e30", "e35", "c5", "c5p", "c10", "c10p"]
    t5 = t5[pd.to_numeric(t5["level"], errors="coerce").notna()]
    grp = pd.DataFrame({
        "anzsic_level": t5["level"].astype(int), "not_further_defined": t5["nfd"].eq("Y"),
        "anzsic_code": t5["code"].astype(str).str.strip(), "industry": t5["industry"].astype(str).str.strip(),
        "employed_may2025": (t5["e25"] * 1000).round(), "projected_may2030": (t5["e30"] * 1000).round(),
        "projected_may2035": (t5["e35"] * 1000).round(), "projected_growth_5y": (t5["c5"] * 1000).round(),
        "projected_growth_5y_pct": (t5["c5p"] * 100).round(1), "projected_growth_10y": (t5["c10"] * 1000).round(),
        "projected_growth_10y_pct": (t5["c10p"] * 100).round(1)})
    grp["anzsic_division"] = grp["anzsic_code"].str[0]
    return div.reset_index(drop=True), grp.reset_index(drop=True)


def _ind_table(sheet):
    raw = pd.read_excel(IND, sheet_name=sheet, header=None)
    h = raw.index[raw[0].astype(str).str.strip().eq("Industry")][0]
    t = raw.iloc[h + 1:].copy()
    t.columns = [str(c).strip() for c in raw.iloc[h]]
    return t[t["Industry"].notna()].loc[:, lambda d: [c for c in d.columns if c != "nan"]]


def industry_profiles():
    t1 = _ind_table("Table_1")
    ov = pd.DataFrame({
        "anzsic_division": t1["Industry"].map(division_code).fillna("All"), "industry": t1["Industry"].str.strip(),
        "employed_feb2026": pd.to_numeric(t1["Employed"], errors="coerce"),
        "female_share_pct": pd.to_numeric(t1["Female Share (%)"], errors="coerce"),
        "part_time_share_pct": pd.to_numeric(t1["Part-time Share (%)"], errors="coerce"),
        "median_weekly_earnings": pd.to_numeric(t1["Median Weekly Earnings"], errors="coerce"),
        "workforce_share_pct": pd.to_numeric(t1["Workforce Share (%)"], errors="coerce"),
        "median_age": pd.to_numeric(t1["Median Age"], errors="coerce")})
    t2 = _ind_table("Table_2")
    q = t2.melt(id_vars="Industry", var_name="quarter", value_name="employed")
    q["quarter"] = pd.to_datetime(q["quarter"], format="%b-%y", errors="coerce").dt.strftime("%Y-%m")
    q = q.dropna(subset=["quarter"])
    q = pd.DataFrame({"anzsic_division": q["Industry"].map(division_code).fillna("All"),
                      "industry": q["Industry"].str.strip(), "quarter": q["quarter"],
                      "employed": pd.to_numeric(q["employed"], errors="coerce")})
    t3 = _ind_table("Table_3")
    sec = pd.DataFrame({"anzsic_division": t3["Industry"].map(division_code), "industry": t3["Industry"].str.strip(),
                        "sector": t3["Sector"].astype(str).str.strip(),
                        "employed_feb2026": pd.to_numeric(t3["Employed"], errors="coerce")})
    t4 = _ind_table("Table_4")
    occ = pd.DataFrame({"anzsic_division": t4["Industry"].map(division_code), "industry": t4["Industry"].str.strip(),
                        "unit_group_code": pd.to_numeric(t4["ANZSCO Code"], errors="coerce").astype("Int64").astype(str),
                        "occupation": t4["Occupation (ranked)"].astype(str).str.strip()})
    occ["rank_in_industry"] = occ.groupby("anzsic_division").cumcount() + 1
    return ov, q, sec, occ[["anzsic_division", "industry", "rank_in_industry", "unit_group_code", "occupation"]]


def visas():
    g = pd.read_csv(TIDY / "skilled_grants_industry_state.csv", dtype=str, keep_default_na=False)
    g["count"] = pd.to_numeric(g["count"])
    complete = g[g["fy_complete"].eq("True")]
    fy = complete["fy"].max()
    fy_prev = f"{int(fy[:4]) - 1}-{fy[2:4]}"
    gp = g[g["applicant_type"].eq("Primary")].copy()
    gp["anzsic_division"] = gp["sponsor_industry"].map(division_code).fillna(gp["sponsor_industry"])
    gp["state"] = gp["state"].map(state_code).fillna("Not specified")
    h = pd.read_csv(TIDY / "skilled_holders_industry_state.csv", dtype=str, keep_default_na=False)
    h["count"] = pd.to_numeric(h["count"])
    snap = h["snapshot_date"].max()
    snap_prev = f"{int(snap[:4]) - 1}{snap[4:]}"
    hp = h[h["applicant_type"].eq("Primary")].copy()
    hp["anzsic_division"] = hp["sponsor_industry"].map(division_code).fillna(hp["sponsor_industry"])
    hp["state"] = hp["state"].map(state_code).fillna("Not specified")
    keys = ["anzsic_division", "state"]
    v = pd.concat([
        gp[gp["fy"].eq(fy)].groupby(keys)["count"].sum().rename("visa_grants_primary"),
        gp[gp["fy"].eq(fy_prev)].groupby(keys)["count"].sum().rename("visa_grants_primary_prev_year"),
        hp[hp["snapshot_date"].eq(snap)].groupby(keys)["count"].sum().rename("visa_holders_primary"),
        hp[hp["snapshot_date"].eq(snap_prev)].groupby(keys)["count"].sum().rename("visa_holders_primary_year_ago"),
    ], axis=1).fillna(0).reset_index()
    return v, fy, fy_prev, snap, snap_prev


def main():
    div, grp = projections()
    ov, q, sec, occ = industry_profiles()
    v, fy, fy_prev, snap, snap_prev = visas()
    vcols = ["visa_grants_primary", "visa_grants_primary_prev_year", "visa_holders_primary", "visa_holders_primary_year_ago"]
    vn = v.groupby("anzsic_division")[vcols].sum().reset_index()

    all_growth = float(div["projected_growth_5y"].sum() / div["employed_may2025"].sum() * 100)
    nat = (div.merge(ov.drop(columns="industry"), on="anzsic_division", how="left")
              .merge(vn, on="anzsic_division", how="outer"))
    nat["industry"] = nat["industry"].fillna(nat["anzsic_division"])
    nat["projected_growth_per_year"] = (nat["projected_growth_5y"] / 5).round()
    nat["growth_vs_all_industries_pp"] = (nat["projected_growth_5y_pct"] - round(all_growth, 1)).round(1)
    nat["visa_grants_per_1000_workers"] = (1000 * nat["visa_grants_primary"] / nat["employed_may2025"]).round(1)
    nat["visa_holders_per_1000_workers"] = (1000 * nat["visa_holders_primary"] / nat["employed_may2025"]).round(1)
    nat["visa_grants_change_pct"] = (100 * (nat["visa_grants_primary"] / nat["visa_grants_primary_prev_year"] - 1)).round(1)
    nat["share_of_visa_grants_pct"] = (100 * nat["visa_grants_primary"] / nat["visa_grants_primary"].sum()).round(1)
    nat["share_of_employment_pct"] = (100 * nat["employed_may2025"] / div["employed_may2025"].sum()).round(1)
    for c in vcols:
        nat[c] = nat[c].fillna(0).astype(int)
    order = list(DIVISIONS) + sorted(set(nat["anzsic_division"]) - set(DIVISIONS))
    nat["_o"] = nat["anzsic_division"].map({c: i for i, c in enumerate(order)})
    nat = nat.sort_values("_o").drop(columns="_o")
    nat["industry"] = nat["anzsic_division"].map(DIVISIONS).fillna(nat["industry"])  # official titles, as in states
    nat["industry_plain_name"] =nat["anzsic_division"].map(INDUSTRY_PLAIN).fillna(nat["industry"])
    nat_cols = ["anzsic_division", "industry", "industry_plain_name", "employed_may2025", "projected_may2030",
                "projected_may2035",
                "projected_growth_5y", "projected_growth_5y_pct", "projected_growth_per_year", "growth_vs_all_industries_pp",
                "projected_growth_10y", "projected_growth_10y_pct", "employed_feb2026", "share_of_employment_pct",
                "median_age", "median_weekly_earnings", "female_share_pct", "part_time_share_pct", "workforce_share_pct",
                "visa_grants_primary", "visa_grants_primary_prev_year", "visa_grants_change_pct", "share_of_visa_grants_pct",
                "visa_holders_primary", "visa_holders_primary_year_ago", "visa_grants_per_1000_workers",
                "visa_holders_per_1000_workers"]
    nat = nat[nat_cols]

    st = v.copy()
    st["industry"] = st["anzsic_division"].map(DIVISIONS).fillna(st["anzsic_division"])
    st["industry_plain_name"] = st["anzsic_division"].map(INDUSTRY_PLAIN).fillna(st["industry"])
    st = st[["anzsic_division", "industry", "industry_plain_name", "state"] + vcols].sort_values(
        ["anzsic_division", "state"])

    outs = {TIDY / "jsa_projections_industry_division.csv": div, TIDY / "jsa_projections_industry_group.csv": grp,
            TIDY / "jsa_industry_overview_feb2026.csv": ov, TIDY / "jsa_industry_employment_quarterly.csv": q,
            TIDY / "jsa_industry_employment_by_sector_feb2026.csv": sec, TIDY / "jsa_industry_top_occupations.csv": occ,
            HERE / "sector_skills_national.csv": nat, HERE / "sector_skills_state.csv": st}
    for path, df in outs.items():
        write_table(df, path)

    g1 = grp[grp["anzsic_level"].eq(1)].set_index("anzsic_code")["employed_may2025"]
    raw_g = pd.read_csv(TIDY / "skilled_grants_industry_state.csv", dtype=str, keep_default_na=False)
    raw_g["count"] = pd.to_numeric(raw_g["count"])
    checks = {
        "divisions_in_projections": int(div.shape[0]),
        "projection_total_may2025": float(div["employed_may2025"].sum()),
        "table5_level1_matches_table1": bool(np.allclose(g1.reindex(div["anzsic_division"]).values,
                                                         div["employed_may2025"].values, atol=1)),
        "all_industries_growth_5y_pct": round(all_growth, 2),
        "industry_profiles_sum_of_divisions_feb2026": float(ov.loc[ov["anzsic_division"].isin(list(DIVISIONS)), "employed_feb2026"].sum()),
        "visa_reference": {"grants_fy": fy, "grants_prev_fy": fy_prev, "holders_snapshot": snap, "holders_prev": snap_prev},
        "visa_grants_primary_total_check": [int(nat["visa_grants_primary"].sum()),
                                            int(raw_g[(raw_g["fy"] == fy) & (raw_g["applicant_type"] == "Primary")]["count"].sum())],
        "sponsor_industry_labels_not_matched": sorted(set(v["anzsic_division"]) - set(DIVISIONS)),
        "rows": {p.name: len(df) for p, df in outs.items()},
    }
    (HERE / "sector_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))

    P = "Projection (JSA, trend-based, not a forecast)"
    OI = "Official estimate (JSA, from ABS Labour Force)"
    OH = "Official data (Home Affairs)"
    m = {
        "anzsic_division": ("ANZSIC 2006 division letter (A to S); 'All' = all industries; other values are Home "
                            "Affairs labels with no division (Not Applicable, Not Specified)", "ABS ANZSIC", "", "Classification"),
        "industry": ("Industry title", "", "", "Classification"),
        "industry_plain_name": ("Plain-English industry name for public-facing pages (official title in 'industry')",
                                "This project", "", "Classification"),
        "employed_may2025": ("Employed persons, May 2025 (projection base)", S_PROJ, "May 2025", "Official estimate (JSA)"),
        "projected_may2030": ("Projected employment, May 2030", S_PROJ, "May 2030", P),
        "projected_may2035": ("Projected employment, May 2035", S_PROJ, "May 2035", P),
        "projected_growth_5y": ("Projected change, May 2025 to May 2030", S_PROJ, "", P),
        "projected_growth_5y_pct": ("Projected change, May 2025 to May 2030, %", S_PROJ, "", P),
        "projected_growth_10y": ("Projected change, May 2025 to May 2035", S_PROJ, "", P),
        "projected_growth_10y_pct": ("Projected change, May 2025 to May 2035, %", S_PROJ, "", P),
        "projected_growth_per_year": ("projected_growth_5y / 5", S_PROJ, "", D),
        "growth_vs_all_industries_pp": ("projected_growth_5y_pct minus the all-industries rate, percentage points", S_PROJ, "", D),
        "anzsic_level": ("ANZSIC level: 1 division, 2 subdivision, 3 group", S_PROJ, "", "Classification"),
        "not_further_defined": ("True for 'nfd' rows", S_PROJ, "", "Classification"),
        "anzsic_code": ("ANZSIC code (letter, 2-digit or 3-digit)", S_PROJ, "", "Classification"),
        "employed_feb2026": ("Employed persons", S_IND, "February 2026", OI),
        "female_share_pct": ("Share of workers who are female, %", S_IND, "February 2026", OI),
        "part_time_share_pct": ("Share of workers who work part time, %", S_IND, "February 2026", OI),
        "median_weekly_earnings": ("Median full-time weekly earnings, $", S_IND, "", OI),
        "workforce_share_pct": ("Share of all workers, %", S_IND, "February 2026", OI),
        "median_age": ("Median age of workers", S_IND, "", OI),
        "quarter": ("Quarter (YYYY-MM)", S_IND, "", "Date"),
        "employed": ("Employed persons (JSA trend)", S_IND, "Quarterly, Feb 2006 to Feb 2026", OI),
        "sector": ("Industry sector within the division, as JSA labels it", S_IND, "", "Classification"),
        "rank_in_industry": ("Rank of the occupation by employment within the industry (1 = largest)", S_IND, "", "Classification"),
        "unit_group_code": ("ANZSCO 4-digit unit group", S_IND, "", "Classification"),
        "occupation": ("Occupation title", S_IND, "", "Classification"),
        "state": ("State of the nominated position (Not specified if missing)", S_HA, "", "Classification"),
        "visa_grants_primary": ("Temporary skilled visas granted to main applicants", S_HA, f"Financial year {fy}", OH),
        "visa_grants_primary_prev_year": ("Same, previous financial year", S_HA, f"Financial year {fy_prev}", OH),
        "visa_holders_primary": ("Main applicants holding a temporary skilled visa", S_HA, f"Snapshot {snap}", OH),
        "visa_holders_primary_year_ago": ("Same, a year earlier", S_HA, f"Snapshot {snap_prev}", OH),
        "visa_grants_change_pct": ("Change in grants on the previous year, %", S_HA, "", D),
        "share_of_visa_grants_pct": ("Share of all main-applicant grants, %", S_HA, "", D),
        "share_of_employment_pct": ("Share of all employment (May 2025), %", S_PROJ, "", D),
        "visa_grants_per_1000_workers": ("visa_grants_primary per 1,000 employed (May 2025)", f"{S_HA}; {S_PROJ}", "", D),
        "visa_holders_per_1000_workers": ("visa_holders_primary per 1,000 employed (May 2025)", f"{S_HA}; {S_PROJ}", "", D),
    }
    rows = []
    for path, df in outs.items():
        rows += dictionary_rows(f"{path.parent.name}/{path.name}", df, m)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
