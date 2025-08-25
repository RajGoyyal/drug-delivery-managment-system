"""
Example usage for the Drug Delivery Management System backend.
Run this file to see the service in action:

    python -m backend.example

This script is intentionally simple and prints friendly messages.
"""
from __future__ import annotations

from datetime import date

from .service import DrugDeliveryService


def main() -> None:
    service = DrugDeliveryService()

    # Create some sample data
    alice_id = service.add_patient(name="Alice Johnson", age=42, contact="alice@example.com")
    drug_id = service.add_drug(name="Amoxicillin", dosage="500 mg", frequency="2x/day")

    # Record a delivery for today
    delivery_id = service.record_delivery(
        patient_id=alice_id,
        drug_id=drug_id,
        delivery_date=date.today().isoformat(),
        status="pending",
    )

    # Fetch delivery history
    history = service.fetch_delivery_history(patient_id=alice_id)
    print("\n[Report] Delivery history:")
    for row in history:
        print(
            f" - #{row['id']}: {row['patient_name']} -> {row['drug_name']} "
            f"({row['dosage']}, {row['frequency']}) on {row['delivery_date']} — status={row['status']}"
        )

    # Update status to delivered
    service.update_delivery_status(delivery_id, status="delivered")

    # Show updated history
    updated = service.fetch_delivery_history(patient_id=alice_id)
    print("\n[Report] Updated delivery history:")
    for row in updated:
        print(
            f" - #{row['id']}: {row['patient_name']} -> {row['drug_name']} on {row['delivery_date']} — status={row['status']}"
        )

    service.close()


if __name__ == "__main__":
    main()
