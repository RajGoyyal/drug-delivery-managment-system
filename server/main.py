"""Flask implementation of the Friendly Med Pal API.

Switched from FastAPI to Flask to avoid compiling Rust extensions (pydantic-core)
on environments without Rust / with SSL interception issues.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any, Dict

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


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/patients")
def create_patient():
    data = request.get_json(force=True) or {}
    name = data.get("name")
    if not name:
        return jsonify({"detail": "name required"}), 400
    age = data.get("age")
    condition = data.get("condition")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO patients(name, age, condition) VALUES (?,?,?)",
            (name, age, condition),
        )
        pid = cur.lastrowid
        row = cur.execute("SELECT * FROM patients WHERE id=?", (pid,)).fetchone()
    return jsonify(row_to_dict(row)), 201


@app.get("/api/patients")
def list_patients():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM patients ORDER BY id DESC").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.post("/api/drugs")
def create_drug():
    data = request.get_json(force=True) or {}
    name = data.get("name")
    if not name:
        return jsonify({"detail": "name required"}), 400
    dosage = data.get("dosage")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO drugs(name, dosage) VALUES (?,?)",
            (name, dosage),
        )
        did = cur.lastrowid
        row = cur.execute("SELECT * FROM drugs WHERE id=?", (did,)).fetchone()
    return jsonify(row_to_dict(row)), 201


@app.get("/api/drugs")
def list_drugs():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM drugs ORDER BY id DESC").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.post("/api/deliveries")
def create_delivery():
    data = request.get_json(force=True) or {}
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
        row = cur.execute("SELECT * FROM deliveries WHERE id=?", (did,)).fetchone()
    return jsonify(row_to_dict(row)), 201


@app.get("/api/deliveries")
def list_deliveries():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM deliveries ORDER BY id DESC"
        ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.patch("/api/deliveries/<int:delivery_id>/status")
def update_delivery_status(delivery_id: int):
    data = request.get_json(force=True) or {}
    status = data.get("status")
    if status not in {"pending", "delivered", "missed", "cancelled"}:
        return jsonify({"detail": "invalid status"}), 400
    with get_conn() as conn:
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM deliveries WHERE id=?", (delivery_id,)).fetchone()
        if not row:
            return jsonify({"detail": "not found"}), 404
        cur.execute("UPDATE deliveries SET status=? WHERE id=?", (status, delivery_id))
        row = cur.execute("SELECT * FROM deliveries WHERE id=?", (delivery_id,)).fetchone()
    return jsonify(row_to_dict(row))


@app.get("/")
def root():
    return jsonify({
        "message": "API running",
        "endpoints": [
            "/api/health",
            "/api/patients",
            "/api/drugs",
            "/api/deliveries",
            "/api/deliveries/<id>/status (PATCH)",
        ],
    })


if __name__ == "__main__":  # pragma: no cover
    app.run(host="127.0.0.1", port=8000, debug=True)
