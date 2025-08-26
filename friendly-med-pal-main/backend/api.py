"""FastAPI application exposing the Drug Delivery Management System service.

Run (development):
    uvicorn backend.api:app --reload

The app serves JSON REST endpoints under /api and also serves the SPA index.html
from the project root so the frontend (converted static index.html) can call
the backend seamlessly (same origin). CORS is enabled permissively for dev.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Path as FPath, Query
import traceback
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


@app.get("/api/debug/routes", include_in_schema=False)
def debug_routes():  # simple diagnostic list
    return [
        {
            "path": r.path,
            "methods": sorted(m for m in r.methods if m not in {"HEAD", "OPTIONS"}),
            "name": r.name,
        }
        for r in app.router.routes
    ]


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


class BatchCreate(BaseModel):
    drug_id: int
    batch_no: Optional[str] = None
    isbn: Optional[str] = None
    producer: Optional[str] = None
    transporter: Optional[str] = None
    mfg_date: Optional[str] = None
    exp_date: Optional[str] = None
    quantity: int
    notes: Optional[str] = None

    @validator("quantity")
    def positive_qty(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be positive")
        return v

    @validator("exp_date")
    def validate_dates(cls, exp: Optional[str], values: dict[str, Optional[str]]):  # noqa: D401
        mfg: Optional[str] = values.get("mfg_date")  # type: ignore[arg-type]
        if exp and mfg and exp < mfg:
            raise ValueError("exp_date must be after mfg_date")
        return exp


class RemovalCreate(BaseModel):
    drug_id: int
    batch_no: Optional[str] = None
    reason: str
    quantity: int
    notes: Optional[str] = None

    @validator("reason")
    def reason_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reason required")
        return v

    @validator("quantity")
    def positive_qty(cls, v: int) -> int:  # noqa: D401
        if v <= 0:
            raise ValueError("quantity must be positive")
        return v


class AdjustRequest(BaseModel):
    drug_id: int
    delta: int
    reason: Optional[str] = "manual"

    @validator("delta")
    def non_zero(cls, v: int) -> int:  # noqa: D401
        if v == 0:
            raise ValueError("delta cannot be zero")
        return v


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


# ----------------------------- Inventory Endpoints ----------------------------
@app.get("/api/inventory/summary")
def inventory_summary():
    return service.inventory_summary()


@app.get("/api/inventory/transactions")
def inventory_transactions(limit: int = Query(300, ge=1, le=1000)):
    return service.list_transactions(limit=limit)


@app.post("/api/inventory/adjust", status_code=201)
def inventory_adjust(payload: AdjustRequest):
    tid = service.adjust_inventory(payload.drug_id, payload.delta, payload.reason or "manual")
    return {"id": tid}


@app.post("/api/drug_batches", status_code=201)
def create_batch(payload: BatchCreate):
    try:
        print(f"[API] /api/drug_batches payload: {payload.dict()}")
        bid = service.add_drug_batch(
            payload.drug_id,
            quantity=payload.quantity,
            batch_no=payload.batch_no,
            isbn=payload.isbn,
            producer=payload.producer,
            transporter=payload.transporter,
            mfg_date=payload.mfg_date,
            exp_date=payload.exp_date,
            notes=payload.notes,
        )
        return {"id": bid}
    except Exception as e:  # convert to 400/500 depending on type
        tb = traceback.format_exc()
        print(f"[API][Error] create_batch failed: {e}\n{tb}")
        # Provide structured error for frontend debugging
        raise HTTPException(status_code=400, detail=f"batch_error: {e}")


@app.get("/api/drug_batches")
def list_batches(drug_id: Optional[int] = None, limit: int = Query(200, ge=1, le=1000)):
    return service.list_batches(drug_id=drug_id, limit=limit)


@app.post("/api/drug_removals", status_code=201)
def create_removal(payload: RemovalCreate):
    rid = service.remove_stock(
        payload.drug_id, payload.quantity, payload.reason, batch_no=payload.batch_no, notes=payload.notes
    )
    return {"id": rid}


@app.get("/api/drug_removals")
def list_removals(drug_id: Optional[int] = None, limit: int = Query(200, ge=1, le=1000)):
    return service.list_removals(drug_id=drug_id, limit=limit)


# ----------------------------- Health -----------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


# ----------------------------- Additional CRUD for Frontend ------------------
class DrugUpdate(BaseModel):
    name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    stock: Optional[int] = None
    reorder_level: Optional[int] = None


@app.patch("/api/drugs/{drug_id}")
def update_drug(drug_id: int, payload: DrugUpdate):
    # Build dynamic SET clause
    fields = []
    params = []
    for col in ["name", "dosage", "frequency", "stock", "reorder_level"]:
        val = getattr(payload, col)
        if val is not None:
            fields.append(f"{col}=?")
            params.append(val)
    if not fields:
        return {"updated": 0}
    params.append(drug_id)
    cur = service.conn.execute(
        f"UPDATE drugs SET {', '.join(fields)} WHERE id=?", params
    )
    service.conn.commit()
    return {"updated": cur.rowcount}


@app.delete("/api/drugs/{drug_id}")
def delete_drug(drug_id: int):
    cur = service.conn.execute("DELETE FROM drugs WHERE id=?", (drug_id,))
    service.conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}


@app.get("/api/deliveries")
def list_deliveries():
    # Basic list for frontend expectations; maps delivery_date -> scheduled_for
    cur = service.conn.execute(
        """
        SELECT id, patient_id, drug_id, delivery_date AS scheduled_for, status,
               1 AS quantity, NULL AS notes
        FROM delivery_logs
        ORDER BY id DESC
        """
    )
    return [dict(r) for r in cur.fetchall()]


@app.delete("/api/deliveries/{delivery_id}")
def delete_delivery(delivery_id: int):
    cur = service.conn.execute("DELETE FROM delivery_logs WHERE id=?", (delivery_id,))
    service.conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}


@app.on_event("shutdown")
def on_shutdown():  # pragma: no cover
    service.close()
