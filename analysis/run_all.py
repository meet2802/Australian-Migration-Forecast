"""Rebuild every tidy and analysis table, in the right order, and the data dictionary.

Run from the Migration folder:
    python3 analysis/run_all.py                 every build script
    python3 analysis/run_all.py housing economy only the scripts whose names contain these words
    python3 analysis/run_all.py --from housing  this script and everything after it

Order matters: later scripts read earlier outputs (for example housing and economy read the population tables,
and the region script reads the occupation table). The Home Affairs visa tables in tidy/ come from a separate,
slower step that only needs rerunning when new workbooks are published:
    python3 analysis/visa_extraction/run_extraction.py .
"""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORDER = [
    "build_occupation_table.py",          # occupation spine, shortages, need, training, visas (national, state)
    "build_population_tables.py",         # population, net overseas migration, visa groups, history
    "build_migration_program_tables.py",  # permanent Migration Program outcomes 2024-25 (PDF)
    "build_sector_tables.py",             # industries: projections, employment, visas
    "build_region_tables.py",             # SA4 regions: employment by occupation, job ads, visas
    "build_housing_tables.py",            # dwelling approvals, starts and completions against population growth
    "build_economy_tables.py",            # GDP, GDP per person, productivity, state final demand, output per worker
    "build_international_tables.py",     # Australia, Canada, UK, US
    "build_job_ads_tables.py",            # job ads history by occupation and skill level
    "build_shortage_list_tables.py",      # 2025 shortage list at every level
    "build_occupation_profile_tables.py", # JSA ANZSCO occupation profiles, all tables
    "build_osca_tables.py",               # JSA OSCA 2021 Census occupation data
    "build_osca_classification_tables.py",  # ABS OSCA structure, correspondences and ANZSCO-OSCA crosswalk
    "build_named_sector_tables.py",       # plain-English sectors (groups of occupations), with industry alongside
    "build_settlement_outcomes_tables.py",  # ABS migrant settlement outcomes by visa stream
    "build_policy_inputs.py",             # each party's announced migration numbers, with sources
    "build_research_estimates.py",        # published estimates of migration's economic effects, with sources
    "build_scenario_model.py",            # each plan's effect on population, working-age people and homes
    "build_fact_check_cards.py",          # claims from every side, tested against the data by the same rules
    "build_everyday_comparisons.py",      # headline numbers as MCG crowds, people a day and familiar places
    "build_extra_analyses.py",            # do visas go where the shortages are; how sensitive the model is
    "describe_visa_tables.py",            # adds the Home Affairs visa tables in tidy/ to the data dictionary
    "export_web_data.py",                 # bundles the tables into the dashboard (docs/data, downloads)
]


def main():
    args = sys.argv[1:]
    todo = ORDER
    if args[:1] == ["--from"] and len(args) > 1:
        start = next(i for i, s in enumerate(ORDER) if args[1] in s)
        todo = ORDER[start:]
    elif args:
        todo = [s for s in ORDER if any(a in s for a in args)]
    root = HERE.parent
    for script in todo:
        t0 = time.time()
        print(f"== {script}", flush=True)
        res = subprocess.run([sys.executable, str(HERE / script)], cwd=root, capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stdout[-2000:])
            print(res.stderr[-4000:])
            raise SystemExit(f"{script} failed; stopped here.")
        print(f"   ok ({time.time() - t0:.0f}s)", flush=True)
    print("All done. Checks are in analysis/*_checks.json; column meanings in analysis/data_dictionary.csv;")
    print("row counts at each step in analysis/row_counts.csv. Open docs/index.html to see the dashboard.")


if __name__ == "__main__":
    main()
