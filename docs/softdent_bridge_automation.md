# SoftDent Bridge Automation

The bridge worker and repo helper scripts now use a single concrete export drop:

- Bridge source folder: `C:\Users\mreno\SoftDentBridge\exports`
- Dashboard destination folder: `C:\NewRidgeFamilyFinancial\app\data\imports\softdent` by default, or whatever `SOFTDENT_IMPORT_DIR` resolves to.

The live dashboard and HAL claims workbench now read canonical SoftDent files from `SOFTDENT_IMPORT_DIR`. The bridge does not transform payloads; it copies named exports into that canonical import directory.

## Required Files

Place these exact files under `C:\Users\mreno\SoftDentBridge\exports`:

- `softdent_dashboard_data.json`
- `softdent_claims_export.csv`
- `softdent_clinical_notes_data.json`

The bridge worker at `C:\Users\mreno\SoftDentBridge\appsettings.json` or the repo helper scripts should copy them to:

- `C:\NewRidgeFamilyFinancial\app\data\imports\softdent\softdent_dashboard_data.json`
- `C:\NewRidgeFamilyFinancial\app\data\imports\softdent\softdent_claims_export.csv`
- `C:\NewRidgeFamilyFinancial\app\data\imports\softdent\softdent_clinical_notes_data.json`

## Claims Export Contract

Recommended CSV header row:

```text
PatientName,MRN,ClaimId,ClaimStatus,Payer,Procedure,ServiceDate,DenialReason,ClaimAmount
```

Canonical fields HAL normalizes for claims:

- `PatientName`: patient display name used for workbench lookup and narrative context
- `MRN`: chart number or patient identifier
- `ClaimId`: claim number or claim identifier
- `ClaimStatus`: submitted, pending, denied, paid, appealed, or equivalent office status
- `Payer`: insurance carrier or plan name
- `Procedure`: procedure description tied to the claim or line item
- `ServiceDate`: date of service
- `DenialReason`: denial, remark, or free-text claim note
- `ClaimAmount`: billed amount, claim amount, or remaining balance

Current alias handling in the backend accepts common variants such as `patient_name`, `patientid`, `claimnumber`, `carrier`, `procdesc`, `dos`, `reason`, and `amount`, but using the canonical header row above avoids ambiguity.

## Clinical Notes Export Contract

Recommended JSON shape:

```json
{
  "notes": [
    {
      "PatientName": "Jane Doe",
      "MRN": "778899",
      "NoteDate": "2026-06-12",
      "Provider": "Dr. Smith",
      "Procedure": "Crown build-up tooth #30",
      "ClinicalNote": "Tooth fractured. Existing restoration failing. Full-coverage restoration recommended after recurrent decay and structural compromise were documented."
    }
  ]
}
```

Supported JSON containers are a top-level array or an object containing an array under keys such as `rows`, `items`, `data`, `claims`, or `notes`.

Canonical fields HAL normalizes for clinical notes:

- `PatientName`
- `MRN`
- `NoteDate`
- `Provider`
- `Procedure`
- `ClinicalNote`

Alias handling also accepts common variants such as `patient_name`, `chartnumber`, `entrydate`, `doctor`, `procdesc`, `note`, `narrative`, and `chartnote`.

## How To Run It

1. Start the bridge worker from `C:\Users\mreno\SoftDentBridge`.
2. Drop or export the three files into `C:\Users\mreno\SoftDentBridge\exports`.
3. Use `scripts\sync_softdent_bridge.ps1` for a one-time stage and refresh.
4. Use `scripts\watch_softdent_bridge.ps1` to watch that folder and refresh automatically when files change.

## Switch Modes

To activate whatever is currently present in `C:\Users\mreno\SoftDentBridge\exports`, run `softdent: activate bridge exports`.

To switch HAL back to the canonical demo dataset, run `softdent: activate demo mode`.

To remove the canonical SoftDent import files without changing the bridge source drop, run `softdent: clear staged bridge data`.

## Activate Current Bridge Exports

If you want to force the app into whatever state is currently sitting in `C:\Users\mreno\SoftDentBridge\exports`, run:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\NewRidgeFamilyFinancial\scripts\activate_softdent_bridge_exports.ps1"
```

That clears the canonical SoftDent import files first, then imports the current bridge export drop through the normal sync path.

If you prefer a VS Code task, run `softdent: activate bridge exports`.

## Seed Demo Data

If you want to repopulate the local demo state without waiting for real SoftDent exports, run:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\NewRidgeFamilyFinancial\scripts\seed_softdent_bridge_samples.ps1"
```

That command regenerates the canonical sample dashboard, claims, and clinical-note exports under `C:\Users\mreno\SoftDentBridge\exports`, then imports them into the canonical SoftDent import directory through the same sync path the live bridge uses.

If you prefer a VS Code task, run `softdent: seed sample bridge data` from the task runner.

If you want a clean demo toggle in one step, run:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\NewRidgeFamilyFinancial\scripts\activate_softdent_demo_mode.ps1"
```

That clears the canonical SoftDent import files first, then regenerates and imports the canonical demo exports.

If you prefer a VS Code task, run `softdent: activate demo mode` from the task runner.

## Clear Staged Demo Data

If you want the app to stop reading the imported bridge or demo files without deleting whatever is sitting in the bridge export drop, run:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\NewRidgeFamilyFinancial\scripts\clear_softdent_bridge_staged_files.ps1"
```

That only removes these canonical SoftDent import files:

- `C:\NewRidgeFamilyFinancial\app\data\imports\softdent\softdent_dashboard_data.json`
- `C:\NewRidgeFamilyFinancial\app\data\imports\softdent\softdent_claims_export.csv`
- `C:\NewRidgeFamilyFinancial\app\data\imports\softdent\softdent_clinical_notes_data.json`

It does not delete files from `C:\Users\mreno\SoftDentBridge\exports`, so you can clear the app state without touching the current bridge source drop.

If you prefer a VS Code task, run `softdent: clear staged bridge data` from the task runner.

If SoftDent can only emit a different filename or a different format for claims or notes, update the bridge config and the matching app environment variable before running the workbench.
