# Metric Methodology

> Status: formulas are finalised and tested in **Phases 3–4**. The definitions below are the planned standards.

| Metric | Planned definition |
|---|---|
| **Outstanding portfolio (POS)** | Sum of principal outstanding on active loans at month-end |
| **PARx** | POS of loans with DPD > x ÷ total POS |
| **Collection efficiency** | Amount collected against current-month dues ÷ current-month dues |
| **First payment default (FPD)** | Share of loans more than 30 DPD on their first scheduled EMI |
| **NPA** | Loans with DPD > 90 (RBI IRACP norm) |
| **Roll forward rate** | Share of accounts moving to a worse DPD bucket month over month |
| **Cure rate** | Share of delinquent accounts returning to Current |
| **Flow rate** | Share of balance in bucket *n* at *t-1* that reaches bucket *n+1* at *t* |
| **Vintage curve** | Cumulative % of a disbursement cohort ever reaching a DPD threshold, by month on book |

## Evidence standards for the intelligence layer

1. A **finding** is a calculated, reproducible observation (e.g. "PAR30 for Branch X rose from a to b").
2. A **contribution** is an arithmetic decomposition of a change across segments.
3. A **hypothesis** is a possible explanation. It is always labelled as such and never presented as fact.
4. A **recommendation** must reference one or more findings.
