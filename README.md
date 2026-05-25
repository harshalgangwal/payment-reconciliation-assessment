# 💳 Payment Reconciliation Engine

> An end-to-end fintech reconciliation system that detects settlement gaps,
> timing mismatches, duplicates, and orphan refunds — with a Streamlit dashboard
> for operational review.

[![Python](https://img.shields.io/badge/python-3.11-blue)]()
[![Streamlit](https://img.shields.io/badge/streamlit-1.35-red)]()
[![Tests](https://img.shields.io/badge/tests-8%20passing-brightgreen)]()

---

## Overview

A payments company's books don't balance at month end.

The platform records customer transactions instantly. The bank settles funds
1–2 days later. This project reconciles those two streams, catches discrepancies,
and presents results through an interactive dashboard.

**Four reconciliation scenarios are intentionally injected:**

| Scenario | Description |
|---|---|
| Cross-month settlement | Transaction in March, settled in April |
| Rounding difference | Platform records £149.995; bank rounds to £150.00 |
| Duplicate settlement | Same transaction settled twice by the bank |
| Orphan refund | Bank-side refund with no matching platform transaction |

---

## Architecture

```
data_generator.py
  └── Generates synthetic platform_transactions.csv + bank_settlements.csv
        │
        ▼
reconciliation.py
  ├── find_missing_settlements()
  ├── find_cross_month_settlements()
  ├── find_duplicate_settlements()
  ├── find_orphan_refunds()
  ├── find_amount_mismatches()
  └── aggregate_reconciliation()
        │
        ▼
validations.py
  └── run_tests() — 8 assertion-based checks → PASS/FAIL summary
        │
        ▼
app.py (Streamlit)
  ├── KPI metrics
  ├── Exception summary cards
  ├── Expandable detail tables + CSV downloads
  ├── Raw data explorer
  └── Test results table
```

All data flows are one-directional. No database. No external services.

---

## Project Structure

```
payment-reconciliation-assessment/
├── app.py                          ← Streamlit dashboard
├── requirements.txt
├── README.md
├── .gitignore
│
├── data/
│   ├── platform_transactions.csv   ← auto-generated
│   └── bank_settlements.csv        ← auto-generated
│
├── src/
│   ├── data_generator.py           ← synthetic data with injected anomalies
│   ├── reconciliation.py           ← reconciliation logic
│   └── validations.py              ← test suite
│
├── reports/                        ← auto-generated exception CSVs
│   ├── missing_settlements.csv
│   ├── cross_month_settlements.csv
│   ├── duplicate_settlements.csv
│   ├── orphan_refunds.csv
│   └── amount_mismatches.csv
│
├── screenshots/
│   └── placeholder.txt
│
└── docs/
    ├── architecture_notes.md
    └── brainstorming_thread.md
```

---

## Setup Instructions

### Prerequisites

- Python 3.10+
- pip

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/payment-reconciliation-assessment.git
cd payment-reconciliation-assessment
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## How to Run

### Generate data + reconciliation reports (CLI)

```bash
python src/reconciliation.py
```

This will:
1. Generate `data/platform_transactions.csv` and `data/bank_settlements.csv`
2. Run all reconciliation checks
3. Export exception reports to `/reports`
4. Print a summary to the console

### Run validation tests (CLI)

```bash
python src/validations.py
```

### Launch the Streamlit dashboard

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

## Deployment (Streamlit Community Cloud)

1. Push the repository to GitHub (public or private)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click **New app**
4. Select your repository, branch (`main`), and main file (`app.py`)
5. Click **Deploy**

The app auto-installs from `requirements.txt` and runs on every push.

**Live demo:** [https://YOUR-DEPLOY-URL.streamlit.app](https://YOUR-DEPLOY-URL.streamlit.app)

---

## Screenshots

| KPI Metrics | Exception Tables |
|---|---|
| ![KPIs](screenshots/kpis.png) | ![Exceptions](screenshots/exceptions.png) |

| Test Results | Raw Data Explorer |
|---|---|
| ![Tests](screenshots/tests.png) | ![Data](screenshots/data_explorer.png) |

> Screenshots added after deployment.

---

## Key Design Decisions

**Pandas over a database** — with 40–60 rows the overhead of SQLite or
PostgreSQL would outweigh any benefit. Pandas makes the logic transparent
and easy to inspect.

**Assertion-based tests over pytest** — the tests run inside Streamlit
without a separate test runner, keeping the setup minimal.

**Streamlit over FastAPI + React** — appropriate for an operational
reporting tool used by a small finance team. A REST API layer would be
the obvious next step for production.

---

## Production Limitations

| Limitation | Explanation |
|---|---|
| No partial settlements | Assumes 1 transaction = 1 settlement. Real banks often batch or split. |
| Single currency | No FX conversion logic. All amounts treated as same currency. |
| No calendar/holiday logic | Settlement delays are 1–2 calendar days; no business-day awareness. |
| No persistent storage | Results regenerate on every run. No historical tracking. |
| No distributed scaling | Pandas runs in a single process. 1M+ rows would need Dask or Spark. |
| No authentication | The dashboard has no login. Not suitable for production without auth. |

---

## Author

Built as a fintech technical assessment. See `docs/architecture_notes.md`
for deeper design notes and `docs/brainstorming_thread.md` for the iterative
thinking process.
