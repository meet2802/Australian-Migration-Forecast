"""Named sectors: plain-English groups of occupations, such as 'Aged and disability care' or 'Tech and IT', with the
main industry each one works in shown alongside.

Decided on 4 October 2026: the dashboard's sectors are groups of occupations (ANZSCO unit groups), not industries,
and their names should make sense to someone with no economics background. Industries stay available alongside.

Run from the Migration folder:  python3 analysis/build_named_sector_tables.py
(Run build_occupation_table.py, build_sector_tables.py, build_osca_tables.py and build_osca_classification_tables.py
first.)

Rules (our choices, written down so they can be checked and changed):
  1. Every ANZSCO unit group sits in exactly one sector (SECTORS below), so the sectors add up to all jobs.
     Borderline jobs go where a non-specialist would look for them first; when that is unclear, they follow the
     industry most of their workers are in (2021 Census, see rule 4).
  2. Comparison groups (comparison_groups.csv) stay inside one sector, so training and visa comparisons are never
     split. One exception: G311 (agricultural, medical and science technicians) is shared between Farming, Other
     health workers and Science, and its group-level figures are shared by May 2025 employment.
  3. 'Not further defined' (nfd) rows, such as 'ICT Professionals nfd', are shared across sectors in proportion to
     May 2025 employment in the unit groups below them.
  4. Industry mix: each occupation's 2021 Census industry shares (JSA OSCA data, moved onto ANZSCO with our crosswalk
     weights), weighted by May 2025 employment. An estimate. Small cells the source does not publish are shown as
     'Not published (small numbers)'.

Outputs:
  analysis/named_sectors.csv                   the sector list: plain names, group, what each includes
  analysis/named_sector_occupations.csv        which occupations make up each sector (shares for nfd rows)
  analysis/named_sector_summary_national.csv   jobs, growth, shortages, workers needed, training, visas, industry
  analysis/named_sector_summary_state.csv      jobs, shortages, job ads, apprentices and visas by state
  analysis/named_sector_industry_mix.csv       estimated share of each sector's workers in each industry
  analysis/named_sector_checks.json
"""
import json
import re

import numpy as np
import pandas as pd

from _common import DIVISIONS, HERE, INDUSTRY_PLAIN, STATES, TIDY, dictionary_rows, log_rows, update_dictionary, write_table

CODE = "unit_group_code"
HC, ED, BT, FM, TS, SB = ("Health and care", "Education, community and safety", "Building, trades and engineering",
                          "Farms, mines and factories", "Tech and science", "Services and business")

