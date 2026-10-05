"""Fact-check cards: claims from every side of the migration debate, tested against official data by the same rules.

Run from the Migration folder:  python3 analysis/build_fact_check_cards.py
(Run build_population_tables.py, build_housing_tables.py, build_named_sector_tables.py, build_research_estimates.py and
the visa extraction first.)

Claims were collected on 4 Oct 2026 from primary sources where possible (media releases, Hansard, party pages, the
organisation's own statements) or news reports quoting the speaker. Each quote and its attribution was checked against
its source twice on 4 Oct 2026, through a text-extraction tool: check each against the live page before publishing.
Ground rule: no card assesses selecting people by nationality, ethnicity or religion.
Attribution (why something happened, or who caused it) is never tested: the cards test the numbers.

Verdicts, the same scale for every side:
  Accurate                 matches official data, with no important context missing
  Mostly accurate          right on the main point; a detail is off or needs context
  Partly accurate          some parts right, some wrong or misleading
  Inaccurate               official data contradicts the main point
  Too early to tell        a prediction or promise that data cannot test yet
  Plan (what it implies)   a policy proposal: the card shows what it would take, not whether it is true
  Can't test with our data needs data this project does not hold (the card says which)
For a single number, the claim counts as accurate within 5% of the official figure, mostly accurate within 15% and
partly accurate within 35%. A prediction about a policy's effects is judged against published research where it
exists (tidy/research_economic_effects.csv); otherwise it is 'Too early to tell'.

Outputs:
  tidy/fact_check_claims.csv        the claims as made: who, when, words, source
  tidy/treasury_nom_forecasts.csv   Treasury's NOM forecasts in each Budget and MYEFO since October 2022, with sources
  analysis/fact_check_cards.csv     one card per claim: verdict, what the data shows, key figures, caveats
  analysis/fact_check_checks.json
"""
import json

import pandas as pd

from _common import HERE, TIDY, dictionary_rows, log_rows, update_dictionary, write_table

CHECKED = "2026-10-04"
QUOTE_NOTE = ("Quote and attribution checked against the source twice on 4 Oct 2026 (text extraction); check against "
              "the live page before publishing")

