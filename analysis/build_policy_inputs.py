"""Party plan inputs for the scenario layer: every migration number each plan has announced, with its source,
date and status, plus the net overseas migration (NOM) path each plan implies.

Run from the Migration folder:  python3 analysis/build_policy_inputs.py
(Run build_population_tables.py and build_housing_tables.py first: the Coalition's cap is tied to ABS dwelling
completions, and One Nation's illustrative range is compared with the lowest NOM on record.)

These are announcements and forecasts, not data. Nothing here is law. Every row carries its source and the date it
was published; re-check before publishing anything, because positions change. Rows were checked on CHECKED.
Ground rule: the tool models skills, not nationality. Country-based measures in any plan are recorded for
completeness but never modelled.

Outputs:
  tidy/policy_migration_positions.csv   one row per plan and measure, with source, status and notes
  analysis/scenario_nom_paths.csv       the NOM path each plan states or implies, by year
"""
import pandas as pd

from _common import HERE, TIDY, dictionary_rows, update_dictionary, write_table

CHECKED = "2026-10-04"
GOV, COA, ON, GRN = "Government (Labor)", "Coalition (Liberal-National)", "One Nation", "Greens"

SRC = {
    "bp3": ("Australian Government (2026), Budget 2026-27, Budget Paper No. 3, Appendix A, Table A.5",
            "https://budget.gov.au/content/bp3/download/bp3_14_appendix_a.pdf", "2026-05-12"),
    "burke": ("Burke, T. (2026, September 17), Migration reform to end rorts and bring in the skills Australia needs "
              "[Media release]", "https://minister.homeaffairs.gov.au/TonyBurke/Pages/migration-reform-end-rorts-"
              "bring-skills-australia-needs-strong-economy.aspx", "2026-09-17"),
    "presscl": ("Burke, T. (2026, September 17), Transcript: National Press Club address",
                "https://www.tonyburke.com.au/speechestranscripts/transcript-national-press-club-address-17-september-"
                "2026", "2026-09-17"),
    "abc_0917": ("ABC News (2026, September 17), Labor tightens visa rules as Tony Burke vows migration targets will be "
                 "met", "https://www.abc.net.au/news/2026-09-17/labor-immigration-crackdown-students-backpackers-"
                 "overstay-visa/107164354", "2026-09-17"),
    "ha_fact": ("Department of Home Affairs (2026), Changes to Student visa application rules [Factsheet]",
                "https://immi.homeaffairs.gov.au/Visa-subsite/files/changes-to-student-visa-applications-factsheet.pdf",
                "2026-10-02"),
    "tat_1002": ("The Australia Today (2026, October 2), Major international student visa changes take effect today as "
                 "Australia targets course and visa hopping", "https://www.theaustraliatoday.com.au/major-"
                 "international-student-visa-changes-take-effect-today-as-australia-targets-course-and-visa-hopping/",
                 "2026-10-02"),
    "npl": ("Study Australia (2025, August 11), Increased student intake for Australia in 2026",
            "https://www.studyaustralia.gov.au/en/tools-and-resources/news/increased-student-intake-for-australia-in-"
            "2026", "2025-08-11"),
    "npl27": ("Study Australia (2026, July 15), Australia confirms international education settings for 2027",
              "https://www.studyaustralia.gov.au/en/tools-and-resources/news/australia-confirms-international-"
              "education-settings-for-2027", "2026-07-15"),
    "planning": ("Department of Home Affairs, Migration Program planning levels (the page did not load here; figures "
                 "as reported by Baker McKenzie in May 2026, and by WorkVisaLawyers and VisaVerge in June 2026)",
                 "https://immi.homeaffairs.gov.au/what-we-do/migration-program-planning-levels", "2026-05-12"),
    "rcoa": ("Refugee Council of Australia (2026, May 13), 2026-27 Federal Budget: What it means for refugees",
             "https://www.refugeecouncil.org.au/2026-27-federal-budget-analysis/", "2026-05-13"),
    "eig": ("Erickson Immigration Group (2026, September 21), Australia's skilled visa processing priorities take "
            "effect", "https://eiglaw.com/australias-skilled-visa-processing-priorities-take-effect/", "2026-09-21"),
    "abc_0514": ("ABC News (2026, May 14), Opposition Leader Angus Taylor proposes migration cap tied to housing "
                 "construction", "https://www.abc.net.au/news/2026-05-14/angus-taylor-ties-migration-cap-to-"
                 "housing-budget-reply/106676622", "2026-05-14"),
    "sbs_0619": ("SBS News (2026, June 19), Which parties want to cut migration, and how far would they go?",
                 "https://www.sbs.com.au/news/article/migration-policy-labor-coalition-greens-one-nation/7dsd8r7y9",
                 "2026-06-19"),
    "abc_0919": ("ABC News (2026, September 19), Labor's migration target comes with a political catch",
                 "https://www.abc.net.au/news/2026-09-19/migration-labor-numbers-political-catch/107165434",
                 "2026-09-19"),
    "on_plan": ("One Nation (2026, September 14), One Nation commits to net-negative migration and cutting 750,000 "
                "temporary visas", "https://www.onenation.org.au/net-negative-migration-plan", "2026-09-14"),
    "on_reset": ("One Nation (2026, September 15), One Nation's immigration plan: cut 750,000 temporary visas and cap "
                 "migration", "https://www.onenation.org.au/immigration-radical-reset", "2026-09-15"),
    "tat_0914": ("The Australia Today (2026, September 14), Pauline Hanson announces plan to cut 750,000 temporary "
                 "visa holders in first three years (citing One Nation's policy document)",
                 "https://www.theaustraliatoday.com.au/pauline-hanson-announces-plan-to-cut-750000-temporary-visa-"
                 "holders-in-first-three-years/", "2026-09-14"),
    "abc_0914": ("ABC News (2026, September 14), 750k visas cut under One Nation plan",
                 "https://www.abc.net.au/news/2026-09-14/750k-visas-cut-under-one-nation-plan/107149702",
                 "2026-09-14"),
    "sbs_0824": ("SBS News (2026, August 24), 130,000 or 230,000? The migration figures One Nation is trying to "
                 "explain", "https://www.sbs.com.au/news/article/one-nation-immigration-target-130000-nom-explained/"
                 "5nxmzgngv", "2026-08-24"),
    "psnews": ("PS News (2026, September 14), One Nation unveils plan to slash temporary migration program",
               "https://psnews.com.au/one-nation-unveils-plan-to-slash-temporary-migration-program/185311/",
               "2026-09-14"),
    "dailyaus": ("The Daily Aus (2026, September 14), One Nation unveils its immigration policy: what's in it?",
                 "https://www.thedailyaus.com.au/politics/one-nation-immigration-cut-14-09-2026", "2026-09-14"),
    "greens": ("Australian Greens, Immigration (policy page, last modified 2 May 2025)",
               "https://greens.org.au/portfolios/immigration", "2025-05-02"),
}

