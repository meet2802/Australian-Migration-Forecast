"""OSCA occupation data from the 2021 Census (Jobs and Skills Australia), ready for the planned move from ANZSCO
to OSCA.

Run from the Migration folder:  python3 analysis/build_osca_tables.py

Input: osca_occupation_data_-_2021_census.xlsx (JSA). OSCA 2024 codes are NOT the same as ANZSCO codes, even where
the digits look alike (OSCA 1111 is Corporate Services Managers; ANZSCO 1111 is Chief Executives and Managing
Directors). Do not join these tables to the ANZSCO spine on the code. Use the ABS ANZSCO-OSCA correspondence.

Outputs (tidy/):
  jsa_osca_census2021_overview.csv        one row per OSCA unit group (4-digit) and occupation (6-digit)
  jsa_osca_census2021_industry_shares.csv share of each occupation's workers in each industry division
  jsa_osca_census2021_state_shares.csv    workers by state (count and share)
  jsa_osca_census2021_age_profile.csv     share of workers in each age group
  jsa_osca_descriptions.csv               skill level, overview, licensing, tasks and other job titles
analysis/osca_checks.json
"""
import json

import pandas as pd

from _common import HERE, ROOT, STATES, TIDY, dictionary_rows, update_dictionary, write_table

XLSX = ROOT / "osca_occupation_data_-_2021_census.xlsx"
SRC = "Jobs and Skills Australia, OSCA occupation data - 2021 Census"
KEY = ["osca_level", "osca_code", "occupation"]


def table(sheet):
    raw = pd.read_excel(XLSX, sheet_name=sheet, header=None, dtype=object)
    h = raw.index[raw[0].astype(str).str.strip().eq("OSCA level")][0]
    df = raw.iloc[h + 1:].copy()
    df.columns = [" ".join(str(c).split()) for c in raw.iloc[h]]
    df = df.dropna(how="all")
    df = df.rename(columns={"OSCA level": "osca_level", "OSCA code": "osca_code", "Occupation name": "occupation"})
    total = df["osca_level"].astype(str).str.startswith("Total")
    df.loc[total, ["osca_level", "osca_code", "occupation"]] = ["Total", "TOTAL", "All occupations"]
    df["osca_level"] = df["osca_level"].replace({"4-digit": "Unit group (4-digit)", "6-digit": "Occupation (6-digit)"})
    df["osca_code"] = df["osca_code"].astype(str).str.strip()
    return df.reset_index(drop=True)


def pct(s):
    return (100 * pd.to_numeric(s, errors="coerce")).round(1)


def flag(s):
    """'<0.1%' = a non-zero share under 0.1%; blank cell = suppressed by JSA (small occupation)."""
    s = pd.Series(s)
    return s.astype("string").str.strip().where(s.astype(str).str.strip().eq("<0.1%"),
                                                 pd.Series("suppressed", index=s.index).where(s.isna(), ""))


def overview():
    t = table("Table_1")
    out = t[KEY].copy()
    out["employed_main_job"] = pd.to_numeric(t["Employment in main job"], errors="coerce")
    out["full_time_pct"] = pct(t["Full-time (%)"])
    out["part_time_pct"] = pct(t["Part-time (%)"])
    out["high_share_away_from_work"] = t['High proportion "away from work"']
    out["median_age"] = pd.to_numeric(t["Median age"], errors="coerce")
    out["male_pct"] = pct(t["Male (%)"])
    out["female_pct"] = pct(t["Female (%)"])
    out["gender_segregation"] = t["Gender Segregation Intensity"]
    out["indigenous_pct"] = pct(t["Indigenous (%)"])
    out["main_industry"] = t["Main employing industry"]
    sk = table("Table_5")[["osca_code", "Skill level"]].rename(columns={"Skill level": "skill_level"})
    out = out.merge(sk, on="osca_code", how="left")
    return out


