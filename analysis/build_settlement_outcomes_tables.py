"""ABS Migrant settlement outcomes, 2026: how permanent migrants are doing, by visa stream (skilled, family,
humanitarian), years since arrival and state, with the total population for comparison.

Run from the Migration folder:  python3 analysis/build_settlement_outcomes_tables.py

Input: MSODC01_2026.xlsx (ABS, released 22 September 2026). Sources inside the ABS release: 2021 Census linked to
settlement records (ACMID), and PLIDA for income (2023-24) and health services (2024).
Limit: this shows employment, income and other outcomes by visa stream. It does not show whether migrants work in
the occupation they were selected for; no official source publishes that.

Outputs:
  tidy/abs_migrant_settlement_outcomes.csv            every table, long format
  tidy/abs_migrant_settlement_outcomes_footnotes.csv  the ABS footnotes for each table
  analysis/migrant_outcomes_by_stream.csv             key indicators for Australia by visa stream and years since
                                                      arrival, with the total population alongside
  analysis/settlement_outcomes_checks.json
"""
import json
import re

import pandas as pd

from _common import HERE, ROOT, TIDY, clean_label, dictionary_rows, log_rows, num, state_code, update_dictionary, write_table

XLSX = ROOT / "MSODC01_2026.xlsx"
SRC = "ABS, Migrant settlement outcomes, 2026 (released 22 September 2026), MSODC01_2026.xlsx"
TABLES = ["Table 1", "Table 2a", "Table 2b", "Table 3a", "Table 3b", "Table 3c", "Table 3d", "Table 4", "Table 5a",
          "Table 5b", "Table 6"]
MEASURE = {"Persons (no.)": "persons", "Proportion (%)": "proportion_pct", "Services (no.)": "services",
           "$": "median_income_aud"}
POP_ORDER = ["Permanent Skilled migrants", "Permanent Family migrants", "Permanent Humanitarian migrants",
             "Total permanent migrants", "Total population"]
ARRIVAL_ORDER = ["Arrived within 5 years", "5-10 years since arrival", "More than 10 years since arrival", "Total"]


def parse(sheet):
    raw = pd.read_excel(XLSX, sheet_name=sheet, header=None, dtype=object)
    title = str(raw.iloc[1, 0])
    m = re.match(r"^\s*Table \w+: (.*), (\d{4}(?:-\d{2})?)\s*$", title)
    topic, period = (m.group(1), m.group(2)) if m else (title, "")
    h = raw.index[raw[0].astype(str).str.strip().eq("Population")][0]
    end = raw.index[raw[0].astype(str).str.strip().eq("Footnotes")][0]
    cols = [c for c in raw.columns[3:] if raw.loc[h - 2, c] is not None and pd.notna(raw.loc[h - 2, c])]
    measures = raw.loc[h, cols].ffill()
    meta = {c: (clean_label(raw.loc[h - 2, c]),
                clean_label(raw.loc[h - 1, c]) if pd.notna(raw.loc[h - 1, c]) else "",
                MEASURE[str(measures[c]).strip()]) for c in cols}
    rows, group, last_key = [], "", None
    for i in range(h + 1, end):
        r = raw.loc[i]
        if pd.isna(r[0]):
            continue
        pop, st, ind = clean_label(r[0]), state_code(r[1]), clean_label(r[2]) if pd.notna(r[2]) else ""
        assert st, (sheet, r[1])
        if (pop, st) != last_key:
            group, last_key = "", (pop, st)
        vals = [r[c] for c in cols]
        if all(pd.isna(v) for v in vals):        # a section heading such as 'Broad type of service'
            group = ind
            continue
        for c, v in zip(cols, vals):
            arr, per, meas = meta[c]
            x = num(v)
            note = "" if pd.isna(v) or not pd.isna(x) else str(v).strip()
            rows.append({"table": sheet, "topic": topic, "reference_period": period, "population": pop, "state": st,
                         "indicator_group": group, "indicator": ind, "arrival_group": arr, "arrival_period": per,
                         "measure": meas, "value": x, "value_note": note})
    notes = []
    for i in range(end + 1, len(raw)):
        t = str(raw.loc[i, 0]).strip()
        mm = re.match(r"^\((\w{1,2})\)\s*(.*)$", t)
        if mm:
            notes.append({"table": sheet, "marker": mm.group(1), "footnote": mm.group(2)})
    return pd.DataFrame(rows), pd.DataFrame(notes)


