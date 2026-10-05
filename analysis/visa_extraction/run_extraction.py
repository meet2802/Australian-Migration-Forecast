"""Extract the Home Affairs visa pivot workbooks (BP0014, BP0015, BP0016, BP0019) into tidy tables.

Usage (from the Migration folder):
    python3 analysis/visa_extraction/run_extraction.py .
    python3 analysis/visa_extraction/run_extraction.py . bp0019_holders     (only some jobs)

Reads the workbooks from that folder and writes tidy CSV tables into <folder>/tidy/, plus a run log in
tidy/_extraction_log.json. Needs Python 3.9+ and pandas. Run it again only when Home Affairs publishes new
workbooks; the build scripts in analysis/ read the tidy tables. The big BP0014 holders file takes about a minute.
Citizenship Country is summed out of every table on purpose (project ground rule: skills, not nationality).
"""
import datetime
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
JOBS = [
    ("bp0014l-temporary-resident-skilled-visa-holders-report-*.xlsx", "views/bp0014_holders.json"),
    ("bp0014ltemporary-resident-skilled-visas-granted-report-*.xlsx", "views/bp0014_granted.json"),
    ("bp0015l-student-visas-granted-report-*.xlsx", "views/bp0015_granted.json"),
    ("bp0015l-student-visas-lodged-report-*.xlsx", "views/bp0015_lodged.json"),
    ("bp0015l-student-visa-grant-rates-*.xlsx", "views/bp0015_grant_rates.json"),
    ("bp0016l-temporary-graduate-visa-granted-report-*.xlsx", "views/bp0016_granted.json"),
    ("bp0016l-temporary-graduate-visas-lodged-report-*.xlsx", "views/bp0016_lodged.json"),
    ("bp0019l-number-of-temporary-visa-holders-in-australia-*.xlsx", "views/bp0019_holders.json"),
]


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    folder = Path(sys.argv[1]).resolve()
    out = folder / "tidy"
    out.mkdir(exist_ok=True)
    log_path = out / "_extraction_log.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {"files": []}
    only = set(sys.argv[2:])
    for pattern, views in JOBS:
        if only and Path(views).stem not in only:
            continue
        matches = sorted(folder.glob(pattern))
        if not matches:
            print(f"skipped (not found): {pattern}")
            continue
        src = matches[-1]
        print(f"\n== {src.name}")
        before = set(out.glob("_summary_*.json"))
        subprocess.run([sys.executable, str(HERE / "extract_views.py"), str(src), str(out), str(HERE / views)],
                       check=True, stdout=subprocess.DEVNULL)
        new = sorted(set(out.glob("_summary_*.json")) - before) or sorted(
            out.glob("_summary_*.json"), key=lambda p: p.stat().st_mtime)[-1:]
        summary = json.loads(new[-1].read_text())
        for p in new:
            try:
                p.unlink()
            except OSError:
                print(f"   (could not remove {p.name}; it can be deleted by hand)")
        print(f"   {summary['records']:,} records read (expected {summary['expected_records']:,}),"
              f" {summary['bad_records']} unreadable")
        files = [str(out / v["file"]) for v in summary["views"].values()]
        subprocess.run([sys.executable, str(HERE / "postprocess.py"), *files], check=True)
        old = next((f for f in log["files"] if f.get("source") == summary["source"]), {})
        keep = {k: v for k, v in old.items() if k == "check_against_workbook"}
        log["files"] = [f for f in log["files"] if f.get("source") != summary["source"]] + [{**summary, **keep}]
    log["extracted_on"] = datetime.date.today().isoformat()
    log["method"] = ("Pivot caches streamed and summed into views; Citizenship Country summed out of every table "
                     "by design.")
    log_path.write_text(json.dumps({k: log[k] for k in ["extracted_on", "method", "files"]}, indent=1))
    print(f"\nDone. Tidy tables are in: {out}")


if __name__ == "__main__":
    main()
