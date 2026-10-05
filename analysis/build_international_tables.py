"""International comparison: net migration, population growth and GDP per person for Australia, Canada, the
United Kingdom and the United States.

Run from the Migration folder:  python3 analysis/build_international_tables.py
Run build_population_tables.py first (Australia comes from analysis/population_years_by_state.csv).

Inputs:
  17100009-eng.zip            Statistics Canada table 17-10-0009, population estimates, quarterly
  17100040-eng.zip            Statistics Canada table 17-10-0040, components of international migration, quarterly
  may2026publicationspreadsheet.xlsx   ONS, Long-term international migration, provisional: YE December 2025
  NST-EST2025-ALLDATA.csv     US Census Bureau, Vintage 2025 population estimates and components
  API_NY.GDP.PCAP.KD_...zip   World Bank WDI, GDP per capita (constant 2015 US$)
  API_SP.POP.TOTL_...zip      World Bank WDI, population, total

All four countries can be lined up on years ending 30 June: Australia's financial year, Canada's July to June
demographic year, the ONS 'year ending June' and the US Census Bureau's July to June estimate year.
Each country defines a migrant differently (see 'definition'), so compare levels with care.

Outputs:
  tidy/statcan_population_quarterly.csv            population on the first day of each quarter, Canada and provinces
  tidy/statcan_international_migration_quarterly.csv   migration components per quarter, Canada and provinces
  tidy/ons_net_migration_uk.csv                    UK immigration, emigration and net migration (all nationalities)
  tidy/ons_visa_migration_by_reason_uk.csv         UK visa-holder migration by reason (work, study, family, ...)
  tidy/uscensus_population_components.csv          US and states: population and components, Vintage 2025
  tidy/worldbank_gdp_per_capita.csv                all economies, 1960 onward
  tidy/worldbank_population.csv                    all economies, 1960 onward
  analysis/international_migration_comparison.csv  net migration and population growth, years ending June
  analysis/international_gdp_per_capita.csv        GDP per person and population growth, calendar years
  analysis/international_checks.json
"""
import json
import re
import zipfile

import numpy as np
import openpyxl
import pandas as pd

from _common import HERE, ROOT, TIDY, dictionary_rows, update_dictionary, write_table

STATCAN_POP = ROOT / "17100009-eng.zip"
STATCAN_MIG = ROOT / "17100040-eng.zip"
ONS = ROOT / "may2026publicationspreadsheet.xlsx"
USCB = ROOT / "NST-EST2025-ALLDATA.csv"
WB_GDP = ROOT / "API_NY.GDP.PCAP.KD_DS2_en_csv_v2_445765.zip"
WB_POP = ROOT / "API_SP.POP.TOTL_DS2_en_csv_v2_446263.zip"
COUNTRIES = {"AUS": "Australia", "CAN": "Canada", "GBR": "United Kingdom", "USA": "United States"}
SRC_CAN_POP = "Statistics Canada, Table 17-10-0009-01 Population estimates, quarterly (accessed Sept 2026)"
SRC_CAN_MIG = "Statistics Canada, Table 17-10-0040-01 Estimates of the components of international migration, quarterly"
SRC_ONS = "ONS, Long-term international migration, provisional: year ending December 2025 (21 May 2026)"
SRC_USCB = "US Census Bureau, Vintage 2025 national and state population estimates (NST-EST2025-ALLDATA)"
SRC_WB = "World Bank, World Development Indicators (last updated 13 July 2026)"
SRC_ABS = "ABS, National, state and territory population, March 2026 (cat. 3101.0), via build_population_tables"
DEFINITIONS = {
    "Australia": "Net overseas migration: people who stay in (or leave) Australia for 12 of the last 16 months, "
                 "whatever their visa or citizenship",
    "Canada": "Net international migration: immigrants (permanent residents) minus net emigration plus the net "
              "change in non-permanent residents (temporary workers, students, asylum claimants)",
    "United Kingdom": "Net long-term migration: people changing their usual residence for at least 12 months "
                      "(ONS 'official statistics in development', rounded to the nearest thousand)",
    "United States": "Net international migration: Census Bureau estimate of all moves into and out of the "
                     "country (foreign-born and native-born)",
}
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
                                      "Dec"], 1)}


