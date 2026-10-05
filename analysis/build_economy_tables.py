"""Economy: national accounts for GDP, GDP per person, hours worked, productivity, state final demand and
output by industry.

Run from the Migration folder:  python3 analysis/build_economy_tables.py
Run build_population_tables.py and build_sector_tables.py first (this script reads their outputs).

Input: All_time_series_workbooks.zip (ABS 5206.0, June quarter 2026). Tables used:
   1 key aggregates (quarterly)          6 industry gross value added (quarterly)
  25 state final demand (quarterly)     34 key aggregates (annual)          37 industry gross value added (annual)
The other 40 tables (income accounts, saving, taxes, inventories, prices and so on) are not needed for this
project's questions and are not extracted.

Outputs:
  tidy/abs_gdp_key_aggregates_quarterly.csv   Table 1, every series, long format
  tidy/abs_gdp_key_aggregates_annual.csv      Table 34, every series, long format
  tidy/abs_state_final_demand_quarterly.csv   Table 25, every series, long format
  tidy/abs_industry_gva_quarterly.csv         Table 6 (revision series dropped), long format
  tidy/abs_industry_gva_annual.csv            Table 37, long format
  analysis/economy_quarterly_australia.csv    GDP, GDP per person, hours and productivity growth, with population
  analysis/economy_annual_australia.csv       the same by financial year, with net overseas migration
  analysis/economy_state_final_demand.csv     state final demand in total and per person, by state
  analysis/sector_output_per_worker.csv       real output (gross value added) per employed person, by industry
  analysis/economy_checks.json
Chain volume measures are in the reference year's prices. They are not additive across industries or states.
"""
import json
import re

import numpy as np
import pandas as pd

from _common import (HERE, ROOT, STATES, TIDY, dictionary_rows, read_abs_timeseries, state_code,
                     update_dictionary, write_table, zip_member)

ZIP = ROOT / "All_time_series_workbooks.zip"
FILES = {"1": "5206001_Key_Aggregates.xlsx", "6": "5206006_Industry_GVA.xlsx", "25": "5206025_SFD_Summary.xlsx",
         "34": "5206034_Key_Aggregates_and_Analytical_Series_Annual_data.xlsx",
         "37": "5206037_Industry_Gross_Value_Added_Annual.xlsx"}
SRC = "ABS, Australian National Accounts: National Income, Expenditure and Product, June 2026 (cat. 5206.0)"
SRC_POP = "ABS, National, state and territory population, March 2026 (cat. 3101.0), via build_population_tables"
SRC_EMP = "JSA, Industry data February 2026 (trend employment from ABS Labour Force), via build_sector_tables"
DIVISIONS = {"A": "Agriculture, forestry and fishing", "B": "Mining", "C": "Manufacturing",
             "D": "Electricity, gas, water and waste services", "E": "Construction", "F": "Wholesale trade",
             "G": "Retail trade", "H": "Accommodation and food services", "I": "Transport, postal and warehousing",
             "J": "Information media and telecommunications", "K": "Financial and insurance services",
             "L": "Rental, hiring and real estate services", "M": "Professional, scientific and technical services",
             "N": "Administrative and support services", "O": "Public administration and safety",
             "P": "Education and training", "Q": "Health care and social assistance",
             "R": "Arts and recreation services", "S": "Other services"}
SFD_PARTS = {"General government ; Final consumption expenditure": "Government consumption",
             "Households ; Final consumption expenditure": "Household consumption",
             "Private ; Gross fixed capital formation": "Private investment",
             "Public ; Gross fixed capital formation": "Public investment",
             "STATE FINAL DEMAND": "State final demand"}
FY = "financial_year"


def yyyymm(d):
    return pd.to_datetime(d).dt.strftime("%Y-%m")


def fin_year(d):
    """ABS annual data are dated at June: 2026-06 -> 2025-26."""
    y = pd.to_datetime(d).dt.year
    return (y - 1).astype(str) + "-" + (y % 100).astype(str).str.zfill(2)


def fy_of_month(yyyymm_values):
    """'2025-09' -> '2025-26' (July to June financial year)."""
    d = pd.to_datetime(pd.Series(list(yyyymm_values)) + "-01")
    end = d.dt.year + (d.dt.month >= 7).astype(int)
    return ((end - 1).astype(str) + "-" + (end % 100).astype(str).str.zfill(2)).to_numpy()


