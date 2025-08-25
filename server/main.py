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
        patient_count = cur.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        drug_count = cur.execute("SELECT COUNT(*) FROM drugs").fetchone()[0]
        delivery_count = cur.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0]
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
