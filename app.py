"""
app.py
------
Streamlit dashboard for the fintech payment reconciliation assessment.

Sections:
  1. KPI metrics
  2. Reconciliation summary
  3. Exception tables (with download buttons)
  4. Test execution summary

Run with:
  streamlit run app.py
"""

import sys
from pathlib import Path

# Make src/ importable when running from project root
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd
import streamlit as st

from data_generator import generate_and_save
from reconciliation import run_all
from validations import run_tests

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Payment Reconciliation Dashboard",
    page_icon="💳",
    layout="wide",
)

# ─────────────────────────────────────────────────────────────────────────────
# Load / generate data (cached so Streamlit doesn't re-run on every click)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data
def load_data():
    txns, sets_ = generate_and_save()
    results     = run_all(txns, sets_)
    tests       = run_tests(results)
    return txns, sets_, results, tests


transactions, settlements, results, test_summary = load_data()
agg = results["aggregate"]

# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────

st.title("💳 Payment Reconciliation Dashboard")
st.caption("Fintech technical assessment — March 2024 month-end close")
st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Section 1: KPI metrics
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("📊 Key Metrics")

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric(
    label="Platform Transactions",
    value=f"{agg['platform_transaction_count']}",
)
col2.metric(
    label="Settlements (raw)",
    value=f"{agg['settlement_count']}",
    delta=f"+{agg['settlement_count'] - agg['deduplicated_settlement_count']} duplicate(s)",
    delta_color="inverse",
)
col3.metric(
    label="Platform Total",
    value=f"£{agg['total_platform_amount']:,.2f}",
)
col4.metric(
    label="Settlement Total",
    value=f"£{agg['total_settlement_amount']:,.2f}",
)

diff = agg["aggregate_difference"]
balanced_label = "✓ Balanced" if agg["is_balanced"] else "✗ Imbalanced"
col5.metric(
    label="Aggregate Difference",
    value=f"£{diff:,.4f}",
    delta=balanced_label,
    delta_color="normal" if agg["is_balanced"] else "inverse",
)

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Section 2: Reconciliation exception summary
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("🔍 Exception Summary")

exception_keys = [
    ("missing_settlements",     "Missing Settlements",     "🔴"),
    ("cross_month_settlements", "Cross-Month Settlements", "🟡"),
    ("duplicate_settlements",   "Duplicate Settlements",   "🟠"),
    ("orphan_refunds",          "Orphan Refunds",          "🔴"),
    ("amount_mismatches",       "Amount Mismatches",       "🟡"),
]

cols = st.columns(len(exception_keys))
for col, (key, label, icon) in zip(cols, exception_keys):
    count = len(results[key])
    col.metric(label=f"{icon} {label}", value=count)

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Section 3: Exception detail tables
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("📋 Exception Detail Tables")


def exception_section(title: str, key: str, filename: str):
    df = results[key]
    with st.expander(f"{title}  ({len(df)} row{'s' if len(df) != 1 else ''})", expanded=len(df) > 0):
        if df.empty:
            st.success("No exceptions found.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button(
                label=f"⬇ Download {filename}",
                data=df.to_csv(index=False),
                file_name=filename,
                mime="text/csv",
                key=f"dl_{key}",
            )


exception_section("🔴 Missing Settlements",     "missing_settlements",     "missing_settlements.csv")
exception_section("🟡 Cross-Month Settlements", "cross_month_settlements", "cross_month_settlements.csv")
exception_section("🟠 Duplicate Settlements",   "duplicate_settlements",   "duplicate_settlements.csv")
exception_section("🔴 Orphan Refunds",          "orphan_refunds",         "orphan_refunds.csv")
exception_section("🟡 Amount Mismatches",       "amount_mismatches",      "amount_mismatches.csv")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Section 4: Raw data explorer
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("🗃 Raw Data Explorer")

tab1, tab2 = st.tabs(["Platform Transactions", "Bank Settlements"])

with tab1:
    st.dataframe(transactions, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇ Download platform_transactions.csv",
        data=transactions.to_csv(index=False),
        file_name="platform_transactions.csv",
        mime="text/csv",
        key="dl_txns",
    )

with tab2:
    st.dataframe(settlements, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇ Download bank_settlements.csv",
        data=settlements.to_csv(index=False),
        file_name="bank_settlements.csv",
        mime="text/csv",
        key="dl_sets",
    )

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Section 5: Validation test results
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("🧪 Validation Test Results")

passed = (test_summary["status"] == "PASS").sum()
failed = (test_summary["status"] == "FAIL").sum()
total  = len(test_summary)

tcol1, tcol2, tcol3 = st.columns(3)
tcol1.metric("Total Tests",  total)
tcol2.metric("✓ Passed",     passed)
tcol3.metric("✗ Failed",     failed, delta_color="inverse" if failed > 0 else "off")

# Colour-code the status column
def _style_status(val):
    colour = "#2d7d46" if val == "PASS" else "#c0392b"
    return f"color: {colour}; font-weight: 600;"

styled = test_summary.style.applymap(_style_status, subset=["status"])
st.dataframe(styled, use_container_width=True, hide_index=True)

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────────────────────

st.caption(
    "Built for a fintech technical assessment. "
    "Synthetic data only — no real transactions processed. "
    "See README for setup and deployment instructions."
)