def load(table):
    return read_abs_timeseries(zip_member(ZIP, FILES[table]))


def split_measure(label):
    """'GDP per capita: Chain volume measures - Percentage changes' -> ('GDP per capita', 'Chain volume measures', True)"""
    m = re.match(r"^(.*?): (.*?)(?: - (Percentage [Cc]hanges))?$", label)
    assert m, label
    return m.group(1), m.group(2), bool(m.group(3))


def key_aggregates(table):
    df = load(table)
    parts = pd.DataFrame([split_measure(s) for s in df["series"]], columns=["measure", "basis", "is_pct_change"],
                         index=df.index)
    df = pd.concat([df, parts], axis=1)
    if table == "1":
        df = df.assign(quarter=yyyymm(df["date"]))
        cols = ["quarter", "measure", "basis", "is_pct_change", "series_type", "unit", "value", "series_id"]
    else:
        df = df.assign(financial_year=fin_year(df["date"]))
        cols = [FY, "measure", "basis", "is_pct_change", "series_type", "unit", "value", "series_id"]
    return df[cols].sort_values(cols[:5], ignore_index=True)


def state_final_demand():
    df = load("25")
    st = df["series"].str.split(" ; ", n=1).str[0].map(state_code)
    rest = df["series"].str.split(" ; ", n=1).str[1]
    pct = rest.str.endswith(": Percentage changes")
    comp = rest.str.replace(": Percentage changes", "", regex=False).map(SFD_PARTS)
    assert st.notna().all() and comp.notna().all(), "unknown SFD label"
    df = df.assign(quarter=yyyymm(df["date"]), state=st, component=comp, is_pct_change=pct)
    cols = ["quarter", "state", "component", "is_pct_change", "series_type", "unit", "value", "series_id"]
    order = {s: i for i, s in enumerate(STATES)}
    return df[cols].sort_values(cols[:5], key=lambda s: s.map(order) if s.name == "state" else s, ignore_index=True)


def industry_gva(table):
    df = load(table)
    rows = []
    for lab in df["series"]:
        first, _, rest = lab.partition(" ; ")
        first, _, tail = first.partition(": ")   # 'GROSS DOMESTIC PRODUCT: Percentage changes'
        rest = rest or tail
        sub, measure = rest, "Level"
        for suffix, name in [("Contributions to growth", "Contribution to growth"),
                             ("Revision to percentage changes", "Revision"), ("Percentage changes", "Percentage change")]:
            if rest == suffix or rest.endswith(": " + suffix):
                sub, measure = rest[: -len(suffix)].rstrip(": ").strip(), name
                break
        m = re.match(r"^(.*) \(([A-S])\)$", first)
        div = m.group(2) if m and m.group(1).lower() == DIVISIONS[m.group(2)].lower() else ""
        first = first.strip()
        industry = DIVISIONS[div] if div else (first.capitalize() if first.isupper() else first)
        rows.append((div, industry, sub, measure))
    lab = pd.DataFrame(rows, columns=["anzsic_division", "industry", "subdivision", "measure"], index=df.index)
    df = pd.concat([df, lab], axis=1)
    df = df[~df["measure"].eq("Revision")]
    if table == "6":
        df = df.assign(quarter=yyyymm(df["date"]))
        cols = ["quarter", "anzsic_division", "industry", "subdivision", "measure", "series_type", "unit", "value",
                "series_id"]
    else:
        df = df.assign(financial_year=fin_year(df["date"]))
        cols = [FY, "anzsic_division", "industry", "subdivision", "measure", "series_type", "unit", "value",
                "series_id"]
    return df[cols].sort_values(cols[:6], ignore_index=True)


def pick(df, period, measure, basis, pct=False, series_type="Seasonally Adjusted"):
    x = df[df["measure"].eq(measure) & df["basis"].eq(basis) & df["is_pct_change"].eq(pct)
           & df["series_type"].eq(series_type)]
    assert len(x) and not x[period].duplicated().any(), (measure, basis, pct, series_type)
    return x.set_index(period)["value"]


def growth(s, lag):
    return (100 * (s / s.shift(lag) - 1)).round(2)