# id, side, speaker, role, date, claim (neutral paraphrase), short quote, type, topic, source title, URL
CLAIMS = [
    ("LAB-1", "Labor", "Tony Burke", "Minister for Home Affairs", "2026-09-17",
     "Net overseas migration has fallen to 292,000 in the year to March 2026, 47% below its post-Covid peak",
     "NOM falling to 292,000, down 47 per cent from the post-Covid peak", "Fact claim", "Migration size and trend",
     "Migration reform to end rorts and bring in the skills Australia needs for a strong economy (media release)",
     "https://minister.homeaffairs.gov.au/TonyBurke/Pages/migration-reform-end-rorts-bring-skills-australia-needs-"
     "strong-economy.aspx"),
    ("LAB-2", "Labor", "Tony Burke", "Minister for Home Affairs", "2026-09-17",
     "The new changes are designed to bring net overseas migration to 245,000 in 2026-27 and 225,000 in 2027-28",
     "245,000 in this financial year and 225,000 in 2027/28", "Prediction or promise", "Migration size and trend",
     "Migration reform to end rorts and bring in the skills Australia needs for a strong economy (media release)",
     "https://minister.homeaffairs.gov.au/TonyBurke/Pages/migration-reform-end-rorts-bring-skills-australia-needs-"
     "strong-economy.aspx"),
    ("LAB-3", "Labor", "Tanya Plibersek", "Minister for Social Services", "2026-09-14",
     "The government has tripled the number of skilled visas going to people who work in construction",
     "We've tripled the number of skilled visas of people who work in construction.", "Fact claim",
     "Skills shortages", "'Race to the bottom': One Nation migration plan slammed (AAP)",
     "https://aapnews.aap.com.au/news/one-nation-pledges-to-slash-immigration-by-750-000"),
    ("LAB-4", "Labor", "Jim Chalmers", "Treasurer", "2026-09-17",
     "Net overseas migration has nearly halved from its peak and is falling faster than forecast",
     "nearly halved from its peak; ahead of forecast", "Fact claim", "Migration size and trend (forecasts)",
     "Migration: 17 Sep 2026: House debates (Hansard, Question Time, via OpenAustralia)",
     "https://www.openaustralia.org.au/debates/?id=2026-09-17.56.1&m=667"),
    ("COA-1", "Coalition", "Angus Taylor", "Leader of the Opposition", "2026-05-14",
     "Since Labor was elected, a record 1.4 million people have come in through migration, about 80% of population "
     "growth", "Since Labor was elected, it has brought in a record 1.4 million people", "Fact claim",
     "Migration size and trend", "Budget Address in Reply (Liberal Party transcript)",
     "https://www.liberal.org.au/2026/05/14/budget-address-in-reply"),
    ("COA-2", "Coalition", "Angus Taylor", "Leader of the Opposition", "2026-05-14",
     "Under Labor, Australia has had the worst fall in living standards of any developed country",
     "the worst collapse in living standards in the developed world", "Fact claim",
     "Economy (international comparison)", "Budget Address in Reply (Liberal Party transcript)",
     "https://www.liberal.org.au/2026/05/14/budget-address-in-reply"),
    ("COA-3", "Coalition", "Andrew Bragg", "Shadow Minister for Housing and Homelessness", "2026-09-16",
     "About 1.5 million people have come into Australia under Labor, against about 500,000 new homes",
     "1.5 million people and 500,000 new homes", "Fact claim", "Housing",
     "Migration: 16 Sep 2026: Senate debates (Hansard, via OpenAustralia)",
     "https://www.openaustralia.org.au/senate/?id=2026-09-16.179.1&m=100967"),
    ("COA-4", "Coalition", "Angus Taylor and Jonathon Duniam",
     "Leader of the Opposition; Shadow Minister for Home Affairs and Immigration", "2026-04-15",
     "Net permanent and long-term arrivals were 479,000 in the year to February 2026, and have run at 400,000 to "
     "500,000 a year under Labor", "net permanent and long-term arrivals of 479,000", "Fact claim",
     "Migration size and trend", "Migration numbers explode under Labor as standards slip (Liberal Party release)",
     "https://www.liberal.org.au/2026/04/15/migration-numbers-explode-under-labor-as-standards-slip"),
    ("ONP-1", "One Nation", "Pauline Hanson", "One Nation leader, Senator for Queensland", "2026-09-16",
     "Labor has added 1.6 million people to Australia's population since taking office in 2022",
     "the 1.6 million people Labor has already added since coming to office", "Fact claim",
     "Migration size and trend", "Migration: 16 Sep 2026: Senate debates (Hansard, via OpenAustralia)",
     "https://www.openaustralia.org.au/senate/?id=2026-09-16.179.1&m=100904"),
    ("ONP-2", "One Nation", "Pauline Hanson", "One Nation leader, Senator for Queensland", "2026-08-23",
     "Since taking office, Labor has repeatedly overshot its own net migration forecasts",
     "repeatedly blown its own migration forecasts since coming to government", "Fact claim",
     "Migration size and trend (forecasts)",
     "Social media post, as reported by ABC News: Hanson intervenes after One Nation MP says migration plan 'not too "
     "different' to Labor",
     "https://www.abc.net.au/news/2026-08-23/one-nation-migration-rates-similar-labor/107068282"),
    ("ONP-3", "One Nation", "Sean Bell", "One Nation Senator for NSW", "2026-09-16",
     "Almost four in five temporary residents live in capital cities, half of them in Sydney and Melbourne",
     "almost four out of five temporary residents live in capital cities", "Fact claim", "Temporary visas",
     "Migration: 16 Sep 2026: Senate debates (Hansard, via OpenAustralia)",
     "https://www.openaustralia.org.au/senate/?id=2026-09-16.179.1&m=100967"),
    ("ONP-4", "One Nation", "One Nation (party)", "Party policy page", "2026-09-15",
     "A One Nation government would cut temporary visas by 750,000, giving net negative migration for three years, "
     "then cap net migration at 130,000 a year",
     "cut temporary visas by 750,000, delivering net negative migration for three years", "Prediction or promise",
     "Migration size; temporary visas", "One Nation's Immigration Plan: Cut 750,000 Temporary Visas and Cap Migration",
     "https://www.onenation.org.au/immigration-radical-reset"),
    ("GRN-1", "Greens", "David Shoebridge", "Greens immigration spokesperson, Senator for NSW", "2026-09-17",
     "Twice as many people are on bridging visas now as three years ago, which he attributes to Labor policy",
     "double the number of people on bridging visas today", "Fact claim", "Temporary visas",
     "Labor's migration policy a bumbling return to Abbott era (Greens media release)",
     "https://greens.org.au/news/media-release/labors-migration-policy-bumbling-return-abbott-era"),
    ("GRN-2", "Greens", "Australian Greens (party)", "Party media release", "2026-09-17",
     "Partner visa waiting times have doubled in recent years to 40 months, and parent visas now take 30 years",
     "Partner visas wait times have doubled in recent years to 40 months", "Fact claim", "Visa processing",
     "Labor's migration policy a bumbling return to Abbott era (Greens media release)",
     "https://greens.org.au/news/media-release/labors-migration-policy-bumbling-return-abbott-era"),
    ("BUS-1", "Business", "Melissa Byrne (Master Builders Australia)", "National Director, Policy and Legal",
     "2026-09-18", "About 7,040 skilled visa holders were working in core construction trades as at September 2025",
     "around 7,040 skilled visa holders were working in core construction trade occupations", "Fact claim",
     "Skills shortages", "Opening Statement: Inquiry into the value of skilled migration to Australia (Master Builders)",
     "https://masterbuilders.com.au/opening-statement-inquiry-into-the-value-of-skilled-migration-to-australia/"),
    ("BUS-2", "Business", "Luke Sheehy (Universities Australia)", "Chief Executive", "2026-05-15",
     "International students make up about 6% of Australia's rental market",
     "international students comprise only around six per cent of Australia's rental market", "Fact claim",
     "Housing; students", "International students not low-hanging fruit in race to the bottom (media release)",
     "https://universitiesaustralia.edu.au/media-item/international-students-not-low-hanging-fruit-in-race-to-the-"
     "bottom/"),
    ("BUS-3", "Business", "Andrew McKellar (ACCI)", "Chief Executive", "2026-09-14",
     "Major cuts to skilled migration would damage the economy, hit the federal budget and weaken the capacity to "
     "provide services and lift living standards",
     "Major cuts that reduce skilled migration would damage our economy, hit the budget", "Prediction or promise",
     "Economy and budget", "'Race to the bottom': One Nation migration plan slammed (AAP)",
     "https://aapnews.aap.com.au/news/one-nation-pledges-to-slash-immigration-by-750-000"),
    ("UNI-1", "Union", "Australian Workers' Union", "National union (media release)", "2025-10-13",
     "Pacific Australia Labour Mobility (PALM) workers make up about 6% of agricultural workers and nearly a third of "
     "meat processing workers", "around 6% of all agricultural and nearly 33% of all meat processing workers",
     "Fact claim", "Jobs and wages", "Government must not miss PALM reform opportunity: AWU (media release)",
     "https://awu.net.au/national/news/2025/10/23179/government-must-not-miss-palm-reform-opportunity-awu/"),
    ("UNI-2", "Union", "ACTU", "Peak union body (submission to a parliamentary inquiry)", "2025-12-20",
     "Some employers game the system, using temporary migration as cheap labour instead of training local workers",
     "rather than training up and giving opportunities to local workers", "Fact claim (qualitative)", "Training",
     "Inquiry into the Value of Skilled Migration to Australia (ACTU submission)",
     "https://www.actu.org.au/policy/inquiry-into-the-value-of-skilled-migration-to-australia/"),
]

