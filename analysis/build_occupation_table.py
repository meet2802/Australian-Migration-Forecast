"""Line up skilled visas with shortage ratings, projected job growth, job ads and local
training, one row per ANZSCO 4-digit unit group.

Run from the Migration folder (pandas and openpyxl needed):
    python3 analysis/build_occupation_table.py

Inputs: the JSA, NCVER, Department of Education and Home Affairs files downloaded into
the Migration folder, plus tidy/skilled_*_occupation_state.csv.gz.

Outputs in analysis/:
    occupation_skills_national.csv   one row per unit group, Australia
    occupation_skills_state.csv      unit group by state
    uni_pipeline_state.csv           university completions by state, 7 mapped courses
    comparison_groups.csv            unit groups compared together for supply, and why
    data_dictionary.csv              what every column means, its source and number type
    join_checks.json                 match rates, totals, coding and title checks
Outputs in tidy/ (Section 14 award course completions, Department of Education):
    uni_special_courses_national.csv          7 courses, every year in the file (table 14.19)
    uni_special_courses_institution.csv       latest year by state and institution (table 14.20)
    uni_completions_broad_field.csv           domestic and overseas students (table 14.3)

Method decisions (October 2026):
  * Classification: ANZSCO 4-digit unit groups in the version the JSA projections use
    (ANZSCO 2013 v1.3). ANZSCO 2022 codes in other sources join directly where the code is
    unchanged. Where codes split or moved, or where NCVER codes trainees to a neighbouring
    or 'nfd' unit group, supply is compared at comparison-group level (GROUPS below).
    OSCA codes get added through the ABS correspondence once the projections move to OSCA.
  * Ranking: two separate questions, not one blended score. Is the job short now (2025
    shortage list)? Is it projected to grow faster than jobs overall to 2030? Six groups plus
    'Not assessed', ranked inside each group by projected new jobs a year.
  * New workers needed = projected net new jobs + estimated retirements + net career moves out.
    Retirements share the
    ABS national count across jobs by their Census 2021 age profiles, using PROVISIONAL age-band
    weights (RETIREMENT_WEIGHTS) until official age-specific rates are added. Career moves use ABS
    Job Mobility flows between the 8 broad occupation groups, adjusted for each job's age mix;
    moves within a broad group are not visible.
  * Workers by state = national employment (May 2025) x JSA state shares (Feb 2026).
No nationality or country-of-birth field is used anywhere.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from _common import log_rows

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TIDY = ROOT / "tidy"
SECTION14 = ROOT / "2024_Section14_Award_Course_Completions.xlsx"

STATE = {
    "NSW": "NSW", "New South Wales": "NSW", "VIC": "VIC", "Victoria": "VIC",
    "QLD": "QLD", "Queensland": "QLD", "SA": "SA", "South Australia": "SA",
    "WA": "WA", "Western Australia": "WA", "TAS": "TAS", "Tasmania": "TAS",
    "NT": "NT", "Northern Territory": "NT", "ACT": "ACT",
    "Australian Capital Territory": "ACT", "AUST": "AUS", "Multi-State": "Multi-state",
}
STATES = ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"]
RATING = {"S": "Shortage", "R": "Regional shortage", "M": "Metropolitan shortage", "NS": "No shortage"}
CODE = "unit_group_code"

# Section 14 special interest courses, keyed by the Department's footnote number, and the
# unit group (or comparison group) each one trains people for.
COURSES = {
    "8.01": ("Initial registration as a nurse", "2544"),
    "8.02": ("Initial teacher education", "G241"),
    "8.03": ("Provisional registration as a medical practitioner", "G253"),
    "8.04": ("Registration as a veterinary practitioner", "2347"),
    "8.05": ("Registration as a dentist", "2523"),
    "8.06": ("Clinical psychology", "2723"),
    "8.07": ("Aviation", "2311"),
}

# Unit groups whose training and visa supply is compared together.
# (group code, name, member codes or prefixes, excluded codes, reason). Earlier groups win.
GROUPS = [
    ("G241", "School teachers (all levels)", ["241"], [],
     "Initial teacher education is not split by school level"),
    ("G253", "Medical practitioners", ["253"], [],
     "Medical graduates start as interns and resident medical officers, then specialise"),
    ("G311", "Agricultural, medical and science technicians", ["311"], [],
     "Most trainee completions are coded only to the group (nfd)"),
    ("G322", "Fabrication engineering trades (incl. welders)", ["322"], [],
     "Apprentices sit under Sheetmetal Workers while visas sit under Structural Steel and Welding"),
    ("G323", "Mechanical engineering trades (incl. fitters)", ["323"], [],
     "Most apprentice completions are coded only to the group (nfd)"),
    ("G324", "Panelbeaters, vehicle body builders, trimmers and painters", ["324"], [],
     "No apprentices are coded to Panelbeaters"),
    ("G351C", "Chefs and cooks", ["3513", "3514"], [],
     "Cookery apprentices sit mostly under Cooks while visas sit mostly under Chefs"),
    ("G393", "Textile, clothing and footwear trades", ["393"], [],
     "Most apprentice completions are coded only to the group (nfd)"),
    ("G431", "Hospitality workers", ["431"], [],
     "Most trainee completions are coded only to the group (nfd)"),
    ("G552", "Financial and insurance clerks", ["552"], [],
     "Most trainee completions are coded only to the group (nfd)"),
    ("G121", "Farmers and farm managers", ["121"], [],
     "ANZSCO 2022 replaced the crop and mixed farmer codes"),
    ("G362", "Gardeners and horticultural trades", ["362"], [],
     "ANZSCO 2022 split Gardeners into three codes"),
    ("G84", "Farm, forestry and garden workers, senior farm workers and shearers",
     ["84", "363", "3612", "3431"], [],
     "ANZSCO 2022 moved these jobs to new codes (pest controllers from 8419 to 8434); Home Affairs codes "
     "fishing leading hands to 3431, the OSCA code for senior aquaculture, crop and forestry workers"),
]
# ANZSCO 2013 v1.3 codes that ANZSCO 2022 replaced, with their 2022 successor codes (matched by
# title; replace with the ABS correspondence once it is added). Used only to carry the 2025
# shortage rating back to the projections code, and only when every successor has the same rating.
SUCCESSORS = {
    "1212": ["1215", "1216"], "1214": ["1217"], "3612": ["3633"], "3622": ["3625", "3626", "3627"],
    "8411": ["8421"], "8412": ["8422"], "8413": ["8431"], "8414": ["8432", "8433"],
    "8415": ["8423"], "8416": ["8424"], "8419": ["8434", "8439"],
}
BAND_PP = 2.0   # within 2 percentage points of all-jobs growth (5 years) counts as average

PROFILES = ROOT / "ANZSCO Occupation data - February 2026.xlsx"
AGE_BANDS = ["15_19", "20_24", "25_34", "35_44", "45_54", "55_59", "60_64", "65_plus"]
# Retirements a year in Australia: people aged 45+ who retired in 2024 (ABS, Retirement and Retirement
# Intentions, Australia, 2024-25: 155.6 thousand by year of retirement; headline "156,000 in 2024-25").
NATIONAL_RETIREMENTS_PER_YEAR = 155_600
# PROVISIONAL relative retirement risk per worker by age band. An assumption, not data: workers aged
# 60-64 and 65+ count fully, 55-59 a quarter (so about 1 in 6 retirements come from 55-59), younger
# workers not at all. Replace with official age-specific rates from ABS 6238.0 Table 14 when available.
RETIREMENT_WEIGHTS = {"55_59": 0.25, "60_64": 1.0, "65_plus": 1.0}
# Share of apprentice and trainee completers employed in the same occupation group as their training
# (NCVER, Apprentice and trainee outcomes 2023: trained in 2022, employed at end of May 2023).
# Trade completers by ANZSCO sub-major group of training; non-trade completers by major group.
NCVER_TRADE_RETENTION_PCT = {"32": 79.4, "33": 84.1, "34": 84.7, "35": 65.1}   # other trade groups below
NCVER_OTHER_TRADE_PCT = 53.7
NCVER_NONTRADE_RETENTION_PCT = {"1": 10.4, "2": 10.4, "4": 42.2, "5": 15.5, "6": 42.7, "7": 44.5, "8": 31.8}
# ABS, Job mobility, February 2026 (release page, Charts 6, 7 and 10). For each ANZSCO major group:
# % of workers who changed employer and left a job in that group, % who changed employer into a job
# in that group, and % of those leaving who stayed in the same major group.
JOB_MOBILITY_2026 = {   # major group: (left %, entered %, stayed in same group %)
    "1": (5.6, 5.3, 56.0), "2": (6.2, 6.4, 81.1), "3": (8.0, 8.0, 75.2), "4": (8.0, 7.2, 57.7),
    "5": (6.8, 7.8, 62.0), "6": (9.9, 7.5, 44.4), "7": (8.8, 9.5, 74.6), "8": (10.3, 8.9, 58.1),
}
# ABS job mobility rate by age, February 2026, used to adjust each job for its age mix
JOB_MOBILITY_BY_AGE_PCT = {"15_19": 12.0, "20_24": 12.0, "25_34": 8.1, "35_44": 8.1,
                           "45_54": 4.6, "55_59": 4.6, "60_64": 4.6, "65_plus": 1.2}


def training_retention_pct(code):
    """Share of completers who end up working in the occupation group they trained for (NCVER 2023)."""
    code = str(code)
    if not code[:1].isdigit():
        return np.nan
    if code.startswith("3"):
        return NCVER_TRADE_RETENTION_PCT.get(code[:2], NCVER_OTHER_TRADE_PCT)
    return NCVER_NONTRADE_RETENTION_PCT.get(code[:1], np.nan)
LOCAL_TRAINING_MEASURED = {"University courses and apprenticeships", "University courses",
                           "Apprenticeships and traineeships"}


def four_digit(series):
    """Return ANZSCO unit group codes as 4-character strings; anything else becomes NaN."""
    s = pd.to_numeric(series, errors="coerce").astype("Int64").astype(str)
    return s.where(s.str.fullmatch(r"[1-8]\d{3}"))


def _num(v):
    """Numbers stay numbers; 'np', '< 5', '.', '-' and blanks become NaN."""
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else np.nan


def _norm_title(s):
    s = str(s).lower()
    for w in ("trades", "workers", "worker", " nfd", "- nfd", " and ", "(general)"):
        s = s.replace(w, " ")
    return re.sub(r"[^a-z]", "", s)


# ---------------------------------------------------------------- sources
def load_projections():
    p = pd.read_excel(ROOT / "employment_projections_-_may_2025_to_may_2035.xlsx",
                      sheet_name="Table_6 Occupation Unit Group", header=None, skiprows=9)
    p = p.iloc[:, :12]
    p.columns = ["level", "nfd", "code", "occupation", "skill_level", "e25", "e30", "e35",
                 "c5", "c5p", "c10", "c10p"]
    p = p[p["level"] == 4].copy()
    p[CODE] = four_digit(p["code"])
    p = p[p[CODE].notna()]
    all_jobs_growth = float(p["e30"].sum() / p["e25"].sum() * 100 - 100)
    out = pd.DataFrame({
        CODE: p[CODE],
        "occupation": p["occupation"].astype(str).str.strip(),
        "not_further_defined": p["nfd"].eq("Y"),
        "skill_level": p["skill_level"].astype(str),
        "employed_may2025": (p["e25"] * 1000).round(),
        "projected_may2030": (p["e30"] * 1000).round(),
        "projected_may2035": (p["e35"] * 1000).round(),
        "projected_growth_5y": (p["c5"] * 1000).round(),
        "projected_growth_5y_pct": (p["c5p"] * 100).round(1),
    })
    return out, all_jobs_growth


def load_osl():
    o = pd.read_excel(ROOT / "2025 Unit Group Shortage List - 4 digit ANZSCO.xlsx",
                      sheet_name="2025 Unit group Shortage List", header=None, skiprows=8)
    o = o.iloc[:, :13]
    o.columns = [CODE, "osl_title", "osl_2025_national"] + STATES + ["osl_skill_level", "major_group"]
    o[CODE] = four_digit(o[CODE])
    o = o[o[CODE].notna()].copy()
    for c in ["osl_2025_national"] + STATES:
        o[c] = o[c].astype(str).str.strip()
    return o


def load_profiles():
    q = pd.read_excel(ROOT / "ANZSCO Occupation data - February 2026.xlsx",
                      sheet_name="Table_1", header=None, skiprows=7)
    q = q.iloc[:, :8]
    q.columns = ["code", "occ", "employed_feb2026", "part_time_pct", "female_pct",
                 "median_weekly_earnings", "median_age", "annual_employment_growth"]
    q[CODE] = four_digit(q["code"])
    q = q[q[CODE].notna()].copy()
    for c in ["employed_feb2026", "median_weekly_earnings", "median_age"]:
        q[c] = pd.to_numeric(q[c], errors="coerce")
    return q[[CODE, "occ", "employed_feb2026", "median_age", "median_weekly_earnings"]]


def _profile_table(sheet, names):
    """A 4-digit table from the JSA occupation profiles workbook (6-digit rows are dropped)."""
    raw = pd.read_excel(PROFILES, sheet_name=sheet, header=None)
    h = raw.index[raw.iloc[:, 0].astype(str).str.strip().eq("ANZSCO Code")][0]
    t = raw.iloc[h + 1:, :len(names) + 2].copy()
    t.columns = ["code", "occ"] + names
    t[CODE] = four_digit(t["code"])
    t = t[t[CODE].notna()].copy()
    for c in names:
        t[c] = pd.to_numeric(t[c], errors="coerce")
    return t[[CODE] + names]


def load_profile_ages():
    """Table 7: % of each occupation's workers by age band (ABS Census 2021)."""
    return _profile_table("Table_7", AGE_BANDS)