S_GOV_FC = "Budget forecast; the government says its measures are designed to deliver it (not law)"
S_GOV_SET = "Set by the government (planning level, not law)"
S_COA = "Opposition policy, not finalised"
S_ON = "Party policy (not in government)"
S_GRN = "Party policy (not in government)"
REL = ("17 Sep 2026 release: the measures 'are designed to deliver the Net Overseas Migration forecasts in the Budget "
       "of 245,000 in this financial year and 225,000 in 2027/28'. The ABC reported Burke treating them as targets")
ON_SPLIT = "Party's split of the cut (from its policy document, as reported by The Australia Today)"

# plan, measure, period, value, value_text, unit, status, model_use, source key, notes
POSITIONS = [
    (GOV, "Net overseas migration", "2025-26", 295_000, "", "persons", "Budget forecast (not law)", "NOM path", "bp3",
     "Population parameter in the May 2026 Budget"),
    (GOV, "Net overseas migration", "2026-27", 245_000, "", "persons", S_GOV_FC, "NOM path", "bp3", REL),
    (GOV, "Net overseas migration", "2027-28", 225_000, "", "persons", S_GOV_FC, "NOM path", "bp3", REL),
    (GOV, "Net overseas migration", "2028-29", 225_000, "", "persons", "Budget projection (not law)", "NOM path",
     "bp3", ""),
    (GOV, "Net overseas migration", "2029-30", 225_000, "", "persons", "Budget projection (not law)", "NOM path",
     "bp3", ""),
    (GOV, "Permanent Migration Program", "2026-27", 185_000, "", "places", S_GOV_SET, "Context", "planning",
     "Same total as 2025-26"),
    (GOV, "Permanent Migration Program: Skill stream", "2026-27", 132_240, "", "places", S_GOV_SET, "Context",
     "planning", "About 71% of the program"),
    (GOV, "Permanent Migration Program: Family stream", "2026-27", 52_460, "", "places", S_GOV_SET, "Context",
     "planning", "Reported by WorkVisaLawyers and VisaVerge; Skill + Family + Special Eligibility = 185,000"),
    (GOV, "Permanent Migration Program: Special Eligibility", "2026-27", 300, "", "places", S_GOV_SET, "Context",
     "planning", "Reported by WorkVisaLawyers and VisaVerge"),
    (GOV, "International student new commencements (National Planning Level)", "2026", 295_000, "", "students",
     S_GOV_SET, "Context", "npl", "Not a cap: a priority level for visa processing. 270,000 in 2025"),
    (GOV, "International student new commencements (National Planning Level)", "2027", 295_000, "", "students",
     S_GOV_SET, "Context", "npl27", "Same as 2026. No active provider gets a lower allocation than in 2026"),
    (GOV, "Humanitarian Program", "2026-27", 20_000, "", "places", S_GOV_SET, "Context", "rcoa",
     "Unchanged since 2023-24"),
    (GOV, "Working holiday maker: second-year visas", "From the 17 Sep 2026 package", 45_000, "Ballot", "places",
     "Announced; no legislation needed", "Context", "abc_0917",
     "About 57,000 before. Also in Burke's Press Club address (17 Sep 2026)"),
    (GOV, "Working holiday maker: third-year visas", "From the 17 Sep 2026 package", 5_000, "Ballot", "places",
     "Announced; no legislation needed", "Context", "abc_0917",
     "About 31,000 before. Also in Burke's Press Club address (17 Sep 2026)"),
    (GOV, "Student visas: family members", "From 2 October 2026", None,
     "Not allowed unless exempt: PhD students, students sponsored by DFAT or Defence, foreign government scholarship "
     "holders, and eligible students from a Pacific or ASEAN country", "", "In force (regulations)", "Context",
     "ha_fact", "Current Student visa holders can no longer add family members. Families already in Australia are not "
                "separated"),
    (GOV, "Student visas: applying from inside Australia", "From 2 October 2026", None,
     "Most temporary visa holders can no longer apply for a Student visa onshore", "", "In force (regulations)",
     "Context", "ha_fact", "Exemptions include staying with the same provider or moving up a qualification level"),
    (GOV, "Student visas: changing course or provider", "Reported start mid-2027", None,
     "New visa needed; only moves to a higher qualification", "", "Announced; not yet in force", "Context",
     "tat_1002", "The Australia Today gives 1 July 2027; BusinessToday (3 Oct 2026) gives 30 June 2027"),
    (GOV, "Student intake: expression of interest system", "Proposed", None, "Needs legislation", "",
     "Proposal (needs Parliament)", "Context", "abc_0917", ""),
    (GOV, "Skilled visa processing priorities", "From 19 September 2026", None,
     "Ministerial Directions 121 and 122 replaced Direction 119", "", "In force (ministerial directions)", "Context",
     "eig", "Law firm summary; check the directions themselves. The ABC reported priority for construction, health "
            "care, agriculture, fisheries and teaching"),
    (COA, "Net overseas migration cap", "Each year", None,
     "Capped at the number of new homes completed in the previous year", "persons", S_COA, "NOM path", "abc_0514",
     "Announced in the Budget reply. Which visas would be cut is to be decided in office"),
    (COA, "Net overseas migration cap", "Each year", None, "Well under 200,000", "persons", S_COA, "NOM path",
     "sbs_0619", ""),
    (COA, "Net overseas migration cap (likely range)", "Each year", None, "150,000 to 170,000", "persons",
     "Reported likely range; policy not finalised", "NOM path", "abc_0919",
     "The ABC's estimate, not a published Coalition figure"),
    (ON, "Net overseas migration", "First three years in government", None, "Net negative (size not stated)",
     "persons", S_ON, "NOM path (our illustrative range; see scenario_nom_paths.csv)", "on_plan", ""),
    (ON, "Temporary visas (headline)", "Over three years", -750_000, "More than 750,000 fewer", "visas", S_ON,
     "Context", "on_plan", "The party's own modelling gives about 766,000 (next rows)"),
    (ON, "Temporary visa holders (party modelling, total)", "Over three years", -766_000,
     "From about 1.616 million to 850,000 in the targeted visa groups", "visa holders", S_ON,
     "Sets the low end of our illustrative NOM range for years 1 to 3", "tat_0914", ON_SPLIT),
    (ON, "Temporary visa holders: students", "Over three years", -240_000, "", "visa holders", S_ON, "Context",
     "tat_0914", "ABC: student visa holders from about 590,000 to 350,000 (the same cut)"),
    (ON, "Temporary visa holders: graduates", "Over three years", -230_000, "", "visa holders", S_ON, "Context",
     "tat_0914", "ABC: graduate visa holders from about 270,000 to 40,000 (the same cut)"),
    (ON, "Temporary visa holders: temporary skilled and dependants", "Over three years", -103_000, "", "visa holders",
     S_ON, "Context", "tat_0914", "Skilled visas themselves stay uncapped and demand-driven"),
    (ON, "Temporary visa holders: bridging visas", "Over three years", -113_000, "", "visa holders", S_ON, "Context",
     "tat_0914", ""),
    (ON, "Temporary visa holders: unlawful non-citizens", "Over three years", -80_000, "", "persons", S_ON, "Context",
     "tat_0914", "The same people as the roughly 80,000 overstayers below; do not count twice"),
    (ON, "Net migration cap", "After the first three years", 130_000, "Strict cap", "persons", S_ON, "NOM path",
     "on_reset", "The ABC reports it would be reviewed year on year; The Australia Today calls it a NOM ceiling"),
    (ON, "Net migration cap: workers outside the cap", "After the first three years", 100_000,
     "About 100,000 through Pacific labour schemes, aged care nurses and skilled workers, taking the total to "
     "about 230,000", "persons", "Statement by Barnaby Joyce; disputed (Pauline Hanson restated 130,000 the same day)",
     "NOM path (high case)", "sbs_0824", "Pauline Hanson describes the 130,000 as net overseas migration"),
    (ON, "International students: new intake", "Each year", 100_000, "Cap", "students", S_ON, "Context",
     "dailyaus", "Also reported by PS News"),
    (ON, "Family members of students and skilled visa holders", "Over three years", 0, "Cut to zero", "visas", S_ON,
     "Context", "abc_0914", "PS News reports 'largely denied'"),
    (ON, "Skilled visas", "Each year", None, "No cap; driven by employer demand", "", S_ON, "Context", "abc_0914",
     "The party's split still cuts 103,000 temporary skilled visa holders and dependants"),
    (ON, "Working holiday makers and Pacific labour scheme", "Each year", None, "Kept", "", S_ON, "Context",
     "abc_0914", ""),
    (ON, "Postgraduate STEM visa (new)", "Each year", 15_000, "About 15,000 expected; no cap", "visas", S_ON,
     "Context", "psnews", ""),
    (ON, "Visa overstayers", "Within three months", 80_000, "About 80,000 told to leave", "persons", S_ON,
     "Context", "psnews", "Same group as the 80,000 unlawful non-citizens above. SBS (June 2026) reported 75,000 under "
                          "an earlier version of the plan"),
    (ON, "Country-based entry restrictions", "Not stated", None,
     "Blocks migration from places under 'do not travel' advice (26 destinations named in reporting)", "", S_ON,
     "Not modelled (skills, not nationality)", "dailyaus",
     "Recorded so the plan is described in full; the tool never models selection by nationality"),
    (GRN, "Net overseas migration", "Not stated", None, "No cap or target", "", S_GRN, "NOM path", "greens",
     "SBS (June 2026): the only party not proposing cuts to overall migration"),
    (GRN, "Humanitarian Program", "Each year", 50_000, "", "places", S_GRN, "Context", "greens",
     "Plus an uncapped private sponsorship program. The program is 20,000 now"),
]


