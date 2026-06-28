# NewRidgeFinancial 2.0

Active program: **NewRidgeFinancial 2.0**.

This repository now runs as a simple local program:

- no React or Vite active runtime
- no FastAPI backend dependency
- no database dependency
- no API dependency
- no frontend/backend coupling
- local static server only, bound to `127.0.0.1:1966`

The old program is kept for reference only. It is not used to render the active
program.

## Run

Double-click:

```text
StartNewRidgeFinancial2.bat
```

Then open:

```text
http://127.0.0.1:1966/
```

## Stop

Double-click:

```text
StopNewRidgeFinancial2.bat
```

## Active Program Files

```text
NewRidgeFinancial2/
  serve.py
  site/
    index.html
    styles.css
    app.js
    pages/
      01-financial-dashboard.png
      02-softdent.png
      03-quickbooks.png
      04-ar-collections.png
      05-claims-workbench.png
      06-insurance-narratives.png
      07-accounting-documents.png
      08-document-library.png
      09-hal-command-center.png
```

## Legacy Reference

The old application code is reference-only:

- `_legacy/`
- `app/`
- `frontend/`
- old API/docs/test assets

Do not use the legacy program to render NewRidgeFinancial 2.0.
