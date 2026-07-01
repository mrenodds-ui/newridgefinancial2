"""Retired legacy host for New Ridge Family Financial.

NewRidgeFinancial 2.0 runs separately on port 8765.
Use StartNewRidgeFinancial2.bat.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="New Ridge Family Financial (retired)")

_RETIRED = {
    "status": "retired",
    "message": "This legacy program is for reference only.",
    "use_instead": {
        "program": "NewRidgeFinancial 2.0",
        "start": "StartNewRidgeFinancial2.bat",
        "url": "http://127.0.0.1:8765/",
    },
}


@app.get("/")
@app.get("/health")
@app.get("/app")
@app.get("/app/{request_path:path}")
def retired():
    return JSONResponse(status_code=410, content=_RETIRED)
