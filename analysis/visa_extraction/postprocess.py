"""Tidy up extracted views: snake_case columns, financial-year helper columns, gzip large files."""
import gzip
import json
import re
import shutil
import sys
from pathlib import Path

import pandas as pd

RENAME = {
    "Financial Year of Visa Grant": "fy_label",
    "Financial Year of Visa Lodged": "fy_label",
    "Financial Year of Decision": "fy_label",
    "Financial Year Quarter": "fy_quarter",
    "Snapshot Date": "snapshot_date",
    "Month": "month",
    "Client Location": "client_location",
    "Applicant Type": "applicant_type",
    "Visa Subclass": "visa_subclass",
    "Visa Type": "visa_type",
    "Visa Sub-type": "visa_subtype",
    "Visa Category": "visa_category",
    "Agreement Type": "agreement_type",
    "Sponsorship - DAMA Agreement Type": "dama_agreement",
    "Nominated Position Location (State)": "state",
    "Nominated Position Location (Statistical Area Level 4)": "sa4",
    "Nominated Position Location (Statistical Area Level 3)": "sa3",
    "Nominated Occupation (Major Group)": "occupation_major_group",
    "Nominated Occupation (Unit Group)": "occupation_unit_group",
    "Nominated Occupation": "occupation",
    "Nominated Occupation (Skill Level)": "skill_level",
    "Sponsor Industry": "sponsor_industry",
    "Gender": "gender",
    "Age Group": "age_group",
    "Sector": "sector",
    "Education Provider Registered State": "provider_state",
    "Last Visa Held - Visa Category": "last_visa_category",
    "Lodgement Channel": "lodgement_channel",
    "Total": "count",
    "Visa Holders": "visa_holders",
    "Grant Total": "grants",
    "Refused Total": "refusals",
}
# In the grant-rate file, "Total" means decisions (grants + refusals)
DECISION_FILES = ("student_decisions",)
GZIP_ABOVE_BYTES = 10 * 1024 * 1024


def fy_helpers(df):
    lab = df["fy_label"].astype(str)
    df.insert(df.columns.get_loc("fy_label") + 1, "fy", lab.str.slice(0, 7))
    upto = lab.str.extract(r"to (\d{1,2} \w+ \d{4})$")[0]
    complete = upto.isna() | upto.str.contains("30 June", na=False)
    df.insert(df.columns.get_loc("fy") + 1, "fy_complete", complete)
    df.insert(df.columns.get_loc("fy_complete") + 1, "data_to", upto.fillna(""))
    return df


def split_code(df, col):
    """'2211 Accountants' -> code '2211' + title 'Accountants' (keeps 'Not Specified' etc.)."""
    m = df[col].astype(str).str.extract(r"^(\d{1,6})\s+(.*)$")
    df.insert(df.columns.get_loc(col), col + "_code", m[0].fillna(""))
    df[col] = m[1].fillna(df[col])
    return df


def tidy(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        df = pd.read_csv(fh, dtype=str, keep_default_na=False)
    if "applicant_type" in df.columns:          # already tidied: leave it alone
        return path, len(df), list(df.columns)
    df = df.rename(columns=RENAME)
    if path.name.startswith(DECISION_FILES):
        df = df.rename(columns={"count": "decisions"})
        for c in ("grants", "refusals", "decisions"):
            df[c] = pd.to_numeric(df[c])
        df["grant_rate"] = (df["grants"] / df["decisions"]).round(4)
    for c in ("count", "visa_holders"):
        if c in df:
            df[c] = pd.to_numeric(df[c])
    if "fy_label" in df:
        df = fy_helpers(df)
    if "snapshot_date" in df:
        df["snapshot_date"] = pd.to_datetime(df["snapshot_date"]).dt.date.astype(str)
    for col in ("occupation", "occupation_unit_group", "occupation_major_group"):
        if col in df:
            df = split_code(df, col)
    sort_cols = [c for c in ("fy", "snapshot_date", "fy_quarter", "month", "state") if c in df]
    df = df.sort_values(sort_cols, kind="stable") if sort_cols else df
    stem = path.name.replace(".csv.gz", "").replace(".csv", "")
    out = path.parent / f"{stem}.csv"
    df.to_csv(out, index=False)
    if path.suffix == ".gz":
        path.unlink()
    if out.stat().st_size > GZIP_ABOVE_BYTES:
        with open(out, "rb") as src, gzip.open(str(out) + ".gz", "wb", compresslevel=6) as dst:
            shutil.copyfileobj(src, dst)
        out.unlink()
        out = Path(str(out) + ".gz")
    return out, len(df), list(df.columns)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        out, n, cols = tidy(Path(p))
        print(f"{out.name}: {n:,} rows, {out.stat().st_size/1e6:.1f} MB | {', '.join(cols)}")
