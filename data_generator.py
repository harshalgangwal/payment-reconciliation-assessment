"""
data_generator.py
-----------------
Generates synthetic platform transactions and bank settlement records
for a fintech payment reconciliation assessment.

Intentionally injects four reconciliation issues:
  1. A transaction settled in the following month
  2. A rounding difference only visible in aggregate totals
  3. A duplicate settlement entry
  4. A refund with no matching original transaction
"""

import pandas as pd
import numpy as np
from pathlib import Path
import random
from datetime import date, timedelta

# ── Reproducibility ────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# ── Paths ──────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Constants ──────────────────────────────────────────────────────────────────
NUM_TRANSACTIONS = 50
MONTH_END = date(2024, 3, 31)
CUSTOMER_IDS = [f"CUST{str(i).zfill(4)}" for i in range(1, 21)]

# IDs reserved for injected anomalies
CROSS_MONTH_TXN_ID     = "TXN-CM-001"   # settled next month
ROUNDING_TXN_ID        = "TXN-RD-001"   # rounding diff in settlement
DUPLICATE_TXN_ID       = "TXN-DUP-001"  # settled twice
ORPHAN_REFUND_TXN_ID   = "TXN-OR-001"   # refund, no matching original


def _random_date_near_month_end(days_before: int = 7) -> date:
    """Return a random date within `days_before` days of MONTH_END."""
    offset = random.randint(0, days_before)
    return MONTH_END - timedelta(days=offset)


def generate_platform_transactions() -> pd.DataFrame:
    """
    Build the platform transactions table.
    Rows represent what the payments platform recorded in real time.
    """
    rows = []

    # ── 1. Normal transactions ─────────────────────────────────────────────────
    for i in range(1, NUM_TRANSACTIONS + 1):
        txn_date = _random_date_near_month_end(days_before=10)
        amount   = round(random.uniform(10.0, 500.0), 2)
        rows.append({
            "transaction_id":     f"TXN-{str(i).zfill(4)}",
            "customer_id":        random.choice(CUSTOMER_IDS),
            "transaction_date":   txn_date,
            "transaction_amount": amount,
            "transaction_type":   "CHARGE",
            "status":             "SUCCESS",
        })

    # ── 2. Inject: cross-month settlement candidate ────────────────────────────
    # Transaction happens on 31 Mar — settlement will land on 2 Apr (next month)
    rows.append({
        "transaction_id":     CROSS_MONTH_TXN_ID,
        "customer_id":        "CUST0005",
        "transaction_date":   date(2024, 3, 31),
        "transaction_amount": 250.00,
        "transaction_type":   "CHARGE",
        "status":             "SUCCESS",
    })

    # ── 3. Inject: rounding difference ────────────────────────────────────────
    # Platform records £149.99; bank settles £150.01 (2p discrepancy).
    # Difference (£0.02) is above the £0.005 tolerance — clearly flagged.
    rows.append({
        "transaction_id":     ROUNDING_TXN_ID,
        "customer_id":        "CUST0010",
        "transaction_date":   date(2024, 3, 28),
        "transaction_amount": 149.99,    # platform value
        "transaction_type":   "CHARGE",
        "status":             "SUCCESS",
    })

    # ── 4. Inject: duplicate settlement candidate ──────────────────────────────
    rows.append({
        "transaction_id":     DUPLICATE_TXN_ID,
        "customer_id":        "CUST0015",
        "transaction_date":   date(2024, 3, 27),
        "transaction_amount": 75.00,
        "transaction_type":   "CHARGE",
        "status":             "SUCCESS",
    })

    # ── 5. No platform record for the orphan refund ────────────────────────────
    # Deliberately NOT adding ORPHAN_REFUND_TXN_ID to platform transactions
    # so the bank-side refund settlement has no match.

    df = pd.DataFrame(rows)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df = df.sort_values("transaction_date").reset_index(drop=True)
    return df


def generate_bank_settlements(transactions: pd.DataFrame) -> pd.DataFrame:
    """
    Build the bank settlements table.
    Simulates settlement 1–2 days after the platform transaction.
    Injects the four required anomalies.
    """
    rows = []
    settlement_counter = 1

    settled_ids = set()

    for _, txn in transactions.iterrows():
        txn_id = txn["transaction_id"]

        # ── Cross-month: settle 2 days after month end (April) ─────────────────
        if txn_id == CROSS_MONTH_TXN_ID:
            settle_date = date(2024, 4, 2)
        else:
            delay = random.randint(1, 2)
            settle_date = txn["transaction_date"].date() + timedelta(days=delay)

        # ── Rounding: bank settles a slightly different amount ──────────────────
        if txn_id == ROUNDING_TXN_ID:
            settle_amount = 150.01   # bank rounds up by £0.02
        else:
            settle_amount = txn["transaction_amount"]

        row = {
            "settlement_id":     f"SET-{str(settlement_counter).zfill(4)}",
            "transaction_id":    txn_id,
            "settlement_date":   settle_date,
            "settlement_amount": settle_amount,
            "settlement_status": "SETTLED",
        }
        rows.append(row)
        settled_ids.add(txn_id)
        settlement_counter += 1

        # ── Duplicate: settle TXN-DUP-001 twice ────────────────────────────────
        if txn_id == DUPLICATE_TXN_ID:
            duplicate_row = {
                "settlement_id":     f"SET-{str(settlement_counter).zfill(4)}",
                "transaction_id":    txn_id,
                "settlement_date":   settle_date + timedelta(days=1),
                "settlement_amount": txn["transaction_amount"],
                "settlement_status": "SETTLED",
            }
            rows.append(duplicate_row)
            settlement_counter += 1

    # ── Orphan refund: bank-side entry with no platform record ─────────────────
    rows.append({
        "settlement_id":     f"SET-{str(settlement_counter).zfill(4)}",
        "transaction_id":    ORPHAN_REFUND_TXN_ID,
        "settlement_date":   date(2024, 3, 29),
        "settlement_amount": -120.00,   # negative = refund
        "settlement_status": "SETTLED",
    })

    df = pd.DataFrame(rows)
    df["settlement_date"] = pd.to_datetime(df["settlement_date"])
    df = df.sort_values("settlement_date").reset_index(drop=True)
    return df


def generate_and_save() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate both datasets, save to /data, and return them."""
    transactions = generate_platform_transactions()
    settlements  = generate_bank_settlements(transactions)

    txn_path = DATA_DIR / "platform_transactions.csv"
    set_path = DATA_DIR / "bank_settlements.csv"

    transactions.to_csv(txn_path, index=False)
    settlements.to_csv(set_path, index=False)

    print(f"[data_generator] Saved {len(transactions)} transactions → {txn_path}")
    print(f"[data_generator] Saved {len(settlements)} settlements  → {set_path}")

    return transactions, settlements


if __name__ == "__main__":
    generate_and_save()