def read_zip_csv(path, member_prefix, **kw):
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.startswith(member_prefix) and "Metadata" not in n
                    and "MetaData" not in n)
        with z.open(name) as f:
            return pd.read_csv(f, **kw)


# ---------- Canada ----------
def statcan():
    pop = read_zip_csv(STATCAN_POP, "17100009")
    pop = pd.DataFrame({"quarter_start": pd.to_datetime(pop["REF_DATE"]).dt.strftime("%Y-%m"), "geo": pop["GEO"],
                        "population": pd.to_numeric(pop["VALUE"], errors="coerce")}).dropna()
    mig = read_zip_csv(STATCAN_MIG, "17100040")
    mig = pd.DataFrame({"quarter_start": pd.to_datetime(mig["REF_DATE"]).dt.strftime("%Y-%m"), "geo": mig["GEO"],
                        "component": mig["Components of population growth"],
                        "persons": pd.to_numeric(mig["VALUE"], errors="coerce")}).dropna()
    return pop.reset_index(drop=True), mig.reset_index(drop=True)


def canada_years(pop, mig):
    c = mig[mig["geo"].eq("Canada")].pivot(index="quarter_start", columns="component", values="persons")
    nim = (c["Immigrants"] - c["Net emigration"] + c["Net non-permanent residents"]).dropna()
    d = pd.to_datetime(pd.Series(nim.index) + "-01")
    year_end = (d.dt.year + (d.dt.month >= 7).astype(int)).to_numpy()   # Jul-Sep quarter starts the next June-year
    g = pd.DataFrame({"y": year_end, "nim": nim.to_numpy()}).groupby("y")["nim"].agg(["sum", "size"])
    g = g[g["size"].eq(4)]["sum"]
    p = pop[pop["geo"].eq("Canada")].set_index("quarter_start")["population"]
    rows = []
    for y, v in g.items():
        start, end = p.get(f"{y - 1}-07"), p.get(f"{y}-07")
        rows.append({"country": "Canada", "year_ending_june": int(y), "net_migration": float(v),
                     "population_start": start, "population_end": end, "status": "",
                     "net_migration_source": SRC_CAN_MIG, "population_source": SRC_CAN_POP})
    return pd.DataFrame(rows)


# ---------- United Kingdom ----------
def _ons_rows(sheet):
    wb = openpyxl.load_workbook(ONS, read_only=True)
    rows = list(wb[sheet].iter_rows(values_only=True))
    hdr_i = next(i for i, r in enumerate(rows) if r[0] and str(r[0]).startswith(("Flow", "Nationality")))
    hdr = [re.sub(r"\s+", " ", re.sub(r"\[.*?\]", "", str(h or ""))).strip() for h in rows[hdr_i]]
    body = [r for r in rows[hdr_i + 1:] if r[0] is not None]
    return pd.DataFrame(body, columns=hdr)


def _period(label):
    m = re.match(r"^YE (\w{3}) (\d{2})\s*(.*)$", str(label).strip())
    assert m, label
    flags = m.group(3).split()
    return f"20{m.group(2)}-{MONTHS[m.group(1)]:02d}", "P" in flags, "R" in flags


