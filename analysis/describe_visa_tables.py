"""Add the Home Affairs visa tables in tidy/ to the data dictionary.

Run from the Migration folder:  python3 analysis/describe_visa_tables.py
The tables themselves come from analysis/visa_extraction/run_extraction.py (BP0014, BP0015, BP0016, BP0019 pivot
workbooks, Citizenship Country summed out). This script only reads them to record what every column means and
which period each table covers.
"""
import pandas as pd

from _common import TIDY, dictionary_rows, update_dictionary

HA = "Home Affairs via data.gov.au, "
SOURCES = {   # file prefix -> (source, what the count column holds)
    "skilled_grants_": (HA + "BP0014 temporary resident (skilled) visas granted, to 30 June 2026", "Visas granted"),
    "skilled_holders_": (HA + "BP0014 temporary resident (skilled) visa holders, quarterly snapshots to 30 June 2026",
                         "Visa holders on the snapshot date"),
    "student_grants_": (HA + "BP0015 student visas granted, data to 31 August 2026", "Visas granted"),
    "student_lodged_": (HA + "BP0015 student visa applications lodged, data to 31 August 2026", "Applications lodged"),
    "student_decisions_": (HA + "BP0015 student visa grant rates, data to 31 August 2026", ""),
    "bp0016_temporary_graduate_granted": (HA + "BP0016 temporary graduate visas granted, to 31 August 2026",
                                          "Visas granted"),
    "bp0016_temporary_graduate_lodged": (HA + "BP0016 temporary graduate visa applications lodged, to 31 August 2026",
                                         "Applications lodged"),
    "bp0019_": (HA + "BP0019 temporary visa holders in Australia, snapshots to 31 August 2026", ""),
}
C, O = "Classification", "Official data (Home Affairs)"
MEANING = {
    "fy_label": "Financial year as Home Affairs labels it; the latest year can be partial ('2025-26 to 30 June 2026')",
    "fy": "Financial year (YYYY-YY)",
    "fy_complete": "False if the financial year is only partly covered",
    "data_to": "Last date covered, for a partial year (blank if the year is complete)",
    "fy_quarter": "Quarter of the financial year (Q1 = July to September)",
    "month": "Month as Home Affairs labels it (for example 'M01 Jul' or '03 SEP')",
    "snapshot_date": "Date of the snapshot (end of quarter or month)",
    "client_location": "Where the applicant was: In Australia or Outside Australia",
    "applicant_type": "Primary (main applicant) or Secondary (family member included in the application)",
    "visa_subclass": "Visa subclass (for example 482, 457, 485, 500)",
    "visa_type": "Visa type or stream",
    "visa_subtype": "Visa sub-type or stream detail (for example Labour Agreement, Core Skills)",
    "visa_category": "Broad temporary visa category (for example Student, Visitor, Working Holiday Maker, Bridging)",
    "agreement_type": "Labour agreement type, where the grant used one",
    "dama_agreement": "Designated Area Migration Agreement (DAMA), where the grant used one",
    "state": "Nominated position location: state or territory, as written in the source (names or abbreviations)",
    "sa4": "Nominated position location: Statistical Area Level 4 (ABS ASGS)",
    "sa3": "Nominated position location: Statistical Area Level 3 (ABS ASGS)",
    "occupation_major_group_code": "Nominated occupation: ANZSCO major group code (1 digit)",
    "occupation_major_group": "Nominated occupation: ANZSCO major group title",
    "occupation_unit_group_code": "Nominated occupation: ANZSCO unit group code (4 digit)",
    "occupation_unit_group": "Nominated occupation: ANZSCO unit group title",
    "occupation_code": "Nominated occupation: 6-digit ANZSCO code (blank for 'Not Specified')",
    "occupation": "Nominated occupation title",
    "skill_level": "Skill level of the nominated occupation",
    "sponsor_industry": "Industry (ANZSIC division) of the sponsoring employer",
    "gender": "Gender",
    "age_group": "Age group",
    "sector": "Education sector of the student's course",
    "provider_state": "State where the education provider is registered",
    "last_visa_category": "Visa category held before this grant",
    "visa_holders": "Temporary visa holders in Australia on the snapshot date",
    "grants": "Visas granted",
    "refusals": "Visas refused",
    "decisions": "Decisions: grants plus refusals",
    "grant_rate": "Grants divided by decisions",
}
PERIOD_COL = ["fy", "snapshot_date"]


def source_for(name):
    return next(v for k, v in SOURCES.items() if name.startswith(k))


def main():
    files = sorted(p for p in TIDY.iterdir() if p.name.startswith(tuple(SOURCES))
                   and p.name.endswith((".csv", ".csv.gz")))
    rows = []
    for path in files:
        src, count_meaning = source_for(path.name)
        head = pd.read_csv(path, nrows=0)
        pcol = next(c for c in PERIOD_COL if c in head.columns)
        per = pd.read_csv(path, usecols=[pcol], dtype=str)[pcol]
        period = f"{per.min()} to {per.max()}"
        m = {}
        for c in head.columns:
            if c == "count":
                m[c] = (count_meaning, src, period, O)
            elif c == "grant_rate":
                m[c] = (MEANING[c], src, period, "Calculated from official data")
            elif c in ("visa_holders", "grants", "refusals", "decisions"):
                m[c] = (MEANING[c], src, period, O)
            else:
                m[c] = (MEANING[c], src, "", C)
        rows += dictionary_rows("tidy/" + path.name, head, m)
        print(f"{path.name}: {len(head.columns)} columns, {period}")
    update_dictionary(rows)


if __name__ == "__main__":
    main()