# sector_id, name, short name, group, what it includes (plain words), note, ANZSCO unit groups
SECTORS = [
    ("nurses", "Nurses and midwives", "Nurses & midwives", HC,
     "Registered and enrolled nurses, midwives, and nurse managers and educators",
     "Assistants in nursing and personal care workers are in Aged and disability care",
     "2541 2542 2543 2544 4114"),
    ("doctors", "Doctors", "Doctors", HC,
     "GPs, hospital doctors, specialists, surgeons, anaesthetists and psychiatrists", "",
     "2531 2532 2533 2534 2535 2539"),
    ("other_health", "Other health workers", "Other health", HC,
     "Physiotherapists, pharmacists, dentists, psychologists, paramedics, radiographers, occupational therapists, "
     "medical lab scientists and medical technicians",
     "Workplace health and safety advisers are in Business, finance and law, because few of them work in health care",
     "1342 2346 2511 2512 2514 2515 2519 2521 2522 2523 2524 2525 2526 2527 2723 3112 4111 4112 4115 4116 4232"),
    ("aged_disability", "Aged and disability care", "Aged & disability care", HC,
     "Aged and disability carers, personal care workers and assistants in nursing",
     "Personal care workers in hospitals are included too, because the data does not separate them",
     "4113 4231 4233"),
    ("child_care", "Child care", "Child care", HC,
     "Child care workers (educators) and child care centre managers",
     "Early childhood teachers are in Teaching and education, because teacher training data is not split by level",
     "1341 4211"),
    ("teaching", "Teaching and education", "Teaching", ED,
     "School and early childhood teachers, university and TAFE teachers, teacher aides, principals and workplace "
     "trainers", "", "1343 1344 2233 2411 2412 2413 2414 2415 2421 2422 2491 2492 2493 4221"),
    ("community", "Community and social services", "Community services", ED,
     "Social workers, counsellors, welfare and youth workers, interpreters and translators, and ministers of "
     "religion", "", "2721 2722 2724 2725 2726 4117 4234"),
    ("police_security", "Police, fire and security", "Police, fire & security", ED,
     "Police, security officers, firefighters and prison officers, plus a small number of defence force members",
     "Paramedics are in Other health workers. Full-time defence force members are not counted, because the ABS "
     "Labour Force Survey behind the job numbers leaves them out",
     "1391 1392 4411 4412 4413 4421 4422"),
    ("construction", "Building and construction", "Construction", BT,
     "Carpenters, electricians, plumbers, bricklayers, painters, plasterers, tilers, labourers, earthmoving and crane "
     "operators, construction managers, architects, surveyors and town planners",
     "Electricians, air-conditioning mechanics and electronics trades workers are here, because construction "
     "employs more of them than any other industry",
     "1331 2321 2322 2326 3121 3126 3311 3312 3321 3322 3331 3332 3333 3334 3341 3411 3421 3422 3423 7121 7212 "
     "8211 8212 8213 8214 8215 8216 8217 8219"),
    ("mechanics_metal", "Mechanics and metal trades", "Mechanics & metal trades", BT,
     "Motor mechanics, auto electricians, welders, metal fitters and machinists, panelbeaters, vehicle painters and "
     "aircraft maintenance engineers", "",
     "3211 3212 3221 3222 3223 3231 3232 3233 3234 3241 3242 3243 8994"),
    ("engineering", "Engineering", "Engineering", BT,
     "Civil, electrical, mechanical, chemical and other engineers, engineering managers, draftspersons and "
     "technicians", "Mining engineers are in Mining",
     "1332 2331 2332 2333 2334 2335 2339 3122 3123 3124 3125 3129"),
    ("farming", "Farming, gardening and animals", "Farming & gardening", FM,
     "Farmers, farm and orchard workers, shearers, gardeners, greenkeepers, nursery workers, florists, pest "
     "controllers, vets, vet nurses and animal carers",
     "Gardeners, florists and pest controllers are here because the job and training data group them with farm "
     "and garden work",
     "1211 1212 1213 1214 1215 1216 1217 2347 3111 3113 3431 3611 3612 3613 3621 3622 3623 3624 3625 3626 3627 "
     "3631 3632 3633 7211 8411 8412 8413 8414 8415 8416 8419 8421 8422 8423 8424 8431 8432 8433 8434 8439 8992"),
    ("mining", "Mining", "Mining", FM,
     "Miners and drillers, mining engineers, geologists, and gas, oil and power plant operators", "",
     "2336 2344 3992 7122"),
    ("manufacturing", "Manufacturing and factory work", "Manufacturing", FM,
     "Factory and machine workers, packers, assemblers, production managers, printers, cabinetmakers, boat builders "
     "and jewellers", "",
     "1334 1335 3921 3922 3923 3931 3932 3933 3941 3942 3991 3994 3996 3999 7111 7112 7113 7114 7115 7116 7117 "
     "7119 7123 7129 8311 8312 8313 8321 8322 8391 8392 8393 8394 8399 8995"),
    ("tech", "Tech and IT", "Tech & IT", TS,
     "Software developers, IT support, network and cyber security specialists, IT managers, IT sales and training, "
     "and telecommunications workers", "",
     "1351 2232 2252 2611 2612 2613 2621 2631 2632 2633 3131 3132 3424"),
    ("science", "Science", "Science", TS,
     "Chemists, environmental scientists, biologists, agricultural scientists, lab technicians and research "
     "managers", "Medical lab scientists are in Other health workers; geologists are in Mining",
     "1325 2341 2342 2343 2345 2349 3114"),
    ("hospitality", "Hospitality and food", "Hospitality & food", SB,
     "Chefs, cooks, bakers, butchers, waiters, baristas, bar staff, kitchenhands, and cafe, hotel and club managers",
     "", "1411 1412 1413 1414 1419 3511 3512 3513 3514 4311 4312 4313 4314 4315 4319 8511 8512 8513"),
    ("transport", "Transport and logistics", "Transport", SB,
     "Truck, bus, delivery, taxi and train drivers, pilots, flight attendants, couriers, forklift drivers, warehouse "
     "workers and logistics managers", "",
     "1336 1494 2311 2312 4517 5612 5614 5912 7213 7219 7311 7312 7313 7321 7331 7411 8911"),
    ("retail", "Retail and sales", "Retail & sales", SB,
     "Shop assistants, checkout operators, shelf fillers, retail managers, sales representatives, real estate agents "
     "and wholesalers", "",
     "1333 1421 2254 6111 6112 6113 6121 6211 6212 6213 6214 6215 6216 6217 6219 6311 6391 6392 6393 6394 6395 "
     "6399 8912"),
    ("business", "Business, finance and law", "Business, finance & law", SB,
     "Chief executives and general managers; finance, HR, sales, marketing, bank and facilities managers; "
     "accountants, financial advisers, lawyers and legal staff; consultants, policy analysts and workplace safety "
     "advisers", "Managers of shops, building sites, IT, schools and other specialist areas are in those sectors",
     "1111 1112 1113 1311 1321 1322 1323 1324 1399 1499 2211 2212 2221 2222 2223 2231 2241 2243 2244 2245 2247 "
     "2249 2251 2253 2513 2711 2712 2713 5991 5992"),
    ("office", "Office and admin", "Office & admin", SB,
     "Clerks, receptionists, bookkeepers, payroll and bank workers, personal assistants, office managers and call "
     "centre staff", "",
     "1492 5110 5111 5121 5122 5211 5212 5311 5321 5411 5412 5421 5511 5512 5513 5521 5522 5523 5611 5613 5615 "
     "5616 5619 5911 5993 5994 5995 5996 5999"),
    ("arts_media", "Arts, design and media", "Arts & media", SB,
     "Actors, musicians, artists, photographers, designers, journalists, writers, librarians and museum staff", "",
     "2111 2112 2113 2114 2121 2122 2123 2124 2242 2246 2323 2324 2325 3993 3995 5997"),
    ("personal_services", "Sport, travel and personal services", "Sport & personal services", SB,
     "Hairdressers, beauty therapists, fitness instructors, sports coaches, travel agents, tour guides, event "
     "organisers and funeral workers", "",
     "1491 1493 3911 4511 4512 4513 4514 4515 4516 4518 4521 4522 4523 4524"),
    ("cleaning_labouring", "Cleaning and other labouring", "Cleaning & labouring", SB,
     "Cleaners, housekeepers, laundry workers, car detailers, handypersons, caretakers and other labourers", "",
     "8111 8112 8113 8114 8115 8116 8991 8993 8996 8997 8999"),
]
NOT_RECORDED = ("not_recorded", "Occupation not recorded (visa data only)")
ALL = ("all", "All jobs")
SHORT_STATE = {"Shortage", "Regional shortage", "Metropolitan shortage"}
NOT_PUBLISHED = "Not published (small numbers)"
S_PROJ = "JSA, Employment projections May 2025 to May 2035, Table 6"
S_OSL = "JSA, 2025 Occupation Shortage List (unit group, ANZSCO 2022)"
S_HA = "Home Affairs, BP0014 temporary resident (skilled) visas (subclass 482 and 457)"
S_IVI = "JSA, Internet Vacancy Index, 4-digit occupations by state"
S_NCV = "NCVER, Apprentices and trainees (contracts of training)"
S_MIX = ("JSA, OSCA occupation data, 2021 Census (industry shares); ABS OSCA correspondence with our crosswalk weights "
         "(anzsco_osca_unit_group_crosswalk.csv)")
S_OCC = "analysis/occupation_skills_national.csv (see its dictionary entries for sources)"
P, D, E, OD = ("Projection (JSA, trend-based, not a forecast)", "Derived (our calculation)",
               "Estimate (our model, see join_checks.json)", "Official data (Home Affairs)")