def summary(df):
    a = df[df["state"].eq("AUS")]

    def pick(table, indicator, measure, startswith=False):
        x = a[a["table"].eq(table) & a["measure"].eq(measure)]
        x = x[x["indicator"].str.startswith(indicator)] if startswith else x[x["indicator"].eq(indicator)]
        assert not x.duplicated(["population", "arrival_group"]).any(), (table, indicator)
        return x.set_index(["population", "arrival_group"])["value"]

    out = pd.DataFrame({
        "participation_pct": pick("Table 3c", "In the labour force", "proportion_pct"),
        "employment_to_population_pct": pick("Table 3c", "Employed", "proportion_pct"),
        "employed": pick("Table 3c", "Employed", "persons"),
        "unemployed": pick("Table 3c", "Unemployed", "persons"),
        "in_labour_force": pick("Table 3c", "In the labour force", "persons"),
        "median_total_income_aud": pick("Table 3b", "Total income", "median_income_aud", startswith=True),
        "receiving_unemployment_payments_pct": pick("Table 3a", "Receiving unemployment payments",
                                                    "proportion_pct"),
        "higher_education_qualification_pct": pick("Table 2b", "Higher education", "proportion_pct"),
        "proficient_english_pct": pick("Table 4", "Proficient in spoken English", "proportion_pct"),
        "home_owner_pct": pick("Table 6", "Tenure type: Owned", "proportion_pct"),
        "renting_pct": pick("Table 6", "Tenure type: Rented", "proportion_pct"),
        "rent_over_30pct_of_income_pct": pick("Table 6", "Rental affordability: Rent payments more than 30%",
                                              "proportion_pct", startswith=True),
        "australian_citizen_pct": pick("Table 1", "Australian citizen", "proportion_pct"),
    })
    out["unemployment_rate_pct"] = (100 * out["unemployed"] / out["in_labour_force"]).round(1)
    out = out.drop(columns=["unemployed", "in_labour_force"]).reset_index()
    out = out.dropna(subset=[c for c in out.columns if c not in ("population", "arrival_group")], how="all")
    out["population"] = pd.Categorical(out["population"], POP_ORDER, ordered=True)
    out["arrival_group"] = pd.Categorical(out["arrival_group"], ARRIVAL_ORDER, ordered=True)
    out = out.sort_values(["population", "arrival_group"]).reset_index(drop=True)
    out["population"] = out["population"].astype(str)
    out["arrival_group"] = out["arrival_group"].astype(str)
    cols = ["population", "arrival_group", "participation_pct", "employment_to_population_pct",
            "unemployment_rate_pct", "employed", "median_total_income_aud", "receiving_unemployment_payments_pct",
            "higher_education_qualification_pct", "proficient_english_pct", "home_owner_pct", "renting_pct",
            "rent_over_30pct_of_income_pct", "australian_citizen_pct"]
    return out[cols]


