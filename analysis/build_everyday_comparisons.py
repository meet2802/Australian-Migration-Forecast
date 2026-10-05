"""Everyday comparisons for the public layer: the dashboard's headline numbers as full MCGs, people a day, and the
populations of places people know.

Run from the Migration folder:  python3 analysis/build_everyday_comparisons.py
(Run build_population_tables.py, build_housing_tables.py, build_policy_inputs.py and build_scenario_model.py first.)

Outputs:
  analysis/everyday_reference_points.csv   the yardsticks (MCG capacity, territory and state populations), sourced
  analysis/everyday_comparisons.csv        each headline number with its comparisons and a plain-words sentence
"""
import pandas as pd

from _common import HERE, TIDY, dictionary_rows, update_dictionary, write_table

MCG = 100_024
MCG_SRC = ("Melbourne Cricket Club, MCG ticket information: 'a total capacity of 100,024' (checked 4 Oct 2026)",
           "https://www.mcg.org.au/plan-a-visit/seating-and-ticket-information/ticket-information")
PLACES = {"NT": "the Northern Territory", "ACT": "the ACT", "TAS": "Tasmania", "SA": "South Australia"}


def words(n):
    """Round a count for plain sentences: 2.9 MCGs, about 800 a day."""
    n = abs(n)
    if n >= 1000:
        return f"{int(round(n, -2)):,}"
    if n >= 100:
        return f"{int(round(n, -1)):,}"
    return f"{n:.0f}"


