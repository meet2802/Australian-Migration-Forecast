"""Job ads history: the Internet Vacancy Index (IVI) by occupation and state, and by skill level and state.

Run from the Migration folder:  python3 analysis/build_job_ads_tables.py
(build_occupation_table.py already uses the latest month of the occupation file; build_region_tables.py covers
the regional file. This script keeps the full monthly history.)

Inputs (Jobs and Skills Australia, August 2026):
  internet_vacancies_anzsco4_occupations_states_and_territories_-_august_2026.xlsx   (3-month averages)
  internet_vacancies_anzsco_skill_level_states_and_territories_-_august_2026.xlsx    (trend and seasonally adjusted)

Outputs:
  tidy/jsa_ivi_occupation4_state_monthly.csv(.gz)   job ads per month, ANZSCO 4-digit by state, 2006 onward
  tidy/jsa_ivi_skill_level_state_monthly.csv        job ads per month, skill level by state, 2006 onward
  analysis/job_ads_trends_state.csv                 latest level, change over 12 months and change on 2019
  analysis/job_ads_checks.json
The IVI counts online job ads (SEEK, Workforce Australia), not all vacancies; ads for some jobs (for example
trades hired by word of mouth) are under-represented.
"""
import json

import numpy as np
import pandas as pd

from _common import HERE, ROOT, STATES, TIDY, dictionary_rows, update_dictionary, write_table

OCC = ROOT / "internet_vacancies_anzsco4_occupations_states_and_territories_-_august_2026.xlsx"
SKILL = ROOT / "internet_vacancies_anzsco_skill_level_states_and_territories_-_august_2026.xlsx"
SRC = "Jobs and Skills Australia, Internet Vacancy Index, August 2026"
STATE = {"AUST": "AUS", "NSW": "NSW", "VIC": "VIC", "QLD": "QLD", "SA": "SA", "WA": "WA", "TAS": "TAS", "NT": "NT",
         "ACT": "ACT"}
ORDER = {s: i for i, s in enumerate(["AUS"] + STATES)}


def _long(df, id_cols, value_name):
    dates = [c for c in df.columns if hasattr(c, "year")]
    long = df.melt(id_vars=id_cols, value_vars=dates, var_name="month", value_name=value_name)
    long[value_name] = pd.to_numeric(long[value_name], errors="coerce")   # '.' = not published
    long = long.dropna(subset=[value_name])
    long["month"] = pd.to_datetime(long["month"]).dt.strftime("%Y-%m")
    return long


def occupation_history():
    iv = pd.read_excel(OCC, sheet_name="4 digit 3 month average")
    iv = iv[iv["ANZSCO_CODE"].astype(str).str.fullmatch(r"\d{4}|0")].copy()
    iv["anzsco_code"] = iv["ANZSCO_CODE"].astype(str).replace({"0": "TOTAL"})
    iv["state"] = iv["state"].map(STATE)
    assert iv["state"].notna().all()
    long = _long(iv.rename(columns={"ANZSCO_TITLE": "occupation"}), ["anzsco_code", "occupation", "state"],
                 "job_ads_3m_avg")
    long["job_ads_3m_avg"] = long["job_ads_3m_avg"].round(1)
    long = long[["month", "state", "anzsco_code", "occupation", "job_ads_3m_avg"]]
    return long.sort_values(["month", "state", "anzsco_code"], key=lambda s: s.map(ORDER) if s.name == "state" else s,
                            ignore_index=True)


def skill_history():
    parts = []
    for sheet, series_type, measure in [("Trend", "Trend", "job_ads"), ("Trend Index", "Trend", "index_jan2006"),
                                        ("Seasonally Adjusted", "Seasonally Adjusted", "job_ads"),
                                        ("Seasonally Adjusted Index", "Seasonally Adjusted", "index_jan2006")]:
        d = pd.read_excel(SKILL, sheet_name=sheet)
        d = d[d["State"].isin(list(STATE))].copy()
        d["state"] = d["State"].map(STATE)
        d["skill_level"] = d["Skill_level"].astype(int)
        long = _long(d, ["state", "skill_level"], "value")
        parts.append(long.assign(series_type=series_type, measure=measure))
    df = pd.concat(parts, ignore_index=True)
    dup = df.duplicated(["month", "state", "skill_level", "series_type", "measure"])
    assert not dup.any(), "duplicate skill-level rows"
    wide = df.pivot_table(index=["month", "state", "skill_level", "series_type"], columns="measure",
                          values="value").reset_index()
    wide.columns.name = None
    wide["skill_level_name"] = wide["skill_level"].map(
        {0: "All skill levels", 1: "Skill level 1 (bachelor degree or higher)",
         2: "Skill level 2 (advanced diploma or diploma)", 3: "Skill level 3 (Certificate IV or III with training)",
         4: "Skill level 4 (Certificate II or III)", 5: "Skill level 5 (Certificate I or secondary school)"})
    wide = wide[["month", "state", "skill_level", "skill_level_name", "series_type", "job_ads", "index_jan2006"]]
    return wide.sort_values(["month", "state", "skill_level", "series_type"],
                            key=lambda s: s.map(ORDER) if s.name == "state" else s, ignore_index=True)


