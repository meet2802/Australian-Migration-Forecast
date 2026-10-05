"""Permanent Migration Program outcomes from the Home Affairs 2024-25 Migration Program report (PDF).

Run from the Migration folder:  python3 analysis/build_migration_program_tables.py
Needs pdftotext (poppler) on the PATH.

Outputs in tidy/:
  ha_program_outcome_by_stream.csv                  places by stream, 2014-15 to 2024-25 (table 1.1)
  ha_program_outcome_by_state.csv                   places by intended state and stream, 2014-15 to 2024-25
  ha_program_outcome_2024_25_by_state_category.csv  places by state, stream and visa category, 2024-25
  ha_program_outcome_2024_25_by_location.csv        places by category, in or outside Australia (table 1.3.1)
  ha_program_outcome_2024_25_top_occupations.csv    top 10 occupations by Skill category, primary applicants
analysis/migration_program_checks.json              reconciliation checks
Outcome = visas granted that count toward the program (primary and secondary applicants unless
stated). The report's citizenship tables are deliberately not extracted.
"""
import json
import re
import subprocess

import numpy as np
import pandas as pd

from _common import HERE, ROOT, TIDY, dictionary_rows, update_dictionary, write_table

PDF = ROOT / "report-migration-program-2024-25.pdf"
SRC = "Department of Home Affairs, 2024-25 Migration Program report (Dec 2025)"
YEARS = [f"{y}-{str(y + 1)[2:]}" for y in range(2014, 2025)]
STATE_PAGES = {"Australian Capital Territory": "ACT", "New South Wales": "NSW", "Northern Territory": "NT",
               "Queensland": "QLD", "South Australia": "SA", "Tasmania": "TAS", "Victoria": "VIC",
               "Western Australia": "WA", "State not specified": "Not specified"}
SKILL = ["Employer Sponsored", "Skilled Independent", "Regional", "State/Territory Nominated",
         "Business Innovation & Investment", "Global Talent", "Distinguished Talent"]
FAMILY = ["Partner", "Parent", "Other Family", "Child"]
NUM = r"(?:[\d,]+|<\d+)"


def pages():
    txt = subprocess.run(["pdftotext", "-layout", str(PDF), "-"], capture_output=True, text=True, check=True).stdout
    return txt.split("\f")


def to_num(s):
    s = s.strip()
    return np.nan if s.startswith("<") else float(s.replace(",", ""))


def by_stream(pg):
    page = next(p for p in pg if "Migration Program Outcome by stream" in p and re.search(r"^\s*2014-15\s+[\d,]", p, re.M))
    rows = []
    for m in re.finditer(r"^\s*(\d{4}-\d{2})\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+[\d.]+%", page, re.M):
        for stream, v in zip(["Skill", "Family", "Child", "Special Eligibility", "Total"], m.groups()[1:]):
            rows.append({"financial_year": m.group(1), "stream": stream, "places": to_num(v)})
    return pd.DataFrame(rows)