def sector_frame():
    rows = []
    for i, (sid, name, short, group, inc, note, codes) in enumerate(SECTORS, start=1):
        rows.append({"sector_order": i, "sector_id": sid, "sector_name": name, "short_name": short,
                     "sector_group": group, "includes": inc, "note": note, "unit_group_codes": codes})
    return pd.DataFrame(rows)


def weights(nat):
    """Each occupation row's share in each sector: 1 for assigned unit groups, employment shares for nfd rows."""
    assign = {}
    for sid, *_, codes in SECTORS:
        for c in codes.split():
            assert c not in assign, f"{c} is listed in two sectors"
            assign[c] = sid
    occ = nat[nat[CODE].str.fullmatch(r"\d{4}")]
    named = occ[~occ["not_further_defined"]]
    missing, extra = sorted(set(named[CODE]) - set(assign)), sorted(set(assign) - set(named[CODE]))
    assert not missing and not extra, f"unassigned: {missing}; not in the occupation table: {extra}"
    rows = [{CODE: c, "sector_id": assign[c], "share": 1.0, "assignment": "Assigned"} for c in named[CODE]]
    emp = named.set_index(CODE)["employed_may2025"].fillna(0)
    for c in occ.loc[occ["not_further_defined"], CODE]:
        kids = [k for k in named[CODE] if k.startswith(c.rstrip("0"))]
        assert kids, f"no unit groups below {c}"
        e = emp.reindex(kids)
        w = e / e.sum() if e.sum() > 0 else pd.Series(1 / len(kids), index=kids)
        for s, v in w.groupby([assign[k] for k in kids]).sum().items():
            if v > 0:
                rows.append({CODE: c, "sector_id": s, "share": float(v), "assignment": "Shared by employment (nfd)"})
    return pd.DataFrame(rows)


def group_shares(nat, w):
    """Share of each comparison group in each sector, by May 2025 employment (equal member shares if none)."""
    m = w.merge(nat[[CODE, "comparison_group", "employed_may2025"]], on=CODE)
    m["e"] = m["employed_may2025"].fillna(0) * m["share"]
    g = m.groupby(["comparison_group", "sector_id"]).agg(e=("e", "sum"), s=("share", "sum")).reset_index()
    members = m.groupby("comparison_group")[CODE].nunique()
    tot = g.groupby("comparison_group")["e"].transform("sum")
    g["gshare"] = np.where(tot > 0, g["e"] / tot.where(tot > 0), g["s"] / g["comparison_group"].map(members))
    return g[["comparison_group", "sector_id", "gshare"]]


def industry_mix(nat, w, divisions):
    """Estimated share of each occupation's and each sector's workers in each industry (2021 Census pattern)."""
    cw = pd.read_csv(HERE / "anzsco_osca_unit_group_crosswalk.csv",
                     dtype={"anzsco_unit_group": str, "osca_unit_group": str})
    ind = pd.read_csv(TIDY / "jsa_osca_census2021_industry_shares.csv", dtype={"osca_code": str})
    ind = ind[ind["osca_level"].eq("Unit group (4-digit)")]
    m = cw.merge(ind[["osca_code", "industry", "share_pct"]], left_on="osca_unit_group", right_on="osca_code")
    by_key = {_key(v): v for v in divisions.values()}
    m["industry"] = m["industry"].map(lambda s: by_key.get(_key(s), s))
    m["f"] = m["share_of_anzsco_unit_group_pct"] / 100 * m["share_pct"].fillna(0) / 100
    occ = m.groupby(["anzsco_unit_group", "industry"])["f"].sum().unstack(fill_value=0)
    names = list(divisions.values())
    assert set(occ.columns) == set(names), set(occ.columns) ^ set(names)
    occ = occ[names]
    occ[NOT_PUBLISHED] = (1 - occ.sum(axis=1)).clip(lower=0)
    occ.index.name = CODE
    # sector: employment-weighted average over its unit groups (nfd rows have no mix and are left out here)
    e = w.merge(nat[[CODE, "employed_may2025"]], on=CODE)
    e = e[e["assignment"].eq("Assigned") & e[CODE].isin(occ.index)]
    e["e"] = e["employed_may2025"].fillna(0) * e["share"]
    sec = occ.reindex(e[CODE]).mul(e["e"].values, axis=0).groupby(e["sector_id"].values).sum()
    covered = e.groupby("sector_id")["e"].sum()
    sec = sec.div(sec.sum(axis=1), axis=0)
    return occ, sec, covered


def _key(name):
    """Match industry titles that differ only in spacing or case ('Health Care' vs 'Healthcare')."""
    return re.sub(r"[^a-z]", "", str(name).lower())


def add_up(df, w, cols, by):
    m = w.merge(df, on=CODE)
    for c in cols:
        m[c] = m[c] * m["share"]
    return m.groupby(by)[cols].sum(min_count=1)


