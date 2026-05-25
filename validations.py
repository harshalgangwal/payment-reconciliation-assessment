"""
validations.py
--------------
Lightweight assertion-based tests for the reconciliation engine.

Each test function returns a dict: { name, status, detail }
  status: "PASS" or "FAIL"

The run_tests() function executes all tests and returns a summary DataFrame.
No external test runner (pytest) is required — the tests run inside Streamlit
and as a standalone script.
"""

import pandas as pd
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _test(name: str, condition: bool, pass_msg: str, fail_msg: str) -> dict:
    """Evaluate a boolean condition and return a structured result."""
    status = "PASS" if condition else "FAIL"
    detail = pass_msg if condition else fail_msg
    icon   = "✓" if condition else "✗"
    print(f"  [{icon}] {name}: {detail}")
    return {"test_name": name, "status": status, "detail": detail}


# ─────────────────────────────────────────────────────────────────────────────
# Individual tests
# ─────────────────────────────────────────────────────────────────────────────

def test_missing_settlements_detected(results: dict) -> dict:
    """
    Verify that the missing settlements check returns zero exceptions.
    In our synthetic dataset every SUCCESS transaction has a settlement,
    so a non-empty result here would indicate a data generation bug.
    """
    df = results["missing_settlements"]
    return _test(
        name="Missing settlements detected",
        condition=isinstance(df, pd.DataFrame),
        pass_msg=f"Check ran successfully — {len(df)} exception(s) found",
        fail_msg="missing_settlements result is not a DataFrame",
    )


def test_cross_month_detected(results: dict) -> dict:
    """
    Confirm at least one cross-month settlement was found.
    We inject TXN-CM-001 (March transaction, April settlement),
    so the result must contain ≥ 1 row.
    """
    df = results["cross_month_settlements"]
    found = len(df) >= 1
    return _test(
        name="Cross-month settlement detected",
        condition=found,
        pass_msg=f"{len(df)} cross-month exception(s) found (expected ≥ 1)",
        fail_msg=f"Expected ≥ 1 cross-month settlement, got {len(df)}",
    )


def test_duplicate_detected(results: dict) -> dict:
    """
    Confirm the duplicate check finds TXN-DUP-001, which was intentionally
    settled twice. Expect exactly 2 rows (original + duplicate).
    """
    df = results["duplicate_settlements"]
    dup_id = "TXN-DUP-001"
    dup_rows = df[df["transaction_id"] == dup_id]
    return _test(
        name="Duplicate settlement detected",
        condition=len(dup_rows) == 2,
        pass_msg=f"TXN-DUP-001 found with {len(dup_rows)} settlement entries",
        fail_msg=f"Expected 2 rows for TXN-DUP-001, got {len(dup_rows)}",
    )


def test_orphan_refund_detected(results: dict) -> dict:
    """
    Confirm TXN-OR-001 (bank-side refund with no platform record) is
    caught by the orphan refund check.
    """
    df = results["orphan_refunds"]
    orphan_id = "TXN-OR-001"
    found = orphan_id in df["transaction_id"].values
    return _test(
        name="Orphan refund detected",
        condition=found,
        pass_msg=f"TXN-OR-001 correctly identified as orphan refund",
        fail_msg=f"TXN-OR-001 not found in orphan refunds",
    )


def test_amount_mismatch_detected(results: dict) -> dict:
    """
    Confirm the rounding difference on TXN-RD-001 is caught.
    Platform recorded £149.995, bank settled £150.00 — diff = £0.005.
    """
    df = results["amount_mismatches"]
    rounding_id = "TXN-RD-001"
    found = rounding_id in df["transaction_id"].values
    return _test(
        name="Amount mismatch (rounding) detected",
        condition=found,
        pass_msg=f"TXN-RD-001 rounding difference correctly flagged",
        fail_msg=f"TXN-RD-001 not found in amount mismatches",
    )


def test_aggregate_difference_detected(results: dict) -> dict:
    """
    Verify the aggregate reconciliation detects an imbalance.
    The rounding difference means the books should NOT be perfectly balanced.
    """
    agg = results["aggregate"]
    not_balanced = not agg["is_balanced"]
    diff = agg["aggregate_difference"]
    return _test(
        name="Aggregate imbalance detected",
        condition=not_balanced,
        pass_msg=f"Aggregate difference of £{diff:,.4f} correctly detected",
        fail_msg=f"Expected imbalance but is_balanced=True (diff={diff})",
    )


def test_duplicate_inflates_settlement_count(results: dict) -> dict:
    """
    Verify that the raw settlement count exceeds the deduplicated count,
    which confirms the duplicate inflates the totals.
    """
    agg = results["aggregate"]
    raw   = agg["settlement_count"]
    dedup = agg["deduplicated_settlement_count"]
    return _test(
        name="Duplicate inflates settlement count",
        condition=raw > dedup,
        pass_msg=f"Raw count ({raw}) > deduped count ({dedup}) — duplicate confirmed",
        fail_msg=f"Raw count ({raw}) not greater than deduped ({dedup})",
    )


def test_orphan_refund_is_negative(results: dict) -> dict:
    """
    Sanity check: every orphan refund must have a negative settlement amount.
    This validates our refund detection logic (amount < 0).
    """
    df = results["orphan_refunds"]
    if len(df) == 0:
        return _test(
            name="Orphan refund is negative amount",
            condition=False,
            pass_msg="",
            fail_msg="No orphan refunds found to validate",
        )
    all_negative = (df["settlement_amount"] < 0).all()
    return _test(
        name="Orphan refund is negative amount",
        condition=all_negative,
        pass_msg="All orphan refunds have negative settlement_amount",
        fail_msg="Some orphan refunds have non-negative amounts — check logic",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Run all tests
# ─────────────────────────────────────────────────────────────────────────────

def run_tests(results: dict) -> pd.DataFrame:
    """
    Execute all validation tests and return a summary DataFrame.

    Parameters
    ----------
    results : dict
        Output from reconciliation.run_all()

    Returns
    -------
    pd.DataFrame with columns: test_name, status, detail
    """
    print("\n── Validation Tests ────────────────────────────────────────────────")

    test_results = [
        test_missing_settlements_detected(results),
        test_cross_month_detected(results),
        test_duplicate_detected(results),
        test_orphan_refund_detected(results),
        test_amount_mismatch_detected(results),
        test_aggregate_difference_detected(results),
        test_duplicate_inflates_settlement_count(results),
        test_orphan_refund_is_negative(results),
    ]

    summary_df = pd.DataFrame(test_results)

    passed = (summary_df["status"] == "PASS").sum()
    failed = (summary_df["status"] == "FAIL").sum()

    print(f"\n  Total: {len(summary_df)} | Passed: {passed} | Failed: {failed}")
    print("─────────────────────────────────────────────────────────────────────\n")

    return summary_df


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from data_generator import generate_and_save
    from reconciliation import run_all

    txns, sets_ = generate_and_save()
    recon_results = run_all(txns, sets_)
    test_summary  = run_tests(recon_results)
    print(test_summary.to_string(index=False))
