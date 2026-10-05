"""ABS OSCA 2024 v1.0 classification files: structure, correspondences to ANZSCO (and ISCO-08, NOL), descriptions
and the title index, plus a weighted crosswalk from our ANZSCO unit groups to OSCA unit groups.

Run from the Migration folder:  python3 analysis/build_osca_classification_tables.py
(Run build_occupation_profile_tables.py and build_osca_tables.py first: the crosswalk weights use their 2021 Census
employment counts.)

Inputs (ABS, OSCA - Occupation Standard Classification for Australia, 2024, Version 1.0):
  OSCA structure.xlsx, OSCA correspondence tables v2.xlsx, OSCA Category Descriptions.xlsx,
  OSCA index of principal titles alternative titles and specialisations.xlsx

Outputs:
  tidy/abs_osca_structure.csv           every OSCA group and occupation, with parents and skill level
  tidy/abs_osca_correspondences.csv     all ten ABS correspondence tables in one long table ('p' = partial)
  tidy/abs_osca_descriptions.csv        ABS descriptions: lead statement, tasks, licensing, skill level
  tidy/abs_osca_title_index.csv         every principal title, alternative title and specialisation
  analysis/anzsco_osca_unit_group_crosswalk.csv   ANZSCO v1.3 unit group -> OSCA unit group, with weights
  analysis/osca_classification_checks.json
Crosswalk weights (an assumption): the ABS says its correspondences do not give proportions. Each ANZSCO 6-digit
occupation's 2021 Census employment is shared across the OSCA occupations it links to, in proportion to those OSCA
occupations' 2021 Census employment (equal shares when none is published). Use the weights to move ANZSCO-coded
counts onto OSCA, and treat the result as an estimate.
"""
import json
import re

import pandas as pd

from _common import HERE, ROOT, TIDY, dictionary_rows, update_dictionary, write_table

STRUCT = ROOT / "OSCA structure.xlsx"
CORR = ROOT / "OSCA correspondence tables v2.xlsx"
DESC = ROOT / "OSCA Category Descriptions.xlsx"
INDEX = ROOT / "OSCA index of principal titles alternative titles and specialisations.xlsx"
SRC = "ABS, OSCA - Occupation Standard Classification for Australia, 2024, Version 1.0"
LEVELS = {1: "Major group", 2: "Sub-major group", 3: "Minor group", 4: "Unit group", 6: "Occupation"}


def code(v):
    s = str(v).strip()
    return s[:-2] if s.endswith(".0") else s


def structure():
    raw = pd.read_excel(STRUCT, sheet_name="Table 5", header=None, dtype=object)
    h = raw.index[raw[0].astype(str).str.strip().eq("Identifier")][0]
    rows, parents = [], {}
    for i in range(h + 1, len(raw)):
        r = raw.loc[i]
        for col in range(5):
            v = r[col]
            if pd.notna(v) and re.fullmatch(r"\d{1,6}", code(v)):
                c = code(v)
                level = LEVELS[len(c)]
                parents[len(c)] = c
                rows.append({"osca_code": c, "title": str(r[col + 1]).strip(), "level": level,
                             "skill_level": code(r[6]) if level == "Occupation" and pd.notna(r[6]) else "",
                             "major_group": parents.get(1, ""), "sub_major_group": parents.get(2, "") if len(c) >= 2
                             else "", "minor_group": parents.get(3, "") if len(c) >= 3 else "",
                             "unit_group": parents.get(4, "") if len(c) >= 4 else ""})
                break
    df = pd.DataFrame(rows)
    groups = pd.read_excel(DESC, sheet_name="Table 2", header=None, dtype=object)
    gh = groups.index[groups[0].astype(str).str.strip().eq("Identifier")][0]
    g = groups.iloc[gh + 1:].dropna(subset=[0])
    g = g[g[0].map(code).str.fullmatch(r"\d{1,4}")]
    gskill = dict(zip(g[0].map(code), g[4].map(lambda v: str(v).strip() if pd.notna(v) else "")))
    df.loc[df["level"].ne("Occupation"), "skill_level"] = df["osca_code"].map(gskill).fillna("")
    return df