def shares(sheet, id_name, keep=None, counts=False):
    t = table(sheet)
    cols = [c for c in t.columns if c not in KEY]
    if keep:
        cols = [c for c in cols if keep(c)]
    long = t.melt(id_vars=KEY, value_vars=cols, var_name=id_name, value_name="value")
    if counts:
        return long
    long[id_name] = long[id_name].str.replace(r"\s*\(%\)$", "", regex=True)
    long["share_pct"] = pct(long["value"])
    long["share_note"] = flag(long["value"])
    return long.drop(columns="value")


def state_shares():
    t = table("Table_3")
    cnt = t.melt(id_vars=KEY, value_vars=STATES, var_name="state", value_name="employed")
    cnt["employed"] = pd.to_numeric(cnt["employed"], errors="coerce")
    shr = t.melt(id_vars=KEY, value_vars=[s + " (%)" for s in STATES], var_name="state", value_name="share")
    shr["state"] = shr["state"].str.replace(" (%)", "", regex=False)
    shr["share_pct"] = pct(shr["share"])
    shr["share_note"] = flag(shr["share"])
    out = cnt.merge(shr[KEY[1:2] + ["state", "share_pct", "share_note"]], on=["osca_code", "state"], how="left")
    order = {s: i for i, s in enumerate(STATES)}
    return out.sort_values(["osca_code", "state"], key=lambda s: s.map(order) if s.name == "state" else s,
                           ignore_index=True)


def descriptions():
    d5 = table("Table_5").rename(columns={"Skill level": "skill_level", "Occupation overview": "overview"})
    d6 = table("Table_6").rename(columns={"Registration or Licensing": "registration_or_licensing",
                                          "What the occupation involves": "tasks"})
    d7 = table("Table_7").rename(columns={"Common occupation titles": "other_titles",
                                          "Specialisations": "specialisations"})
    out = d5[KEY + ["skill_level", "overview"]]
    out = out.merge(d6[["osca_code", "registration_or_licensing", "tasks"]], on="osca_code", how="left")
    out = out.merge(d7[["osca_code", "other_titles", "specialisations"]], on="osca_code", how="left")
    for c in ["overview", "registration_or_licensing", "tasks", "other_titles", "specialisations"]:
        out[c] = out[c].astype("string").str.strip()
    return out