def trends(skill):
    t = skill[skill["series_type"].eq("Trend")]
    latest = t["month"].max()
    prev = f"{int(latest[:4]) - 1}{latest[4:]}"
    base = t[t["month"].str.startswith("2019")].groupby(["state", "skill_level"])["job_ads"].mean()
    now = t[t["month"].eq(latest)].set_index(["state", "skill_level"])
    ago = t[t["month"].eq(prev)].set_index(["state", "skill_level"])["job_ads"]
    out = now[["skill_level_name", "job_ads"]].rename(columns={"job_ads": "job_ads_latest"})
    out["job_ads_year_ago"] = ago
    out["job_ads_2019_avg"] = base.round(0)
    out["change_12m_pct"] = (100 * (out["job_ads_latest"] / out["job_ads_year_ago"] - 1)).round(1)
    out["change_vs_2019_pct"] = (100 * (out["job_ads_latest"] / out["job_ads_2019_avg"] - 1)).round(1)
    out = out.reset_index()
    out.insert(0, "month", latest)
    out["job_ads_latest"] = out["job_ads_latest"].round(0)
    out["job_ads_year_ago"] = out["job_ads_year_ago"].round(0)
    return out.sort_values(["state", "skill_level"], key=lambda s: s.map(ORDER) if s.name == "state" else s,
                           ignore_index=True)


def main():
    occ = occupation_history()
    skill = skill_history()
    tr = trends(skill)
    outs = {TIDY / "jsa_ivi_occupation4_state_monthly.csv": occ, TIDY / "jsa_ivi_skill_level_state_monthly.csv": skill,
            HERE / "job_ads_trends_state.csv": tr}
    written = {p.name: write_table(df, p).name for p, df in outs.items()}

    o_aus = occ[occ["state"].eq("AUS") & occ["anzsco_code"].ne("TOTAL")].groupby("month")["job_ads_3m_avg"].sum()
    o_tot = occ[occ["state"].eq("AUS") & occ["anzsco_code"].eq("TOTAL")].set_index("month")["job_ads_3m_avg"]
    o_states = occ[occ["state"].isin(STATES) & occ["anzsco_code"].eq("TOTAL")].groupby("month")["job_ads_3m_avg"].sum()
    s = skill[skill["series_type"].eq("Trend")]
    s_parts = s[s["skill_level"].gt(0)].groupby(["month", "state"])["job_ads"].sum()
    s_all = s[s["skill_level"].eq(0)].set_index(["month", "state"])["job_ads"]
    checks = {
        "files_written": written,
        "occupation_months": [occ["month"].min(), occ["month"].max()],
        "occupation_codes": int(occ.loc[occ["anzsco_code"].ne("TOTAL"), "anzsco_code"].nunique()),
        "occupations_sum_vs_total_australia_max_abs_pct (some occupations unpublished)": float((100 * (o_aus / o_tot - 1)).abs().max().round(2)),
        "states_sum_vs_australia_total_max_abs_pct": float((100 * (o_states / o_tot - 1)).abs().max().round(2)),
        "skill_levels_sum_vs_all_trend_max_abs_pct (trends are smoothed separately)": float((100 * (s_parts / s_all.reindex(s_parts.index) - 1))
                                                           .abs().max().round(2)),
        "latest_trend_australia": tr[tr["state"].eq("AUS")].set_index("skill_level")[
            ["job_ads_latest", "change_12m_pct", "change_vs_2019_pct"]].to_dict("index"),
        "rows": {p.name: len(df) for p, df in outs.items()},
    }
    (HERE / "job_ads_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))

    O = "Official estimate (JSA)"
    m = {
        "month": ("Month (YYYY-MM)", SRC, "", "Classification"),
        "state": ("State or territory code; AUS = Australia", SRC, "", "Classification"),
        "anzsco_code": ("ANZSCO 4-digit unit group as coded by JSA; TOTAL = all occupations", SRC, "", "Classification"),
        "occupation": ("Unit group title", SRC, "", "Classification"),
        "job_ads_3m_avg": ("Online job ads, average of the three months to this month", SRC, "", O),
        "skill_level": ("ANZSCO skill level 1 (highest) to 5; 0 = all levels", SRC, "", "Classification"),
        "skill_level_name": ("Skill level and the qualification it usually needs", SRC, "", "Classification"),
        "series_type": ("Trend or Seasonally Adjusted", SRC, "", "Classification"),
        "job_ads": ("Online job ads in the month", SRC, "", O),
        "index_jan2006": ("Job ads index, January 2006 = 100", SRC, "", O),
        "job_ads_latest": ("Job ads in the latest month (trend)", SRC, "", O),
        "job_ads_year_ago": ("Job ads in the same month a year earlier (trend)", SRC, "", O),
        "job_ads_2019_avg": ("Average monthly job ads in 2019, the last year before COVID (trend)", SRC, "2019",
                             "Calculated from official estimates"),
        "change_12m_pct": ("Change on a year earlier (%)", SRC, "", "Calculated from official estimates"),
        "change_vs_2019_pct": ("Change on the 2019 average (%)", SRC, "", "Calculated from official estimates"),
    }
    rows = []
    for path, df in outs.items():
        prefix = "tidy/" if path.parent == TIDY else "analysis/"
        rows += dictionary_rows(prefix + written[path.name], df, m)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
