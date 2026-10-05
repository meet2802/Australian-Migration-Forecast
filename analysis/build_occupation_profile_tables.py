"""JSA occupation profiles (ANZSCO basis, February 2026) in tidy form: every table in the workbook.

Run from the Migration folder:  python3 analysis/build_occupation_profile_tables.py
(build_occupation_table.py uses Tables 1, 6 and 7 for the occupation analysis; this script keeps all nine.)

Input: ANZSCO Occupation data - February 2026.xlsx (Jobs and Skills Australia). JSA says this is the last
ANZSCO-based edition; OSCA-based profiles replace it.
Important: unit groups (4-digit) and occupations (6-digit) come from different sources and do not add up.
  4-digit employment, states, part-time and female shares: ABS Labour Force Survey (2025 to Feb 2026)
  6-digit figures, and age and education for both levels: ABS 2021 Census
  earnings: ABS Survey of Employee Earnings and Hours, May 2025 (full-time non-managerial adult employees)

Outputs (tidy/):
  jsa_anzsco_profiles_overview.csv        one row per unit group / occupation: size, earnings, hours, age, description
  jsa_anzsco_profiles_distributions.csv   shares by state, age group and highest qualification
  jsa_anzsco_profiles_industries.csv      top employing industries, ranked (industries under 5% not shown)
  jsa_anzsco_profiles_tasks.csv           main tasks
  jsa_anzsco_profiles_all_occupations.csv the all-occupation benchmarks (Table 9)
analysis/occupation_profile_checks.json
"""
import json

import pandas as pd

from _common import HERE, ROOT, STATES, TIDY, dictionary_rows, update_dictionary, write_table

XLSX = ROOT / "ANZSCO Occupation data - February 2026.xlsx"
SRC = "Jobs and Skills Australia, Occupation data (ANZSCO), February 2026"
LEVEL = {4: "Unit group (4-digit)", 6: "Occupation (6-digit)"}
KEY = ["level", "anzsco_code", "occupation"]


def table(sheet):
    raw = pd.read_excel(XLSX, sheet_name=sheet, header=None, dtype=object)
    h = raw.index[raw[0].astype(str).str.strip().isin(["ANZSCO Code", "All Occupations"])][0]
    df = raw.iloc[h + 1:].copy()
    df.columns = [" ".join(str(c).split()) for c in raw.iloc[h]]
    df = df.loc[:, [c for c in df.columns if c != "nan"]].dropna(how="all")
    if "ANZSCO Code" in df.columns:
        df = df.rename(columns={"ANZSCO Code": "anzsco_code", "Occupation": "occupation"})
        df["anzsco_code"] = df["anzsco_code"].astype(str).str.strip()
        df = df[df["anzsco_code"].str.fullmatch(r"\d{4}|\d{6}")]
        df.insert(0, "level", df["anzsco_code"].str.len().map(LEVEL))
    return df.reset_index(drop=True)


def num(s):
    return pd.to_numeric(s, errors="coerce")


def overview():
    t1, t2, t4 = table("Table_1"), table("Table_2"), table("Table_4")
    out = t1[KEY].copy()
    out["employed"] = num(t1["Employed"])
    out["employed_note"] = t1["Employed"].astype(str).str.strip().where(t1["Employed"].astype(str).str.startswith("<"), "")
    out["part_time_pct"] = num(t1["Part-time share (%)"])
    out["female_pct"] = num(t1["Female share (%)"])
    out["median_weekly_earnings"] = num(t1["Median weekly earnings ($)"])
    out["median_age"] = num(t1["Median age"])
    out["annual_employment_growth"] = num(t1["Annual employment growth"])
    t4 = t4.set_index("anzsco_code")
    out["full_time_pct"] = num(out["anzsco_code"].map(t4["Share of workers who work full-time hours (%)"]))
    out["avg_full_time_hours"] = num(out["anzsco_code"].map(t4["Average full-time hours worked per week"]))
    out["median_full_time_weekly_earnings"] = num(out["anzsco_code"].map(t4["Median full-time earnings per week ($)"]))
    out["median_full_time_hourly_earnings"] = num(out["anzsco_code"].map(t4["Median full-time hourly earnings ($)"]))
    out["description"] = out["anzsco_code"].map(t2.set_index("anzsco_code")["Description"]).astype("string").str.strip()
    return out


def distributions():
    parts = []
    for sheet, dim in [("Table_6", "state"), ("Table_7", "age_group"), ("Table_8", "highest_qualification")]:
        t = table(sheet)
        cats = [c for c in t.columns if c not in KEY]
        long = t.melt(id_vars=KEY, value_vars=cats, var_name="category", value_name="share_pct")
        long["category"] = long["category"].str.replace(r"\s*\(%\)$", "", regex=True).str.replace(" - ", "-")
        long["share_pct"] = num(long["share_pct"])
        long.insert(3, "dimension", dim)
        parts.append(long)
    out = pd.concat(parts, ignore_index=True)
    out["source_basis"] = "ABS 2021 Census"
    lfs = out["dimension"].eq("state") & out["level"].eq(LEVEL[4])
    out.loc[lfs, "source_basis"] = "ABS Labour Force Survey, Feb 2026 (JSA trend)"
    return out


def ranked(sheet, value, value_col):
    t = table(sheet).rename(columns={value: value_col})
    t["rank"] = t.groupby("anzsco_code").cumcount() + 1
    t[value_col] = t[value_col].astype("string").str.strip()
    return t[KEY + ["rank", value_col]]


