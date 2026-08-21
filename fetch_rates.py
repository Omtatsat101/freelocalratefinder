#!/usr/bin/env python3
"""Fetch current US rate benchmarks from FRED (St. Louis Fed) -> data/rates.json.
Public CSV endpoints, no API key required. Run weekly via GitHub Actions.
Sources: Freddie Mac PMMS (30/15yr mortgage), Federal Reserve H.15 (fed funds,
10yr treasury, bank prime). All series are official federal/GSE published data."""
import csv, io, json, os, ssl, urllib.request
from datetime import datetime, timezone

SERIES = {
    "mortgage_30yr": ("MORTGAGE30US", "30-Year Fixed Mortgage", "Freddie Mac PMMS (weekly)"),
    "mortgage_15yr": ("MORTGAGE15US", "15-Year Fixed Mortgage", "Freddie Mac PMMS (weekly)"),
    "fed_funds":     ("FEDFUNDS",     "Federal Funds Rate",     "Federal Reserve H.15 (monthly)"),
    "treasury_10yr": ("DGS10",        "10-Year Treasury Yield", "Federal Reserve H.15 (daily)"),
    "prime_rate":    ("DPRIME",       "Bank Prime Loan Rate",   "Federal Reserve H.15 (daily)"),
}
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

def series(sid):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
    req = urllib.request.Request(url, headers={"User-Agent": "LoanRatesFinder/1.0 (rates updater)"})
    with urllib.request.urlopen(req, timeout=40, context=CTX) as r:
        rows = list(csv.reader(io.StringIO(r.read().decode("utf-8", "replace"))))
    pts = []
    for row in rows[1:]:
        if len(row) < 2: continue
        try: pts.append((row[0], float(row[1])))
        except ValueError: continue          # FRED writes "." for missing
    return pts

def main():
    out = {"updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "source": "Federal Reserve Economic Data (FRED), St. Louis Fed", "rates": {}}
    for key, (sid, label, src) in SERIES.items():
        try:
            pts = series(sid)
            if not pts: raise RuntimeError("no datapoints")
            date, val = pts[-1]
            prev = pts[-2][1] if len(pts) > 1 else val
            yr = [v for d, v in pts if d >= f"{int(date[:4])-1}"]
            out["rates"][key] = {
                "label": label, "series_id": sid, "source": src,
                "value": round(val, 2), "as_of": date,
                "change": round(val - prev, 2),
                "year_low": round(min(yr), 2) if yr else None,
                "year_high": round(max(yr), 2) if yr else None,
                "history": [{"d": d, "v": v} for d, v in pts[-52:]],
            }
            print(f"  {label}: {val}% ({date})")
        except Exception as e:
            print(f"  !! {label} ({sid}): {type(e).__name__}: {e}")
    if not out["rates"]:
        raise SystemExit("no series fetched - aborting so stale data is not overwritten")
    os.makedirs("data", exist_ok=True)
    json.dump(out, open("data/rates.json", "w"), indent=1)
    print(f"wrote data/rates.json with {len(out['rates'])} series")

if __name__ == "__main__":
    main()
