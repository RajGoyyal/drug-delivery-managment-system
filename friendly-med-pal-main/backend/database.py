"""
Database utilities for the Drug Delivery Management System.
Friendly, well-commented, and easy to extend.
"""
from __future__ import annotations

import sqlite3
from sqlite3 import Connection
from typing import Optional
from pathlib import Path

# Default database path (always resolved inside the backend package directory)
_BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = str(_BASE_DIR / "drug_delivery.db")

# --- Schema DDL -------------------------------------------------------------
# We keep the DDL here so it's easy to review and version.
# Note: We enable FOREIGN KEY constraints at connection time (PRAGMA below).

CREATE_TABLE_PATIENTS = """
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    age INTEGER CHECK(age >= 0),
    contact TEXT
);
"""

CREATE_TABLE_DRUGS = """
CREATE TABLE IF NOT EXISTS drugs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    dosage TEXT NOT NULL,      -- e.g., "500 mg"
    frequency TEXT NOT NULL    -- e.g., "2x/day"
);
"""

CREATE_TABLE_DELIVERY_LOGS = """
CREATE TABLE IF NOT EXISTS delivery_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    drug_id INTEGER NOT NULL,
    delivery_date TEXT NOT NULL,  -- store as ISO date string (YYYY-MM-DD) or datetime
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending','delivered','missed','cancelled'
    )),
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (drug_id) REFERENCES drugs(id) ON DELETE CASCADE
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_delivery_logs_patient ON delivery_logs(patient_id);",
    "CREATE INDEX IF NOT EXISTS idx_delivery_logs_drug ON delivery_logs(drug_id);",
    "CREATE INDEX IF NOT EXISTS idx_delivery_logs_date ON delivery_logs(delivery_date);",
]

# Additional inventory / batch related tables (added later in project lifecycle)
CREATE_TABLE_INVENTORY_TRANSACTIONS = """
CREATE TABLE IF NOT EXISTS inventory_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_id INTEGER NOT NULL,
    delta INTEGER NOT NULL,                 -- positive or negative change
    reason TEXT,                             -- free-form reason / source
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (drug_id) REFERENCES drugs(id) ON DELETE CASCADE
);
"""

CREATE_TABLE_DRUG_BATCHES = """
CREATE TABLE IF NOT EXISTS drug_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_id INTEGER NOT NULL,
    batch_no TEXT,
    isbn TEXT,
    producer TEXT,
    transporter TEXT,
    mfg_date TEXT,
    exp_date TEXT,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (drug_id) REFERENCES drugs(id) ON DELETE CASCADE
);
"""

CREATE_TABLE_DRUG_REMOVALS = """
CREATE TABLE IF NOT EXISTS drug_removals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_id INTEGER NOT NULL,
    batch_no TEXT,              -- optional: original batch reference / lot
    reason TEXT NOT NULL,       -- e.g. 'expired', 'damaged', 'manual'
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (drug_id) REFERENCES drugs(id) ON DELETE CASCADE
);
"""


def get_connection(db_path: Optional[str] = None) -> Connection:
    """Create and return a SQLite connection with sensible defaults.

    - Enables foreign keys
    - Sets row factory to sqlite3.Row for dict-like access
    """
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    # Enforce foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn


def init_db(conn: Connection) -> None:
    """Initialize database schema if it doesn't already exist.

    Safe to call multiple times. Prints friendly progress messages.
    """
    print("[DB] Initializing database schema…")
    with conn:  # implicit transaction
        conn.execute(CREATE_TABLE_PATIENTS)
        conn.execute(CREATE_TABLE_DRUGS)
        conn.execute(CREATE_TABLE_DELIVERY_LOGS)
        # Newer tables
        conn.execute(CREATE_TABLE_INVENTORY_TRANSACTIONS)
        conn.execute(CREATE_TABLE_DRUG_BATCHES)
        conn.execute(CREATE_TABLE_DRUG_REMOVALS)
        for ddl in CREATE_INDEXES:
            conn.execute(ddl)

        # Lightweight migration: ensure 'stock' & 'reorder_level' columns exist on drugs
        cur = conn.execute("PRAGMA table_info(drugs);")
        existing_cols = {row[1] for row in cur.fetchall()}
        if 'stock' not in existing_cols:
            try:
                conn.execute("ALTER TABLE drugs ADD COLUMN stock INTEGER NOT NULL DEFAULT 0;")
                print("[DB] Added drugs.stock column")
            except Exception as e:  # pragma: no cover - defensive
                print("[DB][Warn] Could not add stock column:", e)
        if 'reorder_level' not in existing_cols:
            try:
                conn.execute("ALTER TABLE drugs ADD COLUMN reorder_level INTEGER NOT NULL DEFAULT 0;")
                print("[DB] Added drugs.reorder_level column")
            except Exception as e:  # pragma: no cover
                print("[DB][Warn] Could not add reorder_level column:", e)
    print("[DB] Schema ready ✔")
