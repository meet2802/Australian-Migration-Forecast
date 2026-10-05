"""Shared helpers for the build scripts in analysis/ (paths, ABS time series reader, dictionary, row-count log)."""
import atexit
import gzip
import io
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TIDY = ROOT / "tidy"
DICTIONARY = HERE / "data_dictionary.csv"
ROW_LOG = HERE / "row_counts.csv"
_ROWS = []

STATE_NAMES = {
    "New South Wales": "NSW", "NSW": "NSW", "Victoria": "VIC", "Vic.": "VIC", "VIC": "VIC",
    "Queensland": "QLD", "Qld": "QLD", "QLD": "QLD", "South Australia": "SA", "SA": "SA",
    "Western Australia": "WA", "WA": "WA", "Tasmania": "TAS", "Tas.": "TAS", "TAS": "TAS",
    "Northern Territory": "NT", "NT": "NT", "Australian Capital Territory": "ACT", "ACT": "ACT",
    "Australia": "AUS", "AUS": "AUS",
}
STATES = ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"]

# ANZSIC 2006 divisions: official titles, and plain-English names for public-facing pages
DIVISIONS = {
    "A": "Agriculture, Forestry and Fishing", "B": "Mining", "C": "Manufacturing",
    "D": "Electricity, Gas, Water and Waste Services", "E": "Construction", "F": "Wholesale Trade",
    "G": "Retail Trade", "H": "Accommodation and Food Services", "I": "Transport, Postal and Warehousing",
    "J": "Information Media and Telecommunications", "K": "Financial and Insurance Services",
    "L": "Rental, Hiring and Real Estate Services", "M": "Professional, Scientific and Technical Services",
    "N": "Administrative and Support Services", "O": "Public Administration and Safety",
    "P": "Education and Training", "Q": "Health Care and Social Assistance", "R": "Arts and Recreation Services",
    "S": "Other Services",
}
INDUSTRY_PLAIN = {
    "A": "Farming, forestry and fishing", "B": "Mining", "C": "Manufacturing",
    "D": "Electricity, gas, water and waste", "E": "Construction", "F": "Wholesale trade", "G": "Retail trade",
    "H": "Hotels, cafes and restaurants", "I": "Transport, post and warehousing",
    "J": "Media and telecommunications", "K": "Finance and insurance", "L": "Rental, hiring and real estate",
    "M": "Professional and technical services", "N": "Admin and support services",
    "O": "Government and public safety", "P": "Education and training", "Q": "Health care and social assistance",
    "R": "Arts, sport and recreation", "S": "Repairs, personal and other services",
}


def clean_label(s):
    """Drop footnote markers like '(a)', '(b)(c)' and extra spaces from an ABS label."""
    s = re.sub(r"\((?:[a-z]{1,2})\)", "", str(s))
    return re.sub(r"\s+", " ", s).strip()


def state_code(label):
    """'New South Wales', 'Vic.', 'ACT(d)', 'Australia(e)' -> NSW, VIC, ACT, AUS (None if not a state)."""
    return STATE_NAMES.get(clean_label(label))


def num(v):
    """Numbers stay numbers; ABS markers such as 'np', '-', '..', '< 5' become NaN."""
    if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
        return float(v)
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return np.nan


def zip_member(zip_path, name):
    """Bytes of one file inside a zip (exact name, or the first member whose name contains `name`).
    Reading in memory means no temporary files are left behind."""
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        member = name if name in names else next(n for n in names if name in n)
        return z.read(member)