def national(nat, w, gsh, secmix, divisions, ind_nat):
    x = nat.copy()
    e = x["employed_may2025"]
    x["e_short"] = e.where(x["in_shortage_2025"], 0)
    x["e_assessed"] = e.where(x["shortage_now"].ne("Not assessed"), 0)
    x["e_short_faster"] = e.where(x["outlook_group"].eq("Short now, faster than average growth"), 0)
    x["e_age_known"] = e.where(x["share_aged_55_plus_pct"].notna())
    x["e_age55"] = e * x["share_aged_55_plus_pct"] / 100
    unit = ~x["not_further_defined"] & x[CODE].str.fullmatch(r"\d{4}")
    x["n_occ"] = unit.astype(int)
    x["n_short"] = (unit & x["in_shortage_2025"]).astype(int)
    row_cols = ["n_occ", "n_short", "employed_may2025", "projected_may2030", "projected_may2035",
                "projected_growth_5y", "retirements_per_year_est", "career_moves_net_loss_per_year_est",
                "e_short", "e_assessed", "e_short_faster", "e_age_known", "e_age55", "job_ads_latest",
                "job_ads_year_ago", "apprentice_commencements", "apprentice_completions", "visa_grants_primary",
                "visa_holders_primary", "visa_holders_primary_year_ago", "visa_holders_incl_family"]
    for c in row_cols:
        x[c] = pd.to_numeric(x[c], errors="coerce").astype(float)
    s = add_up(x, w, row_cols, "sector_id")

    g = x.drop_duplicates("comparison_group")[["comparison_group", "group_new_workers_needed_per_year_est",
                                                "group_local_training_effective"]].copy()
    for c in g.columns[1:]:
        g[c] = pd.to_numeric(g[c], errors="coerce").astype(float)
    g["measured"] = g["group_local_training_effective"].notna()
    g["need_measured"] = g["group_new_workers_needed_per_year_est"].where(g["measured"], 0)
    gg = gsh.merge(g, on="comparison_group")
    for c in ["group_new_workers_needed_per_year_est", "group_local_training_effective", "need_measured"]:
        gg[c] = gg[c] * gg["gshare"]
    s = s.join(gg.groupby("sector_id")[["group_new_workers_needed_per_year_est", "group_local_training_effective",
                                         "need_measured"]].sum(min_count=1))

    # 'All jobs' and the visa rows with no occupation recorded
    tot = pd.concat([x[row_cols].sum(min_count=1), g[["group_new_workers_needed_per_year_est",
                                                       "group_local_training_effective", "need_measured"]].sum()])
    nr = x[~x[CODE].str.fullmatch(r"\d{4}")]
    vis = ["visa_grants_primary", "visa_holders_primary", "visa_holders_primary_year_ago", "visa_holders_incl_family"]
    s.loc[NOT_RECORDED[0], vis] = nr[vis].sum().values
    s.loc[ALL[0]] = tot

    out = pd.DataFrame(index=s.index)
    out["occupations"] = s["n_occ"]
    out["occupations_in_shortage"] = s["n_short"]
    emp = s["employed_may2025"]
    out["employed_may2025"] = emp
    out["share_of_all_jobs_pct"] = 100 * emp / emp[ALL[0]]
    out["projected_may2030"] = s["projected_may2030"]
    out["projected_may2035"] = s["projected_may2035"]
    out["projected_growth_5y"] = s["projected_growth_5y"]
    out["projected_growth_5y_pct"] = 100 * s["projected_growth_5y"] / emp
    out["projected_growth_10y"] = s["projected_may2035"] - emp
    out["projected_growth_10y_pct"] = 100 * out["projected_growth_10y"] / emp
    all_rate = round(float(out.loc[ALL[0], "projected_growth_5y_pct"]), 1)
    out["growth_vs_all_jobs_pp"] = out["projected_growth_5y_pct"].round(1) - all_rate
    out["projected_growth_per_year"] = s["projected_growth_5y"] / 5
    out["retirements_per_year_est"] = s["retirements_per_year_est"]
    out["career_moves_net_loss_per_year_est"] = s["career_moves_net_loss_per_year_est"]
    need = s["group_new_workers_needed_per_year_est"]
    out["new_workers_needed_per_year_est"] = need
    out["jobs_in_shortage_pct"] = 100 * s["e_short"] / emp
    out["jobs_short_and_growing_faster_pct"] = 100 * s["e_short_faster"] / emp
    out["jobs_assessed_pct"] = 100 * s["e_assessed"] / emp
    out["share_aged_55_plus_pct"] = 100 * s["e_age55"] / s["e_age_known"]
    out["job_ads_latest"] = s["job_ads_latest"]
    out["job_ads_year_ago"] = s["job_ads_year_ago"]
    out["job_ads_change_12m_pct"] = 100 * (s["job_ads_latest"] / s["job_ads_year_ago"] - 1)
    out["apprentice_commencements"] = s["apprentice_commencements"]
    out["apprentice_completions"] = s["apprentice_completions"]
    out["local_training_effective"] = s["group_local_training_effective"]
    out["need_where_training_measured"] = s["need_measured"]
    out["local_training_per_100_needed"] = (100 * s["group_local_training_effective"]
                                            / s["need_measured"].where(s["need_measured"] > 0))
    out["training_measured_share_of_need_pct"] = 100 * s["need_measured"] / need.where(need > 0)
    for c in vis:
        out[c] = s[c]
    out["visa_grants_per_1000_workers"] = 1000 * s["visa_grants_primary"] / emp
    out["visa_holders_per_1000_workers"] = 1000 * s["visa_holders_primary"] / emp
    out["visa_grants_per_100_needed"] = 100 * s["visa_grants_primary"] / need.where(need > 0)

    # industry alongside
    top = secmix.drop(columns=NOT_PUBLISHED)
    first = top.idxmax(axis=1)
    second = top.apply(lambda r: r.drop(r.idxmax()).idxmax(), axis=1)
    code_of = {v: k for k, v in divisions.items()}
    out["main_industry"] = first
    out["main_industry_plain_name"] = first.map(code_of).map(INDUSTRY_PLAIN)
    out["main_industry_share_pct"] = pd.Series({k: 100 * secmix.loc[k, v] for k, v in first.items()})
    out["second_industry"] = second
    out["second_industry_plain_name"] = second.map(code_of).map(INDUSTRY_PLAIN)
    out["second_industry_share_pct"] = pd.Series({k: 100 * secmix.loc[k, v] for k, v in second.items()})
    ind = ind_nat.set_index("anzsic_division")
    letters = first.map(code_of)
    out["main_industry_employed_may2025"] = letters.map(ind["employed_may2025"])
    out["main_industry_growth_5y_pct"] = letters.map(ind["projected_growth_5y_pct"])
    out["main_industry_visa_grants_primary"] = letters.map(ind["visa_grants_primary"])
    return out, all_rate