def main():
    ov = overview()
    ind = shares("Table_2", "industry")
    st = state_shares()
    age = shares("Table_4", "age_group")
    desc = descriptions()
    outs = {TIDY / "jsa_osca_census2021_overview.csv": ov, TIDY / "jsa_osca_census2021_industry_shares.csv": ind,
            TIDY / "jsa_osca_census2021_state_shares.csv": st, TIDY / "jsa_osca_census2021_age_profile.csv": age,
            TIDY / "jsa_osca_descriptions.csv": desc}
    for path, df in outs.items():
        write_table(df, path)

    u = ov[ov["osca_level"].eq("Unit group (4-digit)")]
    o6 = ov[ov["osca_level"].eq("Occupation (6-digit)")]
    tot = float(ov.loc[ov["osca_code"].eq("TOTAL"), "employed_main_job"].iloc[0])
    ind_sum = ind.groupby("osca_code")["share_pct"].sum(min_count=1).dropna()
    age_sum = age.groupby("osca_code")["share_pct"].sum(min_count=1).dropna()
    st_sum = st.groupby("osca_code")["employed"].sum(min_count=1).dropna()
    st_gap = 100 * (st_sum / ov.set_index("osca_code")["employed_main_job"].reindex(st_sum.index) - 1)
    checks = {
        "unit_groups": int(len(u)), "occupations_6_digit": int(len(o6)),
        "total_employed_main_job": tot,
        "unit_groups_sum_vs_total_pct (nfd and suppressed excluded)":
            round(100 * (u["employed_main_job"].sum() / tot - 1), 2),
        "occupations_6_digit_sum_vs_total_pct (nfd and suppressed excluded)":
            round(100 * (o6["employed_main_job"].sum() / tot - 1), 2),
        "industry_shares_sum_pct_range (published codes; small and not-stated industries excluded)":
            [round(float(ind_sum.min()), 1), round(float(ind_sum.max()), 1)],
        "age_shares_sum_pct_range (published codes)": [round(float(age_sum.min()), 1), round(float(age_sum.max()), 1)],
        "codes_with_industry_detail_suppressed": int(ov["osca_code"].nunique() - len(ind_sum)),
        "codes_with_state_detail_suppressed": int(ov["osca_code"].nunique() - len(st_sum)),
        "state_counts_vs_overview_max_abs_pct (rounding and perturbation)": round(float(st_gap.abs().max()), 2),
        "share_cells_below_0_1pct": int(ind["share_note"].eq("<0.1%").sum() + age["share_note"].eq("<0.1%").sum()
                                        + st["share_note"].eq("<0.1%").sum()),
        "skill_level_missing": int(ov["skill_level"].isna().sum()),
        "descriptions_rows": int(len(desc)),
        "rows": {p.name: len(df) for p, df in outs.items()},
    }
    (HERE / "osca_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))

    C = "Official data (ABS Census 2021, compiled by JSA)"
    m = {
        "osca_level": ("Unit group (4-digit), Occupation (6-digit) or Total", SRC, "", "Classification"),
        "osca_code": ("OSCA 2024 code. Not the same as ANZSCO codes; join through the ABS correspondence", SRC, "",
                      "Classification"),
        "occupation": ("OSCA title", SRC, "", "Classification"),
        "employed_main_job": ("People employed in this occupation in their main job (rounded by JSA)", SRC,
                              "Census night, August 2021", C),
        "full_time_pct": ("Share working full-time (%)", SRC, "August 2021", C),
        "part_time_pct": ("Share working part-time (%)", SRC, "August 2021", C),
        "high_share_away_from_work": ("Yes if a high share were away from work on Census night (counts less reliable)",
                                      SRC, "August 2021", "Classification"),
        "median_age": ("Median age of workers (years)", SRC, "August 2021", C),
        "male_pct": ("Share of workers who are male (%)", SRC, "August 2021", C),
        "female_pct": ("Share of workers who are female (%)", SRC, "August 2021", C),
        "gender_segregation": ("JSA gender segregation category", SRC, "August 2021", "Classification"),
        "indigenous_pct": ("Share of workers who are Aboriginal and/or Torres Strait Islander (%)", SRC, "August 2021", C),
        "main_industry": ("Industry division employing the most workers in this occupation", SRC, "August 2021",
                          "Classification"),
        "skill_level": ("OSCA skill level (1 = highest)", SRC, "", "Classification"),
        "industry": ("ANZSIC 2006 industry division", SRC, "", "Classification"),
        "share_pct": ("Share of the occupation's workers in this group (%). Shares may not add to 100 (rounding, "
                      "perturbation, small groups left out)", SRC, "August 2021", C),
        "share_note": ("'<0.1%' = a non-zero share under 0.1% (share_pct blank); 'suppressed' = hidden by JSA because "
                       "the occupation is small", SRC, "", "Classification"),
        "state": ("State or territory code", SRC, "", "Classification"),
        "employed": ("Workers in this occupation in the state (rounded by JSA)", SRC, "August 2021", C),
        "age_group": ("Age group", SRC, "", "Classification"),
        "overview": ("Short description of the occupation", SRC, "", "Text"),
        "registration_or_licensing": ("Registration or licensing needed (6-digit occupations only)", SRC, "", "Text"),
        "tasks": ("What the occupation involves (6-digit occupations only)", SRC, "", "Text"),
        "other_titles": ("Common job titles that fall under this occupation (6-digit only)", SRC, "", "Text"),
        "specialisations": ("Specialisations listed for the occupation (6-digit only)", SRC, "", "Text"),
    }
    rows = []
    for path, df in outs.items():
        rows += dictionary_rows("tidy/" + path.name, df, m)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