def load_profile_states():
    """Table 6: % of each occupation's workers in each state (ABS LFS Detailed, Feb 2026, JSA trend)."""
    return _profile_table("Table_6", STATES)


def load_state_totals():
    """JSA projections Table 4: employment by state, May 2025 baseline (used as a check)."""
    t = pd.read_excel(ROOT / "employment_projections_-_may_2025_to_may_2035.xlsx",
                      sheet_name="Table_4 State & Territory", header=None)
    t = t[t[0].isin(STATES)]
    return pd.Series((t[1].astype(float) * 1000).round().values, index=t[0].values)


def fill_profile(nat, cols):
    """Rows in the projections without their own profile (mostly 'nfd' rows) take the employment-
    weighted average of the closest group that has one. Returns where each row's profile came from."""
    own = nat[cols[0]].notna()
    src = pd.Series(np.where(own & nat["in_jsa_projections"], "Own", ""), index=nat.index)
    base = nat["in_jsa_projections"] & own & nat["employed_may2025"].notna()
    w = nat.loc[base, "employed_may2025"]
    levels = [("comparison group", nat["comparison_group"]), ("minor group", nat[CODE].str[:3]),
              ("sub-major group", nat[CODE].str[:2]), ("major group", nat[CODE].str[:1])]
    for label, key in levels:
        prof = nat.loc[base, cols].mul(w, axis=0).groupby(key[base]).sum().div(
            w.groupby(key[base]).sum(), axis=0)
        todo = nat["in_jsa_projections"] & src.eq("") & key.isin(prof.index)
        for c in cols:
            nat.loc[todo, c] = key[todo].map(prof[c])
        src[todo] = label + " average"
    return src


def load_ivi():
    iv = pd.read_excel(ROOT / "internet_vacancies_anzsco4_occupations_states_and_territories_-_august_2026.xlsx",
                       sheet_name="4 digit 3 month average")
    dates = [c for c in iv.columns if hasattr(c, "year")]
    latest = max(dates)
    year_ago = latest.replace(year=latest.year - 1)
    iv[CODE] = four_digit(iv["ANZSCO_CODE"])
    iv = iv[iv[CODE].notna()].copy()
    num = lambda col: pd.to_numeric(iv[col], errors="coerce").round()   # some cells are text markers
    out = pd.DataFrame({CODE: iv[CODE], "state": iv["state"].map(STATE), "ivi_title": iv["ANZSCO_TITLE"],
                        "job_ads_latest": num(latest), "job_ads_year_ago": num(year_ago)})
    return out, latest.date().isoformat(), year_ago.date().isoformat()


def load_ncver():
    merged, period = None, None
    for fname, measure in [("Apprentices and trainees (4).xlsx", "apprentice_commencements"),
                           ("Apprentices and trainees (5).xlsx", "apprentice_completions")]:
        n = pd.read_excel(ROOT / fname)
        periods = [c for c in n.columns if str(c).startswith("12 months ending")]
        period = periods[-1]
        occ = n["Occupation 4-digit"].astype(str)
        n = n[occ.str.match(r"^\d{4} - ")].copy()
        n[CODE] = n["Occupation 4-digit"].astype(str).str.slice(0, 4)
        n["state"] = n["State/territory"].map(STATE)
        n["ncver_title"] = n["Occupation 4-digit"].astype(str).str.slice(7).str.strip()
        raw = n[period].astype(str).str.strip()
        n[measure] = pd.to_numeric(raw.where(raw != "-", "0"), errors="coerce").fillna(0)  # "-" = nil or rounded to zero
        part = n[[CODE, "state", "ncver_title", measure]]
        merged = part if merged is None else merged.merge(part, on=[CODE, "state", "ncver_title"], how="outer")
    merged[["apprentice_commencements", "apprentice_completions"]] = \
        merged[["apprentice_commencements", "apprentice_completions"]].fillna(0)
    return merged, period


def visa_key(df):
    """Unit group code, or the label in brackets when Home Affairs has no ANZSCO code."""
    code = df["occupation_unit_group_code"].fillna("").astype(str)
    return code.where(code != "", "(" + df["occupation_unit_group"].astype(str) + ")")


