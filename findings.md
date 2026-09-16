# Initial Findings

## Source structure

### orders.csv

- 741 rows
- 8 columns
- The intended grain appears to be one row per storefront order, although 5 exact duplicate rows violate that grain.
- Contains:
  - `order_id`
  - exact `created_at` timestamp
  - `channel`
  - `gross`
  - `refund`
  - `currency`
  - `status`
  - `is_test_order`
- Order creation dates cover 2026-01-06 through 2026-02-04.

### finance_export.csv

- 145 rows
- 3 columns
- Already aggregated to daily revenue by channel.
- Contains:
  - `date`
  - `channel`
  - `revenue_usd`
- Dates cover 2026-01-06 through 2026-02-04.

## Observed differences

### Channel taxonomy

- The two exports use different channel taxonomies.
- A channel normalization or mapping rule will be required before daily revenue can be compared.

### Currency

- Storefront orders contain both USD and CAD.
- Finance reports a single `revenue_usd` value.

Question to investigate:
- Does the available data explain how CAD orders were converted to USD?

### Order status

- 28 storefront orders are marked `cancelled`.

Questions to investigate:
- Are cancelled orders included in the Finance figures?
- Should cancelled orders contribute to the reconciled revenue definition?

### Test orders

- 12 storefront rows are flagged as test orders.

Questions to investigate:
- Are test orders included in the Finance figures?
- Should test orders contribute to reported revenue?

### Refunds

- 38 storefront orders contain a non-zero refund.
- Candidate storefront revenue definitions include:
  - gross revenue
  - net revenue (`gross - refund`)
- The storefront extract contains the order creation timestamp but no separate refund timestamp.

Questions to investigate:
- Does Finance report gross or net revenue?
- If refunds reduce reported revenue, which date should the refund be attributed to?

### Duplicates

- `orders.csv` contains 5 exact duplicate rows.
- There are 741 rows but only 736 unique `order_id` values.

Question to investigate:
- Can these exact duplicates be safely treated as duplicate extract records and removed before aggregation?