# Treasury NOM forecasts: document, date, financial year, forecast, where it is, URL
BP_OCT22 = ("Budget Paper No. 1 2022-23 (October), Statement 2, Table 2.2",
            "https://archive.budget.gov.au/2022-23-october/bp1/download/bp1_bs-2.pdf")
CT_MAY23 = ("As reported by The Canberra Times (9 May 2023), 'Treasury lowers its national population forecast'",
            "https://www.canberratimes.com.au/story/8189711/treasury-lowers-its-national-population-forecast/")
BP_MAY24 = ("Budget Paper No. 1 2024-25, Statement 2, Table 2.2",
            "https://archive.budget.gov.au/2024-25/bp1/download/bp1_bs-2.pdf")
BP_MAR25 = ("Budget Paper No. 1 2025-26, Statement 2, Table 2.2",
            "https://archive.budget.gov.au/2025-26/bp1/download/bp1_bs-2.pdf")
MYEFO25 = ("As reported by Rizvi, A. (2026, January 25), The New Daily; matches the ABC's report that the May 2026 "
           "Budget added 55,000 over 2025-26 and 2026-27", "https://www.thenewdaily.com.au/opinion/2026/01/25/"
           "migration-faulty-forecast")
BP_MAY26 = ("Budget Paper No. 3 2026-27, Appendix A, Table A.5",
            "https://budget.gov.au/content/bp3/download/bp3_14_appendix_a.pdf")
FORECASTS = [
    ("October 2022 Budget", "2022-10-25", "2022-23", 235_000, *BP_OCT22),
    ("October 2022 Budget", "2022-10-25", "2023-24", 235_000, *BP_OCT22),
    ("May 2023 Budget", "2023-05-09", "2022-23", 400_000, *CT_MAY23),
    ("May 2023 Budget", "2023-05-09", "2023-24", 315_000, *CT_MAY23),
    ("May 2023 Budget", "2023-05-09", "2024-25", 260_000, *CT_MAY23),
    ("May 2024 Budget", "2024-05-14", "2023-24", 395_000, *BP_MAY24),
    ("May 2024 Budget", "2024-05-14", "2024-25", 260_000, *BP_MAY24),
    ("May 2024 Budget", "2024-05-14", "2025-26", 255_000, *BP_MAY24),
    ("March 2025 Budget", "2025-03-25", "2024-25", 335_000, *BP_MAR25),
    ("March 2025 Budget", "2025-03-25", "2025-26", 260_000, *BP_MAR25),
    ("March 2025 Budget", "2025-03-25", "2026-27", 225_000, *BP_MAR25),
    ("December 2025 MYEFO", "2025-12", "2025-26", 260_000, *MYEFO25),
    ("December 2025 MYEFO", "2025-12", "2026-27", 225_000, *MYEFO25),
    ("May 2026 Budget", "2026-05-12", "2025-26", 295_000, *BP_MAY26),
    ("May 2026 Budget", "2026-05-12", "2026-27", 245_000, *BP_MAY26),
    ("May 2026 Budget", "2026-05-12", "2027-28", 225_000, *BP_MAY26),
]
# The first forecast this government made for each completed year
FIRST_FORECAST = {"2022-23": "October 2022 Budget", "2023-24": "May 2023 Budget", "2024-25": "May 2024 Budget"}