def ons():
    t1 = _ons_rows("1")
    per = pd.DataFrame([_period(p) for p in t1["Period"]], columns=["year_ending", "provisional", "revised"])
    uk = pd.DataFrame({"flow": t1["Flow"], "year_ending": per["year_ending"], "period_label": t1["Period"],
                       "provisional": per["provisional"], "revised": per["revised"],
                       "estimate": pd.to_numeric(t1["All Nationalities"], errors="coerce")})
    t2 = _ons_rows("2")
    t2 = t2[t2["Flow"].notna() & t2["Period"].notna()]
    t2 = pd.DataFrame({"flow": t2["Flow"], "year_ending": [_period(p)[0] for p in t2["Period"]],
                       "estimate_t2": pd.to_numeric(t2["Estimate"], errors="coerce"),
                       "lower_bound": pd.to_numeric(t2["Lower bound"], errors="coerce"),
                       "upper_bound": pd.to_numeric(t2["Upper bound"], errors="coerce")})
    uk = uk.merge(t2, on=["flow", "year_ending"], how="left")
    t2_gap = float((uk["estimate_t2"] - uk["estimate"]).abs().max())
    uk = uk.drop(columns="estimate_t2")

    parts = []
    for sheet in ["4a", "4b"]:
        t = _ons_rows(sheet)
        long = t.melt(id_vars=["Flow", "Period"], var_name="reason", value_name="persons")
        long["persons"] = pd.to_numeric(long["persons"], errors="coerce")
        long["year_ending"] = [_period(p)[0] for p in long["Period"]]
        long["provisional"] = [_period(p)[1] for p in long["Period"]]
        parts.append(long.rename(columns={"Flow": "flow"}))
    r = pd.concat(parts, ignore_index=True)
    reason_map = {"All reasons": "All reasons", "All Work Related": "Work (all)", "Work: Main applicant": "Work: main applicant",
                  "Work: Dependant": "Work: dependant", "All Study Related": "Study (all)",
                  "Study: Main applicant": "Study: main applicant", "Study: Dependant": "Study: dependant",
                  "Family": "Family", "All Humanitarian": "Humanitarian and asylum",
                  "Humanitarian: BNO": "Humanitarian and asylum", "Humanitarian: Resettlement": "Humanitarian and asylum",
                  "Humanitarian: Ukraine": "Humanitarian and asylum", "Asylum": "Humanitarian and asylum",
                  "Other": "Other"}
    unknown = set(r["reason"]) - set(reason_map)
    assert not unknown, unknown
    r = r[~r["reason"].eq("All Humanitarian")]   # its parts are summed below together with asylum
    r["reason"] = r["reason"].map(reason_map)
    by = r.groupby(["flow", "year_ending", "reason"], as_index=False).agg(persons=("persons", "sum"),
                                                                          provisional=("provisional", "max"))
    order = list(dict.fromkeys(reason_map.values()))
    by["reason"] = pd.Categorical(by["reason"], order, ordered=True)
    by = by.sort_values(["flow", "year_ending", "reason"], ignore_index=True)
    by["reason"] = by["reason"].astype(str)
    return uk, by, t2_gap


def uk_years(uk, wb_pop):
    n = uk[uk["flow"].eq("Net migration") & uk["year_ending"].str.endswith("-06")]
    p = wb_pop[wb_pop["country_code"].eq("GBR")].set_index("year")["population"]
    rows = []
    for _, r in n.iterrows():
        y = int(r["year_ending"][:4])
        rows.append({"country": "United Kingdom", "year_ending_june": y, "net_migration": float(r["estimate"]),
                     "population_start": p.get(y - 1), "population_end": p.get(y),
                     "status": ("Provisional" if r["provisional"] else "") + (" (revised)" if r["revised"] else ""),
                     "net_migration_source": SRC_ONS,
                     "population_source": SRC_WB + " (mid-year population, from ONS)"})
    return pd.DataFrame(rows)