def correspondences():
    xl = pd.ExcelFile(CORR)
    out = []
    for sheet in [s for s in xl.sheet_names if s.startswith("Table ")]:
        raw = xl.parse(sheet, header=None, dtype=object)
        h = raw.index[raw[2].notna() & raw[0].notna() & raw[0].astype(str).str.contains("ANZSCO|OSCA|ISCO|NOL")
                      & ~raw[0].astype(str).str.startswith(("This tab", "OSCA - "))][0]
        frm, to = str(raw.loc[h, 0]).strip(), str(raw.loc[h, 2]).strip()
        body = raw.iloc[h + 1:].copy()
        body = body[body[2].notna()]
        body[0] = body[0].map(lambda v: code(v) if pd.notna(v) else None).ffill()
        body[1] = body[1].map(lambda v: str(v).strip() if pd.notna(v) else None).ffill()
        out.append(pd.DataFrame({"table": sheet, "from_classification": frm, "from_code": body[0],
                                 "from_title": body[1], "to_classification": to,
                                 "to_code": body[2].map(code), "to_title": body[4].astype(str).str.strip(),
                                 "partial": body[3].astype(str).str.strip().eq("p")}))
    return pd.concat(out, ignore_index=True)


def descriptions():
    raw = pd.read_excel(DESC, sheet_name="Table 1", header=None, dtype=object)
    h = raw.index[raw[0].astype(str).str.strip().eq("Identifier")][0]
    d = raw.iloc[h + 1:].copy()
    d.columns = [str(c).strip() for c in raw.iloc[h]]
    d = d[d["Identifier"].notna() & d["Identifier"].map(code).str.fullmatch(r"\d{6}")]
    occ = pd.DataFrame({"osca_code": d["Identifier"].map(code), "level": "Occupation",
                        "title": d["Principal Title"], "alternative_titles": d["Alternative Title"],
                        "lead_statement": d["Lead Statement"], "main_tasks": d["Main Tasks"],
                        "registration_or_licensing": d["Registration or Licensing"],
                        "inclusion_exclusion": d["Inclusion and Exclusion Statements"],
                        "skill_attributes": d["Skill Attributes"], "skill_level": d["Skill Level"].map(
                            lambda v: code(v) if pd.notna(v) else ""),
                        "specialisations": d["Specialisations"], "occupations_in_nec": d["Occupation in NEC category"]})
    raw2 = pd.read_excel(DESC, sheet_name="Table 2", header=None, dtype=object)
    h2 = raw2.index[raw2[0].astype(str).str.strip().eq("Identifier")][0]
    g = raw2.iloc[h2 + 1:].copy()
    g.columns = [str(c).strip() for c in raw2.iloc[h2]]
    g = g[g["Identifier"].notna() & g["Identifier"].map(code).str.fullmatch(r"\d{1,4}")]
    grp = pd.DataFrame({"osca_code": g["Identifier"].map(code), "level": g["Identifier"].map(code).str.len().map(LEVELS),
                        "title": g["Occupation Title"], "lead_statement": g["Lead Statement"],
                        "inclusion_exclusion": g["Inclusion and Exclusion Statements"],
                        "skill_level": g["Skill Level"].map(lambda v: str(v).strip() if pd.notna(v) else "")})
    df = pd.concat([grp, occ], ignore_index=True)
    for c in df.columns:
        if c not in ("osca_code", "level", "skill_level"):
            df[c] = df[c].astype("string").str.strip()
    return df.sort_values("osca_code", key=lambda s: s.str.ljust(6, "0") + s.str.len().astype(str),
                          ignore_index=True)


def title_index():
    raw = pd.read_excel(INDEX, sheet_name="Table 2", header=None, dtype=object)
    h = raw.index[raw[0].astype(str).str.strip().eq("Identifier")][0]
    d = raw.iloc[h + 1:].dropna(subset=[0])
    d = d[d[0].map(code).str.fullmatch(r"\d{6}")]
    return pd.DataFrame({"osca_code": d[0].map(code), "title": d[1].astype(str).str.strip(),
                         "category": d[2].astype(str).str.strip()}).reset_index(drop=True)


