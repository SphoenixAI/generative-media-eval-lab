"""Minimal API boundary stub; Phase 10 is deliberately not implemented."""
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Sphoenix Evaluation Lab — offline checkpoint", docs_url=None, redoc_url=None)


@app.get("/health")
def health():
    return {"phase": 4, "mode": "offline", "paid_execution": False, "public_data_routes": "not_implemented"}


@app.post("/private/execute")
def execution_denied():
    raise HTTPException(403, "Live execution is disabled at this checkpoint")
