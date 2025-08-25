"""FastAPI application exposing the Drug Delivery Management System service.

Run (development):
    uvicorn backend.api:app --reload

The app serves JSON REST endpoints under /api and also serves the SPA index.html
from the project root so the frontend (converted static index.html) can call
the backend seamlessly (same origin). CORS is enabled permissively for dev.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Path as FPath
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, validator

from .service import DrugDeliveryService, ALLOWED_STATUSES

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_FILE = PROJECT_ROOT / "index.html"

service = DrugDeliveryService()

app = FastAPI(title="MedDelivery API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # relax for dev; tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------- Pydantic Models --------------------------------
class PatientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    age: int = Field(..., ge=0, le=150)
    contact: Optional[str] = Field(None, max_length=255)


class DrugCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    dosage: str = Field(..., min_length=1, max_length=100)
    frequency: str = Field(..., min_length=1, max_length=100)


class DeliveryCreate(BaseModel):
    patient_id: int
    drug_id: int
    delivery_date: str  # ISO date (YYYY-MM-DD)
    status: str = "pending"

    @validator("delivery_date")
    def valid_date(cls, v: str) -> str:  # noqa: D401
        try:
            date.fromisoformat(v)
        except ValueError as e:  # pragma: no cover - simple validation
            raise ValueError("delivery_date must be ISO YYYY-MM-DD") from e
        return v

    @validator("status")
    def valid_status(cls, v: str) -> str:
        if v not in ALLOWED_STATUSES:
            raise ValueError(f"status must be one of {sorted(ALLOWED_STATUSES)}")
        return v


class DeliveryStatusUpdate(BaseModel):
    status: str

    @validator("status")
    def valid_status(cls, v: str) -> str:  # noqa: D401
        if v not in ALLOWED_STATUSES:
            raise ValueError(f"status must be one of {sorted(ALLOWED_STATUSES)}")
        return v


class Stats(BaseModel):
    totalPatients: int
    totalDrugs: int
    pendingDeliveries: int
    completedToday: int
    missedDeliveries: int
    upcomingDeliveries: int


# ----------------------------- Helper Logic -----------------------------------
def compute_stats() -> Stats:
    # Query counts directly with SQL for efficiency
    conn = service.conn
    cur = conn.cursor()
    total_patients = cur.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    total_drugs = cur.execute("SELECT COUNT(*) FROM drugs").fetchone()[0]
    today_iso = date.today().isoformat()
    pending_deliveries = cur.execute(
        "SELECT COUNT(*) FROM delivery_logs WHERE status='pending'"
    ).fetchone()[0]
    completed_today = cur.execute(
        "SELECT COUNT(*) FROM delivery_logs WHERE status='delivered' AND delivery_date=?",
        (today_iso,),
    ).fetchone()[0]
    missed_deliveries = cur.execute(
        "SELECT COUNT(*) FROM delivery_logs WHERE status='missed'"
    ).fetchone()[0]
    upcoming_deliveries = cur.execute(
        "SELECT COUNT(*) FROM delivery_logs WHERE status='pending' AND delivery_date>=?",
        (today_iso,),
    ).fetchone()[0]
    return Stats(
        totalPatients=total_patients,
        totalDrugs=total_drugs,
        pendingDeliveries=pending_deliveries,
        completedToday=completed_today,
        missedDeliveries=missed_deliveries,
        upcomingDeliveries=upcoming_deliveries,
    )


# ----------------------------- SPA Root ---------------------------------------
@app.get("/", include_in_schema=False)
def spa_root():  # pragma: no cover - static file serving
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE)
    raise HTTPException(status_code=404, detail="index.html not found")


# ----------------------------- Patient Endpoints ------------------------------
@app.get("/api/patients")
def list_patients():
    cur = service.conn.execute("SELECT id, name, age, contact FROM patients ORDER BY id ASC")
    return [dict(row) for row in cur.fetchall()]


@app.post("/api/patients", status_code=201)
def create_patient(payload: PatientCreate):
    new_id = service.add_patient(payload.name, payload.age, payload.contact)
    return {"id": new_id}


# ----------------------------- Drug Endpoints ---------------------------------
@app.get("/api/drugs")
def list_drugs():
    cur = service.conn.execute(
        "SELECT id, name, dosage, frequency FROM drugs ORDER BY id ASC"
    )
    return [dict(row) for row in cur.fetchall()]


@app.post("/api/drugs", status_code=201)
def create_drug(payload: DrugCreate):
    new_id = service.add_drug(payload.name, payload.dosage, payload.frequency)
    return {"id": new_id}


# ----------------------------- Delivery Endpoints -----------------------------
@app.post("/api/deliveries", status_code=201)
def record_delivery(payload: DeliveryCreate):
    new_id = service.record_delivery(
        patient_id=payload.patient_id,
        drug_id=payload.drug_id,
        delivery_date=payload.delivery_date,
        status=payload.status,
    )
    return {"id": new_id}


@app.get("/api/deliveries/patient/{patient_id}")
def delivery_history(patient_id: int = FPath(..., ge=1)):
    return service.fetch_delivery_history(patient_id)


@app.patch("/api/deliveries/{delivery_id}/status")
def update_delivery_status(delivery_id: int = FPath(..., ge=1), payload: DeliveryStatusUpdate = None):
    service.update_delivery_status(delivery_id, payload.status)
    return {"ok": True}


# ----------------------------- Stats Endpoint ---------------------------------
@app.get("/api/stats", response_model=Stats)
def get_stats():
    return compute_stats()


# ----------------------------- Health -----------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.on_event("shutdown")
def on_shutdown():  # pragma: no cover
    service.close()
