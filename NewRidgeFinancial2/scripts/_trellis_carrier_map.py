"""Automate Trellis Add Patient + Verify for tomorrow worklist via CDP helpers notes.

Carrier SoftDent -> Trellis display name map used by browser operator.
"""
from __future__ import annotations

CARRIER_MAP = {
    "DELTA DENTAL OF MO": "Delta Dental of Missouri",
    "DELTA DENTAL OF KS": "Delta Dental of Kansas",
    "DELTA DENTAL OF IN": "Delta Dental of Indiana",
    "DELTA DENTAL OF PA": "Delta Dental of Pennsylvania",
    "BCBS OF KS": "Blue Cross and Blue Shield of Kansas",
    "METLIFE DENTAL": "MetLife",
    "CIGNA DENTAL": "Cigna",
    "CIGNA DENTAL - HMO": "Cigna",
    "CIGNA DENTAL - 182223": "Cigna",
    "UNITED HEALTHCARE - 30567": "UnitedHealthcare",
    "AETNA MEDICARE ADVANTAGE": "Aetna",
    "AFLAC CLAIMS": "Aflac",
    "AMERITAS": "Ameritas",
    "DOMINION NATIONAL": "Dominion National",
}
