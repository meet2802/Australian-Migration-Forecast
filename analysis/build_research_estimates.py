"""Published estimates of migration's economic effects, for the 'published research ranges' half of the agreed
hybrid method (our own mechanical model + published ranges).

Run from the Migration folder:  python3 analysis/build_research_estimates.py

Each row is one quantified finding with its comparison, horizon, method and citation. These are other people's
estimates under their own assumptions, not our results; keep them side by side with the model, not mixed into it.
Rows were checked on CHECKED. Two IGR 2026 figures come from SBS's reporting because the report's appendix could not
be read here; check them against Appendix A4 of the IGR before publishing.

Output: tidy/research_economic_effects.csv
"""
import pandas as pd

from _common import TIDY, dictionary_rows, update_dictionary, write_table

CHECKED = "2026-10-04"
PC = ("Productivity Commission (2016), Migrant intake into Australia (Inquiry Report No. 77; dated 13 April, released "
      "12 September 2016)", "https://www.homeaffairs.gov.au/reports-and-pubs/files/migration-system-aust-future-"
      "submissions/s-z/The_Productivity_Commission.PDF", "2016-09-12", "Official (Productivity Commission)")
TSY = ("Varela, P., Husek, N., Williams, T., Maher, R., & Kennedy, D. (2021), The lifetime fiscal impact of the "
       "Australian permanent migration program (Treasury Paper), The Treasury",
       "https://treasury.gov.au/sites/default/files/2021-12/p2021-220773_1.pdf", "2021-12-01", "Official (Treasury)")
IGR = ("The Treasury (2026, September 21), 2026 Intergenerational Report, as reported by SBS News (2026, September "
       "23), The numbers raising new questions about Australia's future wealth", "https://www.sbs.com.au/news/article/"
       "treasury-igr-migration-living-standards-gdp-per-capita/krs0abtoh", "2026-09-21",
       "Official (Treasury), via media report")
IGR_G = ("The Treasury (2026, September 21), 2026 Intergenerational Report, as reported by Commins, P. (2026, "
         "September 21), Think Australia would be better off with less migration? The numbers tell a different story, "
         "The Guardian (read via inkl)", "https://www.inkl.com/news/think-australia-would-be-better-off-with-less-"
         "migration-the-numbers-tell-a-different-story", "2026-09-21", "Official (Treasury), via media report")
RBA_ST = ("Saunders, T., & Tulip, P. (2019), A model of the Australian housing market (RBA Research Discussion Paper "
          "2019-01)", "https://www.rba.gov.au/publications/rdp/2019/2019-01/model-responses.html", "2019-03-01",
          "Central bank research")
BD = ("Brell, C., & Dustmann, C. (2019), Immigration and wage growth: The case of Australia, in RBA Conference "
      "Volume 2019", "https://www.rba.gov.au/publications/confs/2019/pdf/christian-dustmann.pdf", "2019-04-01",
      "Research review (RBA conference)")
RBA_H = ("Hunter, S. (2024, May 16), Housing market cycles and fundamentals [Speech], Reserve Bank of Australia",
         "https://www.rba.gov.au/speeches/2024/sp-ag-2024-05-16.html", "2024-05-16", "Central bank speech")

