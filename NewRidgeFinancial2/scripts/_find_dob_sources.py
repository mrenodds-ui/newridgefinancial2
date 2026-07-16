"""Find DOB sources for SoftDent patients."""
from __future__ import annotations

import json
import os
from pathlib import Path

sensei = Path(r"C:\ProgramData\Sensei Gateway Client\DataSync\0000950863")
for name in ["patient", "person", "Reference", "historical_backfill", "processed"]:
    p = sensei / name
    print(f"{name}: exists={p.exists()} is_dir={p.is_dir()}")
    if p.is_dir():
        files = list(p.iterdir())
        print(f"  children={len(files)} sample={[x.name for x in files[:8]]}")
        if name == "Reference":
            for child in files[:20]:
                if child.is_dir():
                    n = len(list(child.glob("*.json")))
                    print(f"  ref/{child.name}: json={n}")
                else:
                    print(f"  ref file {child.name} {child.stat().st_size}")

# SoftDent patient.dat
pat = Path(r"C:\SoftDent\patient.dat")
for cand in [
    Path(r"C:\SoftDent\patient.dat"),
    Path(r"C:\SoftDent\Data\patient.dat"),
    Path(r"C:\SoftDent\Cassidy\patient.dat"),
]:
    print("patient.dat", cand, cand.exists(), cand.stat().st_size if cand.exists() else 0)

# Find patient.dat
for root in [Path(r"C:\SoftDent")]:
    hits = list(root.rglob("patient.dat"))
    print("patient.dat hits", [(str(h), h.stat().st_size) for h in hits[:10]])

# pyodbc drivers
try:
    import pyodbc
    print("drivers", pyodbc.drivers())
except Exception as e:
    print("pyodbc err", e)

# SoftDentReportExports recent
exp = Path(r"C:\SoftDentReportExports")
if exp.is_dir():
    files = sorted(exp.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)[:25]
    for f in files:
        if f.is_file():
            print("export", f.name, f.stat().st_size)
