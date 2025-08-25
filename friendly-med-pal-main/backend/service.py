"""
Data access layer (DAO/Service) for the Drug Delivery Management System.
Uses sqlite3 and keeps things modular, friendly, and easy to extend.
"""
from __future__ import annotations

import sqlite3
from typing import Dict, List, Optional

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
                new_id = int(cur.lastrowid)
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
                    "INSERT INTO drugs (name, dosage, frequency) VALUES (?, ?, ?)",
                    (name, dosage, frequency),
                )
                new_id = int(cur.lastrowid)
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
                new_id = int(cur.lastrowid)
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

    def fetch_delivery_history(self, patient_id: int) -> List[Dict]:
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

    # --- Utility ------------------------------------------------------------
    def close(self) -> None:
        try:
            self.conn.close()
            print("[Service] Connection closed")
        except Exception:
            # Silently ignore close errors; not critical.
            pass
