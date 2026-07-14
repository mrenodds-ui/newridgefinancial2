"""Find Donna Nickel (or similar) in SoftDent analytics / exports."""
from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "NewRidgeFinancial2"))
from softdent_odbc_extract import resolve_sd_sqlite_db

NEEDLES = ("nickel", "nicjel", "donna")


def main() -> None:
    db = resolve_sd_sqlite_db()
    print("db", db)
    if not db or not db.is_file():
        return
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    cur.execute("PRAGMA table_info(sd_patients)")
    cols = [r[1] for r in cur.fetchall()]
    print("sd_patients cols", cols)
    cur.execute("SELECT * FROM sd_patients LIMIT 1")
    sample = cur.fetchone()
    if sample:
        print("sample", dict(zip(cols, sample)))

    # Build searchable text expression
    text_cols = [
        c
        for c in cols
        if any(x in c.lower() for x in ("name", "first", "last", "patient"))
    ]
    print("text_cols", text_cols)
    for needle in NEEDLES:
        clause = " OR ".join(f"lower(cast({c} as text)) LIKE ?" for c in text_cols) or "0"
        params = [f"%{needle}%"] * max(len(text_cols), 1)
        sql = f"SELECT * FROM sd_patients WHERE {clause} LIMIT 30"
        try:
            cur.execute(sql, params)
            rows = cur.fetchall()
            print(f"--- needle {needle!r} hits {len(rows)}")
            for r in rows[:15]:
                print(dict(zip(cols, r)))
        except Exception as exc:
            print("query fail", needle, type(exc).__name__, exc)

    # Also scan transactions csv if present
    tx = Path(r"C:\SoftDentReportExports\transactions_for_period.csv")
    if tx.is_file():
        with tx.open(encoding="utf-8-sig", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            hits = []
            for row in reader:
                blob = " ".join(str(v) for v in row.values()).lower()
                if "nickel" in blob or "nicjel" in blob or (
                    "donna" in blob and "nick" in blob
                ):
                    hits.append(row)
                    if len(hits) >= 20:
                        break
            print("tx csv donna/nickel hits", len(hits))
            for h in hits[:10]:
                print({k: h.get(k) for k in list(h)[:12]})
    con.close()


if __name__ == "__main__":
    main()
