"""Flask implementation of the Friendly Med Pal API.

Switched from FastAPI to Flask to avoid compiling Rust extensions (pydantic-core)
on environments without Rust / with SSL interception issues.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
import os, sys, traceback

from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timezone, timedelta
# Flexible import so script runs both as package (python -m server.main) and standalone (python server/main.py)
try:  # package-relative
    from . import ai_service as _ai_service  # type: ignore
except Exception:
    try:
        import ai_service as _ai_service  # type: ignore
    except Exception:  # final fallback: disabled AI features
        _ai_service = None

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data.db"


def get_conn():
    """Create a new SQLite connection configured for concurrent-ish access.

    Adds WAL, busy timeout and foreign key enforcement. Failures to set pragmas are ignored.
    """
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=3000;")
        conn.execute("PRAGMA foreign_keys=ON;")
    except Exception:
        pass
    return conn
def init_db() -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER,
            condition TEXT
        )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS drugs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dosage TEXT,
            stock INTEGER DEFAULT 0,
            reorder_level INTEGER DEFAULT 0
        )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            drug_id INTEGER NOT NULL,
            scheduled_for TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT,
            stock_decremented INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(patient_id) REFERENCES patients(id),
            FOREIGN KEY(drug_id) REFERENCES drugs(id)
        )"""
        )
        # Inventory adjustment transactions
        cur.execute(
            """CREATE TABLE IF NOT EXISTS inventory_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drug_id INTEGER NOT NULL,
            delta INTEGER NOT NULL,
            reason TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(drug_id) REFERENCES drugs(id)
        )"""
        )
        # Lightweight migration: ensure stock / reorder_level exist (older DBs)
        try:
            existing_cols = {r[1] for r in cur.execute("PRAGMA table_info(drugs)").fetchall()}
            if 'stock' not in existing_cols:
                cur.execute("ALTER TABLE drugs ADD COLUMN stock INTEGER DEFAULT 0")
            if 'reorder_level' not in existing_cols:
                cur.execute("ALTER TABLE drugs ADD COLUMN reorder_level INTEGER DEFAULT 0")
            d_cols = {r[1] for r in cur.execute("PRAGMA table_info(deliveries)").fetchall()}
            if 'quantity' not in d_cols:
                cur.execute("ALTER TABLE deliveries ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1")
            if 'stock_decremented' not in d_cols:
                cur.execute("ALTER TABLE deliveries ADD COLUMN stock_decremented INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass
        # Helpful indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_deliveries_status ON deliveries(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_deliveries_patient ON deliveries(patient_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_deliveries_drug ON deliveries(drug_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_deliveries_sched ON deliveries(scheduled_for)")
        conn.commit()


app = Flask(__name__)
CORS(app)
init_db()


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}

SQL_PATIENT_BY_ID = "SELECT * FROM patients WHERE id=?"
SQL_DRUG_BY_ID = "SELECT * FROM drugs WHERE id=?"
SQL_DELIVERY_BY_ID = "SELECT * FROM deliveries WHERE id=?"
SQL_TXN_INSERT = "INSERT INTO inventory_transactions(drug_id, delta, reason) VALUES (?,?,?)"
SQL_COUNT_PATIENTS = "SELECT COUNT(*) FROM patients"
SQL_COUNT_DRUGS = "SELECT COUNT(*) FROM drugs"
SQL_COUNT_DELIVERIES = "SELECT COUNT(*) FROM deliveries"
NOT_FOUND = {"detail": "not found"}


@app.get("/api/health")
def health():
    """Readiness + liveness endpoint; validates DB connects quickly."""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            patient_any = cur.execute("SELECT 1 FROM patients LIMIT 1").fetchone()
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 503
    return jsonify({"status": "ok", "has_patients": bool(patient_any)})