NOT_TESTED = {
    "COA-2": "OECD comparisons of real household disposable income per person (we hold GDP per person for four "
             "countries only)",
    "COA-4": "ABS Overseas Arrivals and Departures (permanent and long-term movements), which counts intended stays",
    "ONP-3": "ABS 'Temporary visa holders in Australia' (Census-linked), by capital city",
    "BUS-2": "ABS Census housing tenure for temporary visa holders, and the study the release cites",
    "UNI-1": "Department of Employment PALM scheme data by industry, against ABS Labour Force employment",
    "GRN-2": "Home Affairs processing times by visa subclass over several years (its online tool shows only current "
             "times)",
}


def verdict_for(claimed, actual):
    gap = abs(claimed - actual) / abs(actual)
    if gap <= 0.05:
        return "Accurate"
    if gap <= 0.15:
        return "Mostly accurate"
    return "Partly accurate" if gap <= 0.35 else "Inaccurate"


def fmt(x):
    return f"{int(round(x)):,}"


def day(iso):
    t = pd.Timestamp(iso)
    return f"{t.day} {t.strftime('%B %Y')}"


class Data:
    def __init__(self):
        p = pd.read_csv(TIDY / "abs_population_quarterly_by_state.csv")
        p = p[p["state"].eq("AUS")].copy()
        p["q"] = pd.PeriodIndex(p["quarter"], freq="M")
        self.q = p.sort_values("q").set_index("q")
        self.q["nom_12m"] = self.q["nom"].rolling(4).sum()
        d = pd.read_csv(TIDY / "abs_dwellings_commenced_completed_by_state.csv")
        d = d[d["state"].eq("AUS") & d["activity"].eq("Completed") & d["building_type"].eq("All dwellings")
              & d["sector"].eq("All sectors") & d["series_type"].eq("Original")].copy()
        d["q"] = pd.PeriodIndex(d["quarter"], freq="M")
        self.homes = d.set_index("q")["dwellings"]
        self.grants = pd.read_csv(TIDY / "skilled_grants_occupation6_national.csv", dtype=str)
        self.grants["count"] = pd.to_numeric(self.grants["count"])
        self.holders = pd.read_csv(TIDY / "skilled_holders_occupation6_national.csv", dtype=str)
        self.holders["count"] = pd.to_numeric(self.holders["count"])
        self.tvh = pd.read_csv(TIDY / "bp0019_temporary_visa_holders.csv", dtype=str)
        self.tvh["visa_holders"] = pd.to_numeric(self.tvh["visa_holders"])
        sec = pd.read_csv(HERE / "named_sectors.csv")
        self.sector_codes = {r.sector_id: set(r.unit_group_codes.split()) for r in sec.itertuples()}
        self.sectors = pd.read_csv(HERE / "named_sector_summary_national.csv").set_index("sector_id")
        self.research = pd.read_csv(TIDY / "research_economic_effects.csv")
        self.paths = pd.read_csv(HERE / "scenario_nom_paths.csv")
        self.fc = pd.DataFrame(FORECASTS, columns=["document", "published", "financial_year", "nom_forecast",
                                                   "where_in_source", "source_url"])

    def window(self, col, start, end):
        s = self.q.loc[pd.Period(start, "M"):pd.Period(end, "M"), col]
        return float(s.sum()), len(s)

    def growth(self, start, end):
        erp0 = float(self.q.loc[pd.Period(start, "M") - 3, "erp"])
        return float(self.q.loc[pd.Period(end, "M"), "erp"]) - erp0

    def fy(self, fy):
        y = int(fy[:4])
        return self.window("nom", f"{y}-09", f"{y + 1}-06")


def card(verdict, shows, figures, tables, caveats=""):
    return {"verdict": verdict, "what_the_data_shows": shows, "key_figures": json.dumps(figures),
            "evidence_tables": tables, "caveats": caveats}


