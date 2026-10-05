"""Occupation Shortage List 2025 (Jobs and Skills Australia) in long, tidy form, at three levels:
unit groups (ANZSCO 4-digit), occupations (ANZSCO 2022 6-digit) and occupations (OSCA 2024 6-digit).

Run from the Migration folder:  python3 analysis/build_shortage_list_tables.py
(build_occupation_table.py reads the unit group list directly; this script keeps every rating in tidy form and
adds the 6-digit lists, which are needed for the move to OSCA.)

Inputs:
  2025 Unit Group Shortage List - 4 digit ANZSCO.xlsx
  2025 Occupation Shortage List - 6 digit ANZSCO and OSCA.xlsx   (two sheets: ANZSCO 2022 and OSCA 2024)

Outputs:
  tidy/jsa_osl_2025_ratings.csv     one row per list, code and geography (Australia + 8 states and territories)
  analysis/shortage_summary.csv     how many occupations are in shortage, by list, geography and skill level
  analysis/shortage_checks.json
Ratings: S = shortage, R = regional shortage, M = metro shortage, NS = no shortage (national ratings use all four).
"""
import json

import pandas as pd

from _common import HERE, ROOT, STATES, TIDY, dictionary_rows, update_dictionary, write_table

UNIT = ROOT / "2025 Unit Group Shortage List - 4 digit ANZSCO.xlsx"
SIX = ROOT / "2025 Occupation Shortage List - 6 digit ANZSCO and OSCA.xlsx"
SRC = "Jobs and Skills Australia, 2025 Occupation Shortage List (released 2025)"
LISTS = [(UNIT, "2025 Unit group Shortage List", "Unit groups (ANZSCO 4-digit)", "ANZSCO 2022 unit group"),
         (SIX, "2025 OSL (ANZSCO 2022)", "Occupations (ANZSCO 2022 6-digit)", "ANZSCO 2022"),
         (SIX, "2025 OSL (OSCA 2024)", "Occupations (OSCA 2024 6-digit)", "OSCA 2024 v1.0")]
LABEL = {"S": "Shortage", "R": "Regional shortage", "M": "Metro shortage", "NS": "No shortage"}
ORDER = {s: i for i, s in enumerate(["AUS"] + STATES)}


def read_list(path, sheet, list_name, classification):
    raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=object)
    h = raw.index[raw[3].astype(str).str.strip().eq("NSW")][0]
    df = raw.iloc[h + 1:, :13].copy()
    df.columns = ["code", "title", "AUS"] + STATES + ["skill_level", "major_group"]
    df = df[df["code"].notna() & df["code"].astype(str).str.fullmatch(r"\d{4}|\d{6}")]
    df["code"] = df["code"].astype(str)
    long = df.melt(id_vars=["code", "title", "skill_level", "major_group"], value_vars=["AUS"] + STATES,
                   var_name="geography", value_name="rating")
    long["rating"] = long["rating"].astype(str).str.strip()
    long.insert(0, "list", list_name)
    long.insert(1, "classification", classification)
    long["rating_label"] = long["rating"].map(LABEL)
    long["in_shortage"] = long["rating"].isin(["S", "R", "M"])
    long["unit_group_code"] = long["code"].str[:4].where(long["classification"].str.startswith("ANZSCO"), "")
    return long