@app.get("/api/stats")
def stats():
    """Aggregate counts + low stock list (fixed previous connection scope bug)."""
    with get_conn() as conn:
        cur = conn.cursor()
    patient_count = cur.execute(SQL_COUNT_PATIENTS).fetchone()[0]
    drug_count = cur.execute(SQL_COUNT_DRUGS).fetchone()[0]
    delivery_count = cur.execute(SQL_COUNT_DELIVERIES).fetchone()[0]
    status_rows = cur.execute("SELECT status, COUNT(*) FROM deliveries GROUP BY status").fetchall()
    low_stock_rows = cur.execute("SELECT id, name, stock, reorder_level FROM drugs WHERE stock <= reorder_level").fetchall()
    status_map = {r[0]: r[1] for r in status_rows}
    return jsonify({
        "patients": patient_count,
        "drugs": drug_count,
        "deliveries": delivery_count,
        "status_breakdown": status_map,
        "low_stock_drugs": len(low_stock_rows),
        "low_stock_list": [ {"id": r[0], "name": r[1], "stock": r[2], "reorder_level": r[3]} for r in low_stock_rows ],
    })


@app.post("/api/patients")
def create_patient():
    data: Dict[str, Any] = request.get_json(force=True) or {}
    name: Optional[str] = data.get("name")
    if not name:
        return jsonify({"detail": "name required"}), 400
    age: Optional[int] = data.get("age")
    condition: Optional[str] = data.get("condition")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO patients(name, age, condition) VALUES (?,?,?)",
            (name, age, condition),
        )
        pid = cur.lastrowid
        row = cur.execute(SQL_PATIENT_BY_ID, (pid,)).fetchone()
    return jsonify(row_to_dict(row)), 201


@app.get("/api/patients")
def list_patients():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM patients ORDER BY id DESC").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.patch("/api/patients/<int:patient_id>")
def update_patient(patient_id: int):
    data: Dict[str, Any] = request.get_json(force=True) or {}
    fields: List[str] = []
    values: List[Any] = []
    for col in ("name", "age", "condition"):
        if col in data:
            fields.append(f"{col}=?")
            values.append(data[col])
    if not fields:
        return jsonify({"detail": "no fields"}), 400
    with get_conn() as conn:
        cur = conn.cursor()
        row = cur.execute(SQL_PATIENT_BY_ID, (patient_id,)).fetchone()
        if not row:
            return jsonify(NOT_FOUND), 404
        cur.execute(f"UPDATE patients SET {', '.join(fields)} WHERE id=?", (*values, patient_id))
        row = cur.execute(SQL_PATIENT_BY_ID, (patient_id,)).fetchone()
    return jsonify(row_to_dict(row))


@app.delete("/api/patients/<int:patient_id>")
def delete_patient(patient_id: int):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM patients WHERE id=?", (patient_id,))
    return ("", 204)


@app.post("/api/drugs")
def create_drug():
    data: Dict[str, Any] = request.get_json(force=True) or {}
    name: Optional[str] = data.get("name")
    if not name:
        return jsonify({"detail": "name required"}), 400
    dosage: Optional[str] = data.get("dosage")
    stock = int(data.get("stock") or 0)
    reorder_level = int(data.get("reorder_level") or 0)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO drugs(name, dosage, stock, reorder_level) VALUES (?,?,?,?)",
            (name, dosage, stock, reorder_level),
        )
        did = cur.lastrowid
    row = cur.execute(SQL_DRUG_BY_ID, (did,)).fetchone()
    return jsonify(row_to_dict(row)), 201


@app.get("/api/drugs")
def list_drugs():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM drugs ORDER BY id DESC").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.patch("/api/drugs/<int:drug_id>")
def update_drug(drug_id: int):
    data: Dict[str, Any] = request.get_json(force=True) or {}
    fields: List[str] = []
    values: List[Any] = []
    for col in ("name", "dosage", "stock", "reorder_level"):
        if col in data:
            fields.append(f"{col}=?")
            values.append(data[col])
    if not fields:
        return jsonify({"detail": "no fields"}), 400
    with get_conn() as conn:
        cur = conn.cursor()
        row = cur.execute(SQL_DRUG_BY_ID, (drug_id,)).fetchone()
        if not row:
            return jsonify(NOT_FOUND), 404
        cur.execute(f"UPDATE drugs SET {', '.join(fields)} WHERE id=?", (*values, drug_id))
        row = cur.execute(SQL_DRUG_BY_ID, (drug_id,)).fetchone()
    return jsonify(row_to_dict(row))


