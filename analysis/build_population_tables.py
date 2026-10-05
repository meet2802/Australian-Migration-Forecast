"""Population and overseas migration tables: quarterly components by state, rolling years,
NOM by visa group, and the long-run history.

Run from the Migration folder:  python3 analysis/build_population_tables.py

Inputs (Migration folder): 310101.xlsx, 310102.xlsx, 310104.xlsx (ABS National, state and
territory population), HPDC1.xlsx and HPDC7.xlsx (ABS Historical population, 2021),
Time-series-spreadsheets-all.zip (ABS Overseas migration, table set 34070DO004).
Outputs:
  tidy/abs_population_quarterly_by_state.csv       quarterly ERP and components, states + Australia
  tidy/abs_population_components_australia.csv     quarterly births, deaths, NOM arrivals/departures
  tidy/abs_nom_visa_groups_by_state.csv            NOM arrivals and departures by visa group, by FY
  tidy/abs_population_history.csv                  population 1788 onwards, NOM 1860 onwards
  analysis/population_years_by_state.csv           rolling and financial years with rates and shares
  analysis/nom_by_visa_group.csv                   arrivals, departures and net by visa group
  analysis/population_long_run_australia.csv       one row per year: population and NOM, 1860 onwards
  analysis/population_checks.json                  reconciliation checks
Citizenship groups in 34070DO004 are visa/citizenship categories (e.g. NZ citizens), not
nationality; no country-of-birth or nationality breakdown is used.
"""
import io
import json
import re

import numpy as np
import pandas as pd

from _common import (HERE, ROOT, TIDY, STATES, clean_label, dictionary_rows, num, read_abs_timeseries,
                     state_code, update_dictionary, write_table, zip_member)

S_3101 = "ABS, National, state and territory population (3101.0), Mar 2026"
S_HP = "ABS, Historical population, 2021 (HPDC1, HPDC7)"
S_VG = "ABS, Overseas migration 2024-25 (34070DO004)"
D = "Derived (our calculation)"


# ---------------------------------------------------------------- 3101 quarterly
def quarterly_by_state():
    comp = read_abs_timeseries(ROOT / "310102.xlsx")
    parts = comp["series"].str.split(" ; ", expand=True)
    comp["measure"] = parts[0].str.strip()
    comp["state"] = parts[1].map(state_code)
    measure = {"Natural Increase": "natural_increase", "Net Overseas Migration": "nom",
               "Net Interstate Migration": "net_interstate_migration",
               "Change Over Previous Quarter": "growth"}
    comp["measure"] = comp["measure"].map(measure)
    wide = comp.pivot_table(index=["date", "state"], columns="measure", values="value", aggfunc="first")
    erp = read_abs_timeseries(ROOT / "310104.xlsx")
    p = erp["series"].str.split(" ; ", expand=True)
    erp = erp[p[1].str.strip().eq("Persons")].copy()
    erp["state"] = p.loc[erp.index, 2].map(state_code)
    erp = erp.set_index(["date", "state"])["value"].rename("erp")
    q = wide.join(erp, how="outer").reset_index()
    q.loc[q["state"].eq("AUS"), "net_interstate_migration"] = 0.0
    q = q.rename(columns={"date": "quarter"})
    q["quarter"] = pd.to_datetime(q["quarter"]).dt.strftime("%Y-%m")
    cols = ["quarter", "state", "erp", "natural_increase", "nom", "net_interstate_migration", "growth"]
    order = {s: i for i, s in enumerate(STATES + ["AUS"])}
    q = q[cols].sort_values(["quarter", "state"], key=lambda s: s.map(order) if s.name == "state" else s)
    return q.reset_index(drop=True)


def components_australia():
    a = read_abs_timeseries(ROOT / "310101.xlsx")
    a["measure"] = a["series"].str.split(" ; ").str[0].str.strip()
    keep = {"Births": "births", "Deaths": "deaths", "Natural Increase": "natural_increase",
            "Overseas Arrivals": "nom_arrivals", "Overseas Departures": "nom_departures",
            "Net Overseas Migration": "nom", "Estimated Resident Population (ERP)": "erp",
            "Percentage ERP Change Over Previous Year": "erp_change_12m_pct"}
    a = a[a["measure"].isin(keep)].copy()
    a["measure"] = a["measure"].map(keep)
    thousands = a["unit"].str.strip().eq("000")
    a.loc[thousands, "value"] = a.loc[thousands, "value"] * 1000
    w = a.pivot_table(index="date", columns="measure", values="value", aggfunc="first").reset_index()
    w = w.rename(columns={"date": "quarter"})
    w["quarter"] = pd.to_datetime(w["quarter"]).dt.strftime("%Y-%m")
    cols = ["quarter", "births", "deaths", "natural_increase", "nom_arrivals", "nom_departures", "nom",
            "erp", "erp_change_12m_pct"]
    for c in cols[1:-1]:
        w[c] = w[c].round()
    return w[cols]