# ---------- United States ----------
def uscensus():
    u = pd.read_csv(USCB, encoding="latin-1")
    u = u[u["SUMLEV"].isin([10, 40])]
    measures = {"POPESTIMATE": "population_july1", "NPOPCHG_": "population_change", "BIRTHS": "births",
                "DEATHS": "deaths", "NATURALCHG": "natural_change", "INTERNATIONALMIG": "net_international_migration",
                "DOMESTICMIG": "net_domestic_migration", "NETMIG": "net_migration", "RESIDUAL": "residual"}
    rows = []
    for col in u.columns:
        m = re.match(r"^(POPESTIMATE|NPOPCHG_|BIRTHS|DEATHS|NATURALCHG|INTERNATIONALMIG|DOMESTICMIG|NETMIG|RESIDUAL)"
                     r"(\d{4})$", col)
        if m:
            for name, v in zip(u["NAME"], u[col]):
                rows.append({"geo": name, "year": int(m.group(2)), "measure": measures[m.group(1)], "value": float(v)})
    df = pd.DataFrame(rows)
    df["period"] = np.where(df["measure"].eq("population_july1"), "1 July of year",
                            np.where(df["year"].eq(2020), "1 April to 30 June 2020",
                                     "1 July of the previous year to 30 June of year"))
    return df.sort_values(["geo", "measure", "year"],
                          key=lambda s: s.where(s.ne("United States"), "") if s.name == "geo" else s,
                          ignore_index=True)


def us_years(us):
    x = us[us["geo"].eq("United States")].pivot(index="year", columns="measure", values="value")
    rows = []
    for y in range(2021, int(x.index.max()) + 1):
        rows.append({"country": "United States", "year_ending_june": y,
                     "net_migration": float(x.loc[y, "net_international_migration"]),
                     "population_start": float(x.loc[y - 1, "population_july1"]),
                     "population_end": float(x.loc[y, "population_july1"]),
                     "status": "Vintage 2025 (revised each year)", "net_migration_source": SRC_USCB,
                     "population_source": SRC_USCB})
    return pd.DataFrame(rows)


# ---------- World Bank ----------
def worldbank(path, value_name):
    with zipfile.ZipFile(path) as z:
        data = next(n for n in z.namelist() if n.startswith("API_"))
        meta = next(n for n in z.namelist() if n.startswith("Metadata_Country"))
        with z.open(data) as f:
            d = pd.read_csv(f, skiprows=4)
        with z.open(meta) as f:
            m = pd.read_csv(f)
    years = [c for c in d.columns if re.fullmatch(r"\d{4}", str(c))]
    long = d.melt(id_vars=["Country Name", "Country Code"], value_vars=years, var_name="year", value_name=value_name)
    long = long.dropna(subset=[value_name])
    long["year"] = long["year"].astype(int)
    agg = set(m.loc[m["Region"].isna(), "Country Code"])
    long["is_aggregate"] = long["Country Code"].isin(agg)
    long = long.rename(columns={"Country Name": "country", "Country Code": "country_code"})
    return long[["country_code", "country", "year", value_name, "is_aggregate"]].sort_values(
        ["country_code", "year"], ignore_index=True)


# ---------- Australia ----------
def australia_years():
    p = pd.read_csv(HERE / "population_years_by_state.csv")
    p = p[p["state"].eq("AUS") & p["financial_year"].notna()]
    return pd.DataFrame({"country": "Australia", "year_ending_june": p["financial_year"].str[:4].astype(int) + 1,
                         "net_migration": p["nom"], "population_start": p["erp_start"], "population_end": p["erp_end"],
                         "status": "", "net_migration_source": SRC_ABS, "population_source": SRC_ABS})


def comparison(parts):
    df = pd.concat(parts, ignore_index=True)
    df["population_growth"] = df["population_end"] - df["population_start"]
    df["population_growth_pct"] = (100 * df["population_growth"] / df["population_start"]).round(2)
    df["net_migration_per_1000_pop"] = (1000 * df["net_migration"] / df["population_start"]).round(2)
    share = 100 * df["net_migration"] / df["population_growth"].where(df["population_growth"] > 0)
    df["net_migration_share_of_growth_pct"] = share.round(1)
    df["definition"] = df["country"].map(DEFINITIONS)
    order = {c: i for i, c in enumerate(COUNTRIES.values())}
    df = df.sort_values(["country", "year_ending_june"], key=lambda s: s.map(order) if s.name == "country" else s)
    return df[["country", "year_ending_june", "net_migration", "population_start", "population_end",
               "population_growth", "population_growth_pct", "net_migration_per_1000_pop",
               "net_migration_share_of_growth_pct", "status", "definition", "net_migration_source",
               "population_source"]].reset_index(drop=True)


