"""Regional tables at SA4 level: JSA NERO employment by region and occupation, JSA regional job
ads, temporary skilled visas by region, and where each occupation is rated in shortage.

Run from the Migration folder:  python3 analysis/build_region_tables.py

Inputs: 2026-08_nero.zip (JSA Nowcast of Employment by Region and Occupation),
internet_vacancies_anzsco2_occupations_gccsa_and_sa4_regions_-_august_2026.xlsx (JSA IVI),
tidy/skilled_grants_region.csv, tidy/skilled_holders_region.csv.gz (Home Affairs BP0014),
analysis/occupation_skills_state.csv and occupation_skills_national.csv (from build_occupation_table.py).
Outputs:
  tidy/jsa_nero_sa4_occupation_snapshots.csv.gz  employment by SA4 and occupation, same month each year
  tidy/jsa_ivi_regions_monthly.csv.gz            job ads by GCCSA/SA4 region and 1-2 digit occupation
  analysis/region_skills_sa4.csv                 SA4 x broad occupation group (and all jobs)
  analysis/region_occupation_sa4.csv             SA4 x occupation: employment, growth, shortage where it applies
  analysis/region_checks.json
"""
import json
import re
import zipfile

import numpy as np
import pandas as pd

from _common import HERE, ROOT, TIDY, dictionary_rows, state_code, update_dictionary, write_table

NERO = ROOT / "2026-08_nero.zip"
IVI = ROOT / "internet_vacancies_anzsco2_occupations_gccsa_and_sa4_regions_-_august_2026.xlsx"
S_NERO = "JSA, Nowcast of Employment by Region and Occupation (NERO), Aug 2026 release"
S_IVI = "JSA, Internet Vacancy Index, ANZSCO 1-2 digit by GCCSA and SA4 regions, 3-month average"
S_HA = "Home Affairs, BP0014 temporary resident (skilled) visas, by SA4 of the nominated position"
S_OSL = "JSA, 2025 Occupation Shortage List (state ratings)"
D = "Derived (our calculation)"
E = "Estimate (JSA model)"
MAJOR = {"1": "Managers", "2": "Professionals", "3": "Technicians and Trades Workers",
         "4": "Community and Personal Service Workers", "5": "Clerical and Administrative Workers",
         "6": "Sales Workers", "7": "Machinery Operators and Drivers", "8": "Labourers"}


def _key(s):
    return re.sub(r"[^a-z]", "", str(s).lower())


def nero_snapshots():
    with zipfile.ZipFile(NERO) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv"))
        with z.open(name) as f:
            latest = pd.read_csv(f, usecols=["date"])["date"].max()
        month = latest[5:7]
        parts = []
        with z.open(name) as f:
            for ch in pd.read_csv(f, usecols=["state_name", "sa4_code", "sa4_name", "anzsco4_code", "anzsco4_name",
                                              "date", "nsc_emp"], chunksize=1_000_000):
                parts.append(ch[ch["date"].str[5:7].eq(month)])
    n = pd.concat(parts)
    return pd.DataFrame({
        "year": n["date"].str[:4].astype(int), "month": n["date"].str[:7], "state": n["state_name"].map(state_code),
        "sa4_code": n["sa4_code"].astype(int), "sa4_name": n["sa4_name"],
        "unit_group_code": n["anzsco4_code"].astype(str), "occupation": n["anzsco4_name"],
        "employed": n["nsc_emp"].round()}).reset_index(drop=True), latest[:7]


def ivi_regions():
    iv = pd.read_excel(IVI, sheet_name="Averaged")
    dates = [c for c in iv.columns if hasattr(c, "year")]
    long = iv.melt(id_vars=["Level", "State", "region_name", "region_code", "region_level", "ANZSCO_CODE",
                            "ANZSCO_TITLE"], value_vars=dates, var_name="month", value_name="job_ads")
    long["month"] = pd.to_datetime(long["month"]).dt.strftime("%Y-%m")
    long["job_ads"] = pd.to_numeric(long["job_ads"], errors="coerce").round()
    out = pd.DataFrame({"month": long["month"], "state": long["State"].map(state_code).fillna(long["State"]),
                        "region_level": long["region_level"], "region_code": long["region_code"].astype(str),
                        "region_name": long["region_name"], "occupation_level": long["Level"].map({1: "total", 2: "1-digit", 3: "2-digit"}),
                        "anzsco_code": long["ANZSCO_CODE"].astype(str), "occupation": long["ANZSCO_TITLE"],
                        "job_ads": long["job_ads"]})
    return out, max(dates).strftime("%Y-%m")


