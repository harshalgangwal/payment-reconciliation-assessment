"""
reconciliation.py
-----------------
Core reconciliation logic for the fintech payment reconciliation assessment.

Each function is modular and returns a DataFrame of exceptions.
All exception DataFrames are exported to /reports automatically.

Reconciliation checks implemented:
  1. missing_settlements        — platform transactions with no settlement
  2. cross_month_settlements    — settled in a different calendar month
  3. duplicate_settlements      — same transaction_id settled more than once
  4. orphan_refunds             — settlement refunds with no platform transaction
  5. amount_mismatches          — settlement amount differs from transaction amount
  6. aggregate_reconciliation   — sum-level comparison across all records
"""

import pandas as pd
import numpy as np
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Tolerance ──────────────────────────────────────────────────────────────────
AMOUNT_TOLERANCE = 0.005   # £0.005 — anything above this is flagged


# ─────────────────────────────────────────────────────────────────────────────
# 1. Missing settlements
# ─────────────────────────────────────────────────────────────────────────────

def find_missing_settlements(
    transactions: pd.DataFrame,
    settlements: pd.DataFrame,
) -> pd.DataFrame:
    """
    Identify platform transactions that have no corresponding settlement record.

    A transaction is 'missing' if its transaction_id does not appear in the
    settlements table at all (regardless of status).

    Returns a DataFrame of unmatched transactions.
    """
    settled_ids = set(settlements["transaction_id"].unique())

    missing = transactions[~transactions["transaction_id"].isin(settled_ids)].copy()
    missing["exception_type"] = "MISSING_SETTLEMENT"

    _export(missing, "missing_settlements.csv")
    return missing


# ─────────────────────────────────────────────────────────────────────────────
# 2. Cross-month settlements
# ─────────────────────────────────────────────────────────────────────────────

def find_cross_month_settlements(
    transactions: pd.DataFrame,
    settlements: pd.DataFrame,
) -> pd.DataFrame:
    """
    Find transactions where the settlement fell in a different calendar month
    than the original transaction.

    This matters for month-end accounting: revenue recognised in March must
    have settlements in March. A cross-month settlement creates a timing gap
    that must be accrued or explained.

    Returns matched pairs where transaction_month != settlement_month.
    """
    # Only match on settled records
    settled = settlements[settlements["settlement_status"] == "SETTLED"]
    merged = transactions.merge(
        settled[["transaction_id", "settlement_date", "settlement_amount"]],
        on="transaction_id",
        how="inner",
    )

    txn_month  = merged["transaction_date"].dt.to_period("M")
    set_month  = merged["settlement_date"].dt.to_period("M")

    cross_month = merged[txn_month != set_month].copy()
    cross_month["transaction_month"] = txn_month[txn_month != set_month].astype(str)
    cross_month["settlement_month"]  = set_month[txn_month != set_month].astype(str)
    cross_month["exception_type"]    = "CROSS_MONTH_SETTLEMENT"

    _export(cross_month, "cross_month_settlements.csv")
    return cross_month


# ─────────────────────────────────────────────────────────────────────────────
# 3. Duplicate settlements
# ─────────────────────────────────────────────────────────────────────────────

def find_duplicate_settlements(settlements: pd.DataFrame) -> pd.DataFrame:
    """
    Detect transaction_ids that appear more than once in the settlements table.

    Duplicates cause double-counting of settled funds and inflate bank totals
    against platform totals. Each occurrence is returned so the operator can
    see both the original and the duplicate.

    Returns all settlement rows that are part of a duplicated group.
    """
    dup_ids = (
        settlements.groupby("transaction_id")
        .size()
        .loc[lambda s: s > 1]
        .index
    )

    duplicates = settlements[settlements["transaction_id"].isin(dup_ids)].copy()
    duplicates["exception_type"] = "DUPLICATE_SETTLEMENT"

    # Add occurrence rank so it's clear which is the original vs duplicate
    duplicates["occurrence"] = (
        duplicates.groupby("transaction_id").cumcount() + 1
    )

    _export(duplicates, "duplicate_settlements.csv")
    return duplicates


# ─────────────────────────────────────────────────────────────────────────────
# 4. Orphan refunds
# ─────────────────────────────────────────────────────────────────────────────

def find_orphan_refunds(
    transactions: pd.DataFrame,
    settlements: pd.DataFrame,
) -> pd.DataFrame:
    """
    Find settlement refunds (negative amounts) whose transaction_id has no
    matching platform transaction.

    An orphan refund indicates either:
      - a refund was processed by the bank without a platform record, or
      - the original transaction was deleted from the platform ledger.

    Both are operationally dangerous — they represent unreconcilable cash outflows.

    Returns settlement rows for orphan refunds.
    """
    platform_ids = set(transactions["transaction_id"].unique())

    # Refunds are negative-amount settlements
    refunds = settlements[settlements["settlement_amount"] < 0].copy()

    orphans = refunds[~refunds["transaction_id"].isin(platform_ids)].copy()
    orphans["exception_type"] = "ORPHAN_REFUND"

    _export(orphans, "orphan_refunds.csv")
    return orphans