def main():
    parts, notes = zip(*(parse(t) for t in TABLES))
    df = pd.concat(parts, ignore_index=True)
    log_rows(f"Read and stacked {len(parts)} ABS tables (one row per value)", df, "MSODC01_2026.xlsx")
    fn = pd.concat(notes, ignore_index=True)
    s = summary(df)
    outs = {TIDY / "abs_migrant_settlement_outcomes.csv": df,
            TIDY / "abs_migrant_settlement_outcomes_footnotes.csv": fn,
            HERE / "migrant_outcomes_by_stream.csv": s}
    written = {p.name: write_table(d, p).name for p, d in outs.items()}

    tot = df[df["state"].eq("AUS") & df["table"].eq("Table 3c") & df["indicator"].eq("Employed")
             & df["measure"].eq("persons") & df["arrival_group"].eq("Total")].set_index("population")["value"]
    st = df[df["state"].ne("AUS") & df["table"].eq("Table 3c") & df["indicator"].eq("Employed")
            & df["measure"].eq("persons") & df["arrival_group"].eq("Total")].groupby("population")["value"].sum()
    checks = {
        "files_written": written,
        "tables_parsed": sorted(df["table"].unique().tolist()),
        "populations": [p for p in POP_ORDER if p in set(df["population"])],
        "states": sorted(df["state"].unique().tolist()),
        "value_notes": df.loc[df["value_note"].ne(""), "value_note"].value_counts().to_dict(),
        "employed_states_sum_vs_australia_pct (Other Territories in Australia only)":
            {p: round(100 * (st[p] / tot[p] - 1), 2) for p in tot.index if p in st.index},
        "australia_total_arrivals": s[s["arrival_group"].eq("Total")].set_index("population")[
            ["employment_to_population_pct", "unemployment_rate_pct", "median_total_income_aud"]].to_dict("index"),
        "rows": {p.name: len(d) for p, d in outs.items()},
    }
    (HERE / "settlement_outcomes_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))

    C, O = "Classification", "Official data (ABS)"
    m = {
        "table": ("ABS table number in MSODC01_2026.xlsx", SRC, "", C),
        "topic": ("What the table covers", SRC, "", C),
        "reference_period": ("Reference year: 2021 (Census-based tables), 2023-24 (income) or 2024 (health services)",
                             SRC, "", C),
        "population": ("Permanent Skilled, Family or Humanitarian migrants (arrived 2000 onward), all permanent "
                       "migrants, or the total population for comparison", SRC, "", C),
        "state": ("State or territory code; AUS = Australia (includes Other Territories)", SRC, "", C),
        "indicator_group": ("Section heading the indicator sits under, where the table has one", SRC, "", C),
        "indicator": ("Indicator (ABS footnote markers removed; see the footnotes table)", SRC, "", C),
        "arrival_group": ("Years since arrival: within 5 years, 5-10 years, more than 10 years, or Total", SRC, "", C),
        "arrival_period": ("Arrival years covered by the arrival group (blank for Total)", SRC, "", C),
        "measure": ("persons, proportion_pct, services or median_income_aud", SRC, "", C),
        "value": ("Value (blank where ABS shows a marker; see value_note)", SRC, "", O),
        "value_note": ("ABS marker shown instead of a number, if any", SRC, "", C),
        "marker": ("Footnote letter", SRC, "", C),
        "footnote": ("Footnote text", SRC, "", C),
        "participation_pct": ("Share of people aged 15-64 in the labour force (%)", SRC, "Census 2021", O),
        "employment_to_population_pct": ("Share of people aged 15-64 who are employed (%)", SRC, "Census 2021", O),
        "unemployment_rate_pct": ("Unemployed as a share of the labour force (%)", SRC, "Census 2021",
                                  "Calculated from official data"),
        "employed": ("People aged 15-64 who are employed", SRC, "Census 2021", O),
        "median_total_income_aud": ("Median total income including government payments, people aged 15-64 ($)", SRC,
                                    "2023-24", O),
        "receiving_unemployment_payments_pct": ("Share receiving unemployment payments (%)", SRC, "2023-24", O),
        "higher_education_qualification_pct": ("Share of people aged 15-64 whose highest non-school qualification is "
                                               "higher education (%)", SRC, "Census 2021", O),
        "proficient_english_pct": ("Share proficient in spoken English (%)", SRC, "Census 2021", O),
        "home_owner_pct": ("Share in owned homes, outright or with a mortgage (%)", SRC, "Census 2021", O),
        "renting_pct": ("Share renting (%)", SRC, "Census 2021", O),
        "rent_over_30pct_of_income_pct": ("Share of renters paying more than 30% of household income in rent (%)",
                                          SRC, "Census 2021", O),
        "australian_citizen_pct": ("Share who are Australian citizens (%)", SRC, "Census 2021", O),
    }
    rows = []
    for p, d in outs.items():
        prefix = "tidy/" if p.parent == TIDY else "analysis/"
        rows += dictionary_rows(prefix + written[p.name], d, m)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