def load_visas():
    h = pd.read_csv(TIDY / "skilled_holders_occupation_state.csv.gz",
                    dtype={"occupation_unit_group_code": str}, keep_default_na=False)
    latest = h["snapshot_date"].max()
    year_ago = f"{int(latest[:4]) - 1}{latest[4:]}"
    h[CODE] = visa_key(h)
    h["state"] = h["state"].map(STATE).fillna("Not specified")
    keys = [CODE, "state"]
    hp = h[h["applicant_type"] == "Primary"]
    parts = [
        hp[hp["snapshot_date"] == latest].groupby(keys)["count"].sum().rename("visa_holders_primary"),
        hp[hp["snapshot_date"] == year_ago].groupby(keys)["count"].sum().rename("visa_holders_primary_year_ago"),
        h[h["snapshot_date"] == latest].groupby(keys)["count"].sum().rename("visa_holders_incl_family"),
    ]
    g = pd.read_csv(TIDY / "skilled_grants_occupation_state.csv.gz",
                    dtype={"occupation_unit_group_code": str}, keep_default_na=False)
    g["fy_complete"] = g["fy_complete"].astype(str).eq("True")
    latest_fy = g.loc[g["fy_complete"], "fy"].max()
    g[CODE] = visa_key(g)
    g["state"] = g["state"].map(STATE).fillna("Not specified")
    gp = g[(g["fy"] == latest_fy) & (g["applicant_type"] == "Primary")]
    parts.append(gp.groupby(keys)["count"].sum().rename("visa_grants_primary"))
    titles = pd.concat([h[[CODE, "occupation_unit_group"]], g[[CODE, "occupation_unit_group"]]]) \
        .drop_duplicates(CODE).rename(columns={"occupation_unit_group": "visa_title"})
    v = pd.concat(parts, axis=1).fillna(0).reset_index()
    v = v.merge(titles, on=CODE, how="left")
    return v, latest, year_ago, latest_fy


def _course_key(label):
    """'Initial Registration as Nurses(8.01)' -> '8.01'. Footnote rows ('(8.01) Students ...') -> None."""
    label = str(label).strip()
    m = re.search(r"\((8\.0\d)\)", label)
    return m.group(1) if m and not label.startswith("(") else None


def load_section14():
    """University completions from the Department of Education's Section 14 workbook."""
    import openpyxl
    wb = openpyxl.load_workbook(SECTION14, read_only=True, data_only=True)
    rows = lambda name: [r for r in wb[name].iter_rows(values_only=True)]

    # Table 14.19: the 7 special interest courses, all students, 2015 onwards
    t = rows("14.19")
    h = next(i for i, r in enumerate(t) if r and r[0] == "Special Interest Course")
    ycols = [(j, c) for j, c in enumerate(t[h]) if isinstance(c, int)]
    ts = []
    for r in t[h + 1:]:
        key = _course_key(r[0]) if r and r[0] else None
        if key in COURSES:
            for j, y in ycols:
                ts.append({"course_code": key, "course": COURSES[key][0], "maps_to": COURSES[key][1],
                           "year": y, "completions": _num(r[j])})
    ts = pd.DataFrame(ts)

    # Table 14.20: the same courses in the latest year, by state and institution
    t = rows("14.20")
    h = next(i for i, r in enumerate(t) if r and r[0] == "State")
    title = next(str(r[0]) for r in t[:h] if r and str(r[0]).startswith("Table 14.20"))
    inst_year = int(re.search(r"(\d{4})\s*$", title).group(1))
    assert inst_year == ts["year"].max(), (inst_year, ts["year"].max())
    keys = [_course_key(c) for c in t[h]]
    inst, total_row = [], None
    for r in t[h + 1:]:
        if not r or r[0] is None:
            continue
        if r[0] == "Total":
            total_row = r
            break
        for j, key in enumerate(keys):
            if key in COURSES:
                inst.append({"year": inst_year, "state": STATE.get(r[0], r[0]), "institution": r[1],
                             "course_code": key, "course": COURSES[key][0], "maps_to": COURSES[key][1],
                             "completions": _num(r[j]), "suppressed": str(r[j]).strip() == "np"})
    inst = pd.DataFrame(inst)
    total_14_20 = {keys[j]: _num(total_row[j]) for j in range(len(keys)) if keys[j] in COURSES}

    # Table 14.3: domestic and overseas students by broad field of education
    t = rows("14.3")
    h = next(i for i, r in enumerate(t) if r and r[0] == "Citizenship")
    ycols = [(j, c) for j, c in enumerate(t[h]) if isinstance(c, int)]
    bf = []
    for r in t[h + 1:]:
        if not r or r[0] is None or str(r[0]).startswith("("):
            continue
        if r[1] is None:
            continue
        field = str(r[1]).strip()
        field = "Total (unique students)" if field.startswith("Total") else field
        for j, y in ycols:
            raw = r[j]
            bf.append({"student_type": str(r[0]).replace(" Students", "").strip(), "broad_field": field,
                       "year": y, "completions": _num(raw),
                       "note": "" if isinstance(raw, (int, float)) else str(raw).strip()})
    bf = pd.DataFrame(bf)
    return ts, inst, total_14_20, bf


# ---------------------------------------------------------------- helpers
def assign_groups(codes):
    """Map unit group codes to their comparison group (codes not listed map to themselves)."""
    out = {}
    for gcode, _, members, excluded, _ in GROUPS:
        for c in codes:
            if c in out or c in excluded:
                continue
            if any(str(c).startswith(m) for m in members):
                out[c] = gcode
    return out


def coverage_label(has_uni, has_app, degree_level):
    if has_uni and has_app:
        return "University courses and apprenticeships"
    if has_uni:
        return "University courses"
    if degree_level and has_app:
        return "Apprenticeships only (degree-level training not measured)"
    if degree_level:
        return "Not measured (degree-level job)"
    if has_app:
        return "Apprenticeships and traineeships"
    return "Not measured (no apprenticeships recorded)"