def lab1(d):
    last = d.q.index.max()
    latest = float(d.q.loc[last, "nom_12m"])
    peak_q = d.q["nom_12m"].idxmax()
    peak = float(d.q.loc[peak_q, "nom_12m"])
    fall = 100 * (1 - latest / peak)
    v = "Accurate" if verdict_for(292_000, latest) == "Accurate" and abs(fall - 47) <= 2 else "Mostly accurate"
    return card(v, f"ABS: net overseas migration was {fmt(latest)} in the year to {last.strftime('%B %Y')}, "
                   f"{fall:.0f}% below the peak of {fmt(peak)} in the year to {peak_q.strftime('%B %Y')}.",
                {"nom_latest_12m": latest, "peak_12m": peak, "fall_pct": round(fall, 1)},
                "tidy/abs_population_quarterly_by_state.csv")


def lab2(d):
    last = d.q.index.max()
    latest = float(d.q.loc[last, "nom_12m"])
    so_far, n = d.fy("2025-26")
    return card("Too early to tell",
                f"The first ABS figures for 2026-27 (the September quarter 2026) are due in March 2027. For "
                f"context: NOM was {fmt(latest)} in the year to {last.strftime('%B %Y')}, and {fmt(so_far)} in the "
                f"first {3 * n} months of 2025-26. Treasury's May 2026 Budget forecast for 2025-26 is 295,000.",
                {"nom_latest_12m": latest, "nom_2025_26_so_far": so_far},
                "tidy/abs_population_quarterly_by_state.csv; tidy/treasury_nom_forecasts.csv",
                "A forecast, not law; the government says its measures are designed to deliver it")


def lab3(d):
    g = d.grants[d.grants["applicant_type"].eq("Primary")
                 & d.grants["occupation_unit_group_code"].isin(d.sector_codes["construction"])]
    by = g.groupby("fy")["count"].sum()
    ratio = by["2025-26"] / by["2021-22"]
    v = "Accurate" if ratio >= 2.85 else ("Mostly accurate" if ratio >= 2.5 else "Partly accurate")
    return card(v, f"Home Affairs: temporary skilled visas granted to main applicants in building and construction "
                   f"jobs rose from {fmt(by['2021-22'])} in 2021-22, the year Labor took office, to "
                   f"{fmt(by['2025-26'])} in 2025-26: {ratio:.1f} times as many. The starting year was a pandemic "
                   f"low; in 2018-19 there were {fmt(by['2018-19'])}.",
                {"grants_2018_19": int(by["2018-19"]), "grants_2021_22": int(by["2021-22"]),
                 "grants_2025_26": int(by["2025-26"]), "times": round(ratio, 2)},
                "tidy/skilled_grants_occupation6_national.csv; analysis/named_sectors.csv",
                "Temporary skilled visas only (subclass 482, 457 and Skills in Demand); permanent skilled visas are "
                "not in this count. 'Construction' is our Building and construction sector")


def lab4(d):
    last = d.q.index.max()
    latest = float(d.q.loc[last, "nom_12m"])
    peak = float(d.q["nom_12m"].max())
    fall = 100 * (1 - latest / peak)
    budget = float(d.fc.query("document == 'May 2026 Budget' and financial_year == '2025-26'")["nom_forecast"].iloc[0])
    myefo = float(d.fc.query("document == 'December 2025 MYEFO' and financial_year == '2025-26'")["nom_forecast"]
                  .iloc[0])
    halved = 40 <= fall <= 55
    v = ("Accurate" if halved and latest <= myefo else "Mostly accurate" if halved and latest <= budget
         else "Partly accurate")
    return card(v, f"NOM is down {fall:.0f}% from its peak, close to half. The latest 12 months ({fmt(latest)}) are "
                   f"a little below the May 2026 Budget forecast for 2025-26 ({fmt(budget)}), but above the "
                   f"December 2025 forecast ({fmt(myefo)}) that it replaced.",
                {"fall_pct": round(fall, 1), "nom_latest_12m": latest, "budget_may2026_2025_26": budget,
                 "myefo_dec2025_2025_26": myefo},
                "tidy/abs_population_quarterly_by_state.csv; tidy/treasury_nom_forecasts.csv",
                "2025-26 is not finished; the full-year figure is due in December 2026")


def coa1(d):
    nom, n = d.window("nom", "2022-06", "2025-09")
    growth = d.growth("2022-06", "2025-09")
    share = 100 * nom / growth
    roll = d.q["nom"].rolling(n).sum()
    prev = roll[roll.index < pd.Period("2022-06", "M")]
    record = nom > prev.max()
    v = ("Accurate" if verdict_for(1_400_000, nom) == "Accurate" and abs(share - 80) <= 3 and record
         else "Mostly accurate")
    return card(v, f"ABS: NOM added {fmt(nom)} people from the June quarter 2022 to the September quarter 2025, the "
                   f"latest data when he spoke. That is {share:.0f}% of population growth ({fmt(growth)}). The "
                   f"highest total for any earlier {n} quarters was {fmt(prev.max())}. The period began as the "
                   f"borders reopened after Covid, when many students and workers returned.",
                {"nom": nom, "population_growth": growth, "share_pct": round(share, 1), "previous_high": prev.max()},
                "tidy/abs_population_quarterly_by_state.csv",
                "Counted from the June quarter 2022, when Labor took office (23 May 2022)")