@app.delete("/api/drugs/<int:drug_id>")
def delete_drug(drug_id: int):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM drugs WHERE id=?", (drug_id,))
    return ("", 204)


@app.post("/api/deliveries")
def create_delivery():
    data: Dict[str, Any] = request.get_json(force=True) or {}
    required = ["patient_id", "drug_id", "scheduled_for"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"detail": f"missing: {', '.join(missing)}"}), 400
    quantity = int(data.get("quantity") or 1)
    if quantity < 1:
        return jsonify({"detail": "quantity must be >=1"}), 400
    with get_conn() as conn:
        cur = conn.cursor()
        if not cur.execute("SELECT 1 FROM patients WHERE id=?", (data["patient_id"],)).fetchone():
            return jsonify({"detail": "patient not found"}), 404
        drug_row = cur.execute("SELECT * FROM drugs WHERE id=?", (data["drug_id"],)).fetchone()
        if not drug_row:
            return jsonify({"detail": "drug not found"}), 404
        current_stock = drug_row["stock"] or 0
        if current_stock < quantity:
            return jsonify({"detail": "insufficient stock"}), 400
        # Reserve stock immediately
        new_stock = current_stock - quantity
        cur.execute("UPDATE drugs SET stock=? WHERE id=?", (new_stock, data["drug_id"]))
        cur.execute(
            "INSERT INTO deliveries(patient_id, drug_id, scheduled_for, quantity, notes, stock_decremented) VALUES (?,?,?,?,?,1)",
            (data["patient_id"], data["drug_id"], data["scheduled_for"], quantity, data.get("notes")),
        )
        did = cur.lastrowid
        # Log inventory transaction
        cur.execute(
            SQL_TXN_INSERT,
             (data["drug_id"], -quantity, f"reserve delivery #{did}"),
        )
    row = cur.execute(SQL_DELIVERY_BY_ID, (did,)).fetchone()
    return jsonify(row_to_dict(row)), 201


@app.get("/api/deliveries")
def list_deliveries():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM deliveries ORDER BY id DESC"
        ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.delete("/api/deliveries/<int:delivery_id>")
def delete_delivery(delivery_id: int):
    with get_conn() as conn:
        cur = conn.cursor()
        # if reserved stock not consumed, restore
        row = cur.execute(SQL_DELIVERY_BY_ID, (delivery_id,)).fetchone()
        if row and row["stock_decremented"] == 1 and row["quantity"]:
            cur.execute("UPDATE drugs SET stock = stock + ? WHERE id=?", (row["quantity"], row["drug_id"]))
            cur.execute(
                SQL_TXN_INSERT,
                 (row["drug_id"], row["quantity"], f"delete delivery #{delivery_id}"),
            )
        cur.execute("DELETE FROM deliveries WHERE id=?", (delivery_id,))
    return ("", 204)