def positions():
    rows = []
    for plan, measure, period, value, text, unit, status, use, key, notes in POSITIONS:
        src, url, date = SRC[key]
        rows.append({"plan": plan, "measure": measure, "period": period, "value": value, "value_text": text,
                     "unit": unit, "status": status, "model_use": use, "source_key": key, "source": src,
                     "source_url": url, "published": date, "checked_on": CHECKED, "notes": notes})
    df = pd.DataFrame(rows)
    df["value"] = df["value"].astype("Int64")
    return df


def nom_paths():
    h = pd.read_csv(HERE / "housing_vs_population_by_state.csv", dtype={"year_ending": str})
    a = h[h["state"].eq("AUS")].dropna(subset=["dwellings_completed_12m"]).set_index("year_ending")
    fy25 = int(a.loc["2025-06", "dwellings_completed_12m"])
    latest_ye = a.index.max()
    latest = int(a.loc[latest_ye, "dwellings_completed_12m"])
    rule = (f"Cap = homes completed in the previous year. ABS completions: {fy25:,} in 2024-25 and {latest:,} in the "
            f"12 months to {pd.Period(latest_ye, 'M').strftime('%B %Y')}")
    gov_status = {"2025-26": "Budget forecast (not law)", "2026-27": S_GOV_FC, "2027-28": S_GOV_FC,
                  "2028-29": "Budget projection (not law)", "2029-30": "Budget projection (not law)"}
    rows = [{"plan": GOV, "year_basis": "Financial year", "period": fy, "nom": v, "nom_low": None, "nom_high": None,
             "basis": "2026-27 Budget forecast or projection", "source_key": "bp3", "status": gov_status[fy]}
            for fy, v in [("2025-26", 295_000), ("2026-27", 245_000), ("2027-28", 225_000), ("2028-29", 225_000),
                          ("2029-30", 225_000)]]
    rows += [{"plan": COA, "year_basis": "Years in government", "period": "Each year", "nom": None,
              "nom_low": 150_000, "nom_high": 170_000,
              "basis": rule + ". Reported likely range 150,000 to 170,000 (not finalised)",
              "source_key": "abc_0514; abc_0919", "status": S_COA}]
    # One Nation's first three years: the party says 'net negative' without a size. Decided on 4 October 2026: show
    # a range built only from the party's own numbers, clearly labelled as our illustration.
    lr = pd.read_csv(HERE / "population_long_run_australia.csv")
    rec = lr[lr["year"].ge(1920)].nsmallest(1, "nom").iloc[0]
    rec_label = f"{int(rec['year']) - 1}-{str(int(rec['year']))[2:]}" if "30 June" in rec["nom_reference"] else \
        str(int(rec["year"]))
    on_cut = 766_000
    low, mid = -round(on_cut / 3), -round(on_cut / 6)
    on_basis = (f"Our illustration, not a One Nation figure: the party says net negative but gives no size. High end 0 "
                f"(the smallest net-negative result). Low end {low:,} a year: the party's own {on_cut:,} fewer "
                f"temporary visa holders spread evenly over three years, if all of them leave and every other flow "
                f"(permanent migrants, New Zealanders, Australians leaving and returning) adds to zero. Model runs use "
                f"the midpoint, {mid:,}. For scale, NOM was {int(rec['nom']):,} in {rec_label}, with the borders "
                f"closed, the lowest since the First World War (ABS)")
    rows += [{"plan": ON, "year_basis": "Years in government", "period": f"Year {y}", "nom": mid, "nom_low": low,
              "nom_high": 0, "basis": on_basis, "source_key": "on_plan; tat_0914",
              "status": "Our illustration from the party's own figures (the party has not stated a size)"}
             for y in (1, 2, 3)]
    rows += [{"plan": ON, "year_basis": "Years in government", "period": "Year 4 onward", "nom": 130_000,
              "nom_low": 130_000, "nom_high": 230_000,
              "basis": "130,000 cap; about 230,000 if the roughly 100,000 workers Barnaby Joyce described sit outside "
                       "it (disputed: Pauline Hanson restated 130,000)", "source_key": "on_reset; sbs_0824",
              "status": S_ON}]
    rows += [{"plan": GRN, "year_basis": "Not stated", "period": "Each year", "nom": None, "nom_low": None,
              "nom_high": None, "basis": "No NOM target, so no path is modelled (the same rule as for every plan: "
                                         "only what a party's own figures support). Humanitarian intake 50,000 a "
                                         "year (20,000 now)", "source_key": "greens", "status": S_GRN}]
    df = pd.DataFrame(rows)
    for c in ["nom", "nom_low", "nom_high"]:
        df[c] = df[c].astype("Int64")
    df["checked_on"] = CHECKED
    return df


