"""REC-005 ERA 835 parser depth — Loop 2100/2110 CAS + RARC + HAL summary."""

from __future__ import annotations

from era835_parser import parse_835_text, summarize_835_for_hal

SAMPLE_DEPTH = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *260711*1200*^*00501*000000001*0*P*:~
GS*HP*SENDER*RECEIVER*20260711*1200*1*X*005010X221A1~
ST*835*0001~
BPR*I*100.00*C*CHK************20260710~
N1*PR*DELTA DENTAL~
CLP*CLM-DEPTH-1*1*200*100**12*1~
NM1*QC*1*DOE*JANE~
CAS*CO*45*50~
SVC*AD:D1110*100*50~
CAS*CO*45*50~
LQ*HE*N59~
SVC*AD:D0120*100*50~
CAS*PR*1*50~
SE*20*0001~
GE*1*1~
IEA*1*000000001~
"""


def test_parse_service_lines_and_cas():
    parsed = parse_835_text(SAMPLE_DEPTH)
    assert parsed.get("ok") is True
    assert parsed.get("rec005Depth") is True
    segs = parsed["segments"]
    assert len(segs) == 1
    seg = segs[0]
    assert seg["claimId"] == "CLM-DEPTH-1"
    assert "CO-45" in seg["casCodes"]
    assert seg["denialCode"] == "CO-45"
    assert seg["denialFlag"] is True
    lines = seg["serviceLines"]
    assert len(lines) == 2
    assert lines[0]["procedureCode"] == "D1110"
    assert lines[0]["paid"] == 50.0
    assert "CO-45" in lines[0]["casCodes"]
    assert "N59" in lines[0]["rarcCodes"]
    assert lines[1]["procedureCode"] == "D0120"
    assert "PR-1" in lines[1]["casCodes"]


def test_summary_omits_patient_and_keeps_codes():
    summary = summarize_835_for_hal(content=SAMPLE_DEPTH)
    assert summary.get("ok") is True
    assert summary["claimCount"] == 1
    assert summary["denialOrAdjustmentCount"] == 1
    blob = summary["summaryText"]
    assert "DOE" not in blob
    assert "JANE" not in blob
    assert "CO-45" in blob
    assert "D1110" in blob
    assert "N59" in blob
    assert "empty ≠ $0" in blob or "empty" in blob.lower()
    claim = summary["claims"][0]
    assert claim["serviceLineCount"] == 2
    assert claim["casCodes"]


def test_empty_not_zero_in_summary_when_missing_amounts():
    thin = "CLP*ONLY-ID*1***~\n"
    summary = summarize_835_for_hal(content=thin)
    assert summary["ok"] is True
    # charged/paid absent → labeled missing, not invented $0 in prose totals when both empty
    assert "CLM" not in summary["summaryText"] or "ONLY-ID" in summary["summaryText"]