def by_state(pg):
    hist, cat = [], []
    for p in pg:
        m = re.search(r"Migration Program Outcome: (.+?) by stream and", p)
        if not m or "....." in p or m.group(1) not in STATE_PAGES:
            continue
        state = STATE_PAGES[m.group(1)]
        for line in p.splitlines():
            vals = re.findall(NUM, line.split("  ")[-1]) if line.strip() else []
            head = re.match(r"^\s*(Skill|Family|Child|Special Eligibility)\s{2,}(.*)$", line)
            if head:
                nums = re.findall(r"[\d,]+", head.group(2))
                if len(nums) == 11:
                    for y, v in zip(YEARS, nums):
                        hist.append({"financial_year": y, "state": state, "stream": head.group(1), "places": to_num(v)})
                    continue
            se = re.search(r"Special Eligibility Total\s{2,}(" + NUM + r")\s*$", line)
            if se:
                cat.append({"financial_year": "2024-25", "state": state, "stream": "Special Eligibility",
                            "visa_category": "Special Eligibility", "places": to_num(se.group(1)),
                            "suppressed": se.group(1) if se.group(1).startswith("<") else ""})
                continue
            for c in SKILL + FAMILY:
                mm = re.search(r"\s(" + re.escape(c) + r")(?:\s*\([^)]*\))?\s{2,}(" + NUM + r")\s*$", line)
                if mm and not re.search(r"Total\s", line):
                    stream = "Skill" if c in SKILL else "Family"
                    raw = mm.group(2)
                    cat.append({"financial_year": "2024-25", "state": state, "stream": stream, "visa_category": c,
                                "places": to_num(raw), "suppressed": raw if raw.startswith("<") else ""})
                    break
    hist = pd.DataFrame(hist).drop_duplicates(["financial_year", "state", "stream"])
    cat = pd.DataFrame(cat).drop_duplicates(["state", "visa_category"])
    hist["derived"] = False
    return hist, cat


def add_not_specified(hist, streams):
    """The report has no previous-years table for 'Not specified': national minus the states, by stream."""
    nat = streams[~streams["stream"].eq("Total")].set_index(["financial_year", "stream"])["places"]
    st = hist.groupby(["financial_year", "stream"])["places"].sum()
    ns = (nat - st.reindex(nat.index).fillna(0)).reset_index()
    ns = ns.assign(state="Not specified", derived=True)
    return pd.concat([hist, ns[["financial_year", "state", "stream", "places", "derived"]]], ignore_index=True)


def by_location(pg):
    page = next(p for p in pg if "by visa type and location of client" in p and "In Australia" in p)
    rows = []
    stream = None
    for line in page.splitlines():
        m = re.match(r"^\s*(.*?)\s{2,}([\d,]+)\s+([\d,]+)\s+([\d,]+)\s*$", line)
        if not m:
            continue
        label = re.sub(r"\s+", " ", m.group(1)).strip()
        parts = [x.strip() for x in re.split(r"\s{2,}", m.group(1).strip())]
        if parts[0] in ("Skill", "Family"):
            stream = parts[0]
            label = parts[-1]
        if label.endswith("Total"):
            stream_label, cat = label.replace(" Total", ""), "Total"
        else:
            stream_label, cat = stream, label
        rows.append({"financial_year": "2024-25", "stream": stream_label, "visa_category": cat,
                     "in_australia": to_num(m.group(2)), "outside_australia": to_num(m.group(3)),
                     "total": to_num(m.group(4))})
    return pd.DataFrame(rows)


def top_occupations(pg):
    titles = {"2.5.": "Skill stream (all categories)", "2.9.": "Employer Sponsored", "2.10.": "Skilled Independent",
              "2.11.1.": "Regional", "2.12.": "State/Territory Nominated"}
    rows = []
    for p in pg:
        if "....." in p:
            continue
        sec = re.search(r"^\s*(2\.(?:5|9|10|11\.1|11\.2|12)\.)\s", p, re.M)
        if not sec:
            continue
        table = titles.get(sec.group(1))
        rank = 0
        for line in p.splitlines():
            if line.strip() in ("Skilled Employer Sponsored", "Skilled Work Regional"):
                table, rank = "Regional - " + line.strip(), 0
                continue
            m = re.match(r"^\s*(\d{4})\s+(.+?)\s{2,}([\d,]+)\s*$", line)
            if m and table:
                rank += 1
                rows.append({"financial_year": "2024-25", "category": table, "rank": rank,
                             "unit_group_code": m.group(1), "occupation": m.group(2).strip(),
                             "primary_applicants": to_num(m.group(3))})
    return pd.DataFrame(rows)


