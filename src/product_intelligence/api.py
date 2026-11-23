"""Write-through event API. No public-facing authentication in this local reference app."""

import os
from datetime import date

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from product_intelligence.cohorts import account_experiment, retention
from product_intelligence.contracts import ProductEvent
from product_intelligence.metrics import activation_7d, weekly_active_accounts
from product_intelligence.store import connect, ingest

app = FastAPI(title="SaaS Product Intelligence", version="0.1.0")


class Accepted(BaseModel):
    accepted: bool
    duplicate: bool


def db_path() -> str:
    return os.getenv("PRODUCT_DB", "product_analytics.sqlite")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/events", response_model=Accepted, status_code=202)
def receive(event: ProductEvent):
    try:
        with connect(db_path()) as db:
            created = ingest(db, event)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return Accepted(accepted=True, duplicate=not created)


@app.get("/v1/metrics")
def metrics(as_of: date):
    with connect(db_path()) as db:
        return {"activation": activation_7d(db, as_of),
                "week_two_retention": retention(db, as_of),
                "onboarding_experiment": account_experiment(db, as_of, "onboarding-v1"),
                "weekly_active_accounts": weekly_active_accounts(db, as_of)}