def state_table(w, sec):
    st = pd.read_csv(HERE / "occupation_skills_state.csv", dtype={CODE: str})
    st["e"] = st["employed_state_est"]
    st["e_short"] = st["e"].where(st["osl_2025_state_rating"].isin(SHORT_STATE), 0)
    st["e_assessed"] = st["e"].where(st["osl_2025_state_rating"].ne("Not assessed"), 0)
    cols = ["e", "e_short", "e_assessed", "job_ads_latest", "job_ads_year_ago", "apprentice_commencements",
            "apprentice_completions", "visa_grants_primary", "visa_holders_primary", "visa_holders_primary_year_ago"]
    for c in cols:
        st[c] = pd.to_numeric(st[c], errors="coerce").astype(float)
    s = add_up(st, w, cols, ["sector_id", "state"]).reset_index()
    nr = st[~st[CODE].str.fullmatch(r"\d{4}")]
    vis = ["visa_grants_primary", "visa_holders_primary", "visa_holders_primary_year_ago"]
    nr = nr.groupby("state")[vis].sum().reset_index().assign(sector_id=NOT_RECORDED[0])
    s = pd.concat([s, nr], ignore_index=True)
    out = s[["sector_id", "state"]].copy()
    out["employed_state_est"] = s["e"]
    state_tot = s.groupby("state")["e"].transform("sum")
    sector_tot = s.groupby("sector_id")["e"].transform("sum")
    out["share_of_state_jobs_pct"] = 100 * s["e"] / state_tot.where(state_tot > 0)
    out["share_of_sector_jobs_in_state_pct"] = 100 * s["e"] / sector_tot.where(sector_tot > 0)
    out["jobs_in_state_shortage_pct"] = 100 * s["e_short"] / s["e"].where(s["e"] > 0)
    out["jobs_assessed_pct"] = 100 * s["e_assessed"] / s["e"].where(s["e"] > 0)
    out["job_ads_latest"] = s["job_ads_latest"]
    out["job_ads_year_ago"] = s["job_ads_year_ago"]
    out["job_ads_change_12m_pct"] = 100 * (s["job_ads_latest"] / s["job_ads_year_ago"] - 1)
    out["apprentice_commencements"] = s["apprentice_commencements"]
    out["apprentice_completions"] = s["apprentice_completions"]
    for c in vis:
        out[c] = s[c]
    out["visa_grants_per_1000_workers"] = 1000 * s["visa_grants_primary"] / s["e"].where(s["e"] > 0)
    out = out.merge(sec[["sector_id", "sector_name", "sector_order"]], on="sector_id", how="left")
    out["sector_name"] = out["sector_name"].fillna(NOT_RECORDED[1])
    out["sector_order"] = out["sector_order"].fillna(len(SECTORS) + 1)
    out["state_order"] = out["state"].map({s_: i for i, s_ in enumerate(STATES)}).fillna(len(STATES))
    out = out.sort_values(["sector_order", "state_order"]).drop(columns=["sector_order", "state_order"])
    out = out[out[["employed_state_est"] + vis].fillna(0).ne(0).any(axis=1)]
    lead = ["sector_id", "sector_name", "state"]
    return out[lead + [c for c in out.columns if c not in lead]].reset_index(drop=True)


def rounded(df, ints, one_dp, zero_dp=()):
    df = df.copy()
    for c in ints:
        df[c] = df[c].round().astype("Int64")
    for c in one_dp:
        df[c] = df[c].round(1)
    for c in zero_dp:
        df[c] = df[c].round().astype("Int64")
    return df


