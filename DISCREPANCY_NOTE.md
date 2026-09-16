# Revenue Reconciliation Note

## Executive summary

I reconciled the storefront order extract against Finance's daily revenue report for 2026-01-06 through 2026-02-04.

The working revenue definition is:

- one row per unique `order_id`
- paid orders only
- test orders excluded
- revenue net of refunds: `gross - refund`
- USD orders used directly
- CAD converted at `1 CAD = 0.74 USD`
- storefront channels normalized to Finance's channel taxonomy
- revenue grouped by the storefront order date in UTC

Using that definition, 128 of 145 date/channel groups match Finance exactly. The remaining 17 differences fall into three identifiable categories:

1. duplicate storefront records that appear to have flowed into Finance
2. inconsistent historical treatment of orders now marked `cancelled`
3. a likely incomplete Finance snapshot or reporting cutoff on 2026-02-04

The duplicate records can be resolved from the supplied data. Cancellation timing and the February 4 cutoff cannot be resolved confidently because the extracts do not contain the required timestamps or reporting metadata.

---

## 1. Source overview

### `orders.csv`

- 741 rows
- 8 source columns
- intended grain: one row per storefront order
- covers 2026-01-06 through 2026-02-04
- contains USD and CAD orders
- contains paid, cancelled, test, refunded, and duplicated records

Source fields:

- `order_id`
- `created_at`
- `channel`
- `gross`
- `refund`
- `currency`
- `status`
- `is_test_order`

### `finance_export.csv`

- 145 rows
- one row per date/channel combination
- covers 2026-01-06 through 2026-02-04
- reports revenue in USD

Source fields:

- `date`
- `channel`
- `revenue_usd`

---

## 2. Resolved from the supplied data

### Channel taxonomy

The two extracts use different channel names. The working mapping is:

| Storefront channel | Finance channel |
|---|---|
| `(direct)` | `Direct` |
| `email` | `Email` |
| `google` | `Paid Search` |
| `facebook` | `Paid Social` |
| `Facebook Ads` | `Paid Social` |
| `fb` | `Paid Social` |
| `tiktok` | `Other` |
| `affiliate` | `Other` |

This mapping is supported by the daily reconciliation. In particular, mapping TikTok to `Other` rather than `Paid Social` reduced the unexplained USD-only variance to two date/channel groups.

### Refund treatment

There are 38 orders with a non-zero refund. I tested gross revenue against net revenue (`gross - refund`).

For USD-only groups:

- paid, non-test, net revenue: 58 of 60 groups matched exactly
- paid, non-test, gross revenue: 48 of 60 groups matched exactly

**Working rule:** use net revenue: `gross - refund`.

The supplied extract does not contain `refunded_at`, so it cannot independently establish the general timing policy for future refunds. For the supplied period, netting the refund against the order's reporting date reproduces Finance materially better.

### Test orders

There are 12 rows flagged as test orders.

For USD-only groups:

- paid orders including tests, net: 54 exact matches
- paid orders excluding tests, net: 58 exact matches

**Working rule:** exclude test orders from reported revenue.

### CAD to USD conversion

The storefront contains 613 USD rows and 128 CAD rows, while Finance reports only `revenue_usd`.

To isolate the FX rule, I examined 59 date/channel groups containing CAD revenue but no test orders, cancelled orders, or repeated order IDs. For each clean group I solved:

`(Finance revenue - USD storefront revenue) / CAD storefront revenue`

The implied rates were effectively constant:

- median: 0.740000
- mean: 0.739999
- minimum: 0.739837
- maximum: 0.740100

The small variation is consistent with cents-level rounding.

**Working rule:** `1 CAD = 0.74 USD`.

The reconciliation converts CAD values, aggregates the date/channel total, and rounds the final reporting total to cents. This reproduces all clean CAD groups exactly.

### Duplicate storefront records

`orders.csv` contains 741 rows but only 736 unique `order_id` values. Five order IDs are repeated, and each repeated pair is identical across the supplied source fields:

- `E76-1097`
- `E76-1184`
- `E76-1212`
- `E76-1365`
- `E76-1658`

Because the stated source grain is one row per order, the reconciliation retains one record per `order_id`.

Four Finance differences equal exactly one extra copy of a duplicated paid order, which is consistent with duplicate source rows having flowed into Finance. `E76-1365` is different because that order is also currently marked cancelled and is part of the cancellation-timing issue described below.

---

## 3. Requires client input

### Cancelled-order treatment

There are 28 orders currently marked `cancelled`.

Excluding cancelled orders produces the strongest overall agreement with Finance, but the historical treatment is not consistent. Several Finance differences equal exactly the converted net value of orders that are now marked cancelled, while other cancelled orders are not reflected.

The clearest example is 2026-01-28 / Paid Search:

- `E76-1548` is cancelled and has a net USD value of $112.70
- `E76-1560` is cancelled and has a net USD value of $136.63
- Finance exceeds the working reconciliation by exactly $112.70

That means the supplied fields are not enough to infer a rule such as "include all cancelled orders" or "exclude all cancelled orders." The likely missing field is cancellation timing.

**Client question:**

> For historical daily revenue, should an order that was valid on the reporting date but cancelled later remain in that day's revenue, or should historical revenue be restated once the order becomes cancelled? The storefront extract only provides the current status and no `cancelled_at` timestamp, so I cannot reproduce Finance's mixed treatment without this rule.

### February 4 reporting cutoff / incomplete Finance snapshot

The final day has three channels where Finance is lower than the working reconciliation:

- Direct: Finance $199.87 vs reconciled $663.58
- Email: Finance $102.87 vs reconciled $288.77
- Paid Social: Finance $1,022.43 vs reconciled $1,084.57

The order timing is consistent with a late-day cutoff:

- Paid Social includes an eligible order at 21:35 UTC
- Direct orders at 22:10, 22:17, and 23:44 UTC are absent from the Finance total
- Email order `E76-1712` at 23:03 UTC is absent
- Paid Social order `E76-1708` at 23:23 UTC is absent

The observed totals are therefore consistent with a cutoff between approximately 21:35 and 22:10 UTC on February 4. The extracts do not establish whether this was the intended reporting cutoff, the Finance export-generation time, or a synchronization delay.

**Client question:**

> What cutoff time and timezone does the Finance daily export use? Was the 2026-02-04 export generated before the reporting day completed, or should those late orders have been included?

---

## 4. Full mismatch inventory

After applying the working revenue definition, 17 of 145 date/channel groups still differ from Finance.

`Difference = Finance revenue - reconciled revenue`

| Date | Channel | Finance | Reconciled | Difference | Status | Explanation |
|---|---|---:|---:|---:|---|---|
| 2026-01-10 | Other | $513.52 | $469.03 | $44.49 | Resolved | Difference equals one extra copy of duplicate `E76-1097` |
| 2026-01-13 | Direct | $342.35 | $277.16 | $65.19 | Resolved | Difference equals one extra copy of duplicate `E76-1184` |
| 2026-01-14 | Other | $810.20 | $772.78 | $37.42 | Resolved | Difference equals one extra copy of duplicate `E76-1212` |
| 2026-01-15 | Other | $419.33 | $378.57 | $40.76 | Client input | Difference equals the current net value of cancelled `E76-1229` |
| 2026-01-16 | Paid Social | $1,087.44 | $907.99 | $179.45 | Client input | Difference equals the current net value of cancelled `E76-1262` |
| 2026-01-18 | Paid Social | $1,132.35 | $892.70 | $239.65 | Client input | Difference equals cancelled `E76-1301` + `E76-1297` after FX |
| 2026-01-20 | Other | $785.87 | $702.28 | $83.59 | Client input | Difference equals one copy each of cancelled `E76-1341` + `E76-1365` |
| 2026-01-20 | Paid Search | $464.71 | $228.93 | $235.78 | Client input | Difference equals cancelled `E76-1362` + `E76-1351` after FX |
| 2026-01-21 | Paid Social | $1,396.38 | $1,194.07 | $202.31 | Client input | Difference equals cancelled `E76-1370` + `E76-1388` |
| 2026-01-24 | Paid Social | $601.41 | $506.44 | $94.97 | Client input | Difference equals cancelled `E76-1469` after FX |
| 2026-01-28 | Paid Search | $382.60 | $269.90 | $112.70 | Client input | Difference equals cancelled `E76-1548`; cancelled `E76-1560` is not reflected |
| 2026-01-29 | Other | $114.63 | $61.85 | $52.78 | Client input | Difference equals cancelled `E76-1569` |
| 2026-01-29 | Paid Social | $932.48 | $785.13 | $147.35 | Client input | Difference equals cancelled `E76-1574` |
| 2026-02-02 | Paid Search | $425.47 | $340.61 | $84.86 | Resolved | Difference equals one extra copy of duplicate `E76-1658` |
| 2026-02-04 | Direct | $199.87 | $663.58 | -$463.71 | Client input | Finance matches the earlier eligible orders; later paid orders beginning at 22:10 UTC are absent |
| 2026-02-04 | Email | $102.87 | $288.77 | -$185.90 | Client input | Late paid order `E76-1712` at 23:03 UTC is absent |
| 2026-02-04 | Paid Social | $1,022.43 | $1,084.57 | -$62.14 | Client input | Late paid order `E76-1708` at 23:23 UTC is absent |

The affected rows are explicitly documented here rather than silently adjusted to force agreement with Finance.

---

## 5. Reconciliation status

Using the working definition across the full period:

- 145 date/channel groups compared
- 128 exact matches
- 17 remaining differences

All 17 remaining differences are categorized above. No general unexplained revenue-calculation difference remains after accounting for channel normalization, refunds, test orders, FX conversion, duplicate records, cancellation timing, and the final-day cutoff pattern.

---

## 6. Recommended automated checks

For the next monthly reconciliation I would add:

1. **Duplicate order IDs** — fail if more than one source row exists for the same `order_id`.
2. **Unknown channels** — alert when a storefront channel is not in the approved mapping.
3. **Unexpected currencies** — alert when a currency other than USD or CAD appears.
4. **FX validation** — verify the effective CAD-to-USD rate against the configured Finance rate.
5. **Test-order exclusion** — verify no `is_test_order = True` row contributes to reported revenue.
6. **Cancellation timing** — compare revenue against `cancelled_at` once that field is available.
7. **Daily completeness** — verify the Finance export covers the agreed reporting cutoff before the CFO report is published.
8. **Revenue variance** — alert when storefront-derived and Finance date/channel revenue differ by more than $0.01 after approved rules are applied.

## 7. Recommended source-system improvements

The long-term fix is to define revenue once and have both storefront and Finance reporting derive from that shared model. The canonical definition should specify:

- reporting date and timezone
- channel mapping
- treatment of test orders
- cancellation policy
- refund-recognition policy
- FX source and conversion rule
- duplicate handling

I would also add these fields or metadata to the extracts:

- `cancelled_at`
- `refunded_at`
- FX rate applied to converted orders
- Finance export-generation timestamp

Those additions would make future reconciliations deterministic instead of inferential.
