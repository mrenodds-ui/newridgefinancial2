"""Automate Trellis Add Patient + Verify for tomorrow worklist via CDP helpers notes.

Carrier SoftDent -> Trellis display name map used by browser operator.
"""
from __future__ import annotations

CARRIER_MAP = {
    "DELTA DENTAL OF MO": "Delta Dental of Missouri",
    "DELTA DENTAL OF KS": "Delta Dental of Kansas",
    "DELTA DENTAL OF IN": "Delta Dental of Indiana",
    "DELTA DENTAL OF PA": "Delta Dental of Pennsylvania",
    "BCBS OF KS": "Blue Cross Blue Shield of Kansas",
    "METLIFE DENTAL": "MetLife",
    "CIGNA DENTAL": "Cigna",
    "CIGNA DENTAL - HMO": "Cigna Dental (HMO)",
    "CIGNA DENTAL - 182223": "Cigna",
    "UNITED HEALTHCARE - 30567": "United Healthcare Dental",
    "AETNA MEDICARE ADVANTAGE": "Aetna",
    "AFLAC CLAIMS": "AFLAC CLAIMS",
    "AMERITAS": "Ameritas Life Insurance Company",
    "DOMINION NATIONAL": "Dominion National",
}