def main():
    p = pd.read_csv(TIDY / "abs_population_quarterly_by_state.csv")
    p["q"] = pd.PeriodIndex(p["quarter"], freq="M")
    last = p["q"].max()
    pops = p[p["q"].eq(last)].set_index("state")["erp"]
    a = p[p["state"].eq("AUS")].sort_values("q").set_index("q")
    a["nom_12m"] = a["nom"].rolling(4).sum()
    peak_q = a["nom_12m"].idxmax()
    paths = pd.read_csv(HERE / "scenario_nom_paths.csv")
    homes = pd.read_csv(HERE / "housing_vs_population_by_state.csv", dtype={"year_ending": str})
    homes = homes[homes["state"].eq("AUS")].sort_values("year_ending").iloc[-1]
    tvh = pd.read_csv(TIDY / "bp0019_temporary_visa_holders.csv", dtype=str)
    tvh["visa_holders"] = pd.to_numeric(tvh["visa_holders"])
    snap = tvh["snapshot_date"].max()
    sk = pd.read_csv(HERE / "named_sector_summary_national.csv")
    grants = int(sk.loc[sk["row_type"].eq("Total"), "visa_grants_primary"].iloc[0])
    on = paths[paths["plan"].eq("One Nation")].set_index("period")

    ref = pd.DataFrame([
        {"reference_point": "A full MCG", "size": MCG, "unit": "people", "source": MCG_SRC[0], "source_url": MCG_SRC[1],
         "number_type": "Venue capacity"},
        *[{"reference_point": f"Population of {name}", "size": int(pops[code]), "unit": "people",
           "source": f"ABS, National, state and territory population, {last.strftime('%B %Y')}",
           "source_url": "https://www.abs.gov.au/statistics/people/population/national-state-and-territory-population"
                         "/latest-release", "number_type": "Official estimate (ABS)"}
          for code, name in PLACES.items()]])

    S_POP = "tidy/abs_population_quarterly_by_state.csv"
    items = [
        ("Net overseas migration, latest 12 months", float(a.loc[last, "nom_12m"]), "people",
         f"Year to {last.strftime('%B %Y')}", S_POP, "Official estimate (ABS)"),
        ("Net overseas migration, record 12 months", float(a.loc[peak_q, "nom_12m"]), "people",
         f"Year to {peak_q.strftime('%B %Y')}", S_POP, "Official estimate (ABS)"),
        ("Population growth, latest 12 months", float(a["growth"].iloc[-4:].sum()), "people",
         f"Year to {last.strftime('%B %Y')}", S_POP, "Official estimate (ABS)"),
        ("Government plan, 2026-27", 245_000, "people", "2026-27", "analysis/scenario_nom_paths.csv",
         "Forecast (Treasury)"),
        ("Government plan, from 2027-28", 225_000, "people", "2027-28 onward", "analysis/scenario_nom_paths.csv",
         "Forecast (Treasury)"),
        ("Coalition cap, rule applied to the latest homes completed", float(homes["dwellings_completed_12m"]),
         "people", "Each year", "analysis/scenario_nom_paths.csv; analysis/housing_vs_population_by_state.csv",
         "Party policy applied to official data"),
        ("One Nation, each of the first three years (midpoint of our illustration)",
         float(on.loc["Year 1", "nom"]), "people", "Plan years 1 to 3", "analysis/scenario_nom_paths.csv",
         "Our illustration (not a party figure)"),
        ("One Nation cut to temporary visa holders (party's own breakdown)", -766_000.0, "people", "Over three years",
         "tidy/policy_migration_positions.csv", "Party policy (not law)", 3 * 365),
        ("One Nation cap from year four", 130_000, "people", "Plan year 4 onward", "analysis/scenario_nom_paths.csv",
         "Party policy (not law)"),
        ("Homes completed, latest 12 months", float(homes["dwellings_completed_12m"]), "homes",
         f"Year to {pd.Period(homes['year_ending'], 'M').strftime('%B %Y')}",
         "analysis/housing_vs_population_by_state.csv", "Official data (ABS)"),
        ("Temporary visa holders in Australia", float(tvh.loc[tvh["snapshot_date"].eq(snap), "visa_holders"].sum()),
         "people", pd.Timestamp(snap).strftime("%d %B %Y").lstrip("0"), "tidy/bp0019_temporary_visa_holders.csv",
         "Official data (Home Affairs)", None),
        ("Temporary skilled visas granted to main applicants", grants, "people", "2025-26",
         "analysis/named_sector_summary_national.csv", "Official data (Home Affairs)"),
    ]
    items = [i if len(i) == 7 else (*i, 365) for i in items]
    rows = []
    for item, value, unit, period, src, kind, days in items:
        mcg = value / MCG
        per_day = value / days if days else float("nan")
        when = ("" if not days else " a day" if days == 365 else " a day for three years")
        if unit == "people":
            # the best-known place whose population is closest in size
            code = min(PLACES, key=lambda c: abs(abs(value) / pops[c] - 1))
            times = abs(value) / pops[code]
            place_words = (f"about the population of {PLACES[code]}" if 0.9 <= times <= 1.1 else
                           f"about {times:.1f} times the population of {PLACES[code]}" if times > 1.1 else
                           f"about {100 * times:.0f}% of the population of {PLACES[code]}")
            lead = ("A cut of about " if "cut" in item else "More people leaving than arriving: about "
                    if value < 0 else "About ")
            daily = f", or about {words(per_day)} people{when}" if days else ""
            sentence = f"{lead}{abs(mcg):.1f} full MCGs{daily}; {place_words}"
        else:
            code, times, mcg = "", float("nan"), float("nan")
            sentence = f"About {words(per_day)} homes a day"
        rows.append({"item": item, "value": round(value), "unit": unit, "period": period, "number_type": kind,
                     "source_table": src, "mcg_crowds": round(mcg, 2), "per_day": per_day,
                     "nearest_place": code, "times_nearest_place": round(times, 2), "plain_words": sentence})
    comp = pd.DataFrame(rows)
    comp["per_day"] = comp["per_day"].round().astype("Int64")
    comp["times_nearest_place"] = comp["times_nearest_place"].astype(float)

    outs = {HERE / "everyday_reference_points.csv": ref, HERE / "everyday_comparisons.csv": comp}
    for path, df in outs.items():
        write_table(df, path)
    for r in comp.itertuples():
        print(f"{r.item}: {r.value:,} -> {r.plain_words}")

    C = "Classification"
    m = {
        "reference_point": ("The yardstick", "See source", "", C),
        "size": ("Its size", "See source", "", "See number_type"),
        "unit": ("Unit", "", "", C),
        "source": ("Where the size comes from", "", "", C),
        "source_url": ("Link to the source", "", "", C),
        "number_type": ("What kind of number it is", "", "", C),
        "item": ("The headline number being compared", "This project", "", C),
        "value": ("The number (negative = more people leaving than arriving)", "See source_table", "",
                  "See number_type"),
        "period": ("When the number applies", "", "", C),
        "source_table": ("Project table the number comes from", "This project", "", C),
        "mcg_crowds": ("value / 100,024 (full MCGs; people only)", MCG_SRC[0], "", "Derived (our calculation)"),
        "per_day": ("value spread over the days it covers (blank for a count at one date)", "", "",
                    "Derived (our calculation)"),
        "nearest_place": ("State or territory whose population is closest in size (people only)", S_POP, "", C),
        "times_nearest_place": ("value / that population", S_POP, "", "Derived (our calculation)"),
        "plain_words": ("Ready-to-use plain sentence (rounded)", "This project", "", "Derived (our calculation)"),
    }
    rows = []
    for path, df in outs.items():
        rows += dictionary_rows(f"analysis/{path.name}", df, m)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
