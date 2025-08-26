"""
Data access layer (DAO/Service) for the Drug Delivery Management System.
Uses sqlite3 and keeps things modular, friendly, and easy to extend.
"""
from __future__ import annotations

import sqlite3
from typing import Dict, List, Optional, Any

from .database import get_connection, init_db, DEFAULT_DB_PATH

# Allowed status values for deliveries (kept in sync with the table CHECK constraint)
ALLOWED_STATUSES = {"pending", "delivered", "missed", "cancelled"}


class DrugDeliveryService:
    """High-level service that wraps common operations.

    It manages its own connection and ensures the schema exists.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        self.conn = get_connection(self.db_path)
        init_db(self.conn)
        print(f"[Service] Connected to database at '{self.db_path}'")

    # --- Patient operations -------------------------------------------------
    def add_patient(self, name: str, age: int, contact: Optional[str] = None) -> int:
        """Add a new patient and return the new patient ID."""
        try:
            with self.conn:  # transaction
                cur = self.conn.execute(
                    "INSERT INTO patients (name, age, contact) VALUES (?, ?, ?)",
                    (name, age, contact),
                )
                new_id_raw = cur.lastrowid
                new_id = int(new_id_raw) if new_id_raw is not None else 0
            print(f"[Patients] Added patient id={new_id} name='{name}' age={age}")
            return new_id
        except sqlite3.IntegrityError as e:
            print(f"[Patients][Error] Integrity error adding patient: {e}")
            raise
        except Exception as e:
            print(f"[Patients][Error] Unexpected error adding patient: {e}")
            raise

    # --- Drug operations ----------------------------------------------------
    def add_drug(self, name: str, dosage: str, frequency: str) -> int:
        """Add a new drug and return the new drug ID."""
        try:
            with self.conn:
                cur = self.conn.execute(
                    "INSERT INTO drugs (name, dosage, frequency, stock, reorder_level) VALUES (?, ?, ?, 0, 0)",
                    (name, dosage, frequency),
                )
                new_id_raw = cur.lastrowid
                new_id = int(new_id_raw) if new_id_raw is not None else 0
            print(f"[Drugs] Added drug id={new_id} name='{name}' dosage='{dosage}' freq='{frequency}'")
            return new_id
        except sqlite3.IntegrityError as e:
            print(f"[Drugs][Error] Integrity error adding drug: {e}")
            raise
        except Exception as e:
            print(f"[Drugs][Error] Unexpected error adding drug: {e}")
            raise

    # --- Delivery operations -----------------------------------------------
    def record_delivery(
        self,
        patient_id: int,
        drug_id: int,
        delivery_date: str,
        status: str = "pending",
    ) -> int:
        """Record a drug delivery event and return the new delivery ID.

        - delivery_date: use ISO format (YYYY-MM-DD) or an ISO datetime string
        - status: one of ALLOWED_STATUSES
        """
        if status not in ALLOWED_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Allowed: {sorted(ALLOWED_STATUSES)}"
            )
        try:
            with self.conn:
                cur = self.conn.execute(
                    """
                    INSERT INTO delivery_logs (patient_id, drug_id, delivery_date, status)
                    VALUES (?, ?, ?, ?)
                    """,
                    (patient_id, drug_id, delivery_date, status),
                )
                new_id_raw = cur.lastrowid
                new_id = int(new_id_raw) if new_id_raw is not None else 0
            print(
                f"[Deliveries] Recorded delivery id={new_id} patient_id={patient_id} drug_id={drug_id} date={delivery_date} status={status}"
            )
            return new_id
        except sqlite3.IntegrityError as e:
            print(
                "[Deliveries][Error] Integrity error recording delivery (check patient/drug IDs and constraints):",
                e,
            )
            raise
        except Exception as e:
            print(f"[Deliveries][Error] Unexpected error recording delivery: {e}")
            raise

    def fetch_delivery_history(self, patient_id: int) -> List[Dict[str, Any]]:
        """Fetch delivery history for a patient as a list of dicts (most recent first)."""
        try:
            cur = self.conn.execute(
                """
                SELECT dl.id, dl.patient_id, p.name AS patient_name,
                       dl.drug_id, d.name AS drug_name,
                       d.dosage, d.frequency,
                       dl.delivery_date, dl.status
                FROM delivery_logs dl
                JOIN patients p ON p.id = dl.patient_id
                JOIN drugs d    ON d.id = dl.drug_id
                WHERE dl.patient_id = ?
                ORDER BY dl.delivery_date DESC, dl.id DESC
                """,
                (patient_id,),
            )
            rows = cur.fetchall()
            result = [dict(row) for row in rows]
            print(f"[Deliveries] Found {len(result)} deliveries for patient_id={patient_id}")
            return result
        except Exception as e:
            print(f"[Deliveries][Error] Unexpected error fetching history: {e}")
            raise

    def update_delivery_status(self, delivery_id: int, status: str) -> None:
        """Update the status of a delivery log entry."""
        if status not in ALLOWED_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Allowed: {sorted(ALLOWED_STATUSES)}"
            )
        try:
            with self.conn:
                cur = self.conn.execute(
                    "UPDATE delivery_logs SET status = ? WHERE id = ?",
                    (status, delivery_id),
                )
                if cur.rowcount == 0:
                    print(f"[Deliveries] No delivery found with id={delivery_id}")
                else:
                    print(
                        f"[Deliveries] Updated delivery id={delivery_id} to status={status}"
                    )
        except Exception as e:
            print(f"[Deliveries][Error] Unexpected error updating status: {e}")
            raise

    # --- Inventory operations --------------------------------------------
    def _log_inventory_transaction(self, drug_id: int, delta: int, reason: str) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO inventory_transactions (drug_id, delta, reason) VALUES (?, ?, ?)",
                (drug_id, delta, reason),
            )
            lr = cur.lastrowid
            return int(lr) if lr is not None else 0

    def add_drug_batch(
        self,
        drug_id: int,
        quantity: int,
        batch_no: Optional[str] = None,
        isbn: Optional[str] = None,
        producer: Optional[str] = None,
        transporter: Optional[str] = None,
        mfg_date: Optional[str] = None,
        exp_date: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        # Defensive: ensure columns/tables exist (in case legacy DB file present)
        self._ensure_inventory_schema()
        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO drug_batches (drug_id, batch_no, isbn, producer, transporter, mfg_date, exp_date, quantity, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (drug_id, batch_no, isbn, producer, transporter, mfg_date, exp_date, quantity, notes),
            )
            self.conn.execute(
                "UPDATE drugs SET stock = COALESCE(stock,0) + ? WHERE id = ?",
                (quantity, drug_id),
            )
            self._log_inventory_transaction(drug_id, quantity, f"batch:{batch_no or cur.lastrowid}")
            new_id_raw = cur.lastrowid
            new_id = int(new_id_raw) if new_id_raw is not None else 0
            print(f"[Inventory] Added batch id={new_id} drug_id={drug_id} qty={quantity}")
            return new_id

    def remove_stock(
        self,
        drug_id: int,
        quantity: int,
        reason: str,
        batch_no: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if not reason:
            raise ValueError("reason required")
        self._ensure_inventory_schema()
        with self.conn:
            cur_stock = self.conn.execute(
                "SELECT stock FROM drugs WHERE id=?", (drug_id,)
            ).fetchone()
            if not cur_stock:
                raise ValueError("drug not found")
            new_stock = max(0, (cur_stock[0] or 0) - quantity)
            self.conn.execute(
                "UPDATE drugs SET stock=? WHERE id=?", (new_stock, drug_id)
            )
            cur = self.conn.execute(
                """
                INSERT INTO drug_removals (drug_id, batch_no, reason, quantity, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (drug_id, batch_no, reason, quantity, notes),
            )
            self._log_inventory_transaction(drug_id, -quantity, f"remove:{reason}")
            rid_raw = cur.lastrowid
            rid = int(rid_raw) if rid_raw is not None else 0
            print(f"[Inventory] Removed qty={quantity} drug_id={drug_id} reason={reason}")
            return rid

    def adjust_inventory(self, drug_id: int, delta: int, reason: str) -> int:
        if delta == 0:
            raise ValueError("delta cannot be zero")
        self._ensure_inventory_schema()
        with self.conn:
            cur_stock = self.conn.execute(
                "SELECT stock FROM drugs WHERE id=?", (drug_id,)
            ).fetchone()
            if not cur_stock:
                raise ValueError("drug not found")
            new_stock = (cur_stock[0] or 0) + delta
            if new_stock < 0:
                new_stock = 0
            self.conn.execute(
                "UPDATE drugs SET stock=? WHERE id=?", (new_stock, drug_id)
            )
            tid = self._log_inventory_transaction(drug_id, delta, reason)
            print(f"[Inventory] Adjust drug_id={drug_id} delta={delta} reason={reason}")
            return tid

    def list_batches(self, drug_id: Optional[int] = None, limit: int = 200) -> List[Dict[str, Any]]:
        sql = "SELECT id, drug_id, batch_no, isbn, producer, transporter, mfg_date, exp_date, quantity, notes, created_at FROM drug_batches"
        params: List[Any] = []
        if drug_id is not None:
            sql += " WHERE drug_id=?"
            params.append(drug_id)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        cur = self.conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def list_removals(self, drug_id: Optional[int] = None, limit: int = 200) -> List[Dict[str, Any]]:
        sql = "SELECT id, drug_id, batch_no, reason, quantity, notes, created_at FROM drug_removals"
        params: List[Any] = []
        if drug_id is not None:
            sql += " WHERE drug_id=?"
            params.append(drug_id)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        cur = self.conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def list_transactions(self, limit: int = 300) -> List[Dict[str, Any]]:
        cur = self.conn.execute(
            "SELECT id, drug_id, delta, reason, created_at FROM inventory_transactions ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]

    def inventory_summary(self) -> List[Dict[str, Any]]:
        # Basic summary: join drugs with stock info; daily_avg, pending_quantity, days_supply placeholders
        self._ensure_inventory_schema()
        cur = self.conn.execute(
            """
            SELECT d.id, d.name, d.dosage, d.frequency, d.stock, d.reorder_level,
                   0 AS pending_quantity,
                   NULL AS daily_avg,
                   NULL AS days_supply
            FROM drugs d
            ORDER BY d.name ASC
            """
        )
        return [dict(r) for r in cur.fetchall()]

    # --- Internal schema guard -------------------------------------------
    def _ensure_inventory_schema(self) -> None:
        """Ensure legacy databases have new inventory columns/tables.

        Called lazily before inventory ops to avoid 500s when an old DB file
        exists (created before new migrations were added).
        """
        cur = self.conn.execute("PRAGMA table_info(drugs);")
        cols = {row[1] for row in cur.fetchall()}
        with self.conn:
            if 'stock' not in cols:
                try:
                    self.conn.execute("ALTER TABLE drugs ADD COLUMN stock INTEGER NOT NULL DEFAULT 0;")
                    print("[DB][Lazy] Added missing drugs.stock column")
                except Exception as e:
                    print("[DB][Lazy][Warn] stock column add failed:", e)
            if 'reorder_level' not in cols:
                try:
                    self.conn.execute("ALTER TABLE drugs ADD COLUMN reorder_level INTEGER NOT NULL DEFAULT 0;")
                    print("[DB][Lazy] Added missing drugs.reorder_level column")
                except Exception as e:
                    print("[DB][Lazy][Warn] reorder_level column add failed:", e)
            # Ensure inventory tables
            self.conn.execute("CREATE TABLE IF NOT EXISTS inventory_transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, drug_id INTEGER NOT NULL, delta INTEGER NOT NULL, reason TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')), FOREIGN KEY(drug_id) REFERENCES drugs(id) ON DELETE CASCADE);")
            self.conn.execute("CREATE TABLE IF NOT EXISTS drug_batches (id INTEGER PRIMARY KEY AUTOINCREMENT, drug_id INTEGER NOT NULL, batch_no TEXT, isbn TEXT, producer TEXT, transporter TEXT, mfg_date TEXT, exp_date TEXT, quantity INTEGER NOT NULL CHECK(quantity>0), notes TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')), FOREIGN KEY(drug_id) REFERENCES drugs(id) ON DELETE CASCADE);")
            self.conn.execute("CREATE TABLE IF NOT EXISTS drug_removals (id INTEGER PRIMARY KEY AUTOINCREMENT, drug_id INTEGER NOT NULL, batch_no TEXT, reason TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>0), notes TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')), FOREIGN KEY(drug_id) REFERENCES drugs(id) ON DELETE CASCADE);")

    # --- Utility ------------------------------------------------------------
    def close(self) -> None:
        try:
            self.conn.close()
            print("[Service] Connection closed")
        except Exception:
            # Silently ignore close errors; not critical.
            pass