def coa3(d):
    nom, _ = d.window("nom", "2022-06", "2025-12")
    growth = d.growth("2022-06", "2025-12")
    homes = float(d.homes.loc[pd.Period("2022-06", "M"):pd.Period("2025-12", "M")].sum())
    v_people, v_homes = verdict_for(1_500_000, nom), verdict_for(500_000, homes)
    v = "Accurate" if v_people == v_homes == "Accurate" else (
        "Partly accurate" if v_people == "Accurate" else "Inaccurate")
    return card(v, f"People: ABS NOM was {fmt(nom)} from the June quarter 2022 to the December quarter 2025, close to "
                   f"1.5 million. Homes: the ABS counts {fmt(homes)} homes completed over the same period, "
                   f"{100 * (homes / 500_000 - 1):.0f}% more than 500,000. Counting births minus deaths too, the "
                   f"population grew by {fmt(growth)}, or {growth / homes:.1f} people per home completed; the average "
                   f"household is 2.5 people (Census 2021).",
                {"nom": nom, "homes_completed": homes, "population_growth": growth,
                 "people_per_home_completed": round(growth / homes, 2)},
                "tidy/abs_population_quarterly_by_state.csv; tidy/abs_dwellings_commenced_completed_by_state.csv",
                "Completions are gross: homes knocked down are not subtracted")


def onp1(d):
    nom_dec, _ = d.window("nom", "2022-06", "2025-12")
    last = d.q.index.max()
    nom_now, _ = d.window("nom", "2022-06", str(last))
    growth_now = d.growth("2022-06", str(last))
    v = "Mostly accurate" if verdict_for(1_600_000, nom_now) == "Accurate" and growth_now > 1.1 * 1_600_000 else \
        verdict_for(1_600_000, nom_now)
    return card(v, f"Migration added {fmt(nom_dec)} people from the June quarter 2022 to the December quarter 2025 "
                   f"(the latest data when she spoke) and {fmt(nom_now)} to {last.strftime('%B %Y')}. Counting births "
                   f"minus deaths too, the population grew by {fmt(growth_now)} over that time. So 1.6 million is "
                   f"about right for migration alone, and short of total growth.",
                {"nom_to_dec_2025": nom_dec, "nom_to_latest": nom_now, "population_growth_to_latest": growth_now},
                "tidy/abs_population_quarterly_by_state.csv",
                "The claim does not say whether it means migration or all population growth")


def onp2(d):
    rows, above = [], 0
    for fy, doc in FIRST_FORECAST.items():
        f = float(d.fc.query("document == @doc and financial_year == @fy")["nom_forecast"].iloc[0])
        o, _ = d.fy(fy)
        above += o > f
        rows.append((fy, doc, f, o))
    v = "Accurate" if above == len(rows) else ("Partly accurate" if above else "Inaccurate")
    parts = "; ".join(f"{fy}: {fmt(o)} against {fmt(f)} ({doc})" for fy, doc, f, o in rows)
    return card(v, f"Each year's outcome came in above the government's first Budget forecast for it. {parts}. The "
                   f"gap has narrowed each year.",
                {fy: {"forecast": f, "outcome": o} for fy, _, f, o in rows},
                "tidy/treasury_nom_forecasts.csv; tidy/abs_population_quarterly_by_state.csv",
                "The forecasts are Treasury's. The 2022-23 gap came as international borders reopened")


def onp4(d):
    snap = d.tvh["snapshot_date"].max()
    tvh = float(d.tvh.loc[d.tvh["snapshot_date"].eq(snap), "visa_holders"].sum())
    on = d.paths[d.paths["plan"].eq("One Nation") & d.paths["period"].eq("Year 1")].iloc[0]
    lr = pd.read_csv(HERE / "population_long_run_australia.csv")
    rec = lr[lr["year"].ge(1920)].nsmallest(1, "nom").iloc[0]
    return card("Plan (what it implies)",
                f"Home Affairs counted {fmt(tvh)} temporary visa holders on {day(snap)}, so 750,000 is about "
                f"{100 * 750_000 / tvh:.0f}% of them. If all 766,000 in the party's own breakdown left over three "
                f"years, about {fmt(-on['nom_low'])} more people would leave than arrive each year. The lowest year "
                f"since the First World War was 2020-21, with the borders closed, when {fmt(-rec['nom'])} more "
                f"people left than arrived.",
                {"temporary_visa_holders": tvh, "snapshot": snap, "implied_nom_per_year_if_all_leave": on["nom_low"],
                 "record_low_nom": rec["nom"]},
                "tidy/bp0019_temporary_visa_holders.csv; analysis/scenario_nom_paths.csv; "
                "analysis/population_long_run_australia.csv",
                "Temporary visa holders include visitors and New Zealanders on Special Category visas, who are not in "
                "the party's targeted groups")