def economy_quarterly(ka):
    q = "quarter"
    out = pd.DataFrame({
        "gdp_cvm_sa": pick(ka, q, "Gross domestic product", "Chain volume measures"),
        "gdp_growth_q_pct": pick(ka, q, "Gross domestic product", "Chain volume measures", True),
        "gdp_per_capita_cvm_sa": pick(ka, q, "GDP per capita", "Chain volume measures"),
        "gdp_per_capita_growth_q_pct": pick(ka, q, "GDP per capita", "Chain volume measures", True),
        "hours_worked_index_sa": pick(ka, q, "Hours worked", "Index"),
        "gdp_per_hour_worked_index_sa": pick(ka, q, "GDP per hour worked", "Index"),
        "rnndi_per_capita_cvm_sa": pick(ka, q, "Real net national disposable income per capita", "Chain volume measures"),
        "terms_of_trade_index_sa": pick(ka, q, "Terms of trade", "Index"),
    }).sort_index()
    out.insert(2, "gdp_growth_tty_pct", growth(out["gdp_cvm_sa"], 4))
    out.insert(5, "gdp_per_capita_growth_tty_pct", growth(out["gdp_per_capita_cvm_sa"], 4))
    out.insert(7, "hours_worked_growth_tty_pct", growth(out["hours_worked_index_sa"], 4))
    out.insert(9, "gdp_per_hour_worked_growth_tty_pct", growth(out["gdp_per_hour_worked_index_sa"], 4))
    out.insert(11, "rnndi_per_capita_growth_tty_pct", growth(out["rnndi_per_capita_cvm_sa"], 4))
    pop = pd.read_csv(HERE / "population_years_by_state.csv", dtype={"year_ending": str})
    pop = pop[pop["state"].eq("AUS")].set_index("year_ending")
    out["erp_end"] = pop["erp_end"]
    out["population_growth_12m_pct"] = pop["growth_pct"]
    out["nom_12m"] = pop["nom"]
    out = out.reset_index().rename(columns={"index": "quarter"})
    return out[out["quarter"] >= "1959-09"].reset_index(drop=True)


def economy_annual(ka34):
    f = FY
    out = pd.DataFrame({
        "gdp_cvm": pick(ka34, f, "Gross domestic product", "Chain volume measures", series_type="Original"),
        "gdp_growth_pct": pick(ka34, f, "Gross domestic product", "Chain volume measures", True, "Original"),
        "gdp_per_capita_cvm": pick(ka34, f, "GDP per capita", "Chain volume measures", series_type="Original"),
        "gdp_per_capita_growth_pct": pick(ka34, f, "GDP per capita", "Chain volume measures", True, "Original"),
        "hours_worked_growth_pct": pick(ka34, f, "Hours worked", "Index", True, "Original"),
        "gdp_per_hour_worked_growth_pct": pick(ka34, f, "GDP per hour worked", "Index", True, "Original"),
        "rnndi_per_capita_growth_pct": pick(ka34, f, "Real net national disposable income per capita",
                                            "Chain volume measures", True, "Original"),
    }).sort_index()
    pop = pd.read_csv(HERE / "population_years_by_state.csv")
    pop = pop[pop["state"].eq("AUS") & pop[FY].notna()].set_index(FY)
    out["erp_end_june"] = pop["erp_end"]
    out["population_growth"] = pop["growth"]
    out["population_growth_pct"] = pop["growth_pct"]
    out["nom"] = pop["nom"]
    out["nom_per_1000_pop"] = pop["nom_per_1000_pop"]
    out["nom_share_of_population_growth_pct"] = pop["nom_share_of_growth_pct"]
    return out.reset_index().rename(columns={"index": FY})


def state_demand(sfd):
    x = sfd[sfd["component"].eq("State final demand") & sfd["series_type"].eq("Seasonally Adjusted")]
    lvl = x[~x["is_pct_change"]].pivot(index="quarter", columns="state", values="value")
    pct = x[x["is_pct_change"]].pivot(index="quarter", columns="state", values="value")
    pop = pd.read_csv(TIDY / "abs_population_quarterly_by_state.csv", dtype={"quarter": str})
    erp = pop.pivot(index="quarter", columns="state", values="erp")
    rows = []
    for st in STATES:
        e = erp[st].reindex(lvl.index.union(erp.index)) if st in erp else pd.Series(dtype=float)
        avg = ((e + e.shift(1)) / 2).reindex(lvl.index)
        d = pd.DataFrame({"quarter": lvl.index, "state": st, "sfd_cvm_sa": lvl[st].to_numpy(),
                          "sfd_growth_q_pct": pct[st].reindex(lvl.index).to_numpy()})
        d["sfd_growth_tty_pct"] = growth(d["sfd_cvm_sa"], 4).to_numpy()
        d["population_avg"] = avg.to_numpy()
        d["sfd_per_person_sa"] = (1e6 * d["sfd_cvm_sa"] / d["population_avg"]).round(0)
        d["sfd_per_person_growth_tty_pct"] = growth(d["sfd_per_person_sa"], 4).to_numpy()
        rows.append(d)
    return pd.concat(rows, ignore_index=True)