def all_occupations():
    t = table("Table_9")
    t = t.rename(columns={"All Occupations": "basis"})
    long = t.melt(id_vars="basis", var_name="measure", value_name="value")
    long["value"] = num(long["value"])
    long["basis"] = long["basis"].astype(str).str.replace("*", "", regex=False).map(
        {"4-digit": "Benchmark for unit group (4-digit) figures", "6-digit": "Benchmark for occupation (6-digit) figures"})
    return long.dropna(subset=["value"]).reset_index(drop=True)


def main():
    ov = overview()
    dist = distributions()
    ind = ranked("Table_5", "Industry (ranked)", "industry")
    tasks = ranked("Table_3", "Tasks", "task")
    allo = all_occupations()
    outs = {TIDY / "jsa_anzsco_profiles_overview.csv": ov, TIDY / "jsa_anzsco_profiles_distributions.csv": dist,
            TIDY / "jsa_anzsco_profiles_industries.csv": ind, TIDY / "jsa_anzsco_profiles_tasks.csv": tasks,
            TIDY / "jsa_anzsco_profiles_all_occupations.csv": allo}
    for path, df in outs.items():
        write_table(df, path)

    u = ov[ov["level"].eq(LEVEL[4])]
    sums = dist.groupby(["dimension", "level", "anzsco_code"])["share_pct"].sum(min_count=1).dropna()
    checks = {
        "unit_groups": int(len(u)), "occupations_6_digit": int((ov["level"] == LEVEL[6]).sum()),
        "unit_group_employment_total": float(u["employed"].sum()),
        "suppressed_employment (<50)": int(ov["employed_note"].ne("").sum()),
        "share_sums_range_by_dimension": {f"{d} | {lv}": [round(float(s.min()), 1), round(float(s.max()), 1)]
                                          for (d, lv), s in sums.groupby(level=[0, 1])},
        "unit_groups_missing_earnings": int(u["median_weekly_earnings"].isna().sum()),
        "industries_per_code_max": int(ind["rank"].max()),
        "tasks_per_code_max": int(tasks["rank"].max()),
        "rows": {p.name: len(df) for p, df in outs.items()},
    }
    (HERE / "occupation_profile_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))

    LFS = "ABS Labour Force Survey (unit groups) or 2021 Census (6-digit occupations)"
    O = "Official data (ABS, compiled by JSA)"
    m = {
        "level": ("Unit group (4-digit) or Occupation (6-digit). The two levels use different sources and do not add up",
                  SRC, "", "Classification"),
        "anzsco_code": ("ANZSCO code (version used by JSA's profiles, matching the projections spine)", SRC, "",
                        "Classification"),
        "occupation": ("Title", SRC, "", "Classification"),
        "employed": ("People employed in the occupation as their main job (blank where under 50)", SRC + "; " + LFS,
                     "Feb 2026 (unit groups) or Aug 2021 (6-digit)", O),
        "employed_note": ("'<50' where JSA suppressed a small count", SRC, "", "Classification"),
        "part_time_pct": ("Share working part-time (%)", SRC + "; " + LFS, "2025 average or Aug 2021", O),
        "female_pct": ("Share who are female (%)", SRC + "; " + LFS, "2025 average or Aug 2021", O),
        "median_weekly_earnings": ("Median weekly pay, full-time non-managerial adult employees, before tax ($). A guide "
                                   "only", SRC + "; ABS Employee Earnings and Hours", "May 2025", O),
        "median_age": ("Median age of workers", SRC + "; " + LFS, "2025 average or Aug 2021", O),
        "annual_employment_growth": ("Change in employment over the year to February 2026 (people; unit groups only)",
                                     SRC + "; ABS Labour Force Survey (JSA trend)", "Feb 2025 to Feb 2026", O),
        "full_time_pct": ("Share usually working full-time hours in all jobs (%)", SRC + "; " + LFS,
                          "2025 average or Aug 2021", O),
        "avg_full_time_hours": ("Average weekly hours of full-time workers", SRC + "; ABS 2021 Census", "Aug 2021", O),
        "median_full_time_weekly_earnings": ("Median full-time weekly pay ($), as for median_weekly_earnings",
                                             SRC + "; ABS Employee Earnings and Hours", "May 2025", O),
        "median_full_time_hourly_earnings": ("Median full-time hourly pay ($)", SRC + "; ABS Employee Earnings and Hours",
                                             "May 2025", O),
        "description": ("ANZSCO description of the occupation", SRC, "", "Text"),
        "dimension": ("state, age_group or highest_qualification", SRC, "", "Classification"),
        "category": ("State code, age group or qualification level", SRC, "", "Classification"),
        "share_pct": ("Share of the occupation's workers in this category (%). Qualification shares leave out 'not "
                      "stated' and similar answers, so they may not add to 100", SRC, "", O),
        "source_basis": ("Which ABS source the share comes from", SRC, "", "Classification"),
        "rank": ("Rank (1 = largest industry, or first listed task)", SRC, "", "Classification"),
        "industry": ("ANZSIC division among the top employers of the occupation (divisions under 5% not shown)", SRC, "",
                     "Classification"),
        "task": ("A main task of the occupation", SRC, "", "Text"),
        "basis": ("Which data the all-occupation benchmark matches", SRC, "", "Classification"),
        "measure": ("Benchmark measure (as labelled by JSA)", SRC, "", "Classification"),
        "value": ("Benchmark value for all occupations", SRC, "", O),
    }
    rows = []
    for path, df in outs.items():
        rows += dictionary_rows("tidy/" + path.name, df, m)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
