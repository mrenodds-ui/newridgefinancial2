# Open WebUI Local Knowledge Workflow

This repo now includes a repeatable builder for a local Open WebUI knowledge bundle.

## What It Stages

The builder copies a curated set of files into:

`C:\Users\mreno\open-webui-data\knowledge-imports\newridge-family-financial`

It creates three upload-ready collections:

- `01-core-docs`
- `02-accounting-policies`
- `03-live-softdent-exports`

The bundle also includes:

- `00-upload-order.md`
- `manifest.json`

## Run It

```powershell
powershell -ExecutionPolicy Bypass -File "C:\NewRidgeFamilyFinancial\scripts\build_open_webui_knowledge_corpus.ps1"
```

## Recommended Open WebUI Flow

1. Open `http://127.0.0.1:8080`.
2. Create one knowledge collection for repo and policy docs.
3. Upload the contents of `01-core-docs` and `02-accounting-policies`.
4. Create a separate collection for the live export data.
5. Upload the contents of `03-live-softdent-exports`.

Keeping live exports separate makes refreshes simpler because you can replace only the operational-data collection when new SoftDent files arrive.

## Refresh Cycle

Re-run the builder whenever any of these change:

- repo docs under `docs/`
- root SoftDent export files
- accounting policy docs

Then replace the matching files or collection contents in Open WebUI.

## Current Local Runtime

- Open WebUI is running locally on `127.0.0.1:8080`.
- Ollama is serving local models on `127.0.0.1:11434`.
- First startup downloads the default local embedding model used for retrieval.

## Notes

- The builder stages local copies only; it does not call Open WebUI APIs or require Open WebUI credentials.
- The live export collection contains current local SoftDent data staged in this repo, so treat that folder as sensitive local content.