def grn1(d):
    br = d.tvh[d.tvh["visa_category"].eq("Bridging")].groupby("snapshot_date")["visa_holders"].sum()
    then_d, now_d = "2023-09-30", br[br.index <= "2026-09-17"].index.max()
    ratio = br[now_d] / br[then_d]
    v = "Accurate" if ratio >= 1.9 else ("Mostly accurate" if ratio >= 1.6 else "Partly accurate")
    return card(v, f"Home Affairs: {fmt(br[now_d])} people held bridging visas on {day(now_d)}, against "
                   f"{fmt(br[then_d])} on {day(then_d)}: {ratio:.1f} times as many, so more than double. The data "
                   f"does not show why; his explanation is not tested here.",
                {"bridging_then": int(br[then_d]), "bridging_now": int(br[now_d]), "times": round(ratio, 2)},
                "tidy/bp0019_temporary_visa_holders.csv",
                "Bridging visas cover people waiting on a decision, including appeals and onshore applications")


def bus1(d):
    h = d.holders[d.holders["applicant_type"].eq("Primary") & d.holders["snapshot_date"].eq("2025-09-30")]
    trades = h["occupation_unit_group_code"].fillna("").str.match(r"^(33\d\d|341\d)$")
    n = float(h.loc[trades, "count"].sum())
    occ = pd.read_csv(HERE / "occupation_skills_national.csv", dtype={"unit_group_code": str})
    workers = float(occ.loc[occ["unit_group_code"].str.match(r"^(33\d\d|341\d)$") & ~occ["not_further_defined"],
                            "employed_may2025"].sum())
    return card(verdict_for(7_040, n),
                f"Home Affairs: {fmt(n)} main applicants on temporary skilled visas were in construction and "
                f"electrical trades at 30 September 2025, close to 7,040 (their list of core trades may differ a "
                f"little). That is about {1000 * n / workers:.0f} for every 1,000 people working in those trades.",
                {"holders_30_sep_2025": n, "workers_may_2025": workers},
                "tidy/skilled_holders_occupation6_national.csv; analysis/occupation_skills_national.csv",
                "Our count covers ANZSCO construction trades (33) and electricians (341)")


def bus3(d):
    r = d.research
    tsy = float(r.loc[r["finding"].eq("Skill stream primary applicants"), "estimate"].iloc[0])
    gdp = float(r.loc[r["topic"].eq("GDP per person") & r["horizon"].eq("2065-66"), "estimate"].iloc[0])
    debt = float(r.loc[r["topic"].eq("Budget (debt)"), "estimate"].iloc[0])
    return card("Mostly accurate",
                f"Published estimates back the budget point: Treasury (2021) put each skilled primary applicant's "
                f"lifetime contribution at about ${fmt(tsy)} (net present value, 2018-19 dollars). The 2026 "
                f"Intergenerational Report, as reported, found that 185,000 a year instead of 235,000 leaves GDP per "
                f"person only about ${fmt(-gdp)} lower by 2065-66, with gross debt about {debt:g} points of GDP "
                f"higher. So the budget effect is clear; the effect on living standards per person is small.",
                {"treasury_skill_primary_npv": tsy, "igr_gdp_per_person_2065": gdp, "igr_debt_pp": debt},
                "tidy/research_economic_effects.csv",
                "Other researchers' estimates under their own assumptions. Check the IGR figures against its Appendix "
                "A4")


def uni2(d):
    s = d.sectors
    parts = [f"{s.loc[k, 'sector_name'].lower()}: {fmt(s.loc[k, 'visa_grants_primary'])} visas against "
             f"{fmt(s.loc[k, 'apprentice_completions'])} completions"
             for k in ["hospitality", "construction", "mechanics_metal"]]
    return card("Can't test with our data",
                f"Counts can't show why employers sponsor visas or whether visas replace training. For scale, "
                f"temporary skilled visa grants to main applicants (2025-26) and apprentice and trainee completions "
                f"(year to March 2026) were: {'; '.join(parts)}.",
                {k: {"visa_grants": int(s.loc[k, "visa_grants_primary"]),
                     "apprentice_completions": int(s.loc[k, "apprentice_completions"])}
                 for k in ["hospitality", "construction", "mechanics_metal"]},
                "analysis/named_sector_summary_national.csv",
                "Testing the claim would need employer-level data on sponsorship and training")


def not_tested(d, cid):
    shows = ""
    figures = {}
    if cid == "COA-4":
        last = d.q.index.max()
        latest = float(d.q.loc[last, "nom_12m"])
        shows = (f"This figure uses a different measure (intended stays). NOM, the official measure of how many people "
                 f"stay, was {fmt(latest)} in the year to {last.strftime('%B %Y')}. ")
        figures = {"nom_latest_12m": latest}
    return card("Can't test with our data", shows + f"Testing it needs: {NOT_TESTED[cid]}.", figures, "",
                "Not a judgement on the claim")