# ─────────────────────────────────────────────────────────────────────────────
# 5. Amount mismatches
# ─────────────────────────────────────────────────────────────────────────────

def find_amount_mismatches(
    transactions: pd.DataFrame,
    settlements: pd.DataFrame,
    tolerance: float = AMOUNT_TOLERANCE,
) -> pd.DataFrame:
    """
    Compare the transaction_amount on the platform with the settlement_amount
    from the bank for each matched pair.

    A mismatch beyond `tolerance` (default £0.005) is flagged. Small differences
    often arise from FX rounding, fee deductions, or bank-side decimal truncation.

    Returns matched pairs where abs(difference) > tolerance.
    """
    merged = transactions.merge(
        settlements[["transaction_id", "settlement_id", "settlement_amount"]],
        on="transaction_id",
        how="inner",
    )

    merged["amount_difference"] = (
        merged["settlement_amount"] - merged["transaction_amount"]
    ).round(4)

    mismatches = merged[
        merged["amount_difference"].abs() > tolerance
    ].copy()
    mismatches["exception_type"] = "AMOUNT_MISMATCH"

    _export(mismatches, "amount_mismatches.csv")
    return mismatches


# ─────────────────────────────────────────────────────────────────────────────
# 6. Aggregate reconciliation
# ─────────────────────────────────────────────────────────────────────────────

def aggregate_reconciliation(
    transactions: pd.DataFrame,
    settlements: pd.DataFrame,
) -> dict:
    """
    High-level sum comparison between the platform and the bank.

    Returns a summary dict with:
      - total_platform_amount
      - total_settlement_amount
      - aggregate_difference
      - is_balanced  (True if difference < £0.01)
    """
    # Exclude duplicates for aggregate: deduplicate on first occurrence
    deduped_settlements = settlements.drop_duplicates(
        subset="transaction_id", keep="first"
    )

    platform_total    = transactions["transaction_amount"].sum()
    settlement_total  = deduped_settlements["settlement_amount"].sum()
    difference        = round(settlement_total - platform_total, 4)

    summary = {
        "total_platform_amount":   round(platform_total, 2),
        "total_settlement_amount": round(settlement_total, 2),
        "aggregate_difference":    difference,
        "is_balanced":             abs(difference) < 0.01,
        "platform_transaction_count":   len(transactions),
        "settlement_count":             len(settlements),
        "deduplicated_settlement_count": len(deduped_settlements),
    }
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# 7. Run all checks — convenience entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_all(
    transactions: pd.DataFrame,
    settlements: pd.DataFrame,
) -> dict:
    """
    Execute all reconciliation checks and return a results dict containing
    each exception DataFrame and the aggregate summary.
    """
    results = {
        "missing_settlements":     find_missing_settlements(transactions, settlements),
        "cross_month_settlements": find_cross_month_settlements(transactions, settlements),
        "duplicate_settlements":   find_duplicate_settlements(settlements),
        "orphan_refunds":          find_orphan_refunds(transactions, settlements),
        "amount_mismatches":       find_amount_mismatches(transactions, settlements),
        "aggregate":               aggregate_reconciliation(transactions, settlements),
    }

    # Print a brief console summary
    agg = results["aggregate"]
    print("\n── Reconciliation Summary ──────────────────────────────────────────")
    print(f"  Platform total   : £{agg['total_platform_amount']:,.2f}  ({agg['platform_transaction_count']} txns)")
    print(f"  Settlement total : £{agg['total_settlement_amount']:,.2f}  ({agg['deduplicated_settlement_count']} settlements, deduped)")
    print(f"  Difference       : £{agg['aggregate_difference']:,.4f}")
    print(f"  Balanced         : {'✓ YES' if agg['is_balanced'] else '✗ NO'}")
    for key in ["missing_settlements", "cross_month_settlements",
                "duplicate_settlements", "orphan_refunds", "amount_mismatches"]:
        print(f"  {key:<28}: {len(results[key])} exception(s)")
    print("─────────────────────────────────────────────────────────────────────\n")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Internal helper
# ─────────────────────────────────────────────────────────────────────────────

def _export(df: pd.DataFrame, filename: str) -> None:
    """Save exception DataFrame to /reports."""
    path = REPORTS_DIR / filename
    df.to_csv(path, index=False)
    print(f"[reconciliation] Exported {len(df)} rows → {path}")


if __name__ == "__main__":
    from data_generator import generate_and_save
    txns, sets_ = generate_and_save()
    run_all(txns, sets_)
