"""Flatten a Home Affairs BP pivot-table workbook into several tidy aggregate views.

The workbooks store their data in a pivot cache (xl/pivotCache/pivotCacheRecords1.xml).
This script streams that cache once and aggregates every record into each requested view.
Citizenship Country is never used as a dimension: it is summed out by design
(project ground rule: skills, not nationality).

Usage:
    python3 extract_views.py <workbook.xlsx> <out_dir> <views.json>

views.json maps a view name to {"dims": [...cache field names...], "measures": [...]}
"""
import json
import re
import sys
import time
import zipfile
from collections import defaultdict
from html import unescape
from pathlib import Path
import xml.etree.ElementTree as ET

M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
FORBIDDEN_DIMS = {"Citizenship Country"}
CHILD = re.compile(r'<([xnsdmbe])(?: v="([^"]*)")?\s*/>')


def load_definition(zf):
    root = ET.fromstring(zf.read("xl/pivotCache/pivotCacheDefinition1.xml"))
    fields = []
    for fld in root.find(M + "cacheFields"):
        si = fld.find(M + "sharedItems")
        items = [ch.get("v") for ch in si] if si is not None else []
        fields.append({
            "name": fld.get("name"),
            "items": items,
            "in_records": fld.get("databaseField") != "0" and not fld.get("formula"),
        })
    return fields, int(root.get("recordCount") or 0)


def iter_records(zf, chunk_size=1 << 25):
    """Yield the raw text of each <r>...</r> record, streaming the cache XML."""
    with zf.open("xl/pivotCache/pivotCacheRecords1.xml") as fh:
        buf = ""
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            buf += chunk.decode("utf-8")
            parts = buf.split("</r>")
            buf = parts.pop()
            for p in parts:
                i = p.find("<r>")
                if i >= 0:
                    yield p[i + 3:]
        # anything left in buf is the closing tag of the cache, not a record


def main():
    src, out_dir, views_path = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    views = json.loads(Path(views_path).read_text())
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with zipfile.ZipFile(src) as zf:
        fields, expected = load_definition(zf)
        rec_fields = [f for f in fields if f["in_records"]]
        names = [f["name"] for f in rec_fields]
        pos = {n: i for i, n in enumerate(names)}
        for vname, spec in views.items():
            bad = set(spec["dims"]) & FORBIDDEN_DIMS
            if bad:
                raise SystemExit(f"view {vname} uses a forbidden dimension: {bad}")
            missing = [d for d in spec["dims"] + spec["measures"] if d not in pos]
            if missing:
                raise SystemExit(f"view {vname}: unknown fields {missing}; available {names}")
        measures = views[next(iter(views))]["measures"]
        m_pos = [pos[m] for m in measures]
        plans = {v: [pos[d] for d in s["dims"]] for v, s in views.items()}
        aggs = {v: defaultdict(lambda: [0.0] * len(m_pos)) for v in views}
        grand = [0.0] * len(m_pos)
        n = 0
        bad_records = 0
        nf = len(rec_fields)
        for body in iter_records(zf):
            cells = CHILD.findall(body)
            if len(cells) != nf:
                bad_records += 1
                continue
            vals = [None] * nf
            for i, (tag, v) in enumerate(cells):
                if tag == "x":
                    vals[i] = int(v)          # index into shared items, resolved at output
                elif tag == "m":
                    vals[i] = ""
                else:
                    vals[i] = unescape(v) if v is not None else ""
            mv = []
            for j, p in enumerate(m_pos):
                val = vals[p]
                if isinstance(val, int):      # measure stored as shared item
                    val = rec_fields[p]["items"][val]
                x = float(val) if val not in ("", None) else 0.0
                mv.append(x)
                grand[j] += x
            for v, idxs in plans.items():
                a = aggs[v][tuple(vals[i] for i in idxs)]
                for j in range(len(mv)):
                    a[j] += mv[j]
            n += 1
            if n % 1_000_000 == 0:
                print(f"  {n:,} records ({time.time() - t0:.0f}s)", flush=True)

    def label(fidx, v):
        if isinstance(v, int):
            return rec_fields[fidx]["items"][v]
        return v

    summary = {"source": Path(src).name, "records": n, "expected_records": expected,
               "bad_records": bad_records, "grand_totals": dict(zip(measures, grand)), "views": {}}
    import csv
    import gzip
    for v, spec in views.items():
        idxs = plans[v]
        rows = aggs[v]
        gz = len(rows) > 150_000
        path = out_dir / (v + (".csv.gz" if gz else ".csv"))
        opener = (lambda p: gzip.open(p, "wt", newline="", encoding="utf-8")) if gz else \
                 (lambda p: open(p, "w", newline="", encoding="utf-8"))
        with opener(path) as fh:
            w = csv.writer(fh)
            w.writerow(spec["dims"] + measures)
            for key, mvals in rows.items():
                w.writerow([label(i, k) for i, k in zip(idxs, key)] +
                           [int(x) if x == int(x) else round(x, 4) for x in mvals])
        view_tot = [sum(r[j] for r in rows.values()) for j in range(len(measures))]
        summary["views"][v] = {"file": path.name, "rows": len(rows),
                               "totals": dict(zip(measures, view_tot))}
    summary["seconds"] = round(time.time() - t0, 1)
    print(json.dumps(summary, indent=1))
    (out_dir / f"_summary_{Path(src).stem[:40]}.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
