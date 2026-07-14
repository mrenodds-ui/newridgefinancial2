# Moonshot AI — Complete Rejected Carrier Aliases (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Rejected in scope:** 86  
**Spine targets:** 72  
**Script:** `scripts/run_moonshot_rejected_carrier_alias_complete_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> now use moonshot ai with all his powers and vast web resources and his knowledge of other dental offices see if he can complete the list and consult

---

# Verdict  
We can complete **7 HIGH-confidence** industry-identity mappings (Assurant→Sun Life, Connecticut General→CIGNA, MetLife variants→METLIFE DENTAL, UniCare→Anthem) and **2 MEDIUM-confidence** legacy-acquisition mappings (Coventry→Aetna); the remaining **77** masters are honest NONEs (TPAs, employers, discontinued niche carriers, or true orphans) and must stay rejected.

## 0. Operator Intent (verbatim)
now use moonshot ai with all his powers and vast web resources and his knowledge of other dental offices see if he can complete the list and consult

## 1. Method  
Leveraged multi-office SoftDent payer identity knowledge (rebrands, acquisitions, claim-route aliases) and industry truth tables (Assurant acquired by Sun Life 2016; Connecticut General merged into CIGNA 1982; UniCare wholly owned by Anthem; Coventry acquired by Aetna 2013; MetLife dental blocks always settle under METLIFE DENTAL regardless of employer suffix).  
**Limits:** No live SoftDent connection—cannot verify if “Ahc” or “Bma” are office-specific abbreviations for spine carriers, so those remain NONE per “Prefer NONE over a wrong HIGH.” No settlement dollars invented; mappings reuse EXISTING spine ledger pools only.

## 2. Completed mapping table  

| master | spine (exact or blank) | band (HIGH/MEDIUM/LOW/NONE) | rationale (1 short clause) |
|--------|------------------------|----------------------------|----------------------------|
| 2025 - cOMPLETE | | NONE | Plan-year marker, not an insurance carrier |
| 3 | | NONE | ASO shell with no named payer in spine |
| Administrative Services Only | | NONE | ASO administrative shell |
| Ahc | | NONE | Ambiguous abbreviation; no honest spine partner |
| Aircraft Radio Examiners | | NONE | Niche association/employer, not a settlement carrier |
| Allied Benefit Systems, LLC | | NONE | TPA/ASO shell |
| American National Insurnace | | NONE | Carrier not present in spine |
| Assurant | SUN LIFE FINANCIAL | HIGH | Industry rebrand: Assurant group benefits acquired by Sun Life 2016 |
| Bankers | | NONE | Ambiguous; no “Bankers” entry in spine |
| Bankers Life | | NONE | Carrier not in spine |
| Beauty First | | NONE | Employer/discount plan, not a payer |
| Benefit Plan Administrators, Inc. | | NONE | TPA shell |
| Bma | | NONE | Ambiguous abbreviation (possible Blue Cross variant but unverified) |
| Bricklayers Allied Company | | NONE | Union/employer local |
| Bsi | | NONE | TPA abbreviation ambiguous |
| Butler Benefit Services, Inc | | NONE | TPA shell |
| Centennial Life | | NONE | Carrier not in spine |
| Claim Management Services | | NONE | TPA/ASO shell |
| Cna | | NONE | CNA Financial not in spine |
| Connecticut General | CIGNA DENTAL | HIGH | Historical rebrand: Connecticut General merged into CIGNA |
| Consumer Benefits Claims | | NONE | TPA shell |
| Continental General | | NONE | Carrier not in spine |
| Core Source Tucson | | NONE | TPA/employer-specific processor |
| Coventry | AETNA | MEDIUM | Acquired by Aetna 2013; legacy blocks may still route through Coventry but settle as Aetna |
| Coventry Health Care Of Kansas | AETNA | MEDIUM | Kansas-specific Coventry entity; same acquisition logic |
| Cuna Mutual Group | | NONE | Now TruStage; not in spine |
| Definity | | NONE | Definity Health employer plan, not in spine |
| DenteMax | | NONE | Network administrator, not a settlement carrier |
| Diamond J | | NONE | Employer name |
| Ebmc | | NONE | Spelling differs from spine “EBMS”; cannot assume typo |
| FIRST CONTINENTAL LIFE & ACCIDENT | | NONE | Carrier not in spine |
| First Guard Health Plan | | NONE | Carrier not in spine |
| G E Dental Benefits Claims | | NONE | GE benefits divested; no current spine match |
| GUARANTEE TRUST LIFE | | NONE | Carrier not in spine |
| Great-west | | NONE | Now Empower Retirement; not in spine |
| Group Administrators, Ltd | | NONE | TPA shell |
| Group Benefit Services, Inc | | NONE | TPA shell |
| Gsa | | NONE | Federal employer (General Services Administration) |
| Guarantee Life Insurance | | NONE | Carrier not in spine |
| H R M Care Pass Usa | | NONE | Health Risk Management TPA |
| Health Risk Management | | NONE | TPA not in spine |
| Hrm Claim Management | | NONE | TPA shell |
| Hrm Claim Management INC. | | NONE | TPA shell |
| Hunt Taylor/willis Corroon | | NONE | Insurance broker, not carrier |
| Intercare Health Plans | | NONE | Defunct/regional HMO |
| John Hancock | | NONE | Manulife subsidiary; dental not in spine |
| Kanawha Benefit Solutions, Inc | | NONE | TPA shell |
| Lewer Agency | | NONE | Benefits agency |
| Life Of Georgia | | NONE | Carrier not in spine |
| Managed Health Funding Insurance | | NONE | Funding vehicle, not settlement carrier |
| Met Life | METLIFE DENTAL | HIGH | Standard carrier abbreviation |
| Met Life /dental Claims | METLIFE DENTAL | HIGH | Claims-address variant of MetLife |
| Met Life/ Pepsico | METLIFE DENTAL | HIGH | Employer-specific block; carrier identity remains MetLife |
| Meyers Bakery Of Hope | | NONE | Employer self-funded plan |
| NATIVE CARE HEALTH | | NONE | Not in spine |
| National Group Life | | NONE | Carrier not in spine |
| New York Life | | NONE | Carrier not in spine |
| Nippon Life Insurance Co | | NONE | Japanese carrier not in spine |
| North America Administrators | | NONE | TPA shell |
| Ochsner Eye Surgery Center | | NONE | Provider entity, not payer |
| Operating Engineers Local 101 | | NONE | Union employer |
| Pm Group | | NONE | TPA abbreviation |
| Postmasters Benefit Plan | | NONE | Postal-specific plan; distinct from FEP Blue in spine |
| Predent Plan For Dental Car | | NONE | Discount plan, not insurance |
| Preferred Health Care, Inc. | | NONE | TPA/HMO not in spine |
| Preferred Health Professionals | | NONE | Network/discount plan |
| Preferred Health Systems | | NONE | HMO not in spine (distinct from Preferred Plus → Pequot already accepted) |
| Professional Benefit Administrators, Inc | | NONE | TPA shell |
| Protective Dentalcare | | NONE | Carrier not in spine |
| Prudential | | NONE | Carrier not in spine |
| Prudential Health Care | | NONE | Carrier not in spine |
| Rural Carrier Benefit Plan | | NONE | Postal union plan not in spine |
| Safehealth | | NONE | MCO not in spine |
| Safehealth Life Insurance | | NONE | Carrier not in spine |
| Sheffield, Olson & Mcqueen, Inc | | NONE | TPA/agency |
| Shelter Mutual | | NONE | Shelter Insurance not in spine |
| Student Assurance Services | | NONE | Student-plan administrator not in spine |
| The Haskell Company | | NONE | Employer |
| Time | | NONE | Employer (Time Inc) |
| Travelers | | NONE | Travelers Insurance not in spine |
| Tyson Foods | | NONE | Employer ASO |
| UniCare | ANTHEM - 1115 | HIGH | UniCare brand wholly owned by Anthem Inc. |
| Unicare Life & Health Insurance Co | ANTHEM - 1115 | HIGH | Legal entity operating UniCare/Anthem business |
| Voluntary Benefits Plan | | NONE | Generic description, no carrier named |
| Western -southern Life | | NONE | Western & Southern Life not in spine |
| Wichita Police Dept. | | NONE | Municipal employer |
| Wppa | | NONE | Association/employer group (likely Wisconsin Professional Police) |

## 3. Apply package proposal (HAL-10604?)  
**Package:** `HAL-10604` – **Apply Moonshot Industry-Alias Mappings**  
- **Bands to accept on `proceed`:** **HIGH only** (7 rows).  
  - *Rationale:* MEDIUM (Coventry→Aetna) involves legacy routing ambiguity; operator should glance to confirm no active Coventry-specific fee schedules remain before accepting.  
- **Storage schema:**  
  ```sql
  UPDATE carrier_alias 
  SET spine_carrier_name = '<exact_spine>',
      confidence = 'manual',
      review_status = 'accepted',
      match_method = 'moonshot_industry',
      updated_at = NOW()
  WHERE master_company_name = '<master>' AND build_id = 'hal-10604';
  ```  
- **Validation gate:**  
  1. TP probe sample: `Assurant` × `D2391` → must resolve to `SUN LIFE FINANCIAL` dollars; `UniCare` × `D0220` → must resolve to `ANTHEM - 1115` dollars.  
  2. Honesty CI (`HAL-10603`) must remain green—no `null` → `$0.00` regression.  
  3. Excel refresh: `carrier_alias_mapping.csv` shows 7 new `accepted` rows, 77 remain `rejected`.

## 4. Still NONE / keep rejected (count + categories)  
**Count:** 77 masters remain rejected.  
**Categories:**  
- **TPA/ASO shells (22):** Administrative Services Only, Allied Benefit Systems, Benefit Plan Administrators, Claim Management Services, Consumer Benefits Claims, Group Administrators, Group Benefit Services, Kanawha Benefit Solutions, Professional Benefit Administrators, North America Administrators, etc.  
- **Employer-specific / Union locals (18):** Aircraft Radio Examiners, Bricklayers Allied, Diamond J, Meyers Bakery, Operating Engineers Local 101, The Haskell Company, Time, Tyson Foods, Wichita Police Dept., etc.  
- **Discontinued / Niche carriers not in spine (20):** Bankers Life, Centennial Life, Connecticut General (already mapped—remove from this list), Cuna Mutual, First Continental Life, Guarantee Trust Life, Great-west, John Hancock, Life Of Georgia, New York Life, Nippon Life, Shelter Mutual, Travelers, etc.  
- **Ambiguous abbreviations / Typos (8):** Ahc, Bma, Bsi, Ebmc, Gsa, etc.  
- **Discount / Non-insurance plans (4):** Beauty First, Predent Plan, DenteMax, etc.  
- **Provider entities (1):** Ochsner Eye Surgery Center.

## 5. Recommended NEXT after apply (single package)  
**HAL-10605** – **Spine Orphan Triage & Employer-Plan Capture**  
- Target the 77 NONEs: identify which are active payers with recent ledger volume (create `no_settlement` placeholder) vs. dormant masters that can be archived.  
- For employer-specific plans (Tyson, Wichita Police, etc.), build `employer_plan` extension table linked to `carrier_alias` so TP estimator can flag “self-funded—call for fees” rather than showing null.

## 6. What NOT to redo  
Do **not** remap the three already-accepted weak manuals:  
- `First Health/Guardian` → `GUARDIAN LIFE INSURANCE CO.`  
- `Preferred Plus Of Ks` → `PEQUOT PLUS HEALTH - 3620`  
- `Kansas City Life Insurance` → `BCBS OF KANSAS CITY`  

These are frozen; revisiting them risks unsettling historical settlement links.

## 7. Acceptance criteria  
- [ ] All 7 HIGH band rows accepted in `carrier_alias` with exact spine strings copied.  
- [ ] 2 MEDIUM rows remain `review_status = 'pending'` (operator decision).  
- [ ] 77 NONE rows unchanged (`rejected`).  
- [ ] Honesty CI `test_hal10603_honesty_ci.py` passes (no fake zeros).  
- [ ] TP probe shows `Assurant` now pulls Sun Life dollars, `Met Life/Pepsico` pulls MetLife dollars, `UniCare` pulls Anthem dollars.

## 8. Executive Summary (5 bullets)  
- **7 clear industry rebrands** identified (Assurant→Sun Life, Connecticut General→CIGNA, MetLife→METLIFE DENTAL, UniCare→Anthem) allowing immediate alias acceptance.  
- **77 honest orphans** remain—mostly TPAs, municipal employers, and discontinued carriers—safe to leave unmatched (empty ≠ $0).  
- **No synthetic gold** created; every accepted alias reuses existing spine settlement dollars already in the practice’s ledger.  
- **Coventry→Aetna** marked MEDIUM due to legacy routing complexity; recommend manual review before acceptance.  
- Next milestone (HAL-10605) should distinguish true “active no-spine” payers from dormant masters to clean the company master list.

## 9. Approval checklist  
- [ ] Operator confirms MEDIUM band (Coventry variants) should stay pending or be promoted to accepted.  
- [ ] Spine list copy-paste verified: `SUN LIFE FINANCIAL`, `CIGNA DENTAL`, `METLIFE DENTAL`, `ANTHEM - 1115`, `AETNA` strings match exactly (case-sensitive).  
- [ ] Acknowledge that `empty ≠ $0` constraint remains in force.  
- [ ] Confirm `hal-10604` build tag assigned.