def main():
    pos = positions()
    paths = nom_paths()
    outs = {TIDY / "policy_migration_positions.csv": pos, HERE / "scenario_nom_paths.csv": paths}
    for path, df in outs.items():
        write_table(df, path)
    print(pos.groupby("plan").size().to_string())
    print(paths[["plan", "period", "nom", "nom_low", "nom_high"]].to_string())

    T, C = "Announcement or forecast (see status)", "Classification"
    m = {
        "plan": ("Whose plan: the government, the Coalition, One Nation or the Greens", "", "", C),
        "measure": ("What the number is about (NOM, program places, a visa type)", "", "", C),
        "period": ("When it applies, as the source states it", "", "", C),
        "value": ("The number, where one is stated (negative = a cut)", "Source in this row", "", T),
        "value_text": ("The position in words, for anything that is not a single number", "Source in this row", "", T),
        "unit": ("Unit of value", "", "", C),
        "status": ("Legal and political status: Budget forecast, planning level, party policy and so on. None of "
                   "these is law", "", "", C),
        "model_use": ("How the scenario layer uses the row: NOM path, Context, or not modelled", "This project", "", C),
        "source": ("Citation (APA style)", "", "", C),
        "source_url": ("Link to the source", "", "", C),
        "published": ("Date the source was published or last changed", "", "", C),
        "checked_on": ("Date the row was last checked against the source", "", "", C),
        "notes": ("Caveats, conflicting reports and context", "", "", C),
        "year_basis": ("Financial year (government) or years after taking office (opposition plans, whose start "
                       "date depends on an election)", "This project", "", C),
        "nom": ("NOM the plan states for the period (blank if not stated). One Nation years 1 to 3: the midpoint of "
                "our illustrative range (see status and basis)", "See source_key", "", T),
        "nom_low": ("Low end of a stated or reported range (One Nation years 1 to 3: our illustration)",
                    "See source_key", "", T),
        "nom_high": ("High end of a stated or reported range (One Nation years 1 to 3: our illustration)",
                     "See source_key", "", T),
        "basis": ("Where the numbers come from, in words", "", "", C),
        "source_key": ("Short key for the source; the same key in both policy tables points to the same source",
                       "This project", "", C),
    }
    rows = dictionary_rows("tidy/policy_migration_positions.csv", pos, m)
    rows += dictionary_rows("analysis/scenario_nom_paths.csv", paths, m)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
