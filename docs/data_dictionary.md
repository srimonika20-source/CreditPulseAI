# Data Dictionary

> Status: to be completed in **Phase 2** when the synthetic data generator is built.

## Planned tables

| Table | Grain | Description |
|---|---|---|
| `branches` | One row per branch | Fictional branch master (region, state, tier) |
| `loans` | One row per loan account | Static origination attributes (product, amount, tenure, rate, disbursement date, branch) |
| `monthly_performance` | One row per loan per month | Outstanding principal, EMI due, amount collected, DPD, bucket |
| `actions` | One row per action | Action tracker records (Phase 7) |

Column-level definitions, data types, valid ranges and validation rules will be documented here in Phase 2.