def visas_by_sa4():
    g = pd.read_csv(TIDY / "skilled_grants_region.csv", dtype=str, keep_default_na=False)
    g["count"] = pd.to_numeric(g["count"])
    fy = g.loc[g["fy_complete"].eq("True"), "fy"].max()
    h = pd.read_csv(TIDY / "skilled_holders_region.csv.gz", dtype=str, keep_default_na=False)
    h["count"] = pd.to_numeric(h["count"])
    snap = h["snapshot_date"].max()
    def prep(df):
        df = df[df["applicant_type"].eq("Primary")].copy()
        df["major"] = pd.to_numeric(df["occupation_major_group_code"], errors="coerce").astype("Int64").astype(str)
        df["sa4_key"] = df["sa4"].map(_key)
        return df
    gp, hp = prep(g[g["fy"].eq(fy)]), prep(h[h["snapshot_date"].eq(snap)])
    v = pd.concat([gp.groupby(["sa4_key", "sa4", "major"])["count"].sum().rename("visa_grants_primary"),
                   hp.groupby(["sa4_key", "sa4", "major"])["count"].sum().rename("visa_holders_primary")], axis=1)
    return v.fillna(0).reset_index(), fy, snap


def main():
    nero, nero_month = nero_snapshots()
    ivi, ivi_month = ivi_regions()
    vis, fy, snap = visas_by_sa4()
    y_last = int(nero_month[:4])

    # Region type from the IVI file: JSA reports regional SA4s separately and folds capital-city SA4s into GCCSAs
    ivi_sa4 = set(ivi.loc[ivi["region_level"].eq("SA4"), "region_code"].astype(str))
    sa4s = nero[["state", "sa4_code", "sa4_name"]].drop_duplicates()
    sa4s["region_type"] = np.where(sa4s["sa4_code"].astype(str).isin(ivi_sa4), "Rest of state", "Capital city")
    sa4s.loc[sa4s["state"].eq("ACT"), "region_type"] = "Capital city"
    sa4s["sa4_key"] = sa4s["sa4_name"].map(_key)

    # SA4 x occupation
    w = nero.pivot_table(index=["state", "sa4_code", "sa4_name", "unit_group_code", "occupation"], columns="year",
                         values="employed", aggfunc="sum").reset_index()
    occ = w[["state", "sa4_code", "sa4_name", "unit_group_code", "occupation"]].copy()
    occ["employed_latest"] = w[y_last]
    occ["employed_1y_ago"] = w.get(y_last - 1)
    occ["employed_5y_ago"] = w.get(y_last - 5)
    occ["change_1y"] = occ["employed_latest"] - occ["employed_1y_ago"]
    occ["change_5y_pct"] = (100 * (occ["employed_latest"] / occ["employed_5y_ago"] - 1)).where(occ["employed_5y_ago"] > 0).round(1)
    occ = occ.merge(sa4s[["sa4_code", "region_type"]], on="sa4_code", how="left")
    st = pd.read_csv(HERE / "occupation_skills_state.csv", dtype={"unit_group_code": str})
    st = st[st["state"].isin(occ["state"].unique())][["unit_group_code", "state", "osl_2025_state_rating"]]
    occ = occ.merge(st, on=["unit_group_code", "state"], how="left")
    occ["osl_2025_state_rating"] = occ["osl_2025_state_rating"].fillna("Not assessed")
    r = occ["osl_2025_state_rating"]
    occ["shortage_applies_here"] = np.select(
        [r.eq("Shortage"), r.eq("Regional shortage"), r.eq("Metropolitan shortage"), r.eq("No shortage")],
        [True, occ["region_type"].eq("Rest of state"), occ["region_type"].eq("Capital city"), False], default=None)
    nat = pd.read_csv(HERE / "occupation_skills_national.csv", dtype={"unit_group_code": str},
                      usecols=["unit_group_code", "outlook_group", "projected_growth_5y_pct"])
    occ = occ.merge(nat, on="unit_group_code", how="left")
    occ["share_of_sa4_employment_pct"] = (100 * occ["employed_latest"] /
                                          occ.groupby("sa4_code")["employed_latest"].transform("sum")).round(2)
    occ = occ.sort_values(["sa4_code", "unit_group_code"]).reset_index(drop=True)

    # SA4 x broad group (and All)
    occ["major"] = occ["unit_group_code"].str[0]
    agg = occ.groupby(["state", "sa4_code", "sa4_name", "region_type", "major"])[
        ["employed_latest", "employed_1y_ago", "employed_5y_ago"]].sum(min_count=1).reset_index()
    tot = occ.groupby(["state", "sa4_code", "sa4_name", "region_type"])[
        ["employed_latest", "employed_1y_ago", "employed_5y_ago"]].sum(min_count=1).reset_index().assign(major="All")
    reg = pd.concat([agg, tot], ignore_index=True)
    reg["occupation_group"] = reg["major"].map(MAJOR).fillna("All occupations")
    reg["change_1y_pct"] = (100 * (reg["employed_latest"] / reg["employed_1y_ago"] - 1)).round(1)
    reg["change_5y_pct"] = (100 * (reg["employed_latest"] / reg["employed_5y_ago"] - 1)).round(1)
    # shortage share: employment in occupations whose rating applies in this SA4
    sh = occ[occ["shortage_applies_here"].eq(True)].groupby(["sa4_code", "major"])["employed_latest"].sum()
    sh_all = occ[occ["shortage_applies_here"].eq(True)].groupby("sa4_code")["employed_latest"].sum()
    reg["employed_in_shortage_occupations"] = [sh_all.get(c, 0) if m == "All" else sh.get((c, m), 0)
                                               for c, m in zip(reg["sa4_code"], reg["major"])]
    reg["share_in_shortage_occupations_pct"] = (100 * reg["employed_in_shortage_occupations"] / reg["employed_latest"]).round(1)
    # visas
    reg = reg.merge(sa4s[["sa4_code", "sa4_key"]], on="sa4_code", how="left")
    vis_all = vis.groupby(["sa4_key"])[["visa_grants_primary", "visa_holders_primary"]].sum().reset_index().assign(major="All")
    vv = pd.concat([vis.drop(columns="sa4"), vis_all], ignore_index=True)
    reg = reg.merge(vv, on=["sa4_key", "major"], how="left")
    for c in ["visa_grants_primary", "visa_holders_primary"]:
        reg[c] = reg[c].fillna(0).astype(int)
    reg["visa_holders_per_1000_workers"] = (1000 * reg["visa_holders_primary"] / reg["employed_latest"]).round(2)
    # job ads (regional SA4s only)
    iv = ivi[ivi["region_level"].eq("SA4")].copy()
    iv["major"] = np.where(iv["occupation_level"].eq("total"), "All", iv["anzsco_code"])
    iv = iv[iv["occupation_level"].isin(["total", "1-digit"])]
    ym = f"{int(ivi_month[:4]) - 1}{ivi_month[4:]}"
    ads = iv[iv["month"].isin([ivi_month, ym])].pivot_table(index=["region_code", "major"], columns="month",
                                                             values="job_ads", aggfunc="sum").reset_index()
    ads = ads.rename(columns={ivi_month: "job_ads_latest", ym: "job_ads_year_ago"})
    ads["sa4_code"] = ads["region_code"].astype(int)
    reg = reg.merge(ads.drop(columns="region_code"), on=["sa4_code", "major"], how="left")
    reg["job_ads_per_1000_workers"] = (1000 * reg["job_ads_latest"] / reg["employed_latest"]).round(2)
    reg["job_ads_change_12m_pct"] = (100 * (reg["job_ads_latest"] / reg["job_ads_year_ago"] - 1)).round(1)
    reg_cols = ["state", "sa4_code", "sa4_name", "region_type", "major", "occupation_group", "employed_latest",
                "employed_1y_ago", "employed_5y_ago", "change_1y_pct", "change_5y_pct", "employed_in_shortage_occupations",
                "share_in_shortage_occupations_pct", "visa_grants_primary", "visa_holders_primary",
                "visa_holders_per_1000_workers", "job_ads_latest", "job_ads_year_ago", "job_ads_per_1000_workers",
                "job_ads_change_12m_pct"]
    reg = reg[reg_cols].sort_values(["sa4_code", "major"]).reset_index(drop=True)
    occ = occ.drop(columns="major")

    outs = {TIDY / "jsa_nero_sa4_occupation_snapshots.csv": nero, TIDY / "jsa_ivi_regions_monthly.csv": ivi,
            HERE / "region_skills_sa4.csv": reg, HERE / "region_occupation_sa4.csv": occ}
    written = {name: write_table(df, name) for name, df in outs.items()}

    vis_keys = set(vis["sa4_key"])
    checks = {
        "nero_latest_month": nero_month, "snapshot_years": sorted(nero["year"].unique().tolist()),
        "sa4_count": int(sa4s.shape[0]), "region_types": sa4s["region_type"].value_counts().to_dict(),
        "nero_total_latest": float(nero.loc[nero["year"].eq(y_last), "employed"].sum()),
        "ivi_latest_month": ivi_month, "ivi_sa4_regions": len(ivi_sa4),
        "visa_reference": {"grants_fy": fy, "holders_snapshot": snap},
        "visa_sa4_names_not_in_nero": sorted(vis.loc[~vis["sa4_key"].isin(set(sa4s["sa4_key"])), "sa4"].unique().tolist()),
        "visa_holders_matched_share_pct": round(100 * float(vis.loc[vis["sa4_key"].isin(set(sa4s["sa4_key"])), "visa_holders_primary"].sum())
                                                / float(vis["visa_holders_primary"].sum()), 2),
        "nero_sa4_without_visa_records": sorted(sa4s.loc[~sa4s["sa4_key"].isin(vis_keys), "sa4_name"].tolist()),
        "occupation_rows": int(occ.shape[0]),
        "files": {k.name: v.name for k, v in written.items()},
    }
    (HERE / "region_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))

    m = {
        "year": ("Year of the snapshot", S_NERO, "", "Date"),
        "month": ("Month (YYYY-MM)", "", "", "Date"),
        "state": ("State or territory", "", "", "Classification"),
        "sa4_code": ("ABS Statistical Area Level 4 code", S_NERO, "", "Classification"),
        "sa4_name": ("SA4 name", S_NERO, "", "Classification"),
        "region_type": ("Capital city or Rest of state (from how JSA's regional job ads file groups SA4s)", S_IVI, "", "Classification"),
        "unit_group_code": ("ANZSCO 4-digit unit group", S_NERO, "", "Classification"),
        "occupation": ("Occupation title", "", "", "Classification"),
        "employed": ("Estimated employment (NERO nowcast; model-based, not a survey count)", S_NERO,
                     "Same month each year to the latest month", E),
        "region_level": ("GCCSA or SA4", S_IVI, "", "Classification"),
        "region_code": ("GCCSA or SA4 code", S_IVI, "", "Classification"),
        "region_name": ("Region name", S_IVI, "", "Classification"),
        "occupation_level": ("total, 1-digit (major group) or 2-digit (sub-major group)", S_IVI, "", "Classification"),
        "anzsco_code": ("ANZSCO code at that level (0 = total)", S_IVI, "", "Classification"),
        "job_ads": ("Online job ads, 3-month average", S_IVI, "Monthly from Jan 2019", "Official data (JSA)"),
        "employed_latest": ("Estimated employment in the latest month", S_NERO, nero_month, E),
        "employed_1y_ago": ("Estimated employment a year earlier", S_NERO, "", E),
        "employed_5y_ago": ("Estimated employment five years earlier", S_NERO, "", E),
        "change_1y": ("employed_latest minus employed_1y_ago", S_NERO, "", D),
        "change_1y_pct": ("Change over 12 months, %", S_NERO, "", D),
        "change_5y_pct": ("Change over five years, %", S_NERO, "", D),
        "osl_2025_state_rating": ("The occupation's 2025 shortage rating in this state", S_OSL, "2025", "Official rating"),
        "shortage_applies_here": ("True if the state rating covers this SA4: Shortage everywhere, Regional shortage in "
                                  "Rest of state SA4s, Metropolitan shortage in Capital city SA4s; blank if not assessed",
                                  S_OSL, "", D),
        "outlook_group": ("National outlook group from occupation_skills_national.csv", "This project", "", D),
        "projected_growth_5y_pct": ("National projected growth to May 2030, %", "JSA employment projections", "",
                                    "Projection (JSA, trend-based, not a forecast)"),
        "share_of_sa4_employment_pct": ("Share of the SA4's estimated employment, %", S_NERO, "", D),
        "major": ("ANZSCO major group digit (1 to 8) or All", "", "", "Classification"),
        "occupation_group": ("ANZSCO major group name, or All occupations", "", "", "Classification"),
        "employed_in_shortage_occupations": ("Estimated employment in occupations whose shortage rating applies in this SA4",
                                             f"{S_NERO}; {S_OSL}", "", D),
        "share_in_shortage_occupations_pct": ("employed_in_shortage_occupations / employed_latest, %", "", "", D),
        "visa_grants_primary": ("Temporary skilled visas granted to main applicants for positions in this SA4", S_HA,
                                f"Financial year {fy}", "Official data (Home Affairs)"),
        "visa_holders_primary": ("Main applicants holding a temporary skilled visa for positions in this SA4", S_HA,
                                 f"Snapshot {snap}", "Official data (Home Affairs)"),
        "visa_holders_per_1000_workers": ("visa_holders_primary per 1,000 estimated workers", f"{S_HA}; {S_NERO}", "", D),
        "job_ads_latest": ("Online job ads, 3-month average (regional SA4s only; capital cities are reported as GCCSAs)",
                           S_IVI, ivi_month, "Official data (JSA)"),
        "job_ads_year_ago": ("Same, a year earlier", S_IVI, "", "Official data (JSA)"),
        "job_ads_per_1000_workers": ("job_ads_latest per 1,000 estimated workers", f"{S_IVI}; {S_NERO}", "", D),
        "job_ads_change_12m_pct": ("Change in job ads over 12 months, %", S_IVI, "", D),
    }
    rows = []
    for name, df in outs.items():
        rows += dictionary_rows(f"{written[name].parent.name}/{written[name].name}", df, m)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