@app.patch("/api/deliveries/<int:delivery_id>/status")
def update_delivery_status(delivery_id: int):
    data: Dict[str, Any] = request.get_json(force=True) or {}
    status: Optional[str] = data.get("status")
    if status not in {"pending", "delivered", "missed", "cancelled"}:
        return jsonify({"detail": "invalid status"}), 400
    with get_conn() as conn:
        cur = conn.cursor()
        row = cur.execute(SQL_DELIVERY_BY_ID, (delivery_id,)).fetchone()
        if not row:
            return jsonify(NOT_FOUND), 404
        old_status = row["status"]
        quantity = row["quantity"] or 1
        drug_id = row["drug_id"]
        stock_dec = row["stock_decremented"] == 1
        # Transition logic: if moving to cancelled and stock reserved, release
        if status == "cancelled" and stock_dec:
            cur.execute("UPDATE drugs SET stock = stock + ? WHERE id=?", (quantity, drug_id))
            cur.execute(
                SQL_TXN_INSERT,
                 (drug_id, quantity, f"cancel delivery #{delivery_id}"),
            )
            cur.execute("UPDATE deliveries SET stock_decremented=0 WHERE id=?", (delivery_id,))
        # If moving from cancelled back to pending/delivered/missed ensure stock available and reserve again if not already
        if old_status == "cancelled" and status != "cancelled" and not stock_dec:
            drug_row = cur.execute("SELECT stock FROM drugs WHERE id=?", (drug_id,)).fetchone()
            if not drug_row:
                return jsonify({"detail": "drug missing"}), 400
            if (drug_row["stock"] or 0) < quantity:
                return jsonify({"detail": "insufficient stock"}), 400
            cur.execute("UPDATE drugs SET stock = stock - ? WHERE id=?", (quantity, drug_id))
            cur.execute(
                SQL_TXN_INSERT,
                 (drug_id, -quantity, f"re-reserve delivery #{delivery_id}"),
            )
            cur.execute("UPDATE deliveries SET stock_decremented=1 WHERE id=?", (delivery_id,))
        cur.execute("UPDATE deliveries SET status=? WHERE id=?", (status, delivery_id))
        row = cur.execute(SQL_DELIVERY_BY_ID, (delivery_id,)).fetchone()
    return jsonify(row_to_dict(row))


@app.get("/")
def root():
    return jsonify({
        "message": "API running",
        "endpoints": [
            "/api/health",
            "/api/stats",
            "/api/patients",
            "/api/drugs",
            "/api/deliveries",
            "/api/deliveries/<id>/status (PATCH)",
            "/api/inventory/adjust (POST)",
            "/api/inventory/transactions",
            "/api/inventory/summary",
            "/api/insights",
            "/api/ai/summary",
            "/api/ai/chat",
            "/api/ai/answer",
            "/api/ai/status",
        ],
    })


@app.post("/api/seed")
def seed():
    raw = request.get_json(silent=True) or {}
    payload: Dict[str, Any] = raw if isinstance(raw, dict) else {}
    patients_in = payload.get("patients")
    if not isinstance(patients_in, list):
        patients_in = [
            {"name": "Alice", "age": 70, "condition": "Diabetes"},
            {"name": "Bob", "age": 64, "condition": "Hypertension"},
        ]
    drugs_in = payload.get("drugs")
    if not isinstance(drugs_in, list):
        drugs_in = [
            {"name": "Metformin", "dosage": "500mg", "stock": 120, "reorder_level": 40},
            {"name": "Lisinopril", "dosage": "10mg", "stock": 80, "reorder_level": 30},
        ]
    with get_conn() as conn:
        cur = conn.cursor()
        for p in patients_in:
            cur.execute(
                "INSERT INTO patients(name, age, condition) VALUES (?,?,?)",
                (p.get("name"), p.get("age"), p.get("condition")),
            )
        for d in drugs_in:
            cur.execute(
                "INSERT INTO drugs(name, dosage, stock, reorder_level) VALUES(?,?,?,?)",
                (d.get("name"), d.get("dosage"), int(d.get("stock") or 0), int(d.get("reorder_level") or 0)),
            )
        conn.commit()
    return jsonify({"detail": "seeded"})


@app.post("/api/inventory/adjust")
def inventory_adjust():
    data: Dict[str, Any] = request.get_json(force=True) or {}
    drug_id = data.get("drug_id")
    delta = data.get("delta")
    reason = data.get("reason") or None
    if drug_id is None or delta is None:
        return jsonify({"detail": "drug_id and delta required"}), 400
    try:
        delta = int(delta)
    except ValueError:
        return jsonify({"detail": "delta must be integer"}), 400
    with get_conn() as conn:
        cur = conn.cursor()
        row = cur.execute(SQL_DRUG_BY_ID, (drug_id,)).fetchone()
        if not row:
            return jsonify(NOT_FOUND), 404
        current_stock = row["stock"] or 0
        new_stock = current_stock + delta
        if new_stock < 0:
            new_stock = 0
        cur.execute("UPDATE drugs SET stock=? WHERE id=?", (new_stock, drug_id))
        cur.execute(
            SQL_TXN_INSERT,
             (drug_id, delta, reason),
         )
        row = cur.execute(SQL_DRUG_BY_ID, (drug_id,)).fetchone()
    return jsonify(row_to_dict(row))


