# Local AI Accounting Stack

This repo already has two of the three local accounting building blocks in place:

1. Database management system: SQLite already backs HAL state and local financial cache storage.
2. Script runner and automation: the repo already uses Python and PowerShell automation for staged imports and scheduled SoftDent refresh.
3. Document OCR: add local OCR so scanned invoices, receipts, and statements become queryable accounting records.

## Current Repo Mapping

- SQLite analytics and HAL state:
  - `hal_local.sqlite3`
  - `HAL_SQLITE_PATH`
  - `app/hal/storage.py`
- Existing automation and scheduled refresh:
  - `scripts/refresh_from_softdent_and_verify.py`
  - `scripts/scheduled_softdent_bridge_sync.ps1`
  - `scripts/watch_softdent_bridge.ps1`
- Approved staged import surface for HAL financial files:
  - `app/data_pipeline.py`
  - `app/routes.py`
  - `POST /api/hal9000/staged-imports`
  - `POST /api/hal9000/refresh-financial-sources`

## New OCR Connector

Use `scripts/process_financial_document.py` to extract local text from receipts, invoices, bank statements, and OCR-ready PDFs, then persist a normalized record into SQLite.

Supported inputs:

- `.pdf` via `ocrmypdf`
- `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp` via `tesseract`
- `.txt` without OCR

The script stores:

- source file path and hash
- document type
- vendor name
- invoice or receipt number when detected
- first detected document date
- total, subtotal, and tax when detected
- full extracted text and a short preview

The default database target is:

- `LOCAL_AI_ACCOUNTING_DB_PATH` when set
- otherwise `HAL_SQLITE_PATH` when set
- otherwise `hal_local.sqlite3` at repo root

## Local Install

Windows install guidance:

1. Install Tesseract OCR.
2. Install `ocrmypdf` in the repo virtual environment.
3. Install `qpdf` for PDF processing support.
4. Keep everything local. No cloud OCR or remote document upload is required.

## Usage

Single document:

```powershell
.\.venv\Scripts\python.exe .\scripts\process_financial_document.py `
  --input C:\AccountingInbox\invoice-2026-06.pdf `
  --json-output C:\AccountingInbox\invoice-2026-06.ocr.json
```

Inbox automation:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\process_financial_document_inbox.ps1 `
  -InboxPath C:\AccountingInbox `
  -ArchivePath C:\AccountingInbox\processed
```

Dry-run the PowerShell mover first:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\process_financial_document_inbox.ps1 `
  -InboxPath C:\AccountingInbox `
  -ArchivePath C:\AccountingInbox\processed `
  -WhatIf
```

Register the recurring OCR inbox task:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\register_local_accounting_ocr_task.ps1 `
  -InboxPath C:\AccountingInbox `
  -ArchivePath C:\AccountingInbox\processed `
  -RepeatMinutes 30
```

## How This Fits HAL

This does not push raw documents into the browser or into production accounting systems.

It gives HAL a local, queryable document ledger inside SQLite so it can:

- recall historical invoice and receipt text quickly
- search totals across years of scanned documents
- compare OCR-derived totals with imported QuickBooks or SoftDent summaries
- support local-only accounting workflows without widening the write surface

## Recommended Operating Pattern

1. Export structured financial data from SoftDent and QuickBooks as you already do.
2. Drop scanned receipts, vendor invoices, and statements into a local inbox.
3. Register `register_local_accounting_ocr_task.ps1` once, then let the inbox runner process files every 30 minutes.
4. Keep HAL’s approved staged imports limited to the existing allowlisted finance files.
5. Use the OCR ledger as a reference and reconciliation source, not as a direct posting source.