def crosswalk(corr):
    links = corr[corr["table"].eq("Table 1") & corr["to_code"].str.fullmatch(r"\d{6}")].copy()
    prof = pd.read_csv(TIDY / "jsa_anzsco_profiles_overview.csv", dtype={"anzsco_code": str})
    a_emp = prof[prof["level"].eq("Occupation (6-digit)")].set_index("anzsco_code")["employed"]
    osca = pd.read_csv(TIDY / "jsa_osca_census2021_overview.csv", dtype={"osca_code": str})
    o_emp = osca[osca["osca_level"].eq("Occupation (6-digit)")].set_index("osca_code")["employed_main_job"]
    links["anzsco_employed_2021"] = links["from_code"].map(a_emp)
    links["osca_employed_2021"] = links["to_code"].map(o_emp).fillna(0)
    tot = links.groupby("from_code")["osca_employed_2021"].transform("sum")
    n = links.groupby("from_code")["to_code"].transform("size")
    links["split"] = (links["osca_employed_2021"] / tot).where(tot > 0, 1 / n)
    links["employed_2021_est"] = links["anzsco_employed_2021"].fillna(0) * links["split"]
    links["anzsco_unit_group"] = links["from_code"].str[:4]
    links["osca_unit_group"] = links["to_code"].str[:4]
    # weights within an ANZSCO unit group: 2021 employment; if no occupation in the unit group has a published
    # figure (for example single-occupation unit groups), each occupation counts equally
    known = links.groupby("anzsco_unit_group")["anzsco_employed_2021"].transform(lambda s: s.notna().any())
    links["weight"] = links["anzsco_employed_2021"].where(known, 1.0).fillna(0) * links["split"]
    g = links.groupby(["anzsco_unit_group", "osca_unit_group"]).agg(
        links=("to_code", "size"), partial_links=("partial", "sum"),
        anzsco_occupations=("from_code", "nunique"), employed_2021_est=("employed_2021_est", "sum"),
        weight=("weight", "sum"),
        anzsco_without_employment=("anzsco_employed_2021", lambda s: int(s.isna().sum()))).reset_index()
    g["share_of_anzsco_unit_group_pct"] = (100 * g["weight"]
                                           / g.groupby("anzsco_unit_group")["weight"].transform("sum")).round(2)
    osca_tot = g.groupby("osca_unit_group")["employed_2021_est"].transform("sum")
    g["share_of_osca_unit_group_pct"] = (100 * g["employed_2021_est"] / osca_tot.where(osca_tot > 0)).round(2)
    g["employed_2021_est"] = g["employed_2021_est"].round(0)
    g = g.drop(columns="weight")
    return g, links


