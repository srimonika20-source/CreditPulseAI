# CreditPulse AI

**Intelligent credit portfolio monitoring and decision support for banks, NBFCs and lending institutions.**

CreditPulse AI turns loan-level data into evidence-backed risk insight. It combines standard credit-risk analytics (PAR, DPD buckets, vintage curves, roll rates) with an intelligence layer that follows a strict workflow:

> **DETECT → DIAGNOSE → PREDICT → PRESCRIBE → TRACK**

Every recommendation is tied to a calculated metric. Observed findings are always kept separate from possible explanations.

> [!NOTE]
> This is a portfolio project. **All data is synthetic.** It simulates a fictional Indian NBFC with fictional customer IDs and branch names. There is no real borrower information.

---

## Product modules

| # | Module | Capabilities | Phase |
|---|---|---|---|
| 1 | **Executive Portfolio Overview** | Disbursement, outstanding, active accounts, ticket size, PAR30/60/90, collection efficiency, trends, product & branch mix | 3 |
| 2 | **Delinquency Analytics** | DPD buckets, product/branch delinquency, PAR trends, first payment default, NPA | 4 |
| 3 | **Vintage Analysis** | Month-on-book matrix, vintage curves, cohort comparison, FPD by cohort | 4 |
| 4 | **Roll Rate Analysis** | Transition matrix, roll forward/backward, cure rate, flow rate | 4 |
| 5 | **Intelligence Centre** | KPI deviation & segment anomaly detection, root-cause contribution, alerts, recommendations | 5–6 |
| 6 | **AI Credit Analyst** | Natural-language Q&A, anomaly explanations, portfolio summaries, all citing their evidence | 7 |
| 7 | **Action Tracker** | Actions, owners, due dates, status, outcomes | 7 |

## Tech stack

Python 3.11+ · Streamlit · Pandas · NumPy · Plotly · Scikit-learn · SQLite · SQLAlchemy · Pytest

## Architecture

```
creditpulse-ai/
├── app.py                 # Entry point & navigation router
├── config/settings.py     # Single source of truth: paths, seed, risk definitions, theme, registries
├── src/                   # Pure analytics layer (no UI imports)
│   ├── data/              # Synthetic generator, schema, validation
│   ├── metrics/           # Portfolio, delinquency, vintage, roll-rate engines
│   ├── intelligence/      # anomaly_detection → root_cause → forecasting → recommendations
│   ├── analyst/           # Evidence-grounded AI Credit Analyst
│   ├── actions/           # Action tracker service
│   └── utils/             # Formatting (₹, lakh, crore) and logging
├── components/            # Reusable Streamlit UI (theme, layout)
├── pages/                 # One page per module + home
├── database/              # SQLAlchemy engine/session + ORM models
├── data/                  # Generated datasets (git-ignored)
├── tests/                 # Pytest suite
└── docs/                  # Architecture, data dictionary, methodology, roadmap
```

See [docs/architecture.md](docs/architecture.md) for details.

## Getting started

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py

# 4. Run the tests
pytest
```

The app opens at <http://localhost:8501>.

### Configuration

All settings live in [`config/settings.py`](config/settings.py). You can override some of them with environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `CREDITPULSE_SEED` | `42` | Random seed for reproducible synthetic data |
| `CREDITPULSE_NUM_LOANS` | `20000` | Number of synthetic loan accounts |
| `CREDITPULSE_HISTORY_MONTHS` | `36` | Months of portfolio history |
| `CREDITPULSE_DB_PATH` | `database/creditpulse.db` | SQLite database location |
| `CREDITPULSE_LOG_LEVEL` | `INFO` | Logging level |

No API keys are required, and none are stored in the repository.

## Roadmap

| Phase | Milestone | Status |
|---|---|---|
| 1 | Architecture, configuration, documentation, application shell | 🟢 In progress |
| 2 | Synthetic loan data generator & validation | ⚪ Planned |
| 3 | Portfolio metrics engine & executive dashboard | ⚪ Planned |
| 4 | Delinquency, vintage & roll-rate analytics | ⚪ Planned |
| 5 | Anomaly detection & root-cause analysis | ⚪ Planned |
| 6 | Prescriptive recommendation engine | ⚪ Planned |
| 7 | AI Credit Analyst & action tracker | ⚪ Planned |
| 8 | Testing, documentation, UI refinement & deployment | ⚪ Planned |

## Analytical principles

1. **Evidence before opinion.** Every alert and recommendation references the metrics behind it.
2. **Findings ≠ explanations.** Contribution analysis shows *where* a change came from. Any *why* is labelled as a hypothesis.
3. **No fabrication.** The app never shows invented metrics, causes or outcomes. A module with no validated data shows nothing.
4. **Reproducibility.** The same seed always produces the same portfolio.

## License

MIT