# ---------------------------------------------------------------- build
def main():
    proj, all_jobs_growth = load_projections()
    log_rows("Read JSA employment projections: unit groups", proj, "employment_projections_-_may_2025_to_may_2035.xlsx")
    osl = load_osl()
    log_rows("Read the 2025 shortage list: unit groups", osl, "2025 Unit Group Shortage List - 4 digit ANZSCO.xlsx")
    prof = load_profiles()
    log_rows("Read JSA occupation profiles", prof, "ANZSCO Occupation data - February 2026.xlsx")
    ivi, ivi_month, ivi_prev = load_ivi()
    log_rows("Read job ads by occupation and state", ivi, "internet_vacancies_anzsco4 (August 2026)")
    ncv, ncv_period = load_ncver()
    log_rows("Read NCVER apprentices and trainees by occupation and state", ncv, "Apprentices and trainees (NCVER)")
    vis, snap, snap_prev, fy = load_visas()
    log_rows("Read Home Affairs temporary skilled visas by occupation and state", vis, "skilled_*_occupation_state")
    uni_ts, uni_inst, uni_total_14_20, uni_bf = load_section14()
    uni_year = int(uni_ts["year"].max())

    vis_cols = ["visa_holders_primary", "visa_holders_primary_year_ago", "visa_holders_incl_family",
                "visa_grants_primary"]
    app_cols = ["apprentice_commencements", "apprentice_completions"]
    vis_nat = vis.groupby(CODE)[vis_cols].sum().reset_index()
    ncv_nat = ncv.groupby(CODE)[app_cols].sum().reset_index()
    ivi_nat = ivi[ivi["state"] == "AUS"].drop(columns="state")

    # Spine: every unit group JSA projects, plus any code another source has that the spine lacks
    nat = proj.copy()
    extra_titles = pd.concat([
        osl[[CODE, "osl_title"]].rename(columns={"osl_title": "occupation"}),
        ivi_nat[[CODE, "ivi_title"]].rename(columns={"ivi_title": "occupation"}),
        ncv[[CODE, "ncver_title"]].rename(columns={"ncver_title": "occupation"}),
        vis[[CODE, "visa_title"]].rename(columns={"visa_title": "occupation"}),
        prof[[CODE, "occ"]].rename(columns={"occ": "occupation"}),
    ]).drop_duplicates(CODE)
    missing = extra_titles[~extra_titles[CODE].isin(nat[CODE])]
    nat = pd.concat([nat, missing], ignore_index=True)
    log_rows("Spine: projected unit groups plus codes found only in other sources", nat, note=f"{len(missing)} codes added")
    nat["in_jsa_projections"] = nat[CODE].isin(proj[CODE])
    nat["not_further_defined"] = nat["not_further_defined"].eq(True)

    nat = (nat.merge(osl[[CODE, "osl_2025_national"]], on=CODE, how="left")
              .merge(prof.drop(columns="occ"), on=CODE, how="left")
              .merge(ivi_nat.drop(columns="ivi_title"), on=CODE, how="left")
              .merge(ncv_nat, on=CODE, how="left")
              .merge(vis_nat, on=CODE, how="left"))
    log_rows("Joined shortage list, profiles, job ads, apprentices and visas onto the spine (left joins)", nat,
             note="Left joins keep every spine row")
    for c in vis_cols + app_cols:
        nat[c] = nat[c].fillna(0).astype(int)

    # Shortage rating, carried back to replaced ANZSCO 2013 codes when all successors agree
    osl_map = {c: r for c, r in zip(osl[CODE], osl["osl_2025_national"]) if r in RATING}
    nat["osl_rating_source"] = np.where(nat["osl_2025_national"].isin(list(RATING)), "2025 list", "")
    carried = {}
    for old, new in SUCCESSORS.items():
        ratings = {osl_map.get(c) for c in new}
        row = nat[CODE].eq(old)
        if row.any() and len(ratings) == 1 and None not in ratings and nat.loc[row, "osl_rating_source"].eq("").all():
            nat.loc[row, "osl_2025_national"] = ratings.pop()
            nat.loc[row, "osl_rating_source"] = "2025 list via ANZSCO 2022 code(s) " + " ".join(new)
            carried[old] = new
        else:
            carried[old] = "not carried: successor ratings " + ", ".join(
                f"{c}={osl_map.get(c, 'none')}" for c in new)

    # Plain indicators (descriptive only, not a model)
    nat["osl_2025_rating"] = nat["osl_2025_national"].map(RATING).fillna("Not assessed")
    nat["in_shortage_2025"] = nat["osl_2025_national"].isin(["S", "R", "M"])
    emp = nat["employed_may2025"]
    nat["visa_primary_per_1000_workers"] = (nat["visa_holders_primary"] / emp * 1000).round(1)
    nat["projected_growth_per_year"] = (nat["projected_growth_5y"] / 5).round()
    nat["job_ads_change_12m_pct"] = ((nat["job_ads_latest"] / nat["job_ads_year_ago"] - 1) * 100).round(1)

    # Outlook: short now? x growth to 2030 compared with all jobs
    all_growth_shown = round(all_jobs_growth, 1)
    nat["growth_vs_all_jobs_pp"] = (nat["projected_growth_5y_pct"] - all_growth_shown).round(1)
    diff = nat["growth_vs_all_jobs_pp"]
    band = np.select([diff > BAND_PP, diff < -BAND_PP], ["Faster than average", "Slower than average"],
                     default="About average")
    nat["growth_band"] = np.where(diff.isna(), "No projection", band)
    nat["shortage_now"] = np.select(
        [nat["in_shortage_2025"], nat["osl_2025_rating"].eq("No shortage")],
        ["Short now", "Not short now"], default="Not assessed")
    assessed = nat["shortage_now"].ne("Not assessed") & nat["growth_band"].ne("No projection")
    nat["outlook_group"] = np.where(
        assessed, nat["shortage_now"] + ", " + nat["growth_band"].str.lower() + " growth", "Not assessed")
    nat["rank_in_outlook_group"] = (nat[assessed].groupby("outlook_group")["projected_growth_per_year"]
                                    .rank(ascending=False, method="first")).astype("Int64")

    # Comparison groups: supply measured at the level the sources can support
    groups = assign_groups(nat[CODE].unique())
    nat["comparison_group"] = nat[CODE].map(groups).fillna(nat[CODE])
    gname = {g[0]: g[1] for g in GROUPS}
    nat["comparison_group_name"] = nat["comparison_group"].map(gname).fillna(nat["occupation"])

    # Age profile (Census 2021) and state shares (LFS, Feb 2026) from the JSA occupation profiles
    age_cols = ["age_" + b for b in AGE_BANDS]
    st_share_cols = ["share_" + s for s in STATES]
    ages = load_profile_ages().rename(columns=dict(zip(AGE_BANDS, age_cols)))
    shares = load_profile_states().rename(columns=dict(zip(STATES, st_share_cols)))
    nat = nat.merge(ages, on=CODE, how="left").merge(shares, on=CODE, how="left")
    nat["age_profile_source"] = fill_profile(nat, age_cols)
    nat["state_share_source"] = fill_profile(nat, st_share_cols)
    nat["share_aged_55_plus_pct"] = nat[["age_55_59", "age_60_64", "age_65_plus"]].sum(axis=1, min_count=1).round(1)
    nat["share_aged_60_plus_pct"] = nat[["age_60_64", "age_65_plus"]].sum(axis=1, min_count=1).round(1)

    # Retirements a year (replacement demand from retirement only): the national ABS total, shared
    # across occupations by their older workers, weighted by age band (RETIREMENT_WEIGHTS)
    weighted = sum(nat["age_" + b] / 100 * wgt for b, wgt in RETIREMENT_WEIGHTS.items()) * nat["employed_may2025"]
    weighted = weighted.where(nat["in_jsa_projections"])
    retire_k = NATIONAL_RETIREMENTS_PER_YEAR / weighted.sum()
    nat["retirements_per_year_est"] = (weighted * retire_k).round()
    retire_by_band = {b: round(float((nat["age_" + b] / 100 * wgt * nat["employed_may2025"] * retire_k)
                                     .where(nat["in_jsa_projections"]).sum()))
                      for b, wgt in RETIREMENT_WEIGHTS.items()}
    # Career moves between broad occupation groups a year (people changing employer). Group flows come
    # from ABS Job Mobility; inside a group, moves out scale with the job's age mix (younger workers
    # move more) and moves in are shared by employment. Moves within a broad group are not visible.
    major = nat[CODE].str[:1]
    emp_p = nat["employed_may2025"].where(nat["in_jsa_projections"])
    mob = pd.DataFrame(JOB_MOBILITY_2026, index=["left_pct", "entered_pct", "stayed_pct"]).T
    mob["employed"] = emp_p.groupby(major).sum().reindex(mob.index)
    mob["changed_jobs_left"] = mob["employed"] * mob["left_pct"] / 100
    mob["changed_jobs_entered"] = mob["employed"] * mob["entered_pct"] / 100
    # Every job changer is counted once by the group left and once by the group entered, so the two
    # totals must match. The published (rounded) rates don't quite, so both sides meet in the middle.
    mob_gap = float(mob["changed_jobs_left"].sum() - mob["changed_jobs_entered"].sum())
    mid = (mob["changed_jobs_left"].sum() + mob["changed_jobs_entered"].sum()) / 2
    mob["changed_jobs_left"] *= mid / mob["changed_jobs_left"].sum()
    mob["changed_jobs_entered"] *= mid / mob["changed_jobs_entered"].sum()
    mob["stayed_in_group"] = mob["changed_jobs_left"] * mob["stayed_pct"] / 100
    mob["moved_out"] = mob["changed_jobs_left"] - mob["stayed_in_group"]
    mob["moved_in"] = mob["changed_jobs_entered"] - mob["stayed_in_group"]
    age_factor = sum(nat["age_" + b] / 100 * r for b, r in JOB_MOBILITY_BY_AGE_PCT.items())
    mean_af = (age_factor * emp_p).groupby(major).sum() / emp_p.groupby(major).sum()
    age_adj = age_factor / major.map(mean_af)
    nat["career_moves_out_per_year_est"] = (emp_p * major.map(mob["moved_out"] / mob["employed"]) * age_adj).round()
    nat["career_moves_in_per_year_est"] = (emp_p * major.map(mob["moved_in"] / mob["employed"])).round()
    nat["career_moves_net_loss_per_year_est"] = nat["career_moves_out_per_year_est"] - nat["career_moves_in_per_year_est"]

    nat["new_workers_needed_per_year_est"] = (nat["projected_growth_per_year"] + nat["retirements_per_year_est"]
                                              + nat["career_moves_net_loss_per_year_est"]).clip(lower=0)

    # Apprentice and trainee completions that actually end up in the occupation group trained for
    nat["training_retention_pct"] = nat[CODE].map(training_retention_pct).where(nat["apprentice_completions"] > 0)
    nat["apprentice_completions_effective"] = nat["apprentice_completions"] * nat["training_retention_pct"].fillna(0) / 100

    gsum = nat.groupby("comparison_group")[["employed_may2025", "projected_growth_5y"]].sum(min_count=1)
    gsum = gsum.join(nat.groupby("comparison_group")[["apprentice_completions", "visa_grants_primary",
                                                      "visa_holders_primary"]].sum())
    gsum.columns = ["group_employed_may2025", "group_projected_growth_5y", "group_apprentice_completions",
                    "group_visa_grants_primary", "group_visa_holders_primary"]
    uni_latest = uni_ts[uni_ts["year"] == uni_year].groupby("maps_to")["completions"].sum(min_count=1)
    unmapped_courses = sorted(set(uni_latest.index) - set(gsum.index))
    gsum["group_uni_completions"] = uni_latest.reindex(gsum.index)
    lead = (nat.sort_values("employed_may2025", ascending=False)
               .drop_duplicates("comparison_group").set_index("comparison_group")["skill_level"])
    degree = lead.astype(str).str.strip().str.startswith("1").reindex(gsum.index).fillna(False)
    gsum["local_training_coverage"] = [
        coverage_label(pd.notna(u), a > 0, d) for u, a, d in
        zip(gsum["group_uni_completions"], gsum["group_apprentice_completions"], degree)]
    measured = gsum["local_training_coverage"].isin(LOCAL_TRAINING_MEASURED)
    gsum["group_local_training"] = (gsum["group_uni_completions"].fillna(0)
                                    + gsum["group_apprentice_completions"]).where(measured)
    app_eff = nat.groupby("comparison_group")["apprentice_completions_effective"].sum()
    gsum["group_local_training_effective"] = (gsum["group_uni_completions"].fillna(0) + app_eff).where(measured)
    gsum["group_projected_growth_per_year"] = (gsum["group_projected_growth_5y"] / 5).round()
    gemp = gsum["group_employed_may2025"]
    gsum["group_local_training_per_1000_workers"] = (gsum["group_local_training"] / gemp * 1000).round(1)
    gsum["group_visa_grants_per_1000_workers"] = (gsum["group_visa_grants_primary"] / gemp * 1000).round(1)
    gsum["group_retirements_per_year_est"] = nat.groupby("comparison_group")["retirements_per_year_est"].sum(min_count=1)
    gsum["group_career_moves_net_loss_per_year_est"] = nat.groupby("comparison_group")[
        "career_moves_net_loss_per_year_est"].sum(min_count=1)
    need = (gsum["group_projected_growth_per_year"] + gsum["group_retirements_per_year_est"]
            + gsum["group_career_moves_net_loss_per_year_est"].fillna(0)).clip(lower=0)
    gsum["group_new_workers_needed_per_year_est"] = need
    gsum["group_local_training_per_100_needed"] = (gsum["group_local_training_effective"] / need * 100).where(need > 0).round()
    gsum["group_visa_grants_per_100_needed"] = (gsum["group_visa_grants_primary"] / need * 100).where(need > 0).round()
    gsum = gsum.drop(columns="group_projected_growth_5y")
    nat = nat.merge(gsum, left_on="comparison_group", right_index=True, how="left")
    nat = nat.drop(columns=["osl_2025_national"]).sort_values(CODE).reset_index(drop=True)

    # Estimated workers by state: national employment (May 2025) x the occupation's state shares
    emp_long =nat.loc[nat["in_jsa_projections"], [CODE, "employed_may2025"] + st_share_cols].melt(
        id_vars=[CODE, "employed_may2025"], var_name="state", value_name="share_of_occupation_in_state_pct")
    emp_long["state"] = emp_long["state"].str.replace("share_", "", regex=False)
    emp_long["employed_state_est"] = emp_long["employed_may2025"] * emp_long["share_of_occupation_in_state_pct"] / 100
    emp_long = emp_long.drop(columns="employed_may2025")
    nat = nat.drop(columns=age_cols + st_share_cols)

    nat_cols = [
        CODE, "occupation", "skill_level", "not_further_defined", "in_jsa_projections",
        "osl_2025_rating", "osl_rating_source", "in_shortage_2025", "shortage_now", "projected_growth_5y_pct",
        "growth_vs_all_jobs_pp", "growth_band", "outlook_group", "rank_in_outlook_group",
        "employed_may2025", "projected_may2030", "projected_may2035", "projected_growth_5y",
        "projected_growth_per_year", "retirements_per_year_est", "career_moves_out_per_year_est",
        "career_moves_in_per_year_est", "career_moves_net_loss_per_year_est", "new_workers_needed_per_year_est",
        "employed_feb2026", "median_age", "share_aged_55_plus_pct", "share_aged_60_plus_pct",
        "age_profile_source", "state_share_source", "median_weekly_earnings",
        "job_ads_latest", "job_ads_year_ago", "job_ads_change_12m_pct",
        "apprentice_commencements", "apprentice_completions", "training_retention_pct",
        "visa_holders_primary", "visa_holders_primary_year_ago", "visa_holders_incl_family",
        "visa_grants_primary", "visa_primary_per_1000_workers",
        "comparison_group", "comparison_group_name", "local_training_coverage",
        "group_employed_may2025", "group_projected_growth_per_year", "group_retirements_per_year_est",
        "group_career_moves_net_loss_per_year_est", "group_new_workers_needed_per_year_est",
        "group_apprentice_completions",
        "group_uni_completions", "group_local_training", "group_local_training_effective",
        "group_local_training_per_1000_workers",
        "group_visa_grants_primary", "group_visa_holders_primary", "group_visa_grants_per_1000_workers",
        "group_local_training_per_100_needed", "group_visa_grants_per_100_needed",
    ]
    nat = nat.drop(columns="apprentice_completions_effective")
    assert set(nat_cols) == set(nat.columns), set(nat.columns) ^ set(nat_cols)
    nat = nat[nat_cols]
    whole = ["employed_may2025", "projected_may2030", "projected_may2035", "projected_growth_5y",
             "projected_growth_per_year", "retirements_per_year_est", "new_workers_needed_per_year_est",
             "career_moves_out_per_year_est", "career_moves_in_per_year_est", "career_moves_net_loss_per_year_est",
             "group_career_moves_net_loss_per_year_est",
             "employed_feb2026", "job_ads_latest", "job_ads_year_ago",
             "group_employed_may2025", "group_projected_growth_per_year", "group_retirements_per_year_est",
             "group_new_workers_needed_per_year_est", "group_uni_completions", "group_local_training",
             "group_local_training_effective",
             "group_local_training_per_100_needed", "group_visa_grants_per_100_needed"]
    nat[whole] = nat[whole].round().astype("Int64")
    log_rows("Written", nat, "occupation_skills_national.csv")
    nat.to_csv(HERE / "occupation_skills_national.csv", index=False)

    # State table
    osl_long = osl.melt(id_vars=[CODE], value_vars=STATES, var_name="state", value_name="osl_2025_state")
    osl_long["osl_2025_state_rating"] = osl_long["osl_2025_state"].map(RATING).fillna("Not assessed")
    st = (osl_long.drop(columns="osl_2025_state")
          .merge(vis.drop(columns="visa_title"), on=[CODE, "state"], how="outer")
          .merge(ivi[ivi["state"] != "AUS"].drop(columns="ivi_title"), on=[CODE, "state"], how="outer")
          .merge(ncv.drop(columns="ncver_title"), on=[CODE, "state"], how="outer")
          .merge(emp_long, on=[CODE, "state"], how="outer"))
    st = st.merge(nat[[CODE, "occupation", "osl_2025_rating", "comparison_group"]].rename(
        columns={"osl_2025_rating": "osl_2025_national_rating"}), on=CODE, how="left")
    for c in vis_cols + app_cols:
        st[c] = st[c].fillna(0).astype(int)
    st["osl_2025_state_rating"] = st["osl_2025_state_rating"].fillna("Not assessed")
    st["comparison_group"] = st["comparison_group"].fillna(st[CODE])
    gst = (st.groupby(["comparison_group", "state"])[["apprentice_completions", "visa_grants_primary",
                                                      "visa_holders_primary"]].sum().add_prefix("group_"))
    gst["group_employed_state_est"] = st.groupby(["comparison_group", "state"])["employed_state_est"].sum(min_count=1)
    uni_state = (uni_inst.groupby(["maps_to", "state"])["completions"].sum(min_count=1)
                 .rename("group_uni_completions"))
    uni_state.index = uni_state.index.set_names(["comparison_group", "state"])
    gst = gst.join(uni_state, how="left")
    gst_emp = gst["group_employed_state_est"]
    gst["group_apprentice_completions_per_1000_workers"] = (
        gst["group_apprentice_completions"] / gst_emp * 1000).where(gst_emp > 0).round(1)
    gst["group_visa_grants_per_1000_workers"] = (
        gst["group_visa_grants_primary"] / gst_emp * 1000).where(gst_emp > 0).round(1)
    st = st.merge(gst, left_on=["comparison_group", "state"], right_index=True, how="left")
    st_cols = [CODE, "occupation", "state", "comparison_group", "osl_2025_state_rating",
               "osl_2025_national_rating", "share_of_occupation_in_state_pct", "employed_state_est",
               "visa_holders_primary", "visa_holders_primary_year_ago",
               "visa_holders_incl_family", "visa_grants_primary", "job_ads_latest", "job_ads_year_ago",
               "apprentice_commencements", "apprentice_completions", "group_employed_state_est",
               "group_apprentice_completions", "group_uni_completions", "group_visa_grants_primary",
               "group_visa_holders_primary", "group_apprentice_completions_per_1000_workers",
               "group_visa_grants_per_1000_workers"]
    assert set(st_cols) == set(st.columns), set(st.columns) ^ set(st_cols)
    st = st[st_cols].sort_values([CODE, "state"])
    st["share_of_occupation_in_state_pct"] = st["share_of_occupation_in_state_pct"].round(1)
    whole = ["employed_state_est", "job_ads_latest", "job_ads_year_ago", "group_employed_state_est",
             "group_apprentice_completions", "group_uni_completions",
             "group_visa_grants_primary", "group_visa_holders_primary"]
    st[whole] = st[whole].round().astype("Int64")
    log_rows("Written", st, "occupation_skills_state.csv")
    st.to_csv(HERE / "occupation_skills_state.csv", index=False)

    # University pipeline tables
    name_of = dict(zip(nat["comparison_group"], nat["comparison_group_name"]))
    uni_ts.to_csv(TIDY / "uni_special_courses_national.csv", index=False)
    uni_inst.to_csv(TIDY / "uni_special_courses_institution.csv", index=False)
    uni_bf.to_csv(TIDY / "uni_completions_broad_field.csv", index=False)
    ups = (uni_inst.groupby(["year", "state", "course_code", "course", "maps_to"])
           .agg(completions=("completions", lambda s: s.sum(min_count=1)),
                suppressed_cells=("suppressed", "sum")).reset_index())
    ups["maps_to_name"] = ups["maps_to"].map(name_of)
    ups = ups[["year", "state", "course_code", "course", "maps_to", "maps_to_name", "completions",
               "suppressed_cells"]].sort_values(["course_code", "state"])
    ups.to_csv(HERE / "uni_pipeline_state.csv", index=False)

    # Comparison groups, written out so they can be reviewed
    cg = []
    for gcode, name, members, excluded, reason in GROUPS:
        mem = nat[nat["comparison_group"] == gcode]
        cg.append({"comparison_group": gcode, "name": name, "reason": reason,
                   "member_codes": " ".join(mem[CODE]),
                   "member_codes_not_in_projections": " ".join(mem.loc[~mem["in_jsa_projections"], CODE]),
                   "excluded_codes": " ".join(excluded)})
    pd.DataFrame(cg).to_csv(HERE / "comparison_groups.csv", index=False)

    # Data dictionary
    periods = {
        "proj": "Base May 2025, projected to May 2030 and May 2035",
        "osl": "2025",
        "prof": "February 2026",
        "ivi": f"3-month average to {ivi_month} (year ago: {ivi_prev})",
        "ncv": str(ncv_period),
        "hold": f"Snapshot {snap}",
        "hold_prev": f"Snapshot {snap_prev}",
        "grant": f"Financial year {fy}",
        "uni": str(uni_year),
    }
    S_PROJ = "JSA, Employment projections May 2025 to May 2035, Table 6"
    S_OSL = "JSA, 2025 Occupation Shortage List (unit group, ANZSCO 2022)"
    S_PROF = "JSA, ANZSCO occupation data February 2026, Table 1"
    S_IVI = "JSA, Internet Vacancy Index, 4-digit occupations by state"
    S_NCV = "NCVER, Apprentices and trainees (contracts of training)"
    S_HA = "Home Affairs, BP0014 temporary resident (skilled) visas (subclass 482 and 457)"
    S_UNI = "Department of Education, Section 14 award course completions, tables 14.19 and 14.20"
    S_AGE = "JSA occupation profiles Table 7 (ABS Census 2021 age profile)"
    S_STS = "JSA occupation profiles Table 6 (ABS LFS Detailed, Feb 2026, JSA trend)"
    S_RET = "ABS, Retirement and Retirement Intentions, Australia, 2024-25 (national total)"
    S_MOB = "ABS, Job mobility, February 2026 (rates by major occupation group and by age)"
    D = "Derived (our calculation)"
    E = "Estimate (our model, see join_checks.json)"
    meaning = {
        CODE: ("ANZSCO 4-digit unit group code, in the version the JSA projections use (ANZSCO 2013 v1.3). "
               "Rows not in the projections are codes found only in other sources (mostly ANZSCO 2022) "
               "or Home Affairs labels in brackets", "ABS ANZSCO", "", "Classification"),
        "occupation": ("Unit group title (projections title where available)", "JSA / source files", "", "Classification"),
        "state": ("State or territory. 'Not specified' = Home Affairs record without a state", "Source files", "", "Classification"),
        "skill_level": ("ANZSCO skill level(s); 1 = bachelor degree or higher", S_PROJ, "", "Classification"),
        "not_further_defined": ("True for 'nfd' rows: workers coded only to a broader group", S_PROJ, "", "Classification"),
        "in_jsa_projections": ("True if JSA projects this unit group", S_PROJ, "", "Classification"),
        "osl_2025_rating": ("National shortage rating", S_OSL, periods["osl"], "Official rating"),
        "osl_rating_source": ("Where the rating comes from. 'via ANZSCO 2022 code(s)' = rating of the codes that replaced "
                              "this one, used only when they all agree", S_OSL, periods["osl"], "Official rating"),
        "osl_2025_national_rating": ("National shortage rating", S_OSL, periods["osl"], "Official rating"),
        "osl_2025_state_rating": ("Shortage rating for this state", S_OSL, periods["osl"], "Official rating"),
        "in_shortage_2025": ("True if rated shortage, regional shortage or metro shortage", S_OSL, periods["osl"], D),
        "shortage_now": ("Short now / Not short now / Not assessed (from the 2025 rating)", S_OSL, periods["osl"], D),
        "projected_growth_5y_pct": ("Projected employment growth May 2025 to May 2030, %", S_PROJ, periods["proj"], "Projection (JSA, trend-based, not a forecast)"),
        "growth_vs_all_jobs_pp": (f"Projected 5-year growth minus growth for all jobs ({all_growth_shown}%), percentage points",
                                  S_PROJ, periods["proj"], D),
        "growth_band": (f"Faster / slower than average = more than {BAND_PP:g} points above / below all-jobs growth; "
                        "otherwise About average", S_PROJ, periods["proj"], D),
        "outlook_group": ("shortage_now combined with growth_band. Not assessed if either is missing",
                          f"{S_OSL}; {S_PROJ}", "", D),
        "rank_in_outlook_group": ("Rank inside the outlook group by projected new jobs a year (1 = most)", S_PROJ, periods["proj"], D),
        "employed_may2025": ("Employed persons, May 2025 (projection base)", S_PROJ, "May 2025", "Official estimate (JSA)"),
        "projected_may2030": ("Projected employment, May 2030", S_PROJ, "May 2030", "Projection (JSA, trend-based, not a forecast)"),
        "projected_may2035": ("Projected employment, May 2035", S_PROJ, "May 2035", "Projection (JSA, trend-based, not a forecast)"),
        "projected_growth_5y": ("Projected net change in employment, May 2025 to May 2030 (excludes replacement demand)",
                                S_PROJ, periods["proj"], "Projection (JSA, trend-based, not a forecast)"),
        "projected_growth_per_year": ("projected_growth_5y divided by 5", S_PROJ, periods["proj"], D),
        "retirements_per_year_est": (f"Estimated retirements a year: the ABS national total ({NATIONAL_RETIREMENTS_PER_YEAR:,}) "
                                     "shared across jobs by their workers aged 55+, weighted by age band (provisional "
                                     "weights). Retirement only; people changing careers are not counted",
                                     f"{S_RET}; {S_AGE}; {S_PROJ}", "Retirements in 2024; age profile 2021", E),
        "career_moves_out_per_year_est": ("Estimated workers a year who change employer and move to a job in a different "
                                          "broad occupation group. Group rate from ABS Job Mobility, scaled by this job's "
                                          "age mix. Moves within a broad group, and occupation changes with the same "
                                          "employer, are not counted", f"{S_MOB}; {S_AGE}", "Year to Feb 2026", E),
        "career_moves_in_per_year_est": ("Estimated workers a year arriving from a different broad occupation group, "
                                         "shared by employment within the group", S_MOB, "Year to Feb 2026", E),
        "career_moves_net_loss_per_year_est": ("career_moves_out minus career_moves_in. Negative = the job gains people "
                                               "from other jobs", S_MOB, "Year to Feb 2026", E),
        "group_career_moves_net_loss_per_year_est": ("Net career moves out of the comparison group a year (negative = "
                                                     "net gain)", S_MOB, "Year to Feb 2026", E),
        "new_workers_needed_per_year_est": ("projected_growth_per_year + retirements_per_year_est + "
                                             "career_moves_net_loss_per_year_est (not below 0). Moves within a broad "
                                             "occupation group are not counted",
                                            f"{S_PROJ}; {S_RET}", "", E),
        "share_aged_55_plus_pct": ("Share of workers aged 55 and over (see age_profile_source)", S_AGE, "August 2021",
                                   "Official data (ABS Census via JSA)"),
        "share_aged_60_plus_pct": ("Share of workers aged 60 and over (see age_profile_source)", S_AGE, "August 2021",
                                   "Official data (ABS Census via JSA)"),
        "age_profile_source": ("'Own' = the occupation's own Census 2021 profile; otherwise the employment-weighted "
                               "average of the closest group (mostly for 'nfd' rows)", S_AGE, "", "Classification"),
        "state_share_source": ("'Own' = the occupation's own state shares; otherwise the closest group's average",
                               S_STS, "", "Classification"),
        "employed_feb2026": ("Employed persons", S_PROF, periods["prof"], "Official estimate (JSA)"),
        "median_age": ("Median age of workers", S_PROF, periods["prof"], "Official estimate (JSA)"),
        "median_weekly_earnings": ("Median full-time weekly earnings, $", S_PROF, periods["prof"], "Official estimate (JSA)"),
        "job_ads_latest": ("Online job ads, 3-month average", S_IVI, periods["ivi"], "Official data (JSA)"),
        "job_ads_year_ago": ("Online job ads, 3-month average, a year earlier", S_IVI, periods["ivi"], "Official data (JSA)"),
        "job_ads_change_12m_pct": ("Change in online job ads over 12 months, %", S_IVI, periods["ivi"], D),
        "apprentice_commencements": ("Apprentice and trainee commencements (as coded by NCVER)", S_NCV, periods["ncv"], "Official data (NCVER)"),
        "apprentice_completions": ("Apprentice and trainee completions (as coded by NCVER). Use group columns for grouped jobs",
                                   S_NCV, periods["ncv"], "Official data (NCVER)"),
        "visa_holders_primary": ("Main applicants holding a temporary skilled visa", S_HA, periods["hold"], "Official data (Home Affairs)"),
        "visa_holders_primary_year_ago": ("Main applicants holding a temporary skilled visa a year earlier", S_HA,
                                          periods["hold_prev"], "Official data (Home Affairs)"),
        "visa_holders_incl_family": ("All holders including family members (family have no nominated job; "
                                     "they appear under 'Not Applicable')", S_HA, periods["hold"], "Official data (Home Affairs)"),
        "visa_grants_primary": ("Temporary skilled visas granted to main applicants", S_HA, periods["grant"], "Official data (Home Affairs)"),
        "visa_primary_per_1000_workers": ("visa_holders_primary per 1,000 employed (May 2025)", f"{S_HA}; {S_PROJ}", "", D),
        "comparison_group": ("Group used to compare training and visa supply (unit group code itself unless listed in "
                             "comparison_groups.csv)", "This project", "", "Classification"),
        "comparison_group_name": ("Name of the comparison group", "This project", "", "Classification"),
        "local_training_coverage": ("Which local training sources are measured for this group", "This project", "", D),
        "group_employed_may2025": ("Employed persons in the comparison group, May 2025", S_PROJ, "May 2025", D),
        "group_projected_growth_per_year": ("Projected net new jobs a year in the comparison group (excludes replacement demand)",
                                            S_PROJ, periods["proj"], D),
        "group_apprentice_completions": ("Apprentice and trainee completions in the comparison group", S_NCV, periods["ncv"], D),
        "group_uni_completions": ("University completions in the mapped special interest course (all students, "
                                       "domestic and overseas). State tables: by the institution's state", S_UNI, periods["uni"],
                                       "Official data (Department of Education)"),
        "group_local_training": ("Uni completions plus apprentice and trainee completions, only where coverage is "
                                 "reasonably complete (see local_training_coverage); blank otherwise",
                                 f"{S_UNI}; {S_NCV}", f"{periods['uni']} and {periods['ncv']}", D),
        "group_local_training_per_1000_workers": ("group_local_training per 1,000 employed in the group", "", "", D),
        "group_visa_grants_primary": ("Main-applicant temporary skilled visa grants in the comparison group", S_HA, periods["grant"], D),
        "group_visa_holders_primary": ("Main-applicant temporary skilled visa holders in the comparison group", S_HA, periods["hold"], D),
        "group_visa_grants_per_1000_workers": ("group_visa_grants_primary per 1,000 employed in the group (state table: "
                                               "per 1,000 estimated workers in the group in that state)", "", "", D),
        "group_retirements_per_year_est": ("Estimated retirements a year in the comparison group",
                                           f"{S_RET}; {S_AGE}", "", E),
        "group_new_workers_needed_per_year_est": ("Projected net new jobs + estimated retirements + net career moves out, a "
                                                  "year, in the comparison group (not below 0). Moves within a broad "
                                                  "occupation group are not counted", f"{S_PROJ}; {S_RET}", "", E),
        "training_retention_pct": ("Share of apprentice and trainee completers working in the occupation group they "
                                   "trained for (trades by sub-major group, others by major group)",
                                   "NCVER, Apprentice and trainee outcomes 2023", "Trained 2022, employed May 2023",
                                   "Official survey data (NCVER)"),
        "group_local_training_effective": ("Local training that ends up in the job: uni completions plus apprentice and "
                                           "trainee completions x training_retention_pct. Uni completions are not "
                                           "discounted (no equivalent data yet)",
                                           "Department of Education; NCVER", "", E),
        "group_local_training_per_100_needed": ("group_local_training_effective per 100 new workers needed. Over 100 does not mean "
                                                "enough: uni completions include overseas students and are not "
                                                "discounted, and moves within a broad occupation group are not in the need", "", "", E),
        "group_visa_grants_per_100_needed": ("Main-applicant temporary skilled visa grants per 100 new workers needed",
                                             "", "", E),
        "share_of_occupation_in_state_pct": ("Share of the occupation's workers who are in this state (see "
                                             "state_share_source in the national table)", S_STS, "February 2026",
                                             "Official estimate (JSA)"),
        "employed_state_est": ("Estimated workers in this state: employed_may2025 x share_of_occupation_in_state_pct",
                               f"{S_PROJ}; {S_STS}", "May 2025 level, Feb 2026 shares", E),
        "group_employed_state_est": ("Estimated workers in the comparison group in this state", f"{S_PROJ}; {S_STS}", "", E),
        "group_apprentice_completions_per_1000_workers": ("Apprentice and trainee completions in the comparison group "
                                                          "per 1,000 estimated workers in this state", "", "", D),
        "year": ("Calendar year of completion", S_UNI, periods["uni"], "Classification"),
        "course_code": ("Department of Education footnote number for the special interest course", S_UNI, "", "Classification"),
        "course": ("Special interest course", S_UNI, "", "Classification"),
        "maps_to": ("Unit group or comparison group the course trains people for", "This project", "", "Classification"),
        "maps_to_name": ("Name of maps_to", "This project", "", "Classification"),
        "completions": ("Award course completions, all students. Blank cells were suppressed ('np')", S_UNI,
                             periods["uni"], "Official data (Department of Education)"),
        "suppressed_cells": ("Institution cells marked 'np' (not published) and left out of the sum", S_UNI, periods["uni"], D),
    }
    S_BF = "Department of Education, Section 14 award course completions, table 14.3"
    meaning.update({
        "institution": ("Higher education provider", S_UNI, periods["uni"], "Classification"),
        "suppressed": ("True if the source cell was 'np' (not published); completions left blank", S_UNI,
                       periods["uni"], "Classification"),
        "name": ("Name of the comparison group", "This project", "", "Classification"),
        "reason": ("Why these unit groups are compared together", "This project", "", "Classification"),
        "member_codes": ("ANZSCO 4-digit unit groups in the group (space separated)", "This project", "",
                         "Classification"),
        "member_codes_not_in_projections": ("Members JSA does not project (mostly ANZSCO 2022 codes)", "This project",
                                            "", "Classification"),
        "excluded_codes": ("Codes deliberately left out of the group", "This project", "", "Classification"),
    })
    inst_meaning = dict(meaning)
    inst_meaning["state"] = ("State of the institution", S_UNI, "", "Classification")
    bf_meaning = dict(meaning)
    bf_meaning.update({
        "student_type": ("Domestic (citizens and permanent residents) or Overseas (temporary visa holders)", S_BF, "",
                         "Classification"),
        "broad_field": ("Broad field of education", S_BF, "", "Classification"),
        "completions": ("Award course completions. Combined courses count in each of their fields", S_BF, "",
                        "Official data (Department of Education)"),
        "note": ("Source footnote, where one applies", S_BF, "", "Classification"),
    })
    dd = []
    for table, cols, mm in [("analysis/occupation_skills_national.csv", nat_cols, meaning),
                            ("analysis/occupation_skills_state.csv", st_cols, meaning),
                            ("analysis/uni_pipeline_state.csv", list(ups.columns), meaning),
                            ("analysis/comparison_groups.csv", list(pd.DataFrame(cg).columns), meaning),
                            ("tidy/uni_special_courses_national.csv", list(uni_ts.columns), meaning),
                            ("tidy/uni_special_courses_institution.csv", list(uni_inst.columns), inst_meaning),
                            ("tidy/uni_completions_broad_field.csv", list(uni_bf.columns), bf_meaning)]:
        for c in cols:
            m, s, p, t = mm[c]
            dd.append({"table": table, "column": c, "meaning": m, "source": s, "period": p, "number_type": t})
    dd = pd.DataFrame(dd)
    ddp = HERE / "data_dictionary.csv"          # shared with the other build scripts: replace only our tables
    if ddp.exists():
        old = pd.read_csv(ddp, dtype=str, keep_default_na=False)
        old = old[~old["table"].isin(dd["table"].unique()) & ~old["table"].isin(
            ["occupation_skills_national.csv", "occupation_skills_state.csv", "uni_pipeline_state.csv"])]
        dd = pd.concat([old, dd], ignore_index=True)
    dd.to_csv(ddp, index=False)

    # Checks
    def match(df, measure=None):
        codes = df[CODE].dropna().unique()
        hit = [c for c in codes if c in set(proj[CODE])]
        res = {"unit_groups": len(codes), "matched_to_projections": len(hit)}
        if measure:
            tot = float(df[measure].sum())
            res[f"{measure}_total"] = tot
            res[f"{measure}_share_matched_pct"] = round(
                100 * float(df.loc[df[CODE].isin(proj[CODE]), measure].sum()) / tot, 2) if tot else None
        return res

    def title_diffs(df, title_col):
        t = df[[CODE, title_col]].dropna().drop_duplicates(CODE).merge(proj[[CODE, "occupation"]], on=CODE)
        t = t[t[title_col].map(_norm_title) != t["occupation"].map(_norm_title)]
        return [f"{r[CODE]}: '{r[title_col]}' vs projections '{r['occupation']}'" for _, r in t.iterrows()]

    # Training-coding flags: candidates for a comparison group, so new data surfaces new problems
    flags = []
    by_code = ncv_nat.set_index(CODE)["apprentice_completions"]
    nfd = by_code[by_code.index.str.endswith("0") & (by_code > 0)]
    for code, n in nfd.items():
        minor = by_code[by_code.index.str[:3] == code[:3]].sum()
        if n >= 50 and n / minor >= 0.25:
            flags.append({"rule": "25%+ of minor group completions coded nfd", "code": code,
                          "completions": int(n), "share_pct": round(100 * n / minor, 1),
                          "in_comparison_group": groups.get(code, "NO")})
    rate = nat[nat["in_jsa_projections"] & ~nat["not_further_defined"] & (nat["employed_may2025"] > 0)]
    rate = rate[rate["apprentice_completions"] / rate["employed_may2025"] > 0.25]
    for _, r in rate.iterrows():
        flags.append({"rule": "completions above 25% of the workforce", "code": r[CODE],
                      "completions": int(r["apprentice_completions"]),
                      "share_pct": round(100 * r["apprentice_completions"] / r["employed_may2025"], 1),
                      "in_comparison_group": groups.get(r[CODE], "NO")})

    unmatched_visa = (vis_nat[~vis_nat[CODE].isin(proj[CODE])]
                      .merge(vis[[CODE, "visa_title"]].drop_duplicates(CODE), on=CODE, how="left")
                      .sort_values(["visa_holders_primary", CODE], ascending=[False, True]))
    og = nat.groupby("outlook_group").agg(occupations=(CODE, "count"),
                                          visa_holders_primary=("visa_holders_primary", "sum"),
                                          visa_grants_primary=("visa_grants_primary", "sum"),
                                          projected_growth_per_year=("projected_growth_per_year", "sum"))
    for c in ["visa_holders_primary", "visa_grants_primary"]:
        og[c + "_share_pct"] = (100 * og[c] / og[c].sum()).round(1)
    groups_unique = nat.drop_duplicates("comparison_group")
    uni_by_course = uni_ts[uni_ts["year"] == uni_year].set_index("course_code")["completions"]
    inst_sum = uni_inst.groupby("course_code")["completions"].sum()
    inst_np = uni_inst.groupby("course_code")["suppressed"].sum()
    est_by_state = emp_long.groupby("state")["employed_state_est"].sum()
    jsa_states = load_state_totals()
    checks = {
        "reference_periods": {
            "projections_base": "May 2025 (projected to May 2030 and May 2035), ANZSCO 2013 v1.3",
            "shortage_list": "2025 Occupation Shortage List (unit group, ANZSCO 2022)",
            "occupation_profiles": "February 2026",
            "job_ads": f"3-month average to {ivi_month} (year ago: {ivi_prev})",
            "apprentices": ncv_period,
            "visa_holders": f"snapshot {snap} (year ago: {snap_prev})",
            "visa_grants": f"financial year {fy}",
            "university_completions": f"calendar year {uni_year} (Section 14)",
        },
        "all_jobs_growth_5y_pct": round(all_jobs_growth, 2),
        "growth_band_rule": f"More than {BAND_PP:g} points above/below {all_growth_shown}% = faster/slower than average",
        "outlook_groups": og.reset_index().to_dict("records"),
        "match_to_projection_unit_groups": {
            "shortage_list": match(osl),
            "occupation_profiles": match(prof),
            "job_ads": match(ivi_nat, "job_ads_latest"),
            "apprentices": match(ncv_nat, "apprentice_completions"),
            "visa_holders_primary": match(vis_nat, "visa_holders_primary"),
            "visa_grants_primary": match(vis_nat, "visa_grants_primary"),
        },
        "visa_codes_not_in_projections": unmatched_visa[[CODE, "visa_title", "visa_holders_primary",
                                                          "visa_grants_primary"]].head(25).to_dict("records"),
        "same_code_different_title": {
            "shortage_list": title_diffs(osl, "osl_title"),
            "apprentices": title_diffs(ncv, "ncver_title"),
            "visas": title_diffs(vis, "visa_title"),
            "job_ads": title_diffs(ivi_nat, "ivi_title"),
        },
        "training_coding_flags": flags,
        "shortage_rating_carried_to_anzsco_2013_codes": carried,
        "replacement_demand": {
            "method": ("Retirement only. The ABS national count of people who retired in a year is shared across "
                       "occupations in proportion to employed_may2025 x sum(age share x weight) over the age bands "
                       "below. Age profiles are ABS Census 2021 (latest by occupation). Weights are PROVISIONAL "
                       "assumptions until official age-specific retirement rates are added."),
            "national_retirements_per_year": NATIONAL_RETIREMENTS_PER_YEAR,
            "weights": RETIREMENT_WEIGHTS,
            "implied_annual_retirement_rate_pct_by_band": {b: round(100 * retire_k * w, 2)
                                                           for b, w in RETIREMENT_WEIGHTS.items()},
            "implied_retirements_by_band": retire_by_band,
            "implied_share_of_retirements_by_band_pct": {
                b: round(100 * v / NATIONAL_RETIREMENTS_PER_YEAR, 1) for b, v in retire_by_band.items()},
            "retirements_in_national_table": int(nat["retirements_per_year_est"].sum()),
            "age_profile_source_rows": nat.loc[nat["in_jsa_projections"], "age_profile_source"].value_counts().to_dict(),
            "age_profile_source_employment": nat.loc[nat["in_jsa_projections"]].groupby("age_profile_source")[
                "employed_may2025"].sum().round().astype(int).to_dict(),
            "top_by_retirements_per_year": nat.nlargest(10, "retirements_per_year_est")[
                [CODE, "occupation", "retirements_per_year_est", "share_aged_55_plus_pct"]].to_dict("records"),
            "new_workers_needed_per_year_total": int(nat["new_workers_needed_per_year_est"].sum()),
            "net_growth_per_year_total": int(nat["projected_growth_per_year"].sum()),
        },
        "career_moves": {
            "method": ("ABS Job Mobility (Feb 2026) gives, per major group, the % of workers who changed employer "
                       "leaving that group's jobs, the % entering it, and the % of leavers who stayed in the same "
                       "group. Moves out = leavers who changed group; moves in = enterers minus within-group movers, "
                       "with both sides scaled to the same total of job changers. Inside each group, moves out are scaled by "
                       "the job's age mix (ABS job mobility by age) and moves in are shared by employment."),
            "by_major_group": mob.assign(**{c: mob[c].round() for c in ["employed", "changed_jobs_left",
                                            "changed_jobs_entered", "stayed_in_group", "moved_out", "moved_in"]})
                                 .reset_index().rename(columns={"index": "major_group"}).to_dict("records"),
            "changed_jobs_left_minus_entered_before_balancing": int(round(mob_gap)),
            "national_net_after_balancing": int(nat["career_moves_net_loss_per_year_est"].sum()),
            "top_net_losers": nat.nlargest(10, "career_moves_net_loss_per_year_est")[
                [CODE, "occupation", "career_moves_net_loss_per_year_est"]].to_dict("records"),
            "top_net_gainers": nat.nsmallest(10, "career_moves_net_loss_per_year_est")[
                [CODE, "occupation", "career_moves_net_loss_per_year_est"]].to_dict("records"),
        },
        "state_employment_check": {
            s: {"our_estimate": int(round(est_by_state.get(s, 0))), "jsa_projections_table_4": int(jsa_states.get(s, 0)),
                "difference_pct": round(100 * (est_by_state.get(s, 0) / jsa_states.get(s, 1) - 1), 2)}
            for s in STATES},
        "university_pipeline": {
            "courses_not_mapped_to_a_row": unmapped_courses,
            "by_course": [{"course_code": k, "course": COURSES[k][0], "maps_to": COURSES[k][1],
                           f"table_14_19_{uni_year}": uni_by_course.get(k),
                           "table_14_20_total_row": uni_total_14_20.get(k),
                           "sum_of_institutions": float(inst_sum.get(k, 0)),
                           "suppressed_cells": int(inst_np.get(k, 0))} for k in COURSES],
        },
        "totals_preserved": {
            "visa_holders_primary_source": int(vis["visa_holders_primary"].sum()),
            "visa_holders_primary_national_table": int(nat["visa_holders_primary"].sum()),
            "visa_holders_primary_state_table": int(st["visa_holders_primary"].sum()),
            "visa_grants_primary_groups": int(groups_unique["group_visa_grants_primary"].sum()),
            "visa_grants_primary_national_table": int(nat["visa_grants_primary"].sum()),
            "apprentice_completions_source": int(ncv["apprentice_completions"].sum()),
            "apprentice_completions_national_table": int(nat["apprentice_completions"].sum()),
            "apprentice_completions_groups": int(groups_unique["group_apprentice_completions"].sum()),
            f"uni_completions_{uni_year}_source": float(uni_by_course.sum()),
            f"uni_completions_{uni_year}_groups": float(groups_unique["group_uni_completions"].sum()),
        },
    }
    (HERE / "join_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))


if __name__ == "__main__":
    main()
