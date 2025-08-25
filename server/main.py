"""Flask implementation of the Friendly Med Pal API.

Switched from FastAPI to Flask to avoid compiling Rust extensions (pydantic-core)
on environments without Rust / with SSL interception issues.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, request
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
            dosage TEXT
        )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            drug_id INTEGER NOT NULL,
            scheduled_for TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT,
            FOREIGN KEY(patient_id) REFERENCES patients(id),
            FOREIGN KEY(drug_id) REFERENCES drugs(id)
        )"""
        )
        conn.commit()


app = Flask(__name__)
CORS(app)
init_db()


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}

SQL_PATIENT_BY_ID = "SELECT * FROM patients WHERE id=?"
SQL_DRUG_BY_ID = "SELECT * FROM drugs WHERE id=?"
SQL_DELIVERY_BY_ID = "SELECT * FROM deliveries WHERE id=?"
NOT_FOUND = {"detail": "not found"}


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/stats")
def stats():
    with get_conn() as conn:
        cur = conn.cursor()
        patient_count = cur.execute("SELECT COUNT(*) c FROM patients").fetchone()[0]
        drug_count = cur.execute("SELECT COUNT(*) c FROM drugs").fetchone()[0]
        delivery_count = cur.execute("SELECT COUNT(*) c FROM deliveries").fetchone()[0]
        status_rows = cur.execute("SELECT status, COUNT(*) c FROM deliveries GROUP BY status").fetchall()
    status_map = {r[0]: r[1] for r in status_rows}
    return jsonify({
        "patients": patient_count,
        "drugs": drug_count,
        "deliveries": delivery_count,
        "status_breakdown": status_map,
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
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO drugs(name, dosage) VALUES (?,?)",
            (name, dosage),
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
    for col in ("name", "dosage"):
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
    with get_conn() as conn:
        cur = conn.cursor()
        if not cur.execute("SELECT 1 FROM patients WHERE id=?", (data["patient_id"],)).fetchone():
            return jsonify({"detail": "patient not found"}), 404
        if not cur.execute("SELECT 1 FROM drugs WHERE id=?", (data["drug_id"],)).fetchone():
            return jsonify({"detail": "drug not found"}), 404
        cur.execute(
            "INSERT INTO deliveries(patient_id, drug_id, scheduled_for, notes) VALUES (?,?,?,?)",
            (data["patient_id"], data["drug_id"], data["scheduled_for"], data.get("notes")),
        )
        did = cur.lastrowid
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
        ],
    })


@app.post("/api/seed")
def seed():
    payload = request.get_json(silent=True) or {}
    patients = payload.get("patients") or [
        {"name": "Alice", "age": 70, "condition": "Diabetes"},
        {"name": "Bob", "age": 64, "condition": "Hypertension"},
    ]
    drugs = payload.get("drugs") or [
        {"name": "Metformin", "dosage": "500mg"},
        {"name": "Lisinopril", "dosage": "10mg"},
    ]
    with get_conn() as conn:
        cur = conn.cursor()
        for p in patients:
            cur.execute(
                "INSERT INTO patients(name, age, condition) VALUES (?,?,?)",
                (p.get("name"), p.get("age"), p.get("condition")),
            )
        for d in drugs:
            cur.execute(
                "INSERT INTO drugs(name, dosage) VALUES(?,?)",
                (d.get("name"), d.get("dosage")),
            )
        conn.commit()
    return jsonify({"detail": "seeded"})


if __name__ == "__main__":  # pragma: no cover
    app.run(host="127.0.0.1", port=8000, debug=True)