def main():
    pg = pages()
    s = by_stream(pg)
    hist, cat = by_state(pg)
    hist = add_not_specified(hist, s)
    loc = by_location(pg)
    occ = top_occupations(pg)
    outs = {TIDY / "ha_program_outcome_by_stream.csv": s, TIDY / "ha_program_outcome_by_state.csv": hist,
            TIDY / "ha_program_outcome_2024_25_by_state_category.csv": cat,
            TIDY / "ha_program_outcome_2024_25_by_location.csv": loc,
            TIDY / "ha_program_outcome_2024_25_top_occupations.csv": occ}
    for path, df in outs.items():
        write_table(df, path)

    tot = s[s["stream"].eq("Total")].set_index("financial_year")["places"]
    parts = s[~s["stream"].eq("Total")].groupby("financial_year")["places"].sum()
    states_sum = hist.groupby("financial_year")["places"].sum()
    cat_known = cat.groupby("state")["places"].sum()
    hist25 = hist[hist["financial_year"].eq("2024-25")].groupby("state")["places"].sum()
    checks = {
        "streams_add_to_total": bool((parts - tot).abs().max() < 1),
        "states_add_to_national_total_by_year": {y: [float(states_sum.get(y, np.nan)), float(tot.get(y, np.nan))] for y in YEARS},
        "state_tables_found": sorted(hist.loc[~hist["derived"], "state"].unique().tolist()),
        "not_specified_derived_2024_25": float(hist[(hist["state"] == "Not specified") &
                                                    (hist["financial_year"] == "2024-25")]["places"].sum()),
        "2024_25_category_sums_vs_state_totals": {st: [float(cat_known.get(st, np.nan)), float(hist25.get(st, np.nan))]
                                                  for st in sorted(hist25.index)},
        "suppressed_category_cells": int(cat["suppressed"].ne("").sum()),
        "location_total": float(loc.loc[loc["stream"].eq("Migration Program"), "total"].sum()),
        "in_australia_share_pct": round(100 * float(loc.loc[loc["stream"].eq("Migration Program"), "in_australia"].sum())
                                        / float(loc.loc[loc["stream"].eq("Migration Program"), "total"].sum()), 1),
        "occupation_tables": occ.groupby("category")["rank"].max().to_dict(),
        "rows": {p.name: len(df) for p, df in outs.items()},
    }
    (HERE / "migration_program_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))

    O = "Official data (Home Affairs)"
    m = {
        "financial_year": ("Program year", SRC, "", "Classification"),
        "stream": ("Skill, Family, Child (in Family from 2022-23), Special Eligibility, or Total", SRC, "", "Classification"),
        "places": ("Visas granted that count toward the Migration Program (primary and secondary applicants). "
                   "Blank where the report shows <5 or <10", SRC, "", O),
        "state": ("Intended state of residence as recorded by the applicant ('Not specified' if not recorded)", SRC, "", "Classification"),
        "visa_category": ("Visa category within the stream (Total = stream total)", SRC, "", "Classification"),
        "suppressed": ("The report's suppression marker (for example <5, <10, <20) where places is blank", SRC, "", "Classification"),
        "derived": ("True for 'Not specified' rows, calculated as the national total minus the states", SRC, "", "Classification"),
        "in_australia": ("Places granted to people in Australia when they applied", SRC, "2024-25", O),
        "outside_australia": ("Places granted to people outside Australia when they applied", SRC, "2024-25", O),
        "total": ("All places in the category", SRC, "2024-25", O),
        "category": ("Skill category of the top-10 table (Regional subcategories shown separately)", SRC, "", "Classification"),
        "rank": ("Rank within the category's top 10", SRC, "", "Classification"),
        "unit_group_code": ("ANZSCO 4-digit unit group", SRC, "", "Classification"),
        "occupation": ("Unit group title", SRC, "", "Classification"),
        "primary_applicants": ("Places granted to primary applicants in this occupation (top 10 per category only)", SRC, "2024-25", O),
    }
    rows = []
    for path, df in outs.items():
        rows += dictionary_rows(f"tidy/{path.name}", df, m)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