def main():
    df = pd.concat([read_list(*x) for x in LISTS], ignore_index=True)
    assert df["rating_label"].notna().all(), df.loc[df["rating_label"].isna(), "rating"].unique()
    df["skill_level"] = pd.to_numeric(df["skill_level"], errors="coerce").astype("Int64")
    df["major_group"] = pd.to_numeric(df["major_group"], errors="coerce").astype("Int64")
    df = df[["list", "classification", "code", "unit_group_code", "title", "skill_level", "major_group", "geography",
             "rating", "rating_label", "in_shortage"]]
    df = df.sort_values(["list", "code", "geography"], key=lambda s: s.map(ORDER) if s.name == "geography" else s,
                        ignore_index=True)

    g = df.groupby(["list", "geography", "skill_level"])
    by_skill = g.agg(occupations=("code", "size"), in_shortage=("in_shortage", "sum"),
                     shortage=("rating", lambda s: int(s.eq("S").sum())),
                     regional_shortage=("rating", lambda s: int(s.eq("R").sum())),
                     metro_shortage=("rating", lambda s: int(s.eq("M").sum()))).reset_index()
    allsk = df.groupby(["list", "geography"]).agg(
        occupations=("code", "size"), in_shortage=("in_shortage", "sum"),
        shortage=("rating", lambda s: int(s.eq("S").sum())),
        regional_shortage=("rating", lambda s: int(s.eq("R").sum())),
        metro_shortage=("rating", lambda s: int(s.eq("M").sum()))).reset_index()
    allsk["skill_level"] = "All"
    by_skill["skill_level"] = by_skill["skill_level"].astype("Int64").astype("string")
    summ = pd.concat([allsk, by_skill], ignore_index=True)
    summ["in_shortage_pct"] = (100 * summ["in_shortage"] / summ["occupations"]).round(1)
    summ = summ.sort_values(["list", "geography", "skill_level"],
                            key=lambda s: s.map(ORDER) if s.name == "geography" else s, ignore_index=True)
    summ = summ[["list", "geography", "skill_level", "occupations", "in_shortage", "in_shortage_pct", "shortage",
                 "regional_shortage", "metro_shortage"]]

    outs = {TIDY / "jsa_osl_2025_ratings.csv": df, HERE / "shortage_summary.csv": summ}
    for path, d in outs.items():
        write_table(d, path)

    nat = summ[summ["geography"].eq("AUS") & summ["skill_level"].eq("All")].set_index("list")
    checks = {
        "national_in_shortage": {k: [int(v["in_shortage"]), int(v["occupations"])] for k, v in nat.iterrows()},
        "jsa_headline (inventory note)": {"Occupations (OSCA 2024 6-digit)": [293, 1022],
                                          "Occupations (ANZSCO 2022 6-digit)": [273, 916]},
        "rating_counts": df.groupby(["list", "rating"]).size().unstack(fill_value=0).to_dict("index"),
        "national_rating_values": sorted(df.loc[df["geography"].eq("AUS"), "rating"].unique().tolist()),
        "codes_per_list": df.groupby("list")["code"].nunique().to_dict(),
        "rows": {p.name: len(d) for p, d in outs.items()},
    }
    (HERE / "shortage_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))

    m = {
        "list": ("Which list: unit groups (ANZSCO 4-digit), occupations (ANZSCO 2022 6-digit) or occupations (OSCA "
                 "2024 6-digit)", SRC, "", "Classification"),
        "classification": ("Occupation classification the codes belong to", SRC, "", "Classification"),
        "code": ("Occupation or unit group code in that classification", SRC, "", "Classification"),
        "unit_group_code": ("ANZSCO 4-digit unit group (first four digits; blank for OSCA, whose codes do not map "
                            "this way)", SRC, "", "Classification"),
        "title": ("Occupation or unit group title", SRC, "", "Classification"),
        "skill_level": ("Skill level (1 = highest)", SRC, "", "Classification"),
        "major_group": ("Major occupation group (1 = Managers ... 8 = Labourers)", SRC, "", "Classification"),
        "geography": ("AUS = the national rating; otherwise the state or territory rating", SRC, "", "Classification"),
        "rating": ("S, R, M or NS", SRC, "2025 list", "Official assessment (JSA)"),
        "rating_label": ("Shortage, Regional shortage, Metro shortage or No shortage", SRC, "2025 list",
                         "Official assessment (JSA)"),
        "in_shortage": ("True for S, R or M", SRC, "2025 list", "Official assessment (JSA)"),
        "occupations": ("Number of occupations or unit groups assessed", SRC, "2025 list", "Count of official ratings"),
        "in_shortage_pct": ("Share in shortage of any kind (%)", SRC, "2025 list", "Calculated from official ratings"),
        "shortage": ("Number rated S", SRC, "2025 list", "Count of official ratings"),
        "regional_shortage": ("Number rated R", SRC, "2025 list", "Count of official ratings"),
        "metro_shortage": ("Number rated M", SRC, "2025 list", "Count of official ratings"),
    }
    m_sum = dict(m)
    m_sum["skill_level"] = ("Skill level 1 to 5, or All", SRC, "", "Classification")
    m_sum["in_shortage"] = ("Number in shortage of any kind (S, R or M)", SRC, "2025 list", "Count of official ratings")
    rows = dictionary_rows("tidy/jsa_osl_2025_ratings.csv", df, m)
    rows += dictionary_rows("analysis/shortage_summary.csv", summ, m_sum)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