@app.get("/api/inventory/transactions")
def inventory_transactions():
    limit = int(request.args.get("limit", 200))
    drug_id = request.args.get("drug_id")
    with get_conn() as conn:
        if drug_id:
            rows = conn.execute(
                "SELECT * FROM inventory_transactions WHERE drug_id=? ORDER BY id DESC LIMIT ?",
                (drug_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM inventory_transactions ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.get("/api/inventory/summary")
def inventory_summary():
    """Return per‑drug inventory metrics including pending quantities and usage velocity."""
    with get_conn() as conn:
        cur = conn.cursor()
        rows = cur.execute(
            """
            WITH recent AS (
                SELECT drug_id, SUM(quantity) qty
                FROM deliveries
                WHERE scheduled_for >= datetime('now','-14 day')
                GROUP BY drug_id
            ),
            pending AS (
                SELECT drug_id,
                       COALESCE(SUM(CASE WHEN status='pending' THEN quantity END),0) pending_qty,
                       COALESCE(COUNT(CASE WHEN status='pending' THEN 1 END),0) pending_count
                FROM deliveries
                GROUP BY drug_id
            )
            SELECT d.id, d.name, d.dosage, d.stock, d.reorder_level,
                   COALESCE(p.pending_qty,0) AS pending_quantity,
                   COALESCE(p.pending_count,0) AS pending_deliveries,
                   ROUND(COALESCE(r.qty,0)/14.0,2) AS daily_avg,
                   CASE WHEN COALESCE(r.qty,0) > 0 THEN ROUND(d.stock / (COALESCE(r.qty,0)/14.0),1) ELSE NULL END AS days_supply
            FROM drugs d
            LEFT JOIN pending p ON p.drug_id = d.id
            LEFT JOIN recent r ON r.drug_id = d.id
            ORDER BY d.name
            """
        ).fetchall()
    return jsonify([
        {
            "id": r[0],
            "name": r[1],
            "dosage": r[2],
            "stock": r[3],
            "reorder_level": r[4],
            "pending_quantity": r[5],
            "pending_deliveries": r[6],
            "daily_avg": r[7],
            "days_supply": r[8],
        } for r in rows
    ])


def compute_insights(horizon_days: int = 14) -> Dict[str, Any]:
    """Produce heuristic insights dict (shared by route & RAG context)."""
    since = datetime.now(timezone.utc) - timedelta(days=horizon_days)
    with get_conn() as conn:
        cur = conn.cursor()
        adh_row = cur.execute(
            """
            SELECT 
              SUM(CASE WHEN status='delivered' THEN 1 ELSE 0 END) delivered,
              SUM(CASE WHEN status='missed' THEN 1 ELSE 0 END) missed
            FROM deliveries
            WHERE scheduled_for >= ?
            """,
            (since.isoformat(),)
        ).fetchone()
        delivered = (adh_row[0] or 0)
        missed = (adh_row[1] or 0)
        adherence_rate = round(delivered / (delivered + missed) * 100, 1) if (delivered + missed) else None
        risk_rows = cur.execute(
            """
            SELECT patient_id,
                   SUM(CASE WHEN status='missed' THEN 1 ELSE 0 END) missed,
                   SUM(CASE WHEN status='delivered' THEN 1 ELSE 0 END) delivered
            FROM deliveries
            WHERE scheduled_for >= ?
            GROUP BY patient_id
            HAVING missed >= 1
            ORDER BY missed DESC, delivered ASC
            LIMIT 8
            """,
            (since.isoformat(),)
        ).fetchall()
        patient_names = {r[0]: r[1] for r in cur.execute("SELECT id, name FROM patients").fetchall()}
        risk_patients = [
            {"patient_id": r[0], "name": patient_names.get(r[0], f"Patient {r[0]}"), "missed": r[1], "delivered": r[2]}
            for r in risk_rows
        ]
        inv_rows = cur.execute(
            """
            WITH recent AS (
                SELECT drug_id, SUM(quantity) qty
                FROM deliveries
                WHERE scheduled_for >= datetime('now','-30 day')
                GROUP BY drug_id
            )
            SELECT d.id, d.name, d.stock, d.reorder_level,
                   COALESCE(r.qty,0) AS qty30
            FROM drugs d
            LEFT JOIN recent r ON r.drug_id = d.id
            ORDER BY d.name
            """
        ).fetchall()
    inventory_issues: List[Dict[str, Any]] = []
    recommendations: List[str] = []
    for _id, name, stock, reorder_level, qty30 in inv_rows:
        daily = (qty30 / 30.0) if qty30 else 0.0
        days_supply = round(stock / daily, 1) if daily > 0 else None
        low_threshold = (reorder_level or 0)
        severity = None
        if stock <= low_threshold:
            severity = "LOW" if (days_supply or 999) >= 3 else "CRITICAL"
        elif days_supply is not None and days_supply < 5:
            severity = "CRITICAL"
        if severity:
            inventory_issues.append({
                "drug_id": _id,
                "name": name,
                "stock": stock,
                "reorder_level": reorder_level,
                "days_supply": days_supply,
                "severity": severity,
            })
            if severity == "CRITICAL":
                target_days = 21
                if daily > 0:
                    needed = int(max(0, (daily * target_days) - stock))
                else:
                    base = reorder_level * 2 if reorder_level else 50
                    needed = int(base)
                if needed > 0:
                    recommendations.append(
                        f"Consider reordering ~{needed} units of {name} (stock {stock}, days supply {days_supply})."
                    )
    if (delivered + missed):
        if adherence_rate is not None:
            if adherence_rate < 85:
                recommendations.append(
                    f"Overall adherence is {adherence_rate}%. Investigate missed doses."
                )
            elif adherence_rate < 95:
                recommendations.append(
                    f"Adherence at {adherence_rate}% is moderate; aim for >=95%."
                )
    if not recommendations and not inventory_issues and not risk_patients:
        recommendations.append("System stable: no immediate risks detected.")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "horizon_days": horizon_days,
        "adherence": {
            "overall_percent": adherence_rate,
            "risk_patients": risk_patients,
        },
        "inventory": {"issues": inventory_issues},
        "recommendations": recommendations,
        "disclaimer": "Heuristic preview – not medical advice.",
    }


@app.get("/api/insights")
def insights():
    horizon_days = int(request.args.get("horizon", 14))
    return jsonify(compute_insights(horizon_days))


def _ai_enabled():
    return bool(_ai_service and getattr(_ai_service, 'ai_enabled', lambda: False)())

@app.get("/api/ai/summary")
def ai_summary():
    # Gather stats + insights for summary
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            patient_count = cur.execute(SQL_COUNT_PATIENTS).fetchone()[0]
            drug_count = cur.execute(SQL_COUNT_DRUGS).fetchone()[0]
            delivery_count = cur.execute(SQL_COUNT_DELIVERIES).fetchone()[0]
            low_stock = cur.execute("SELECT COUNT(*) FROM drugs WHERE stock <= reorder_level").fetchone()[0]
        stats = {"patients": patient_count, "drugs": drug_count, "deliveries": delivery_count, "low_stock_drugs": low_stock}
        # Reuse internal insights logic via request dispatch (cheap call)
        insights_data = insights().json if hasattr(insights(), 'json') else None  # fallback if direct
        if not insights_data:
            # If direct call caused duplicate execution, just skip
            insights_data = {}
        if _ai_service and hasattr(_ai_service, 'summarize'):
            summary = _ai_service.summarize({"stats": stats, "insights": insights_data})
        else:
            summary = "AI module unavailable. Provide GOOGLE_GENAI_API_KEY and restart."
        return jsonify({"summary": summary, "ai": _ai_enabled()})
    except Exception as e:
        return jsonify({"summary": f"Summary unavailable: {e}", "ai": False}), 500


@app.post("/api/ai/chat")
def ai_chat():
    data = request.get_json(force=True) or {}
    history = data.get("history") or []
    if not isinstance(history, list):
        return jsonify({"detail": "history must be a list"}), 400
    # Coerce shape
    sanitized = []
    for m in history[-12:]:
        if isinstance(m, dict) and isinstance(m.get("content"), str):
            role = m.get("role", "user")
            if role not in ("user", "assistant"): role = "user"
            sanitized.append({"role": role, "content": m["content"][:2000]})
    if not (_ai_service and hasattr(_ai_service, 'chat_reply')):
        fallback = "AI module not loaded. Set GOOGLE_GENAI_API_KEY and restart server."
        sanitized.append({"role": "assistant", "content": fallback})
        return jsonify({"reply": fallback, "history": sanitized, "ai": False}), 200
    try:
        reply = _ai_service.chat_reply(sanitized)
        sanitized.append({"role": "assistant", "content": reply})
        return jsonify({"reply": reply, "history": sanitized, "ai": _ai_enabled()})
    except Exception as e:
        err = f"AI error: {e}"
        sanitized.append({"role": "assistant", "content": err})
        return jsonify({"reply": err, "history": sanitized, "ai": False}), 500


@app.get("/api/ai/status")
def ai_status():
    enabled = _ai_enabled()
    model = None
    if _ai_service:
        model = getattr(_ai_service, 'DEFAULT_MODEL', None)
    reason = None
    if not enabled:
        if not _ai_service:
            reason = "ai_service module not loaded"
        elif not getattr(_ai_service, 'ai_enabled', lambda: False)():
            reason = "GOOGLE_GENAI_API_KEY not set or placeholder"
        else:
            reason = "unknown"
    last_err = None
    try:
        if _ai_service:
            last_err = getattr(_ai_service, 'LAST_AI_ERROR', None)
    except Exception:
        last_err = None
    return jsonify({
        "ai": enabled,
        "model": model,
        "reason": reason,
        "last_ai_error": last_err,
    })


def _tokenize(text: str) -> List[str]:
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return []
    return [t for t in ''.join(c.lower() if (c.isalnum() or c in ('-')) else ' ' for c in (text or '')).split() if t]


_RAG_CACHE: Dict[str, Any] = {"ts": 0, "insights": None}

def _build_rag_context(question: str) -> Dict[str, Any]:
    terms = set(_tokenize(question))
    ctx: Dict[str, Any] = {}
    now_ts = datetime.now(timezone.utc).timestamp()
    with get_conn() as conn:
        cur = conn.cursor()
        patient_count = cur.execute(SQL_COUNT_PATIENTS).fetchone()[0]
        drug_count = cur.execute(SQL_COUNT_DRUGS).fetchone()[0]
        delivery_count = cur.execute(SQL_COUNT_DELIVERIES).fetchone()[0]
        low_stock_rows = cur.execute("SELECT id,name,stock,reorder_level FROM drugs WHERE stock <= reorder_level LIMIT 60").fetchall()
        patients = cur.execute("SELECT id,name,age,condition FROM patients LIMIT 600").fetchall()
        drugs = cur.execute("SELECT id,name,dosage,stock,reorder_level FROM drugs LIMIT 600").fetchall()
        deliveries = cur.execute("SELECT id,patient_id,drug_id,scheduled_for,status,quantity,notes FROM deliveries ORDER BY id DESC LIMIT 200").fetchall()
    ctx['stats'] = {"patients": patient_count, "drugs": drug_count, "deliveries": delivery_count, "low_stock": len(low_stock_rows)}
    # Scoring function: term overlap across name + condition / notes
    def score_tokens(*texts: str) -> int:
        local_terms: set[str] = set()
        for t in texts:
            local_terms.update(_tokenize(t))
        return len(local_terms & terms)
    patient_matches = []
    for r in patients:
        sc = score_tokens(r[1] or '', r[3] or '')
        if sc:
            patient_matches.append((sc, {"id": r[0], "name": r[1], "age": r[2], "condition": r[3]}))
    drug_matches = []
    for r in drugs:
        sc = score_tokens(r[1] or '')
        if sc:
            drug_matches.append((sc, {"id": r[0], "name": r[1], "dosage": r[2], "stock": r[3], "reorder_level": r[4]}))
    delivery_matches = []
    for r in deliveries:
        # r indices: 0 id,1 patient_id,2 drug_id,3 scheduled_for,4 status(str),5 quantity(int),6 notes(str)
        sc = score_tokens(r[4] or '', r[6] or '')  # status + notes (fix wrong index that caused int iteration)
        if sc:
            delivery_matches.append((sc, {"id": r[0], "patient_id": r[1], "drug_id": r[2], "scheduled_for": r[3], "status": r[4], "quantity": r[5], "notes": r[6]}))
    patient_matches.sort(key=lambda x: -x[0])
    drug_matches.sort(key=lambda x: -x[0])
    delivery_matches.sort(key=lambda x: -x[0])
    if patient_matches:
        ctx['matched_patients'] = [m[1] for m in patient_matches[:40]]
    if drug_matches:
        ctx['matched_drugs'] = [m[1] for m in drug_matches[:40]]
    if delivery_matches:
        ctx['matched_deliveries'] = [m[1] for m in delivery_matches[:60]]
    ctx['recent_deliveries'] = [
        {"id": r[0], "patient_id": r[1], "drug_id": r[2], "scheduled_for": r[3], "status": r[4], "quantity": r[5]} for r in deliveries[:120]
    ]
    ctx['low_stock_list'] = [
        {"id": r[0], "name": r[1], "stock": r[2], "reorder_level": r[3]} for r in low_stock_rows[:60]
    ]
    # Cache insights for 60s
    if _RAG_CACHE['insights'] is None or (now_ts - _RAG_CACHE['ts']) > 60:
        try:
            _RAG_CACHE['insights'] = compute_insights()
            _RAG_CACHE['ts'] = now_ts
        except Exception:
            _RAG_CACHE['insights'] = {}
    ctx['insights'] = _RAG_CACHE['insights'] or {}
    ctx['query_terms'] = list(terms)[:40]
    return ctx


@app.post('/api/ai/answer')
def ai_answer():
    data = request.get_json(force=True) or {}
    question_raw = data.get('question')
    question = (question_raw or '').strip()
    include_ctx = bool(data.get('include_context'))
    if not question:
        return jsonify({"detail": "question required"}), 400
    if not (_ai_service and hasattr(_ai_service, 'answer_with_context')):
        return jsonify({"answer": "AI module not loaded.", "ai": False}), 200
    try:
        ctx = _build_rag_context(question)
        answer = _ai_service.answer_with_context(question, ctx)
        resp: Dict[str, Any] = {"answer": answer, "ai": _ai_enabled(), "context_keys": list(ctx.keys())}
        if include_ctx:
            # Provide truncated context excerpt for transparency
            import json as _json
            excerpt = _json.dumps(ctx)[:4000]
            resp['context_excerpt'] = excerpt
        return jsonify(resp)
    except Exception as e:
        return jsonify({"answer": f"RAG answer failed: {e}", "ai": False}), 500


@app.errorhandler(Exception)
def handle_unhandled(e: Exception):
    """Global 500 handler to avoid silent failures causing frontend hangs."""
    traceback.print_exc()
    if os.environ.get("DEBUG_ERRORS"):
        return jsonify({"detail": "internal error", "error": str(e), "trace": traceback.format_exc().splitlines()[-6:]}), 500
    return jsonify({"detail": "internal error"}), 500


if __name__ == "__main__":  # pragma: no cover
    import os, sys
    host = os.environ.get("HOST", "0.0.0.0")  # bind all interfaces by default
    try:
        port = int(os.environ.get("PORT", "8000"))
    except ValueError:
        port = 8000
    print(f"[startup] Friendly Med Pal API starting on http://{host}:{port} (override with HOST / PORT env vars)", flush=True)
    try:
        app.run(host=host, port=port, debug=True)
    except OSError as e:
        print(f"[error] Failed to bind {host}:{port} -> {e}", file=sys.stderr)
        if "in use" in str(e).lower():
            alt = port + 1
            print(f"[startup] Retrying on port {alt}", flush=True)
            app.run(host=host, port=alt, debug=True)