def years_by_state(q):
    """Rolling 4-quarter sums ending each quarter; financial years are the June rows."""
    out = []
    for state, g in q.groupby("state"):
        g = g.sort_values("quarter").reset_index(drop=True)
        roll = g[["natural_increase", "nom", "net_interstate_migration", "growth"]].rolling(4).sum()
        y = pd.DataFrame({"year_ending": g["quarter"], "state": state, "nom": roll["nom"],
                          "natural_increase": roll["natural_increase"],
                          "net_interstate_migration": roll["net_interstate_migration"],
                          "growth": roll["growth"], "erp_end": g["erp"], "erp_start": g["erp"].shift(4)})
        out.append(y)
    y = pd.concat(out).dropna(subset=["nom", "erp_start"])
    y["financial_year"] = np.where(y["year_ending"].str[5:7].eq("06"),
                                   (pd.to_datetime(y["year_ending"]).dt.year - 1).astype(str) + "-"
                                   + pd.to_datetime(y["year_ending"]).dt.strftime("%y"), "")
    y["growth_pct"] = (100 * y["growth"] / y["erp_start"]).round(2)
    y["nom_per_1000_pop"] = (1000 * y["nom"] / y["erp_start"]).round(2)
    y["nom_share_of_growth_pct"] = (100 * y["nom"] / y["growth"]).where(y["growth"] > 0).round(1)
    cols = ["year_ending", "financial_year", "state", "nom", "natural_increase", "net_interstate_migration",
            "growth", "erp_start", "erp_end", "growth_pct", "nom_per_1000_pop", "nom_share_of_growth_pct"]
    return y[cols].sort_values(["year_ending", "state"]).reset_index(drop=True)


# ---------------------------------------------------------------- 34070DO004
def nom_visa_groups():
    xl = pd.ExcelFile(io.BytesIO(zip_member(ROOT / "Time-series-spreadsheets-all.zip", "DO004")))
    rows = []
    for sheet in [s for s in xl.sheet_names if s.startswith("Table 4.")]:
        raw = xl.parse(sheet, header=None)
        title_row = raw[raw[0].astype(str).str.startswith("Table 4.")]
        if sheet == "Table 4.1":
            state = "AUS"
        else:
            m = re.search(r"groups, (.+?), \d{4}-\d{2} to", str(title_row.iloc[0, 0]))
            state = state_code(m.group(1))
        h = raw.index[raw[0].astype(str).str.strip().eq("Direction")][0]
        ycols = [c for c in raw.columns if re.match(r"^\d{4}-\d{2}", str(raw.loc[h, c]))]
        direction = category = None
        for i in range(h + 1, len(raw)):
            r = raw.loc[i]
            if isinstance(r[0], str) and r[0].startswith("©"):
                break
            if isinstance(r[0], str) and r[0].strip():
                direction = "arrivals" if "arrivals" in r[0] else "departures"
            c1 = clean_label(r[1]) if pd.notna(r[1]) else ""
            c2 = clean_label(r[2]) if pd.notna(r[2]) else ""
            if not c1 and not c2:
                continue
            if c1 and c2:
                category, group = c1, c2
            elif c2:
                group = c2
            else:
                category = group = c1
            low = group.lower()
            if low.startswith("total permanent"):
                category, group_type = "Permanent visas", "subtotal"
            elif low.startswith("total temporary"):
                category, group_type = "Temporary visas", "subtotal"
            elif low.startswith("total"):
                category, group, group_type = "All", "Total", "total"
            elif group.startswith("Student - "):
                group_type = "detail"          # parts of the Student row
            else:
                group_type = "group"           # groups sum to the total
            for c in ycols:
                rows.append({"financial_year": str(raw.loc[h, c])[:7], "state": state, "direction": direction,
                             "visa_category": category, "visa_group": group, "row_type": group_type,
                             "persons": num(r[c])})
    return pd.DataFrame(rows)