def read_abs_timeseries(src, sheets=None):
    """Read an ABS time series workbook (Data1, Data2, ...) into long format:
    date, series_id, series, unit, series_type, value. src is a path, or the bytes of a workbook."""
    xl = pd.ExcelFile(io.BytesIO(src) if isinstance(src, (bytes, bytearray)) else src)
    sheets = sheets or [s for s in xl.sheet_names if s.startswith("Data")]
    out = []
    for sheet in sheets:
        raw = xl.parse(sheet, header=None)
        meta = raw.iloc[:10]
        labels = meta.iloc[0, 1:]
        ids = raw[raw[0].astype(str).str.strip().eq("Series ID")].iloc[0, 1:]
        units = raw[raw[0].astype(str).str.strip().eq("Unit")].iloc[0, 1:]
        types = raw[raw[0].astype(str).str.strip().eq("Series Type")].iloc[0, 1:]
        body = raw.iloc[10:]
        dates = pd.to_datetime(body[0], errors="coerce")
        for col in raw.columns[1:]:
            vals = pd.to_numeric(body[col], errors="coerce")
            keep = dates.notna() & vals.notna()
            out.append(pd.DataFrame({
                "date": dates[keep].dt.date, "series_id": str(ids[col]).strip(),
                "series": re.sub(r"\s*;\s*", " ; ", str(labels[col])).strip(" ;"),
                "unit": str(units[col]).strip(), "series_type": str(types[col]).strip(),
                "value": vals[keep]}))
    res = pd.concat(out, ignore_index=True)
    name = Path(src).name if not isinstance(src, (bytes, bytearray)) else "workbook from a zip"
    log_rows(f"Read ABS time series ({res['series_id'].nunique()} series)", res, table=name)
    return res


def log_rows(step, df, table="", note=""):
    """Record how many rows a table has at a cleaning step. Saved to analysis/row_counts.csv when the script ends
    (this script's earlier rows are replaced). Only reads len(df): never changes the data."""
    if not _ROWS:
        atexit.register(_save_rows)
    n = int(df) if isinstance(df, (int, np.integer)) else len(df)
    cols = len(df.columns) if hasattr(df, "columns") else ""
    _ROWS.append({"step_no": len(_ROWS) + 1, "step": step, "table": table, "rows": n, "columns": cols, "note": note})
    return df


def _script_name():
    main = sys.modules.get("__main__")
    f = getattr(main, "__file__", None) or (sys.argv[0] if sys.argv else "")
    return Path(f).name if f else "interactive"


def _save_rows():
    script = _script_name()
    new = pd.DataFrame(_ROWS)
    new.insert(0, "script", script)
    if ROW_LOG.exists():
        old = pd.read_csv(ROW_LOG, dtype=str, keep_default_na=False)
        old = old[old["script"].ne(script)]
        new = pd.concat([old, new.astype(str)], ignore_index=True)
    try:
        from run_all import ORDER
    except Exception:
        ORDER = []
    rank = {s: i for i, s in enumerate(ORDER)}
    new["_r"] = new["script"].map(lambda s: rank.get(s, len(rank)))
    new["_n"] = pd.to_numeric(new["step_no"])
    new = new.sort_values(["_r", "script", "_n"], kind="stable").drop(columns=["_r", "_n"])
    new.to_csv(ROW_LOG, index=False)


def write_table(df, path, gzip_above_mb=10):
    """Write a CSV, or a .csv.gz if it would be larger than gzip_above_mb. The gzip header carries no
    timestamp, so the same data always gives the same file. Returns the path written."""
    path = Path(path)
    data = df.to_csv(index=False).encode("utf-8")
    gz = Path(str(path) + ".gz")
    log_rows("Written", df, table=path.name)
    if len(data) > gzip_above_mb * 1024 * 1024:
        gz.write_bytes(gzip.compress(data, compresslevel=6, mtime=0))
        out, stale = gz, path
    else:
        path.write_bytes(data)
        out, stale = path, gz
    if stale.exists():   # an older run wrote the other format
        try:
            stale.unlink()
        except OSError:
            print(f"Note: could not remove the old file {stale.name}; it can be deleted by hand.")
    return out


def update_dictionary(rows):
    """Replace this script's tables in analysis/data_dictionary.csv. rows: list of dicts with
    table, column, meaning, source, period, number_type."""
    new = pd.DataFrame(rows, columns=["table", "column", "meaning", "source", "period", "number_type"])
    if DICTIONARY.exists():
        old = pd.read_csv(DICTIONARY, dtype=str, keep_default_na=False)
        old = old[~old["table"].isin(new["table"].unique())]
        new = pd.concat([old, new], ignore_index=True)
    new.to_csv(DICTIONARY, index=False)


def dictionary_rows(table, df, meanings):
    """Build dictionary rows for every column of df from a {column: (meaning, source, period, type)} map."""
    missing = [c for c in df.columns if c not in meanings]
    assert not missing, f"{table}: no dictionary entry for {missing}"
    return [dict(zip(["table", "column", "meaning", "source", "period", "number_type"], (table, c, *meanings[c])))
            for c in df.columns]