def main():
    st = structure()
    corr = correspondences()
    desc = descriptions()
    idx = title_index()
    cw, links = crosswalk(corr)
    ug_title = st[st["level"].eq("Unit group")].set_index("osca_code")["title"]
    cw.insert(2, "osca_unit_group_title", cw["osca_unit_group"].map(ug_title))
    outs = {TIDY / "abs_osca_structure.csv": st, TIDY / "abs_osca_correspondences.csv": corr,
            TIDY / "abs_osca_descriptions.csv": desc, TIDY / "abs_osca_title_index.csv": idx,
            HERE / "anzsco_osca_unit_group_crosswalk.csv": cw}
    for p, d in outs.items():
        write_table(d, p)

    spine = pd.read_csv(HERE / "occupation_skills_national.csv", dtype={"unit_group_code": str})
    spine = spine[spine["in_jsa_projections"].astype(str).eq("True")
                  & spine["not_further_defined"].astype(str).eq("False")]["unit_group_code"]
    covered = set(cw["anzsco_unit_group"])
    idx1 = pd.read_excel(INDEX, sheet_name="Table 1", header=None, dtype=object)
    checks = {
        "structure_counts": st["level"].value_counts().to_dict(),
        "correspondence_tables": corr.groupby(["table", "from_classification", "to_classification"]).size()
                                     .reset_index(name="rows").to_dict("records"),
        "no_correspondence_rows": int(corr["to_code"].eq("xxxxxx").sum() + corr["from_code"].eq("xxxxxx").sum()),
        "partial_share_table1_pct": round(100 * corr.loc[corr["table"].eq("Table 1"), "partial"].mean(), 1),
        "anzsco_v13_occupations_in_table1": int(corr.loc[corr["table"].eq("Table 1"), "from_code"].nunique()),
        "crosswalk_unit_group_pairs": int(len(cw)),
        "spine_unit_groups_covered (excluding 'nfd' rows)": f"{len(set(spine) & covered)} of {spine.nunique()}",
        "spine_unit_groups_not_covered": sorted(set(spine) - covered),
        "anzsco_occupations_without_2021_employment": int(links.drop_duplicates("from_code")
                                                          ["anzsco_employed_2021"].isna().sum()),
        "one_to_one_unit_groups": int((cw.groupby("anzsco_unit_group")["osca_unit_group"].nunique() == 1).sum()),
        "descriptions": desc["level"].value_counts().to_dict(),
        "title_index_rows": int(len(idx)),
        "title_index_table1_rows": int(idx1[0].astype(str).str.fullmatch(r"\d{6}").sum()),
        "rows": {p.name: len(d) for p, d in outs.items()},
    }
    (HERE / "osca_classification_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps({k: v for k, v in checks.items() if k != "correspondence_tables"}, indent=1, default=str))

    C = "Classification"
    m = {
        "osca_code": ("OSCA 2024 v1.0 code (1 to 4 digits for groups, 6 for occupations)", SRC, "", C),
        "title": ("Title", SRC, "", C),
        "level": ("Major group, Sub-major group, Minor group, Unit group or Occupation", SRC, "", C),
        "skill_level": ("OSCA skill level (1 = highest); groups can span several levels", SRC, "", C),
        "major_group": ("Major group the row belongs to", SRC, "", C),
        "sub_major_group": ("Sub-major group the row belongs to (blank for major groups)", SRC, "", C),
        "minor_group": ("Minor group the row belongs to (blank above minor group level)", SRC, "", C),
        "unit_group": ("Unit group the row belongs to (blank above unit group level)", SRC, "", C),
        "table": ("ABS correspondence table number", SRC, "", C),
        "from_classification": ("Classification of from_code (ANZSCO v1.3, ANZSCO 2021 or 2022 Australian Update, "
                                "OSCA 2024 v1.0, ISCO-08 or NOL v1.0)", SRC, "", C),
        "from_code": ("Code in the from classification ('xxxxxx' = no correspondence)", SRC, "", C),
        "from_title": ("Title in the from classification", SRC, "", C),
        "to_classification": ("Classification of to_code", SRC, "", C),
        "to_code": ("Code in the to classification ('xxxxxx' = no correspondence)", SRC, "", C),
        "to_title": ("Title in the to classification", SRC, "", C),
        "partial": ("True where ABS marks 'p': from_code covers only part of to_code. ABS gives no proportions", SRC,
                    "", C),
        "alternative_titles": ("Other names for the occupation", SRC, "", "Text"),
        "lead_statement": ("Short statement of what the group or occupation does", SRC, "", "Text"),
        "main_tasks": ("Main tasks", SRC, "", "Text"),
        "registration_or_licensing": ("Registration or licensing requirements", SRC, "", "Text"),
        "inclusion_exclusion": ("What is included in or excluded from the category", SRC, "", "Text"),
        "skill_attributes": ("Skill attributes", SRC, "", "Text"),
        "specialisations": ("Specialisations within the occupation", SRC, "", "Text"),
        "occupations_in_nec": ("Occupations placed in this 'not elsewhere classified' category", SRC, "", "Text"),
        "category": ("Principal Title, Alternative Title, Specialisation or Occupation in nec category", SRC, "", C),
        "anzsco_unit_group": ("ANZSCO v1.3 unit group (the project's spine)", SRC, "", C),
        "osca_unit_group": ("OSCA 2024 v1.0 unit group", SRC, "", C),
        "osca_unit_group_title": ("OSCA unit group title", SRC, "", C),
        "links": ("Occupation-level correspondence links between the two unit groups", SRC, "", "Count"),
        "partial_links": ("Links marked partial", SRC, "", "Count"),
        "anzsco_occupations": ("ANZSCO 6-digit occupations with a link", SRC, "", "Count"),
        "employed_2021_est": ("2021 Census employment of the ANZSCO occupations, shared across their OSCA links in "
                              "proportion to the OSCA occupations' 2021 employment", SRC + "; JSA occupation profiles "
                              "(ANZSCO) and JSA OSCA Census 2021 data", "August 2021",
                              "Estimate (our assumption on how partial links split)"),
        "anzsco_without_employment": ("Linked ANZSCO occupations with no published 2021 employment (counted as 0)",
                                      "JSA occupation profiles", "", "Count"),
        "share_of_anzsco_unit_group_pct": ("Share of the ANZSCO unit group that moves to this OSCA unit group (%), "
                                           "weighted by 2021 employment; occupations count equally where the unit "
                                           "group has no published 6-digit employment", "", "",
                                           "Estimate (our assumption)"),
        "share_of_osca_unit_group_pct": ("Share of the OSCA unit group's estimated employment that comes from this "
                                         "ANZSCO unit group (%)", "", "", "Estimate (our assumption)"),
    }
    rows = []
    for p, d in outs.items():
        prefix = "tidy/" if p.parent == TIDY else "analysis/"
        rows += dictionary_rows(prefix + p.name, d, m)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