def nom_net(vg):
    w = vg.pivot_table(index=["financial_year", "state", "visa_category", "visa_group", "row_type"],
                       columns="direction", values="persons", aggfunc="sum").reset_index()
    # The ABS total includes unknown visas, so add the difference as its own row (rounding in recent years)
    keys = ["financial_year", "state"]
    tot = w[w["row_type"].eq("total")].set_index(keys)[["arrivals", "departures"]]
    grp = w[w["row_type"].eq("group")].groupby(keys)[["arrivals", "departures"]].sum()
    res = (tot - grp).reset_index().assign(visa_category="Unknown", row_type="residual",
                                           visa_group="Unknown or not listed (total minus groups)")
    w = pd.concat([w, res], ignore_index=True)
    w["net"] = w["arrivals"] - w["departures"]
    tot = w[w["row_type"].eq("total")][["financial_year", "state", "net"]].rename(columns={"net": "total_net"})
    w = w.merge(tot, on=["financial_year", "state"], how="left")
    w["share_of_total_net_pct"] = (100 * w["net"] / w["total_net"]).round(1)
    w = w.drop(columns="total_net")
    return w[["financial_year", "state", "visa_category", "visa_group", "row_type", "arrivals", "departures",
              "net", "share_of_total_net_pct"]].sort_values(["financial_year", "state", "visa_category"])


# ---------------------------------------------------------------- history
def _wide_years(path, sheet, id_cols):
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    h = raw.index[raw.apply(lambda r: any(str(v).strip().startswith(("1788", "1860", "1901", "1971", "1972"))
                                           for v in r.values[:4]), axis=1)][0]
    years = {c: int(re.match(r"\d{4}", str(raw.loc[h, c])).group(0)) for c in raw.columns
             if re.match(r"^\d{4}", str(raw.loc[h, c]))}
    body = raw.iloc[h + 1:]
    body = body[body[list(years)[0]].notna()]
    recs = []
    lab = {}
    for _, r in body.iterrows():
        for k, c in enumerate(id_cols):
            if pd.notna(r[k]):
                lab[c] = clean_label(r[k])
        for c, y in years.items():
            recs.append({**lab, "year": y, "value": num(r[c])})
    return pd.DataFrame(recs)


def history():
    hp1, hp7 = ROOT / "HPDC1.xlsx", ROOT / "HPDC7.xlsx"
    t1 = _wide_years(hp1, "Table 1", ["sex", "state"]).assign(measure="population", reference="31 December")
    t2 = _wide_years(hp1, "Table 2", ["sex", "state"]).assign(measure="population", reference="30 June")
    pop = pd.concat([t1, t2])
    pop = pop[pop["sex"].isin(["Person", "Persons"])].drop(columns="sex")
    nom_fy = _wide_years(hp7, "Table 1", ["state"]).assign(measure="nom", reference="year ended 30 June")
    t4 = _wide_years(hp7, "Table 4", ["state", "series"])
    nom_cy = t4[t4["series"].eq("NOM")].drop(columns="series").assign(measure="nom", reference="year ended 31 December")
    h = pd.concat([pop, nom_fy, nom_cy], ignore_index=True)
    h["state"] = h["state"].map(state_code)
    h = h.dropna(subset=["state", "value"])
    return h[["measure", "reference", "state", "year", "value"]].sort_values(["measure", "reference", "state", "year"])


def long_run(hist, years):
    """One row per year for Australia: population at 30 June (31 Dec before 1901) and NOM
    (calendar years to 1971, financial years from 1972; ABS quarterly series from 2022)."""
    a = hist[hist["state"].eq("AUS")]
    pop_dec = a[(a["measure"] == "population") & (a["reference"] == "31 December")].set_index("year")["value"]
    pop_jun = a[(a["measure"] == "population") & (a["reference"] == "30 June")].set_index("year")["value"]
    nom_cy = a[(a["measure"] == "nom") & (a["reference"] == "year ended 31 December")].set_index("year")["value"]
    nom_fy = a[(a["measure"] == "nom") & (a["reference"] == "year ended 30 June")].set_index("year")["value"]
    fy = years[years["state"].eq("AUS") & years["financial_year"].ne("")].copy()
    fy["year"] = pd.to_datetime(fy["year_ending"]).dt.year
    recent = fy.set_index("year")
    rows = []
    for y in range(1860, int(recent.index.max()) + 1):
        if y <= 1900:
            pop, pref = pop_dec.get(y), "31 December"
        elif y in recent.index and y > pop_jun.index.max():
            pop, pref = recent.loc[y, "erp_end"], "30 June (3101.0)"
        else:
            pop, pref = pop_jun.get(y), "30 June"
        if y in recent.index and y > nom_fy.index.max():
            nom, nref = recent.loc[y, "nom"], "year ended 30 June (3101.0)"
        elif y >= 1972:
            nom, nref = nom_fy.get(y), "year ended 30 June"
        else:
            nom, nref = nom_cy.get(y), "year ended 31 December"
        rows.append({"year": y, "population": pop, "population_reference": pref, "nom": nom, "nom_reference": nref})
    lr = pd.DataFrame(rows)
    lr[["population", "nom"]] = lr[["population", "nom"]].apply(pd.to_numeric, errors="coerce")
    lr["nom_per_1000_pop"] = (1000 * lr["nom"] / lr["population"].shift(1)).round(2)
    return lr