def gdp_table(gdp, pop):
    g = gdp[gdp["country_code"].isin(list(COUNTRIES))].merge(
        pop[["country_code", "year", "population"]], on=["country_code", "year"], how="left")
    g = g.sort_values(["country_code", "year"], ignore_index=True)
    by = g.groupby("country_code")
    g["gdp_per_capita_growth_pct"] = by["gdp_per_capita_usd_2015"].transform(
        lambda s: (100 * (s / s.shift(1) - 1)).round(2))
    g["population_growth_pct"] = by["population"].transform(lambda s: (100 * (s / s.shift(1) - 1)).round(2))
    g["country"] = g["country_code"].map(COUNTRIES)
    g["gdp_per_capita_usd_2015"] = g["gdp_per_capita_usd_2015"].round(0)
    return g[["country", "country_code", "year", "gdp_per_capita_usd_2015", "gdp_per_capita_growth_pct",
              "population", "population_growth_pct"]]


def main():
    can_pop, can_mig = statcan()
    uk, uk_reason, t2_gap = ons()
    us = uscensus()
    wb_gdp = worldbank(WB_GDP, "gdp_per_capita_usd_2015")
    wb_pop = worldbank(WB_POP, "population")
    cmp_ = comparison([australia_years(), canada_years(can_pop, can_mig), uk_years(uk, wb_pop), us_years(us)])
    gdp = gdp_table(wb_gdp, wb_pop)
    outs = {TIDY / "statcan_population_quarterly.csv": can_pop,
            TIDY / "statcan_international_migration_quarterly.csv": can_mig,
            TIDY / "ons_net_migration_uk.csv": uk, TIDY / "ons_visa_migration_by_reason_uk.csv": uk_reason,
            TIDY / "uscensus_population_components.csv": us, TIDY / "worldbank_gdp_per_capita.csv": wb_gdp,
            TIDY / "worldbank_population.csv": wb_pop, HERE / "international_migration_comparison.csv": cmp_,
            HERE / "international_gdp_per_capita.csv": gdp}
    for path, df in outs.items():
        write_table(df, path)

    # checks
    nat = {"AUS": australia_years().set_index("year_ending_june")["population_end"],
           "CAN": can_pop[can_pop["geo"].eq("Canada") & can_pop["quarter_start"].str.endswith("-07")]
                  .assign(y=lambda d: d["quarter_start"].str[:4].astype(int)).set_index("y")["population"],
           "USA": us[us["geo"].eq("United States") & us["measure"].eq("population_july1")].set_index("year")["value"]}
    wbp = wb_pop.set_index(["country_code", "year"])["population"]
    pop_gap = {}
    for cc, s in nat.items():
        yrs = [y for y in s.index if (cc, y) in wbp.index and y >= 2015]
        pop_gap[cc] = round(float(max(abs(100 * (wbp[(cc, y)] / s[y] - 1)) for y in yrs)), 3)
    c = can_mig[can_mig["geo"].eq("Canada")].pivot(index="quarter_start", columns="component", values="persons")
    ne_gap = float((c["Net emigration"] - (c["Emigrants"] - c["Returning emigrants"]
                                           + c["Net temporary emigration"])).abs().max())
    uk_net = uk[uk["flow"].eq("Net migration")].set_index("year_ending")["estimate"]
    uk_in = uk[uk["flow"].eq("Immigration")].set_index("year_ending")["estimate"]
    uk_out = uk[uk["flow"].eq("Emigration")].set_index("year_ending")["estimate"]
    reason_all = uk_reason[uk_reason["reason"].eq("All reasons")].set_index(["flow", "year_ending"])["persons"]
    reason_parts = uk_reason[uk_reason["reason"].isin(["Work (all)", "Study (all)", "Family",
                                                       "Humanitarian and asylum", "Other"])] \
        .groupby(["flow", "year_ending"])["persons"].sum()
    latest = cmp_.dropna(subset=["net_migration"]).groupby("country", sort=False).tail(1)   # already in year order
    checks = {
        "years_by_country": cmp_.groupby("country")["year_ending_june"].agg(["min", "max"]).astype(int)
                                .apply(list, axis=1).to_dict(),
        "latest_year_by_country": latest.set_index("country")[["year_ending_june", "net_migration",
                                                               "net_migration_per_1000_pop",
                                                               "population_growth_pct"]].to_dict("index"),
        "year_ending_june_2025": cmp_[cmp_["year_ending_june"].eq(2025)].set_index("country")[
            ["net_migration", "net_migration_per_1000_pop", "population_growth_pct"]].to_dict("index"),
        "canada_net_emigration_identity_max_abs": ne_gap,
        "uk_table2_vs_table1_estimate_max_abs": t2_gap,
        "uk_net_minus_immigration_plus_emigration_max_abs (rounding to 1,000)":
            float((uk_net - (uk_in - uk_out)).abs().max()),
        "uk_reason_parts_minus_all_reasons_max_abs (rounding)": float((reason_parts - reason_all).abs().max()),
        "uk_latest_period": uk["year_ending"].max(),
        "worldbank_vs_national_population_max_abs_pct_since_2015": pop_gap,
        "worldbank_latest_year": {cc: int(wb_gdp[wb_gdp["country_code"].eq(cc)]["year"].max()) for cc in COUNTRIES},
        "rows": {p.name: len(df) for p, df in outs.items()},
    }
    (HERE / "international_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))

    O = "Official data"
    m = {
        "quarter_start": ("First month of the quarter (YYYY-MM). Population is on the first day; migration covers the "
                          "three months starting then", SRC_CAN_POP, "", "Classification"),
        "geo": ("Country, province, territory or US state", "", "", "Classification"),
        "population": ("Population (persons)", "", "", "Official estimate"),
        "component": ("Migration component (immigrants, emigrants, returning emigrants, net temporary emigration, net "
                      "emigration, net non-permanent residents and their inflows and outflows)", SRC_CAN_MIG, "",
                      "Classification"),
        "persons": ("Persons in the period", "", "", "Official estimate"),
        "flow": ("Immigration, Emigration or Net migration", SRC_ONS, "", "Classification"),
        "year_ending": ("Last month of the 12-month period (YYYY-MM)", SRC_ONS, "", "Classification"),
        "period_label": ("ONS period label (P = provisional, R = revised)", SRC_ONS, "", "Classification"),
        "provisional": ("True if ONS marks the estimate provisional", SRC_ONS, "", "Classification"),
        "revised": ("True if ONS has revised the estimate since first publication", SRC_ONS, "", "Classification"),
        "estimate": ("Persons, all nationalities, rounded to the nearest 1,000 by ONS", SRC_ONS, "",
                     "Official statistics in development (ONS)"),
        "lower_bound": ("Lower end of the ONS uncertainty interval", SRC_ONS, "", "Official statistics in development (ONS)"),
        "upper_bound": ("Upper end of the ONS uncertainty interval", SRC_ONS, "", "Official statistics in development (ONS)"),
        "reason": ("Main reason for migrating. Visa holders only (EU+ visa holders and non-EU+ nationals added "
                   "together); British, Irish and EU settled status migrants are not split by reason. Before YE June "
                   "2021 only non-EU+ nationals (the EU+ visa category began in January 2021)", SRC_ONS, "",
                   "Classification"),
        "measure": ("population_july1, population_change, births, deaths, natural_change, net_international_migration, "
                    "net_domestic_migration, net_migration or residual", SRC_USCB, "", "Classification"),
        "year": ("Year (US: estimate year ending 30 June; World Bank: calendar year, population at mid-year)", "", "",
                 "Classification"),
        "value": ("Persons", SRC_USCB, "", "Official estimate (US Census Bureau)"),
        "period": ("Period the value covers", SRC_USCB, "", "Classification"),
        "country_code": ("ISO3 country code (World Bank)", SRC_WB, "", "Classification"),
        "country": ("Country name", "", "", "Classification"),
        "gdp_per_capita_usd_2015": ("GDP per person in constant 2015 US dollars", SRC_WB, "Calendar year",
                                    "Official data (World Bank, from national statistics)"),
        "is_aggregate": ("True for regional or income-group aggregates rather than single economies", SRC_WB, "",
                         "Classification"),
        "year_ending_june": ("Year ending 30 June (2025 = July 2024 to June 2025)", "", "", "Classification"),
        "net_migration": ("Net migration in the year (persons; see definition)", "", "12 months to June", O),
        "population_start": ("Population at the start of the year (1 July)", "", "", O),
        "population_end": ("Population at the end of the year (30 June or 1 July)", "", "", O),
        "population_growth": ("Population at the end minus the start", "", "", "Calculated from official data"),
        "population_growth_pct": ("Population growth (%)", "", "", "Calculated from official data"),
        "net_migration_per_1000_pop": ("Net migration per 1,000 people at the start of the year. The fairest way to "
                                       "compare countries of different size", "", "", "Calculated from official data"),
        "net_migration_share_of_growth_pct": ("Net migration as a share of population growth (%), blank when growth "
                                              "is zero or negative", "", "", "Calculated from official data"),
        "status": ("Provisional, revised or vintage notes from the source", "", "", "Classification"),
        "definition": ("How the country defines net migration", "", "", "Classification"),
        "net_migration_source": ("Source of the net migration figure", "", "", "Classification"),
        "population_source": ("Source of the population figures", "", "", "Classification"),
        "gdp_per_capita_growth_pct": ("Growth in real GDP per person on the previous calendar year (%)", SRC_WB, "",
                                      "Calculated from official data"),
    }
    rows = []
    for path, df in outs.items():
        prefix = "tidy/" if path.parent == TIDY else "analysis/"
        mm = dict(m)
        if path.name.startswith("statcan_"):
            mm["geo"] = ("Canada, province or territory", SRC_CAN_POP, "", "Classification")
            mm["population"] = ("Population on the first day of the quarter", SRC_CAN_POP, "",
                                "Official estimate (Statistics Canada)")
            mm["persons"] = ("Persons in the quarter", SRC_CAN_MIG, "", "Official estimate (Statistics Canada)")
        if path.name == "ons_visa_migration_by_reason_uk.csv":
            mm["persons"] = ("Persons, sum of the ONS EU+ visa holder and non-EU+ tables (each rounded to 1,000)",
                             SRC_ONS, "", "Official statistics in development (ONS), summed here")
            mm["provisional"] = ("True if ONS marks the period provisional", SRC_ONS, "", "Classification")
        if path.name == "uscensus_population_components.csv":
            mm["geo"] = ("United States or state name", SRC_USCB, "", "Classification")
        if path.name.startswith("worldbank_population"):
            mm["population"] = ("Population at mid-year", SRC_WB, "Calendar year", "Official data (World Bank)")
        if path.name == "international_gdp_per_capita.csv":
            mm["population"] = ("Population at mid-year", SRC_WB, "Calendar year", "Official data (World Bank)")
            mm["population_growth_pct"] = ("Population growth on the previous calendar year (%)", SRC_WB, "",
                                           "Calculated from official data")
        rows += dictionary_rows(prefix + path.name, df, mm)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
