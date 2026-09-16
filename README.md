# Revenue Reconciliation

Reconciliation of an order-level storefront export against Finance's daily revenue-by-channel export.

## Deliverables

- `output/reconciled_revenue.csv` — reconciled daily revenue by channel
- `DISCREPANCY_NOTE.md` — findings, discrepancy inventory, working assumptions, and client questions
- `reconcile.py` — reproducible reconciliation and diagnostic script

## Project structure

```text
revenue-reconciliation/
├── data/
│   ├── orders.csv
│   └── finance_export.csv
├── output/
│   └── reconciled_revenue.csv
├── .gitignore
├── DISCREPANCY_NOTE.md
├── README.md
├── reconcile.py
└── requirements.txt
```

## Run

```bash
pip install -r requirements.txt
python reconcile.py
```

The script validates the source grain, profiles the extracts, tests competing revenue definitions on USD-only groups, infers the CAD-to-USD rate from clean groups, prints the remaining mismatches, and writes the final CSV.

## Working revenue definition

The reconciliation uses:

- one row per unique `order_id`
- paid orders only
- test orders excluded
- revenue net of refunds (`gross - refund`)
- CAD converted at `1 CAD = 0.74 USD`
- storefront channels normalized to Finance's channel taxonomy
- revenue grouped by the UTC storefront order date

Unresolved cancellation timing and the February 4 Finance cutoff are documented in `DISCREPANCY_NOTE.md` rather than silently adjusted.