# ---------------------------------------------------------------- main
def main():
    q = quarterly_by_state()
    a = components_australia()
    y = years_by_state(q)
    vg = nom_visa_groups()
    net = nom_net(vg)
    hist = history()
    lr = long_run(hist, y)

    outs = {
        TIDY / "abs_population_quarterly_by_state.csv": q,
        TIDY / "abs_population_components_australia.csv": a,
        TIDY / "abs_nom_visa_groups_by_state.csv": vg,
        TIDY / "abs_population_history.csv": hist,
        HERE / "population_years_by_state.csv": y,
        HERE / "nom_by_visa_group.csv": net,
        HERE / "population_long_run_australia.csv": lr,
    }
    for path, df in outs.items():
        write_table(df, path)

    # Checks
    last_q = q["quarter"].max()
    aus_y = y[y["state"].eq("AUS")].set_index("year_ending")
    states_sum = y[y["state"].isin(STATES)].groupby("year_ending")["nom"].sum()
    vg_tot = net[net["state"].eq("AUS") & net["visa_category"].eq("All")].set_index("financial_year")["net"]
    fy_3101 = y[y["state"].eq("AUS") & y["financial_year"].ne("")].set_index("financial_year")["nom"]
    hist_aus_fy = hist[(hist["state"] == "AUS") & (hist["measure"] == "nom") &
                       (hist["reference"] == "year ended 30 June")].set_index("year")["value"]
    a_q = a.set_index("quarter")
    q_aus = q[q["state"].eq("AUS")].set_index("quarter")
    checks = {
        "latest_quarter": last_q,
        "nom_year_to_latest_quarter_AUS": float(aus_y.loc[last_q, "nom"]),
        "nom_financial_years_AUS_3101": {k: float(v) for k, v in fy_3101.tail(6).items()},
        "nom_financial_years_AUS_34070DO004": {k: float(v) for k, v in vg_tot.tail(6).items()},
        "note_vintages": "34070 (Dec 2025 release) and 3101 (Mar 2026 release) differ for recent years because "
                         "ABS revises preliminary NOM.",
        "states_sum_vs_AUS_nom_latest_year": {"states": float(states_sum.loc[last_q]),
                                              "australia": float(aus_y.loc[last_q, "nom"]),
                                              "difference_is_other_territories": float(aus_y.loc[last_q, "nom"] - states_sum.loc[last_q])},
        "3101_tables_agree_on_quarterly_nom": bool(np.allclose(
            a_q["nom"].reindex(q_aus.index).dropna(), q_aus["nom"].reindex(a_q.index).dropna().loc[
                a_q["nom"].reindex(q_aus.index).dropna().index], atol=500)),
        "history_vs_3101_FY2020_21_nom": {"HPDC7": float(hist_aus_fy.get(2021, np.nan)),
                                          "3101": float(fy_3101.get("2020-21", np.nan))},
        "rows": {p.name: len(df) for p, df in outs.items()},
    }
    (HERE / "population_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))

    # Data dictionary
    Q = "Quarterly"
    m = {
        "quarter": ("Quarter, as the year and month it ends (YYYY-MM)", S_3101, Q, "Date"),
        "state": ("State or territory code; AUS = Australia (includes Other Territories)", "", "", "Classification"),
        "erp": ("Estimated resident population at the end of the quarter", S_3101, Q, "Official estimate (ABS)"),
        "natural_increase": ("Births minus deaths", S_3101, Q, "Official estimate (ABS)"),
        "nom": ("Net overseas migration: migrant arrivals minus departures (12/16 month rule)", S_3101, Q,
                "Official estimate (ABS); recent quarters preliminary"),
        "net_interstate_migration": ("Interstate arrivals minus departures (0 for Australia)", S_3101, Q, "Official estimate (ABS)"),
        "growth": ("Change in ERP over the period", S_3101, Q, "Official estimate (ABS)"),
        "births": ("Births", S_3101, Q, "Official estimate (ABS)"),
        "deaths": ("Deaths", S_3101, Q, "Official estimate (ABS)"),
        "nom_arrivals": ("Overseas migrant arrivals counted in NOM", S_3101, Q, "Official estimate (ABS)"),
        "nom_departures": ("Overseas migrant departures counted in NOM", S_3101, Q, "Official estimate (ABS)"),
        "erp_change_12m_pct": ("ERP change over the previous year, %", S_3101, Q, "Official estimate (ABS)"),
        "financial_year": ("Financial year (blank in the rolling-year table when the year does not end in June)", "", "", "Classification"),
        "direction": ("arrivals or departures", S_VG, "", "Classification"),
        "visa_category": ("Permanent visas, Temporary visas, New Zealand citizens, Australian citizens, or All",
                          S_VG, "", "Classification"),
        "visa_group": ("Visa group at the time of travel (e.g. Student - higher education, Working holiday)", S_VG, "", "Classification"),
        "row_type": ("group (groups add up to the total), detail (parts of Student), subtotal (Total permanent / "
                     "temporary visas), total, or residual (the ABS total minus the listed groups: unknown visas plus rounding; "
                     "groups + residual = total)", S_VG, "", "Classification"),
        "persons": ("Overseas migrant arrivals or departures, rounded by ABS to confidentialise", S_VG,
                    "Financial years 2004-05 to 2024-25", "Official estimate (ABS); 2024-25 preliminary"),
        "arrivals": ("Overseas migrant arrivals", S_VG, "Financial years", "Official estimate (ABS)"),
        "departures": ("Overseas migrant departures", S_VG, "Financial years", "Official estimate (ABS)"),
        "net": ("Arrivals minus departures (this visa group's contribution to NOM)", S_VG, "Financial years", D),
        "share_of_total_net_pct": ("net as a share of total NOM for that year and state", S_VG, "", D),
        "measure": ("population or nom", S_HP, "", "Classification"),
        "reference": ("Reference date or period of the value", S_HP, "", "Classification"),
        "year": ("Year (see reference columns for whether it is calendar or financial)", "", "", "Date"),
        "value": ("Persons", S_HP, "", "Official estimate (ABS); pre-1971 counts of people present"),
        "year_ending": ("Last quarter (YYYY-MM) of the 12 months summed", S_3101, "", "Date"),
        "erp_start": ("ERP 12 months before year_ending", S_3101, "", "Official estimate (ABS)"),
        "erp_end": ("ERP at year_ending", S_3101, "", "Official estimate (ABS)"),
        "growth_pct": ("growth / erp_start, %", S_3101, "", D),
        "nom_per_1000_pop": ("NOM per 1,000 residents at the start of the year", S_3101, "", D),
        "nom_share_of_growth_pct": ("NOM as a share of population growth, % (blank when growth is not positive)", S_3101, "", D),
        "population": ("Population (31 December to 1900, 30 June from 1901)", f"{S_HP}; {S_3101}", "", "Official estimate (ABS)"),
        "population_reference": ("Reference date and source of the population value", "", "", "Classification"),
        "nom_reference": ("Period and source of the NOM value (calendar years to 1971, financial years from 1972)", "", "", "Classification"),
    }
    m_y = dict(m)
    m_y["nom"] = ("Net overseas migration over the 12 months", S_3101, "", "Official estimate (ABS); recent quarters preliminary")
    m_y["natural_increase"] = ("Births minus deaths over the 12 months", S_3101, "", "Official estimate (ABS)")
    m_y["net_interstate_migration"] = ("Net interstate migration over the 12 months", S_3101, "", "Official estimate (ABS)")
    m_y["growth"] = ("Population change over the 12 months", S_3101, "", "Official estimate (ABS)")
    m_lr = dict(m)
    m_lr["nom"] = ("Net overseas migration for the year (see nom_reference)", f"{S_HP}; {S_3101}", "", "Official estimate (ABS); series break in 2006")
    m_lr["nom_per_1000_pop"] = ("NOM per 1,000 population at the end of the previous year", "", "", D)
    rows = []
    for path, df in outs.items():
        rows += dictionary_rows(f"{path.parent.name}/{path.name}", df, m_lr if "long_run" in path.name
                                else m_y if "years_by_state" in path.name else m)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