def output_per_worker(gva37):
    g = gva37[gva37["anzsic_division"].ne("") & gva37["subdivision"].eq("") & gva37["measure"].eq("Level")]
    g = g.rename(columns={"value": "gva_cvm"})[["anzsic_division", FY, "gva_cvm"]]
    emp = pd.read_csv(TIDY / "jsa_industry_employment_quarterly.csv", dtype={"quarter": str})
    emp = emp[emp["anzsic_division"].isin(list(DIVISIONS))].copy()
    emp[FY] = fy_of_month(emp["quarter"])   # Aug and Nov belong to the financial year ending the next June
    cnt = emp.groupby(["anzsic_division", FY])["employed"].agg(["mean", "size"]).reset_index()
    cnt = cnt[cnt["size"].eq(4)].rename(columns={"mean": "employed_avg"}).drop(columns="size")
    df = g.merge(cnt, on=["anzsic_division", FY], how="left")
    df = df[df[FY] >= cnt[FY].min()].copy()
    df.insert(1, "industry", df["anzsic_division"].map(DIVISIONS))
    df = df.sort_values(["anzsic_division", FY], ignore_index=True)
    by = df.groupby("anzsic_division")
    df["gva_growth_pct"] = by["gva_cvm"].transform(lambda s: growth(s, 1))
    df["employed_growth_pct"] = by["employed_avg"].transform(lambda s: growth(s, 1))
    df["gva_per_worker"] = (1e6 * df["gva_cvm"] / df["employed_avg"]).round(0)
    df["gva_per_worker_growth_pct"] = df.groupby("anzsic_division")["gva_per_worker"].transform(lambda s: growth(s, 1))
    df["employed_avg"] = df["employed_avg"].round(0)
    return df[["anzsic_division", "industry", FY, "gva_cvm", "gva_growth_pct", "employed_avg", "employed_growth_pct",
               "gva_per_worker", "gva_per_worker_growth_pct"]]


