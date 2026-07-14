import json

p = r"C:\NewRidgeFamilyFinancial\NewRidgeFinancial2\docs\_nr2_page_smoke_report.json"
r = json.load(open(p, encoding="utf-8"))
print("working", r["working"], "gap", r["gap_n"], "broken", r["broken_n"])
print("--- ALL GAPS ---")
for g in r["gap"]:
    print(
        g["page"],
        g["id"],
        g["status"],
        g.get("gapCode"),
        (g.get("msg") or "")[:140],
        sep="\t",
    )
print("--- APIS ---")
for a in r["apis"]:
    print(a["method"], a["path"], a["http"], a["ok"], (a.get("snip") or "")[:140])
print("--- PAGE BY ---")
for k, v in r["pages"].items():
    print(k, v["n"], v["by"])
print("--- SOFTDENT ---")
for w in r["pages"]["softdent"]["widgets"]:
    print(w["state"], w["id"], w["status"], w.get("gapCode"), (w.get("msg") or "")[:120])
print("--- HAL ---")
for w in r["pages"]["hal"]["widgets"]:
    print(w["state"], w["id"], w["status"], (w.get("msg") or "")[:120])
print("--- OM NON-WORKING ---")
for w in r["pages"]["office-manager"]["widgets"]:
    if w["state"] != "working":
        print(w["state"], w["id"], w["status"], w.get("gapCode"), (w.get("msg") or "")[:120])