def main():
    nat = pd.read_csv(HERE / "occupation_skills_national.csv", dtype={CODE: str})
    log_rows("Read the occupation table", nat, "occupation_skills_national.csv")
    nat["not_further_defined"] = nat["not_further_defined"].astype(str).eq("True")
    nat["in_shortage_2025"] = nat["in_shortage_2025"].astype(str).eq("True")
    ind_nat = pd.read_csv(HERE / "sector_skills_national.csv")
    ind_nat = ind_nat[ind_nat["anzsic_division"].isin(list(DIVISIONS))]
    divisions = DIVISIONS

    sec = sector_frame()
    w = weights(nat)
    log_rows("Assigned unit groups to the 24 job groups (one row per code and job group)", w,
             note="Not further defined codes are shared by employment")
    gsh = group_shares(nat, w)
    occmix, secmix, covered = industry_mix(nat, w, divisions)

    # 1. sector list
    sec["occupations"] = sec["unit_group_codes"].str.split().str.len()
    sectors_out = sec[["sector_id", "sector_name", "short_name", "sector_group", "includes", "note", "occupations",
                       "unit_group_codes"]]

    # 2. occupations in each sector
    top = occmix.drop(columns=NOT_PUBLISHED)
    occ_first = top.idxmax(axis=1).where(top.max(axis=1) > 0)
    occ_share = pd.Series({k: 100 * occmix.loc[k, v] for k, v in occ_first.dropna().items()})
    o = w.merge(nat[[CODE, "occupation", "not_further_defined", "in_jsa_projections", "comparison_group",
                     "employed_may2025"]], on=CODE)
    o = o.merge(sec[["sector_id", "sector_name", "sector_order"]], on="sector_id")
    o["share_of_code_pct"] = (100 * o["share"]).round(1)
    o["employed_may2025_in_sector"] = (o["employed_may2025"] * o["share"]).round().astype("Int64")
    o["main_industry"] = o[CODE].map(occ_first)
    o["main_industry_share_pct"] = o[CODE].map(occ_share).round(1)
    o = o.sort_values(["sector_order", "not_further_defined", CODE]).reset_index(drop=True)
    occ_out = o[["sector_id", "sector_name", CODE, "occupation", "not_further_defined", "in_jsa_projections",
                 "assignment", "share_of_code_pct", "employed_may2025_in_sector", "comparison_group",
                 "main_industry", "main_industry_share_pct"]]

    # 3. national summary
    summ, all_rate = national(nat, w, gsh, secmix, divisions, ind_nat)
    summ = summ.reset_index(names="sector_id")
    names = dict(zip(sec["sector_id"], sec["sector_name"])) | {NOT_RECORDED[0]: NOT_RECORDED[1], ALL[0]: ALL[1]}
    summ.insert(1, "sector_name", summ["sector_id"].map(names))
    shorts = dict(zip(sec["sector_id"], sec["short_name"])) | {NOT_RECORDED[0]: "Not recorded", ALL[0]: "All jobs"}
    summ.insert(2, "short_name", summ["sector_id"].map(shorts))
    summ.insert(3, "sector_group", summ["sector_id"].map(dict(zip(sec["sector_id"], sec["sector_group"]))))
    summ.insert(4, "row_type", np.select([summ["sector_id"].eq(ALL[0]), summ["sector_id"].eq(NOT_RECORDED[0])],
                                         ["Total", "Visa data only"], "Named sector"))
    order = {s_: i for i, s_ in enumerate(list(sec["sector_id"]) + [NOT_RECORDED[0], ALL[0]])}
    summ = summ.sort_values("sector_id", key=lambda c: c.map(order)).reset_index(drop=True)
    ints = ["occupations", "occupations_in_shortage", "employed_may2025", "projected_may2030", "projected_may2035",
            "projected_growth_5y", "projected_growth_10y", "projected_growth_per_year", "retirements_per_year_est",
            "career_moves_net_loss_per_year_est", "new_workers_needed_per_year_est", "job_ads_latest",
            "job_ads_year_ago", "apprentice_commencements", "apprentice_completions", "local_training_effective",
            "need_where_training_measured", "visa_grants_primary", "visa_holders_primary",
            "visa_holders_primary_year_ago", "visa_holders_incl_family", "main_industry_employed_may2025",
            "main_industry_visa_grants_primary"]
    one = ["share_of_all_jobs_pct", "projected_growth_5y_pct", "projected_growth_10y_pct", "growth_vs_all_jobs_pp",
           "jobs_in_shortage_pct", "jobs_short_and_growing_faster_pct", "jobs_assessed_pct", "share_aged_55_plus_pct",
           "job_ads_change_12m_pct", "visa_grants_per_1000_workers", "visa_holders_per_1000_workers",
           "main_industry_share_pct", "second_industry_share_pct", "main_industry_growth_5y_pct"]
    zero = ["local_training_per_100_needed", "training_measured_share_of_need_pct", "visa_grants_per_100_needed"]
    summ = rounded(summ, ints, one, zero)

    # 4. state summary
    state = state_table(w, sec)
    state = rounded(state, ["employed_state_est", "job_ads_latest", "job_ads_year_ago", "apprentice_commencements",
                            "apprentice_completions", "visa_grants_primary", "visa_holders_primary",
                            "visa_holders_primary_year_ago"],
                    ["share_of_state_jobs_pct", "share_of_sector_jobs_in_state_pct", "jobs_in_state_shortage_pct",
                     "jobs_assessed_pct", "job_ads_change_12m_pct", "visa_grants_per_1000_workers"])

    # 5. industry mix (long)
    sec_emp = summ.set_index("sector_id")["employed_may2025"].astype(float)
    mix = secmix.stack().rename("share").reset_index().rename(columns={"level_0": "sector_id",
                                                                       "level_1": "industry"})
    mix.columns = ["sector_id", "industry", "share"]
    code_of = {v: k for k, v in divisions.items()}
    mix["anzsic_division"] = mix["industry"].map(code_of).fillna("")
    mix["industry_plain_name"] = mix["anzsic_division"].map(INDUSTRY_PLAIN).fillna(mix["industry"])
    mix["share_of_sector_pct"] = (100 * mix["share"]).round(1)
    mix["employed_est"] = (mix["share"] * mix["sector_id"].map(sec_emp))
    ind_tot = mix[mix["anzsic_division"].ne("")].groupby("industry")["employed_est"].transform("sum")
    mix["share_of_industry_pct"] = (100 * mix["employed_est"] / ind_tot).round(1)
    mix["employed_est"] = mix["employed_est"].round().astype("Int64")
    mix = mix.merge(sec[["sector_id", "sector_name", "sector_order"]], on="sector_id")
    dorder = {c: i for i, c in enumerate(list(INDUSTRY_PLAIN) + [""])}
    mix = mix.sort_values(["sector_order", "anzsic_division"], key=lambda c: c.map(dorder) if c.name ==
                          "anzsic_division" else c).reset_index(drop=True)
    mix_out = mix[["sector_id", "sector_name", "anzsic_division", "industry", "industry_plain_name",
                   "share_of_sector_pct", "employed_est", "share_of_industry_pct"]]

    outs = {HERE / "named_sectors.csv": sectors_out, HERE / "named_sector_occupations.csv": occ_out,
            HERE / "named_sector_summary_national.csv": summ, HERE / "named_sector_summary_state.csv": state,
            HERE / "named_sector_industry_mix.csv": mix_out}
    written = {p.name: write_table(d, p).name for p, d in outs.items()}

    # checks
    named = summ[summ["row_type"].eq("Named sector")]
    total = summ[summ["row_type"].eq("Total")].iloc[0]
    nfd = w[w["assignment"].ne("Assigned")].merge(nat[[CODE, "occupation", "employed_may2025"]], on=CODE)
    nfd_big = (nfd.assign(e=nfd["employed_may2025"] * nfd["share"]).groupby([CODE, "occupation"])
               .apply(lambda d: {s_: round(100 * v, 1) for s_, v in zip(d["sector_id"], d["share"])},
                      include_groups=False))
    nfd_emp = nat.loc[nat["not_further_defined"], ["occupation", "employed_may2025"]].set_index("occupation")
    occ_emp = nat[nat[CODE].str.fullmatch(r"\d{4}") & ~nat["not_further_defined"]]
    titles = list(divisions.values())
    norm = occmix[titles].div(occmix[titles].sum(axis=1).where(lambda s: s > 0), axis=0)
    est = norm.mul(occ_emp.set_index(CODE)["employed_may2025"].reindex(norm.index).fillna(0), axis=0).sum()
    jsa = ind_nat.set_index("industry")["employed_may2025"]
    named_groups = set(pd.read_csv(HERE / "comparison_groups.csv")["comparison_group"])
    spanning = gsh[gsh["comparison_group"].isin(named_groups)].groupby("comparison_group")["sector_id"].nunique()
    assert spanning[spanning > 1].index.tolist() == ["G311"], spanning[spanning > 1]
    checks = {
        "files_written": written,
        "named_sectors": int(len(sec)),
        "sector_groups": sec.groupby("sector_group", sort=False)["sector_name"].apply(list).to_dict(),
        "unit_groups_assigned (each exactly once)": int(w["assignment"].eq("Assigned").sum()),
        "nfd_rows_shared": int(nfd[CODE].nunique()),
        "nfd_employment_shared": int(nfd_emp["employed_may2025"].sum()),
        "largest_nfd_rows_and_their_sector_shares_pct": {
            f"{c} {t}": v for (c, t), v in nfd_big.items()
            if nat.loc[nat[CODE].eq(c), "employed_may2025"].iloc[0] >= 5000},
        "comparison_groups_split_across_sectors (nfd rows aside)": spanning[spanning > 1].index.tolist(),
        "employment_sectors_vs_all_jobs": [int(named["employed_may2025"].sum()), int(total["employed_may2025"])],
        "need_sectors_vs_all_jobs": [int(named["new_workers_needed_per_year_est"].sum()),
                                     int(total["new_workers_needed_per_year_est"])],
        "visa_grants_sectors_plus_not_recorded_vs_total": [
            int(summ.loc[summ["row_type"].ne("Total"), "visa_grants_primary"].sum()), int(total["visa_grants_primary"])],
        "state_employment_vs_national": [int(state["employed_state_est"].sum()), int(total["employed_may2025"])],
        "state_visa_grants_vs_national": [int(state["visa_grants_primary"].sum()), int(total["visa_grants_primary"])],
        "all_jobs_growth_5y_pct": all_rate,
        "industry_mix_employment_covered_pct (unit groups with a crosswalk, excludes nfd)": round(
            100 * float(covered.sum()) / float(total["employed_may2025"]), 1),
        "industry_mix_not_published_share_pct (all sectors)": round(
            100 * float((secmix[NOT_PUBLISHED] * covered.reindex(secmix.index)).sum() / covered.sum()), 1),
        "industry_totals_our_estimate_vs_jsa_may2025_pct_diff": {
            k: round(100 * (est[k] / jsa[k] - 1), 1) for k in divisions.values()},
        "sectors": named.set_index("sector_name")[["employed_may2025", "projected_growth_5y_pct",
                                                    "jobs_in_shortage_pct", "new_workers_needed_per_year_est",
                                                    "visa_grants_primary", "main_industry",
                                                    "main_industry_share_pct"]].to_dict("index"),
        "rows": {p.name: len(d) for p, d in outs.items()},
    }
    (HERE / "named_sector_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))

    C = "Classification"
    m = {
        "sector_id": ("Short id of the named sector ('all' = all jobs, 'not_recorded' = visa records with no "
                      "occupation)", "This project", "", C),
        "sector_name": ("Plain-English sector name for public-facing pages", "This project", "", C),
        "short_name": ("Shorter label for charts", "This project", "", C),
        "sector_group": ("One of six headings that group the sectors", "This project", "", C),
        "includes": ("The main jobs in the sector, in plain words", "This project", "", C),
        "note": ("Where a job someone might look for here sits instead, or why a borderline job is here",
                 "This project", "", C),
        "occupations": ("Number of ANZSCO unit groups in the sector (nfd rows not counted)", "This project", "", C),
        "unit_group_codes": ("ANZSCO unit groups in the sector, space-separated", "ABS ANZSCO; this project", "", C),
        CODE: ("ANZSCO 4-digit unit group (or nfd row), as in occupation_skills_national.csv", "ABS ANZSCO", "", C),
        "occupation": ("Unit group title", S_OCC, "", C),
        "not_further_defined": ("True for 'nfd' rows (workers coded only to a broader group)", S_PROJ, "", C),
        "in_jsa_projections": ("True if JSA projects this unit group", S_PROJ, "", C),
        "assignment": ("'Assigned' (the unit group sits wholly in this sector) or 'Shared by employment (nfd)'",
                       "This project", "", C),
        "share_of_code_pct": ("Share of the row's figures counted in this sector: 100 for assigned unit groups; for "
                              "nfd rows, the sector's share of May 2025 employment in the unit groups below",
                              f"This project; {S_PROJ}", "May 2025", D),
        "employed_may2025_in_sector": ("Employed persons counted in this sector (employed_may2025 x share)", S_PROJ,
                                       "May 2025", D),
        "comparison_group": ("Group used to compare training and visa supply (see comparison_groups.csv)",
                             "This project", "", C),
        "main_industry": ("Industry (ANZSIC division) that employs the most of these workers", S_MIX,
                          "Census 2021 industry pattern", "Estimate (our crosswalk)"),
        "main_industry_share_pct": ("Estimated share of these workers in the main industry, %", S_MIX,
                                    "Census 2021 industry pattern", "Estimate (our crosswalk)"),
        "row_type": ("Named sector, Visa data only (no occupation recorded) or Total", "This project", "", C),
        "occupations_in_shortage": ("Unit groups rated shortage, regional shortage or metro shortage in 2025", S_OSL,
                                    "2025", D),
        "employed_may2025": ("Employed persons, May 2025 (JSA projection base)", S_PROJ, "May 2025",
                             "Official estimate (JSA), summed by us"),
        "share_of_all_jobs_pct": ("Share of all jobs, %", S_PROJ, "May 2025", D),
        "projected_may2030": ("Projected employment, May 2030", S_PROJ, "May 2030", P),
        "projected_may2035": ("Projected employment, May 2035", S_PROJ, "May 2035", P),
        "projected_growth_5y": ("Projected net change, May 2025 to May 2030 (excludes replacement demand)", S_PROJ,
                                "2025 to 2030", P),
        "projected_growth_5y_pct": ("Projected change, May 2025 to May 2030, %", S_PROJ, "2025 to 2030", P),
        "projected_growth_10y": ("Projected net change, May 2025 to May 2035", S_PROJ, "2025 to 2035", P),
        "projected_growth_10y_pct": ("Projected change, May 2025 to May 2035, %", S_PROJ, "2025 to 2035", P),
        "growth_vs_all_jobs_pp": (f"projected_growth_5y_pct minus growth for all jobs ({all_rate}%), percentage "
                                  "points", S_PROJ, "2025 to 2030", D),
        "projected_growth_per_year": ("projected_growth_5y / 5", S_PROJ, "2025 to 2030", D),
        "retirements_per_year_est": ("Estimated retirements a year (sum of the occupation estimates)", S_OCC, "", E),
        "career_moves_net_loss_per_year_est": ("Estimated net career moves out a year (negative = the sector gains "
                                               "people from other jobs)", S_OCC, "", E),
        "new_workers_needed_per_year_est": ("New workers needed a year: projected growth + retirements + net career "
                                            "moves, netted within each comparison group (not below 0) and added up. "
                                            "So it can differ from the sum of the three columns", S_OCC, "", E),
        "jobs_in_shortage_pct": ("Share of the sector's jobs in occupations rated in shortage nationally (any type), "
                                 "%", f"{S_OSL}; {S_PROJ}", "2025", D),
        "jobs_short_and_growing_faster_pct": ("Share of the sector's jobs in occupations that are short now and "
                                              "projected to grow faster than average (both questions yes), %",
                                              f"{S_OSL}; {S_PROJ}", "2025 to 2030", D),
        "jobs_assessed_pct": ("Share of the jobs in occupations the 2025 shortage list rated (the rest, mostly nfd "
                              "rows, were not assessed), %", f"{S_OSL}; {S_PROJ}", "2025", D),
        "share_aged_55_plus_pct": ("Share of workers aged 55 and over (employment-weighted across the occupations)",
                                   "JSA occupation profiles Table 7 (ABS Census 2021 age profile)", "August 2021", D),
        "job_ads_latest": ("Online job ads, 3-month average", S_IVI, "3 months to August 2026", "Official data (JSA)"),
        "job_ads_year_ago": ("Online job ads, 3-month average, a year earlier", S_IVI, "3 months to August 2025",
                             "Official data (JSA)"),
        "job_ads_change_12m_pct": ("Change in online job ads over 12 months, %", S_IVI, "", D),
        "apprentice_commencements": ("Apprentice and trainee commencements", S_NCV, "12 months to 31 March 2026",
                                     "Official data (NCVER)"),
        "apprentice_completions": ("Apprentice and trainee completions", S_NCV, "12 months to 31 March 2026",
                                   "Official data (NCVER)"),
        "local_training_effective": ("Local training that ends up in the job, a year, for the comparison groups "
                                     "where training is measured (uni completions in mapped courses plus apprentice "
                                     "and trainee completions x retention)", S_OCC, "", E),
        "need_where_training_measured": ("new_workers_needed for the comparison groups where training is measured",
                                         S_OCC, "", E),
        "local_training_per_100_needed": ("local_training_effective per 100 new workers needed, where training is "
                                          "measured. Over 100 does not mean enough: uni completions include "
                                          "overseas students", S_OCC, "", E),
        "training_measured_share_of_need_pct": ("Share of the sector's need in groups where local training is "
                                                "measured. Low = the training ratio covers little of the sector",
                                                S_OCC, "", D),
        "visa_grants_primary": ("Temporary skilled visas granted to main applicants", S_HA, "Financial year 2025-26",
                                OD),
        "visa_holders_primary": ("Main applicants holding a temporary skilled visa", S_HA, "Snapshot 2026-06-30", OD),
        "visa_holders_primary_year_ago": ("Main applicants holding a temporary skilled visa a year earlier", S_HA,
                                          "Snapshot 2025-06-30", OD),
        "visa_holders_incl_family": ("All holders including family members (family members have no nominated job "
                                     "and appear under not_recorded)", S_HA, "Snapshot 2026-06-30", OD),
        "visa_grants_per_1000_workers": ("visa_grants_primary per 1,000 employed", f"{S_HA}; {S_PROJ}", "", D),
        "visa_holders_per_1000_workers": ("visa_holders_primary per 1,000 employed", f"{S_HA}; {S_PROJ}", "", D),
        "visa_grants_per_100_needed": ("visa_grants_primary per 100 new workers needed a year", S_OCC, "", E),
        "main_industry_plain_name": ("Plain-English name of the main industry", "This project", "", C),
        "second_industry": ("Industry that employs the second most of the sector's workers", S_MIX,
                            "Census 2021 industry pattern", "Estimate (our crosswalk)"),
        "second_industry_plain_name": ("Plain-English name of the second industry", "This project", "", C),
        "second_industry_share_pct": ("Estimated share of the sector's workers in the second industry, %", S_MIX,
                                      "Census 2021 industry pattern", "Estimate (our crosswalk)"),
        "main_industry_employed_may2025": ("All workers in the main industry (every occupation), May 2025",
                                           "JSA, Employment projections May 2025 to May 2035 (Table 1)", "May 2025",
                                           "Official estimate (JSA)"),
        "main_industry_growth_5y_pct": ("Projected growth of the main industry, May 2025 to May 2030, %",
                                        "JSA, Employment projections May 2025 to May 2035 (Table 1)", "2025 to 2030",
                                        P),
        "main_industry_visa_grants_primary": ("Temporary skilled visas granted to main applicants sponsored by "
                                              "employers in the main industry",
                                              "Home Affairs, BP0014 temporary resident (skilled) visas, by sponsor "
                                              "industry", "Financial year 2025-26", OD),
        "state": ("State or territory ('Not specified' = visa records with no state)", "", "", C),
        "employed_state_est": ("Estimated workers in the state: national employment (May 2025) x each occupation's "
                               "state share (LFS, February 2026)", S_OCC, "May 2025", D),
        "share_of_state_jobs_pct": ("Sector's share of the state's jobs, %", S_OCC, "May 2025", D),
        "share_of_sector_jobs_in_state_pct": ("State's share of the sector's jobs nationally, %", S_OCC, "May 2025",
                                              D),
        "jobs_in_state_shortage_pct": ("Share of the sector's jobs in the state in occupations rated in shortage in "
                                       "that state (any type), %", f"{S_OSL}; {S_OCC}", "2025", D),
        "anzsic_division": ("ANZSIC 2006 division letter (blank for the not-published remainder)", "ABS ANZSIC", "",
                            C),
        "industry": ("Industry (ANZSIC division) title, or 'Not published (small numbers)'", "ABS ANZSIC", "", C),
        "industry_plain_name": ("Plain-English industry name", "This project", "", C),
        "share_of_sector_pct": ("Estimated share of the sector's workers in the industry, %", S_MIX,
                                "Census 2021 industry pattern", "Estimate (our crosswalk)"),
        "employed_est": ("share_of_sector_pct x the sector's May 2025 employment", f"{S_MIX}; {S_PROJ}", "May 2025",
                         "Estimate (our crosswalk)"),
        "share_of_industry_pct": ("Estimated share of the industry's workers who are in this sector, % (across the "
                                  "named sectors; excludes the not-published remainder)", f"{S_MIX}; {S_PROJ}",
                                  "May 2025", "Estimate (our crosswalk)"),
    }
    rows = []
    for p, d in outs.items():
        rows += dictionary_rows("analysis/" + written[p.name], d, m)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