TESTS = {"LAB-1": lab1, "LAB-2": lab2, "LAB-3": lab3, "LAB-4": lab4, "COA-1": coa1, "COA-3": coa3, "ONP-1": onp1,
         "ONP-2": onp2, "ONP-4": onp4, "GRN-1": grn1, "BUS-1": bus1, "BUS-3": bus3, "UNI-2": uni2}


def main():
    d = Data()
    claims = pd.DataFrame(CLAIMS, columns=["card_id", "side", "speaker", "role", "date_said", "claim", "short_quote",
                                           "claim_type", "topic", "source_title", "source_url"])
    log_rows("Claims collected from every side", claims)
    claims["checked_on"] = CHECKED
    claims["quote_check"] = QUOTE_NOTE
    assert claims["short_quote"].str.split().str.len().le(14).all(), "quotes must stay under 15 words"
    cards = []
    for c in claims.itertuples():
        res = TESTS[c.card_id](d) if c.card_id in TESTS else not_tested(d, c.card_id)
        cards.append({"card_id": c.card_id, "side": c.side, "speaker": c.speaker, "date_said": c.date_said,
                      "claim": c.claim, "claim_type": c.claim_type, "topic": c.topic, **res,
                      "claim_source": c.source_title, "claim_url": c.source_url, "checked_on": CHECKED})
    cards = pd.DataFrame(cards)
    fc = d.fc.assign(number_type="Forecast (Treasury)", checked_on=CHECKED)
    outs = {TIDY / "fact_check_claims.csv": claims, TIDY / "treasury_nom_forecasts.csv": fc,
            HERE / "fact_check_cards.csv": cards}
    written = {p.name: write_table(df, p).name for p, df in outs.items()}
    checks = {"files_written": written, "cards": int(len(cards)),
              "by_side": cards.groupby("side").size().to_dict(),
              "verdicts_by_side": cards.groupby(["side", "verdict"]).size().unstack(fill_value=0).to_dict("index"),
              "verdicts": cards.set_index("card_id")["verdict"].to_dict()}
    (HERE / "fact_check_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))
    for r in cards.itertuples():
        print(f"\n{r.card_id} [{r.verdict}] {r.what_the_data_shows}")

    C = "Classification"
    m = {
        "card_id": ("Card id: side prefix and number", "This project", "", C),
        "side": ("Labor, Coalition, One Nation, Greens, Business or Union", "", "", C),
        "speaker": ("Who made the claim", "Source in claim_url / source_url", "", C),
        "role": ("The speaker's role when they made the claim", "Source in source_url", "", C),
        "date_said": ("Date the claim was made", "Source in source_url", "", "Date"),
        "claim": ("The claim in plain, neutral words (our paraphrase)", "This project", "", C),
        "short_quote": ("Short exact quote (under 15 words)", "Source in source_url", "", "Quote"),
        "claim_type": ("Fact claim, or prediction or promise", "This project", "", C),
        "topic": ("Topic of the claim", "This project", "", C),
        "source_title": ("Title of the source", "", "", C),
        "source_url": ("Link to the source", "", "", C),
        "checked_on": ("Date the claim and evidence were last checked", "", "", "Date"),
        "quote_check": ("How the quote was checked, and what to do before publishing", "This project", "", C),
        "verdict": ("Accurate, Mostly accurate, Partly accurate, Inaccurate, Too early to tell, Plan (what it "
                    "implies) or Can't test with our data. Rules at the top of build_fact_check_cards.py",
                    "This project", "", "Judgement (rules stated)"),
        "what_the_data_shows": ("Plain-words summary of the evidence, built from the evidence tables",
                                "See evidence_tables", "", "Derived (our calculation)"),
        "key_figures": ("The numbers behind the card, as JSON", "See evidence_tables", "", "Derived (our calculation)"),
        "evidence_tables": ("Project tables the evidence comes from", "This project", "", C),
        "caveats": ("Limits to keep next to the verdict", "This project", "", C),
        "claim_source": ("Title of the source of the claim", "", "", C),
        "claim_url": ("Link to the source of the claim", "", "", C),
        "document": ("Budget or MYEFO the forecast comes from", "Treasury", "", C),
        "published": ("Date the document was published", "Treasury", "", "Date"),
        "financial_year": ("Financial year the forecast is for", "Treasury", "", C),
        "nom_forecast": ("Net overseas migration forecast", "Treasury (see where_in_source)", "",
                         "Forecast (Treasury)"),
        "where_in_source": ("Where the number is in the source, or which report quoted it", "", "", C),
        "number_type": ("What kind of number it is", "", "", C),
    }
    rows = []
    for p, df in outs.items():
        prefix = "tidy/" if p.parent == TIDY else "analysis/"
        rows += dictionary_rows(prefix + written[p.name], df, m)
    update_dictionary(rows)


if __name__ == "__main__":
    main()