# topic, finding, estimate, low, high, unit, comparison, horizon, method, source, caveats
ROWS = [
    ("GDP per person", "Migration at the long-run average raises GDP per person, mainly because migrants are younger",
     7.0, None, None, "% of GDP per person (about $7,000 a person in 2013-14 dollars)",
     "NOM at the long-term historical average vs zero NOM", "2060", "Demographic and economic projection", PC,
     "Assumes the intake keeps its young age profile. Does not count congestion, environmental or housing costs"),
    ("Population ageing", "Share of the population aged 65 and over", 25.0, None, 30.0, "% of population",
     "Current NOM (estimate) vs zero NOM (estimate_high)", "2060", "Demographic projection", PC,
     "Migration delays ageing but does not stop it"),
    ("Wages and jobs of existing workers", "Recent immigrants had a negligible effect on the wages, employment and "
     "participation of existing workers at the aggregate level", None, None, None, "", "Econometric analysis "
     "commissioned for the inquiry", "Recent years before 2016", "Econometrics", PC,
     "Effects can be concentrated among lower-skilled and young workers"),
    ("Budget (lifetime fiscal impact)", "Lifetime fiscal cost of a parent visa holder, per adult", None, -410_000,
     -335_000, "$ net present value per adult (2015-16)", "Parent visa holder", "Lifetime",
     "Fiscal accounting model", PC, "Older arrivals use more health care and work less"),
    ("Budget (lifetime fiscal impact)", "Skill stream primary applicants", 415_000, None, None,
     "$ net present value per person (2018-19 dollars, 5% nominal discount rate)", "2018-19 permanent cohort",
     "Lifetime", "Fiscal microsimulation", TSY, "Employer sponsored and skilled independent are the largest positives"),
    ("Budget (lifetime fiscal impact)", "Partner visa primary applicants", -92_000, None, None,
     "$ net present value per person (2018-19 dollars, 5% nominal discount rate)", "2018-19 permanent cohort",
     "Lifetime", "Fiscal microsimulation", TSY, ""),
    ("Budget (lifetime fiscal impact)", "Parent visa primary applicants", -394_000, None, None,
     "$ net present value per person (2018-19 dollars, 5% nominal discount rate)", "2018-19 permanent cohort",
     "Lifetime", "Fiscal microsimulation", TSY, ""),
    ("Budget (lifetime fiscal impact)", "Humanitarian entrants", -400_000, None, None,
     "$ net present value per person (2018-19 dollars, 5% nominal discount rate)", "2018-19 permanent cohort",
     "Lifetime", "Fiscal microsimulation", TSY, "Humanitarian intake is not set on economic grounds"),
    ("Budget (lifetime fiscal impact)", "Whole 2018-19 permanent migrant cohort, average", 41_000, None, None,
     "$ net present value per person (2018-19 dollars, 5% nominal discount rate)", "2018-19 permanent cohort",
     "Lifetime", "Fiscal microsimulation", TSY, "$127,000 a person more positive than the 2018-19 population overall"),
    ("GDP per person", "Lower migration (185,000 a year instead of the 235,000 baseline) reduces GDP per person "
     "only slightly", -400, None, None, "$ per person", "NOM 185,000 vs 235,000 a year", "2065-66",
     "Long-run projection", IGR, "As reported by SBS; check IGR Appendix A4 (sensitivity analysis)"),
    ("GNI per person", "Higher migration (285,000 a year) raises gross national income per person only slightly",
     100, None, None, "$ per person", "NOM 285,000 vs 235,000 a year", "2065-66", "Long-run projection", IGR,
     "As reported by SBS; check IGR Appendix A4"),
    ("Population ageing", "Old-age dependency ratio (people 65+ per 100 of working age)", 40.2, 37.8, 43.0,
     "ratio", "Baseline NOM 235,000 (estimate), high 285,000 (estimate_low), low 185,000 (estimate_high); 27.4 today",
     "2065-66", "Long-run projection", IGR, "As reported by SBS; the ABC's IGR story gives about 29 now and 39 by "
                                            "2066 on another definition. Check IGR Appendix A4"),
    ("Budget (debt)", "Lower migration raises gross debt: about 32.2% of GDP instead of 27.4%", 4.8, None, None,
     "percentage points of GDP (most likely)", "NOM 185,000 vs 235,000 a year", "2065-66", "Long-run projection",
     IGR_G, "SBS says 'rise by 4.8 per cent'. 27.4% is the Treasurer's baseline; 32.2% is The Guardian's figure. The "
            "Guardian also says 'nearly 10 percentage points', which does not fit. Check IGR Appendix A4"),
    ("Housing (rents)", "The 2005-2018 population surge (adult population 3.3% higher by 2018) left real rents "
     "higher than otherwise", 9.0, None, None, "% higher real rents", "Population growth rising from 1.5% (2005) to "
     "a 2.4% peak (2008) vs staying at 1.5%", "2018", "Structural housing market model", RBA_ST,
     "Prices follow rents gradually. Larger than many local studies find; effects grow with geographic scale"),
    ("Wages and jobs of existing workers", "Review of Australian studies: effects on existing workers' earnings "
     "are modest and generally positive", None, 0.4, 1.5, "% earnings change per 1% increase in immigrants in a "
     "skill group (foreign-born population in Bond and Gaston; immigrant share in Kifle)", "Skill-group studies (Bond and Gaston 2011; Kifle 2009)", "Various", "Literature review", BD,
     "Some negative effects for workers with vocational qualifications, but not robust"),
    ("Housing (reference)", "Average household size; at 2.8 people per home Australia would need 1.2 million fewer "
     "dwellings", 2.5, None, 2.8, "people per household", "Recent (estimate) vs mid-1980s (estimate_high)",
     "2024", "Descriptive", RBA_H, "Just under 27 million people in about 11 million households (speech, May 2024)"),
]


def main():
    rows = []
    for topic, finding, est, low, high, unit, comp, horizon, method, src, caveats in ROWS:
        cite, url, date, kind = src
        rows.append({"topic": topic, "finding": finding, "estimate": est, "estimate_low": low,
                     "estimate_high": high, "unit": unit, "comparison": comp, "horizon": horizon, "method": method,
                     "evidence_type": kind, "source": cite, "source_url": url, "published": date,
                     "checked_on": CHECKED, "caveats": caveats})
    df = pd.DataFrame(rows)
    write_table(df, TIDY / "research_economic_effects.csv")
    print(df.groupby("topic").size().to_string())
    C, E = "Classification", "Published estimate (other researchers' model or analysis)"
    m = {
        "topic": ("Which effect: GDP per person, ageing, budget, wages and jobs, housing", "", "", C),
        "finding": ("The finding in plain words", "Source in this row", "", C),
        "estimate": ("Point estimate, where one is given", "Source in this row", "See horizon", E),
        "estimate_low": ("Low end of a range (or the second value named in comparison)", "Source in this row",
                         "See horizon", E),
        "estimate_high": ("High end of a range (or the second value named in comparison)", "Source in this row",
                          "See horizon", E),
        "unit": ("Unit of the estimate", "", "", C),
        "comparison": ("What is compared with what", "", "", C),
        "horizon": ("Year or period the estimate applies to", "", "", C),
        "method": ("How the estimate was made", "", "", C),
        "evidence_type": ("Who produced it: official agency, central bank, research review, or a media report of an "
                          "official report", "", "", C),
        "source": ("Citation (APA style)", "", "", C),
        "source_url": ("Link to the source", "", "", C),
        "published": ("Publication date", "", "", C),
        "checked_on": ("Date the row was last checked", "", "", C),
        "caveats": ("Assumptions and limits to keep next to the number", "", "", C),
    }
    update_dictionary(dictionary_rows("tidy/research_economic_effects.csv", df, m))


if __name__ == "__main__":
    main()