def main():
    ka = key_aggregates("1")
    ka34 = key_aggregates("34")
    sfd = state_final_demand()
    gva6 = industry_gva("6")
    gva37 = industry_gva("37")
    eq = economy_quarterly(ka)
    ea = economy_annual(ka34)
    sd = state_demand(sfd)
    ow = output_per_worker(gva37)
    outs = {TIDY / "abs_gdp_key_aggregates_quarterly.csv": ka, TIDY / "abs_gdp_key_aggregates_annual.csv": ka34,
            TIDY / "abs_state_final_demand_quarterly.csv": sfd, TIDY / "abs_industry_gva_quarterly.csv": gva6,
            TIDY / "abs_industry_gva_annual.csv": gva37, HERE / "economy_quarterly_australia.csv": eq,
            HERE / "economy_annual_australia.csv": ea, HERE / "economy_state_final_demand.csv": sd,
            HERE / "sector_output_per_worker.csv": ow}
    for path, df in outs.items():
        write_table(df, path)

    q_orig = pick(ka, "quarter", "Gross domestic product", "Chain volume measures", series_type="Original")
    q_fy = fy_of_month(q_orig.index)
    q_sum = q_orig.groupby(q_fy).agg(["sum", "size"])
    q_sum = q_sum.loc[q_sum["size"].eq(4), "sum"]
    a = ea.set_index(FY)["gdp_cvm"]
    common = a.index.intersection(q_sum.index)
    g37 = gva37[gva37["industry"].eq("Gross domestic product") & gva37["measure"].eq("Level")].set_index(FY)["value"]
    last = eq.iloc[-3:].set_index("quarter")
    checks = {
        "latest_quarter": eq["quarter"].iloc[-1],
        "latest_financial_year": ea[FY].iloc[-1],
        "gdp_per_capita_last_3_quarters": {k: {"q_pct": float(r["gdp_per_capita_growth_q_pct"]),
                                               "tty_pct": float(r["gdp_per_capita_growth_tty_pct"])}
                                           for k, r in last.iterrows()},
        "gdp_last_3_quarters": {k: {"q_pct": float(r["gdp_growth_q_pct"]), "tty_pct": float(r["gdp_growth_tty_pct"])}
                                for k, r in last.iterrows()},
        "annual_gdp_equals_sum_of_quarters_max_abs_pct": float((100 * (a[common] / q_sum[common] - 1)).abs().max()),
        "annual_gdp_table34_vs_table37_max_abs": float((a - g37.reindex(a.index)).abs().max()),
        "sfd_states": sorted(sfd["state"].unique().tolist()),
        "sfd_latest_quarter": sfd["quarter"].max(),
        "industry_divisions_found": sorted(set(gva37["anzsic_division"]) - {""}),
        "output_per_worker_years": [ow[FY].min(), ow.dropna(subset=["employed_avg"])[FY].max()],
        "output_per_worker_latest_full_year": ow.dropna(subset=["gva_per_worker"]).sort_values(FY)
            .groupby("anzsic_division").tail(1).set_index("industry")["gva_per_worker"].sort_values().to_dict(),
        "annual_recent": ea[ea[FY] >= "2018-19"].set_index(FY)[["gdp_growth_pct", "gdp_per_capita_growth_pct",
                                                                "population_growth_pct", "nom"]].to_dict("index"),
        "rows": {p.name: len(df) for p, df in outs.items()},
    }
    (HERE / "economy_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))

    O, C = "Official data (ABS)", "Calculated from official data"
    tty = "Through-the-year growth: change on the same quarter a year earlier, from seasonally adjusted levels (%)"
    m = {
        "quarter": ("Quarter, labelled by its last month (YYYY-MM)", SRC, "", "Classification"),
        FY: ("Financial year (July to June)", SRC, "", "Classification"),
        "measure": ("ABS data item (for example Gross domestic product, GDP per capita, Hours worked)", SRC, "", "Classification"),
        "basis": ("Chain volume measures (real, reference-year prices), Current prices, Index, Ratio", SRC, "", "Classification"),
        "is_pct_change": ("True if the value is the ABS percentage change on the previous period", SRC, "", "Classification"),
        "series_type": ("Original, Seasonally Adjusted or Trend", SRC, "", "Classification"),
        "unit": ("ABS unit ($ Millions, $, Index Numbers, Percent, Index Points, proportion)", SRC, "", "Classification"),
        "value": ("Value of the series", SRC, "", O),
        "series_id": ("ABS series ID", SRC, "", "Classification"),
        "state": ("State or territory code", SRC, "", "Classification"),
        "component": ("State final demand or one of its parts: household consumption, government consumption, "
                      "private investment, public investment (chain volume measures)", SRC, "", "Classification"),
        "anzsic_division": ("ANZSIC 2006 division letter (blank for GDP, total GVA, ownership of dwellings, taxes "
                            "less subsidies and the statistical discrepancy)", SRC, "", "Classification"),
        "industry": ("Industry division or aggregate", SRC, "", "Classification"),
        "subdivision": ("Industry subdivision or group within the division (blank = whole division)", SRC, "", "Classification"),
        "gdp_cvm_sa": ("Gross domestic product, chain volume measures, seasonally adjusted ($ million per quarter)", SRC, "", O),
        "gdp_growth_q_pct": ("GDP growth on the previous quarter (%, ABS)", SRC, "", O),
        "gdp_growth_tty_pct": ("GDP " + tty, SRC, "", C),
        "gdp_per_capita_cvm_sa": ("GDP per person, chain volume measures, seasonally adjusted ($ per quarter)", SRC, "", O),
        "gdp_per_capita_growth_q_pct": ("GDP per person growth on the previous quarter (%, ABS)", SRC, "", O),
        "gdp_per_capita_growth_tty_pct": ("GDP per person " + tty, SRC, "", C),
        "hours_worked_index_sa": ("Hours worked index, seasonally adjusted", SRC, "", O),
        "hours_worked_growth_tty_pct": ("Hours worked " + tty, SRC, "", C),
        "gdp_per_hour_worked_index_sa": ("GDP per hour worked index (labour productivity), seasonally adjusted", SRC, "", O),
        "gdp_per_hour_worked_growth_tty_pct": ("GDP per hour worked " + tty, SRC, "", C),
        "rnndi_per_capita_cvm_sa": ("Real net national disposable income per person, seasonally adjusted ($ per quarter). "
                                    "A living-standards measure that includes the terms of trade", SRC, "", O),
        "rnndi_per_capita_growth_tty_pct": ("Real net national disposable income per person " + tty, SRC, "", C),
        "terms_of_trade_index_sa": ("Terms of trade index (export prices relative to import prices)", SRC, "", O),
        "erp_end": ("Estimated resident population at the end of the quarter (Australia)", SRC_POP, "", "Official data (ABS)"),
        "population_growth_12m_pct": ("Population growth over the 12 months to the quarter (%)", SRC_POP, "", "Official data (ABS)"),
        "nom_12m": ("Net overseas migration over the 12 months to the quarter", SRC_POP, "",
                    "Official data (ABS; recent quarters are preliminary)"),
        "gdp_cvm": ("Gross domestic product, chain volume measures ($ million in the year)", SRC, "", O),
        "gdp_growth_pct": ("GDP growth on the previous financial year (%, ABS)", SRC, "", O),
        "gdp_per_capita_cvm": ("GDP per person, chain volume measures ($ in the year)", SRC, "", O),
        "gdp_per_capita_growth_pct": ("GDP per person growth on the previous financial year (%, ABS)", SRC, "", O),
        "hours_worked_growth_pct": ("Hours worked growth on the previous financial year (%, ABS)", SRC, "", O),
        "gdp_per_hour_worked_growth_pct": ("GDP per hour worked growth on the previous financial year (%, ABS)", SRC, "", O),
        "rnndi_per_capita_growth_pct": ("Real net national disposable income per person growth (%, ABS)", SRC, "", O),
        "erp_end_june": ("Estimated resident population at 30 June", SRC_POP, "", "Official data (ABS)"),
        "population_growth": ("Population growth over the financial year", SRC_POP, "", "Official data (ABS)"),
        "population_growth_pct": ("Population growth over the financial year (%)", SRC_POP, "", "Official data (ABS)"),
        "nom": ("Net overseas migration over the financial year", SRC_POP, "", "Official data (ABS; latest year preliminary)"),
        "nom_per_1000_pop": ("Net overseas migration per 1,000 residents at the start of the year", SRC_POP, "", C),
        "nom_share_of_population_growth_pct": ("Net overseas migration as a share of population growth (%)", SRC_POP, "", C),
        "sfd_cvm_sa": ("State final demand, chain volume measures, seasonally adjusted ($ million per quarter). Spending "
                       "by households, governments and businesses in the state; excludes trade, so it is not gross "
                       "state product", SRC, "", O),
        "sfd_growth_q_pct": ("State final demand growth on the previous quarter (%, ABS)", SRC, "", O),
        "sfd_growth_tty_pct": ("State final demand " + tty, SRC, "", C),
        "population_avg": ("Average population over the quarter (mean of estimated resident population at the start "
                           "and end)", SRC_POP, "", C),
        "sfd_per_person_sa": ("State final demand per person ($ per quarter, chain volume measures)", SRC, "", C),
        "sfd_per_person_growth_tty_pct": ("State final demand per person, change on the same quarter a year earlier (%)",
                                          SRC, "", C),
        "gva_cvm": ("Gross value added by the industry, chain volume measures ($ million in the year)", SRC, "", O),
        "gva_growth_pct": ("Growth in the industry's gross value added on the previous year (%)", SRC, "", C),
        "employed_avg": ("Average employed persons in the industry over the four quarters of the financial year "
                         "(JSA trend; Aug, Nov, Feb, May)", SRC_EMP, "", "Official estimate (JSA trend)"),
        "employed_growth_pct": ("Growth in average employment on the previous year (%)", SRC_EMP, "", C),
        "gva_per_worker": ("Real output per employed person ($, chain volume measures). Per person, not per hour, so "
                           "industries with more part-time work look less productive", SRC, "", C),
        "gva_per_worker_growth_pct": ("Growth in real output per employed person on the previous year (%)", SRC, "", C),
    }
    rows = []
    for path, df in outs.items():
        prefix = "tidy/" if path.parent == TIDY else "analysis/"
        rows += dictionary_rows(prefix + path.name, df, m)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
