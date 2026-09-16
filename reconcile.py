from pathlib import Path

import pandas as pd


# =========================================================
# CONFIGURATION
# =========================================================

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

ORDERS_PATH = DATA_DIR / "orders.csv"
FINANCE_PATH = DATA_DIR / "finance_export.csv"
OUTPUT_PATH = OUTPUT_DIR / "reconciled_revenue.csv"

CAD_TO_USD_RATE = 0.74
MATCH_TOLERANCE = 0.01

CHANNEL_MAP = {
    "(direct)": "Direct",
    "email": "Email",
    "google": "Paid Search",
    "facebook": "Paid Social",
    "Facebook Ads": "Paid Social",
    "fb": "Paid Social",
    "tiktok": "Other",
    "affiliate": "Other",
}

ORDER_COLUMNS = {
    "order_id",
    "created_at",
    "channel",
    "gross",
    "refund",
    "currency",
    "status",
    "is_test_order",
}

FINANCE_COLUMNS = {
    "date",
    "channel",
    "revenue_usd",
}


# =========================================================
# LOADING AND VALIDATION
# =========================================================


def require_columns(dataframe: pd.DataFrame, required: set[str], source: str) -> None:
    missing = required - set(dataframe.columns)
    if missing:
        raise ValueError(f"{source} is missing required columns: {sorted(missing)}")


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and minimally normalize both supplied extracts."""

    orders = pd.read_csv(ORDERS_PATH)
    finance = pd.read_csv(FINANCE_PATH)

    require_columns(orders, ORDER_COLUMNS, "orders.csv")
    require_columns(finance, FINANCE_COLUMNS, "finance_export.csv")

    orders["gross"] = pd.to_numeric(orders["gross"], errors="raise")
    orders["refund"] = pd.to_numeric(orders["refund"], errors="raise")
    finance["revenue_usd"] = pd.to_numeric(finance["revenue_usd"], errors="raise")

    finance["date"] = pd.to_datetime(finance["date"], errors="raise").dt.date.astype(str)

    return orders, finance


def validate_sources(orders: pd.DataFrame, finance: pd.DataFrame) -> None:
    """Fail early on source conditions that would make the reconciliation ambiguous."""

    finance_duplicates = finance[
        finance.duplicated(subset=["date", "channel"], keep=False)
    ]
    if not finance_duplicates.empty:
        raise ValueError(
            "finance_export.csv contains duplicate date/channel rows; "
            "its stated grain is not unique."
        )

    repeated_ids = orders[
        orders.duplicated(subset=["order_id"], keep=False)
    ]

    conflicting_ids: list[str] = []
    if not repeated_ids.empty:
        for order_id, group in repeated_ids.groupby("order_id"):
            if len(group[list(ORDER_COLUMNS)].drop_duplicates()) > 1:
                conflicting_ids.append(str(order_id))

    if conflicting_ids:
        raise ValueError(
            "Repeated order IDs contain conflicting source values: "
            f"{conflicting_ids}"
        )


def prepare_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Add analytical fields without changing the source rows."""

    prepared = orders.copy()

    prepared["created_at"] = pd.to_datetime(
        prepared["created_at"],
        utc=True,
        errors="raise",
    )
    prepared["date"] = prepared["created_at"].dt.date.astype(str)
    prepared["net_revenue"] = prepared["gross"] - prepared["refund"]
    prepared["normalized_channel"] = prepared["channel"].map(CHANNEL_MAP)

    unmapped = prepared[prepared["normalized_channel"].isna()]["channel"].drop_duplicates()
    if not unmapped.empty:
        raise ValueError(
            "Unmapped storefront channel values found: "
            f"{unmapped.tolist()}"
        )

    return prepared


# =========================================================
# SOURCE PROFILING
# =========================================================


def profile_sources(orders: pd.DataFrame, finance: pd.DataFrame) -> None:
    """Print the source characteristics used during investigation."""

    print("\n" + "=" * 60)
    print("SOURCE PROFILING")
    print("=" * 60)

    print(f"\nOrders rows:  {len(orders)}")
    print(f"Finance rows: {len(finance)}")

    print("\n=== ORDER CHANNELS ===")
    print(orders["channel"].value_counts(dropna=False))

    print("\n=== FINANCE CHANNELS ===")
    print(finance["channel"].value_counts(dropna=False))

    print("\n=== CURRENCIES ===")
    print(orders["currency"].value_counts(dropna=False))

    print("\n=== STATUSES ===")
    print(orders["status"].value_counts(dropna=False))

    print("\n=== TEST ORDERS ===")
    print(orders["is_test_order"].value_counts(dropna=False))

    print("\n=== REFUNDS ===")
    print(f"Orders with non-zero refunds: {(orders['refund'] > 0).sum()}")

    print("\n=== DUPLICATES ===")
    print(f"Exact duplicate rows: {orders.duplicated().sum()}")
    print(f"Unique order IDs:     {orders['order_id'].nunique()}")

    repeated = orders[
        orders.duplicated(subset=["order_id"], keep=False)
    ].sort_values("order_id")

    if not repeated.empty:
        print("\n=== REPEATED ORDER IDS ===")
        print(repeated.to_string(index=False))


def print_channel_mapping(orders: pd.DataFrame) -> None:
    mapping = (
        orders[["channel", "normalized_channel"]]
        .drop_duplicates()
        .sort_values(["normalized_channel", "channel"])
    )

    print("\n" + "=" * 60)
    print("CHANNEL MAPPING")
    print("=" * 60)
    print(mapping.to_string(index=False))


# =========================================================
# HYPOTHESIS TESTING ON USD-ONLY GROUPS
# =========================================================


def get_usd_only_groups(orders: pd.DataFrame) -> pd.DataFrame:
    """Return date/channel groups whose source orders are all USD."""

    currencies = (
        orders.groupby(["date", "normalized_channel"])["currency"]
        .agg(lambda values: set(values))
        .reset_index(name="currencies")
    )

    groups = currencies[
        currencies["currencies"].apply(lambda value: value == {"USD"})
    ][["date", "normalized_channel"]].copy()

    print("\n" + "=" * 60)
    print("CURRENCY ISOLATION")
    print("=" * 60)
    print(f"USD-only date/channel groups: {len(groups)}")

    return groups


def build_candidate_variants(orders: pd.DataFrame):
    """Build alternative revenue interpretations for empirical comparison."""

    deduplicated = orders.drop_duplicates(subset=["order_id"], keep="first")
    no_tests = orders[~orders["is_test_order"]]
    paid_only = orders[orders["status"] == "paid"]
    paid_no_tests = orders[
        (orders["status"] == "paid") & (~orders["is_test_order"])
    ]

    dedup_no_tests = deduplicated[~deduplicated["is_test_order"]]
    dedup_paid = deduplicated[deduplicated["status"] == "paid"]
    dedup_paid_no_tests = deduplicated[
        (deduplicated["status"] == "paid")
        & (~deduplicated["is_test_order"])
    ]

    datasets = {
        "raw": orders,
        "deduplicated": deduplicated,
        "exclude tests": no_tests,
        "dedup + exclude tests": dedup_no_tests,
        "paid only": paid_only,
        "paid excluding tests": paid_no_tests,
        "dedup + paid": dedup_paid,
        "dedup + paid + exclude tests": dedup_paid_no_tests,
    }

    variants = []
    for label, dataframe in datasets.items():
        variants.append((f"{label} gross", dataframe, "gross"))
        variants.append((f"{label} net", dataframe, "net_revenue"))

    return variants


def evaluate_variant(
    name: str,
    dataframe: pd.DataFrame,
    revenue_column: str,
    finance: pd.DataFrame,
    usd_only_groups: pd.DataFrame,
) -> dict:
    aggregated = (
        dataframe.groupby(
            ["date", "normalized_channel"],
            as_index=False,
        )[revenue_column]
        .sum()
        .rename(columns={revenue_column: "calculated_revenue"})
    )

    comparison = usd_only_groups.merge(
        finance,
        left_on=["date", "normalized_channel"],
        right_on=["date", "channel"],
        how="left",
    ).merge(
        aggregated,
        on=["date", "normalized_channel"],
        how="left",
    )

    comparison["difference"] = (
        comparison["revenue_usd"] - comparison["calculated_revenue"]
    )

    abs_difference = comparison["difference"].abs()

    return {
        "variant": name,
        "exact_matches": int(abs_difference.le(MATCH_TOLERANCE).sum()),
        "groups_tested": len(comparison),
        "total_absolute_difference": round(abs_difference.sum(), 2),
        "comparison": comparison,
    }


def compare_candidate_definitions(
    orders: pd.DataFrame,
    finance: pd.DataFrame,
    usd_only_groups: pd.DataFrame,
):
    results = [
        evaluate_variant(name, dataframe, revenue_column, finance, usd_only_groups)
        for name, dataframe, revenue_column in build_candidate_variants(orders)
    ]

    summary = pd.DataFrame(
        [
            {
                "variant": result["variant"],
                "exact_matches": result["exact_matches"],
                "groups_tested": result["groups_tested"],
                "total_absolute_difference": result["total_absolute_difference"],
            }
            for result in results
        ]
    ).sort_values(
        ["exact_matches", "total_absolute_difference"],
        ascending=[False, True],
    )

    print("\n" + "=" * 60)
    print("CANDIDATE REVENUE DEFINITIONS")
    print("=" * 60)
    print(summary.to_string(index=False))

    return results, summary


def inspect_best_variant(results, summary) -> None:
    best_name = summary.iloc[0]["variant"]
    best = next(result for result in results if result["variant"] == best_name)
    comparison = best["comparison"].copy()
    comparison["absolute_difference"] = comparison["difference"].abs()

    mismatches = comparison[
        comparison["absolute_difference"] > MATCH_TOLERANCE
    ].copy()

    print("\n" + "=" * 60)
    print("BEST USD-ONLY CANDIDATE - DIAGNOSTIC")
    print("=" * 60)
    print(f"Variant:       {best_name}")
    print(f"Groups tested: {len(comparison)}")
    print(
        "Exact matches: "
        f"{(comparison['absolute_difference'] <= MATCH_TOLERANCE).sum()}"
    )
    print(f"Mismatches:    {len(mismatches)}")

    if not mismatches.empty:
        print("\n=== REMAINING USD-ONLY MISMATCHES ===")
        print(
            mismatches[
                [
                    "date",
                    "normalized_channel",
                    "revenue_usd",
                    "calculated_revenue",
                    "difference",
                ]
            ]
            .sort_values(
                "difference",
                key=lambda values: values.abs(),
                ascending=False,
            )
            .to_string(index=False)
        )


def inspect_usd_mismatch_orders(orders, results, summary) -> None:
    """Print raw storefront rows behind the residual USD-only mismatches."""

    best_name = summary.iloc[0]["variant"]
    best = next(result for result in results if result["variant"] == best_name)
    comparison = best["comparison"].copy()
    mismatches = comparison[
        comparison["difference"].abs() > MATCH_TOLERANCE
    ]

    if mismatches.empty:
        return

    print("\n" + "=" * 60)
    print("ORDERS BEHIND USD-ONLY MISMATCHES")
    print("=" * 60)

    columns = [
        "order_id",
        "created_at",
        "channel",
        "gross",
        "refund",
        "net_revenue",
        "currency",
        "status",
        "is_test_order",
    ]

    for _, mismatch in mismatches.iterrows():
        date = mismatch["date"]
        channel = mismatch["normalized_channel"]
        relevant = orders[
            (orders["date"] == date)
            & (orders["normalized_channel"] == channel)
        ].sort_values("created_at")

        print(f"\n--- {date} / {channel} ---")
        print(f"Finance revenue:    ${mismatch['revenue_usd']:.2f}")
        print(f"Calculated revenue: ${mismatch['calculated_revenue']:.2f}")
        print(f"Difference:         ${mismatch['difference']:.2f}")
        print(relevant[columns].to_string(index=False))


# =========================================================
# FX INFERENCE
# =========================================================


def infer_cad_conversion_rate(
    orders: pd.DataFrame,
    finance: pd.DataFrame,
) -> pd.DataFrame:
    """Infer Finance's CAD-to-USD rate from clean date/channel groups."""

    analysis = orders.copy()
    analysis["duplicate_order_id"] = analysis.duplicated(
        subset=["order_id"],
        keep=False,
    )

    flags = (
        analysis.groupby(["date", "normalized_channel"], as_index=False)
        .agg(
            has_cancelled=("status", lambda values: (values == "cancelled").any()),
            has_test_order=("is_test_order", "any"),
            has_duplicate_order=("duplicate_order_id", "any"),
        )
    )

    eligible = analysis[
        (analysis["status"] == "paid")
        & (~analysis["is_test_order"])
    ]

    currency_totals = (
        eligible.groupby(
            ["date", "normalized_channel", "currency"],
            as_index=False,
        )["net_revenue"]
        .sum()
        .pivot(
            index=["date", "normalized_channel"],
            columns="currency",
            values="net_revenue",
        )
        .fillna(0)
        .reset_index()
    )

    for currency in ("USD", "CAD"):
        if currency not in currency_totals.columns:
            currency_totals[currency] = 0.0

    comparison = (
        currency_totals.merge(
            flags,
            on=["date", "normalized_channel"],
            how="left",
        )
        .merge(
            finance,
            left_on=["date", "normalized_channel"],
            right_on=["date", "channel"],
            how="inner",
        )
    )

    clean = comparison[
        (comparison["CAD"] > 0)
        & (~comparison["has_cancelled"])
        & (~comparison["has_test_order"])
        & (~comparison["has_duplicate_order"])
    ].copy()

    clean["implied_cad_to_usd_rate"] = (
        clean["revenue_usd"] - clean["USD"]
    ) / clean["CAD"]

    print("\n" + "=" * 60)
    print("CAD -> USD RATE INVESTIGATION")
    print("=" * 60)
    print(f"Clean groups available: {len(clean)}")
    print(clean["implied_cad_to_usd_rate"].describe())
    print(
        "Median implied rate: "
        f"{clean['implied_cad_to_usd_rate'].median():.6f}"
    )

    return clean


# =========================================================
# FINAL RECONCILIATION
# =========================================================


def build_working_reconciliation(
    orders: pd.DataFrame,
    finance: pd.DataFrame,
):
    """
    Apply the evidence-supported working definition:

    - one record per unique order_id
    - paid orders only
    - test orders excluded
    - net revenue = gross - refund
    - CAD converted to USD at 0.74
    - channels normalized to Finance taxonomy
    - revenue grouped by UTC storefront order date

    Unresolved cancellation timing and the final-day Finance cutoff are
    documented rather than silently forced to match.
    """

    working = orders.drop_duplicates(
        subset=["order_id"],
        keep="first",
    ).copy()

    working = working[
        (working["status"] == "paid")
        & (~working["is_test_order"])
    ].copy()

    working["revenue_usd"] = working["net_revenue"]
    cad = working["currency"] == "CAD"
    working.loc[cad, "revenue_usd"] = (
        working.loc[cad, "net_revenue"] * CAD_TO_USD_RATE
    )

    # Finance behavior is reproduced by aggregating converted values first
    # and rounding the date/channel reporting total to cents once.
    reconciled = (
        working.groupby(
            ["date", "normalized_channel"],
            as_index=False,
        )["revenue_usd"]
        .sum()
        .rename(
            columns={
                "normalized_channel": "channel",
                "revenue_usd": "reconciled_revenue_usd",
            }
        )
    )
    reconciled["reconciled_revenue_usd"] = (
        reconciled["reconciled_revenue_usd"].round(2)
    )

    comparison = finance.merge(
        reconciled,
        on=["date", "channel"],
        how="outer",
    )
    comparison["difference"] = (
        comparison["revenue_usd"]
        - comparison["reconciled_revenue_usd"]
    )
    comparison["absolute_difference"] = comparison["difference"].abs()

    return reconciled, comparison


def print_full_reconciliation(comparison: pd.DataFrame) -> None:
    mismatches = comparison[
        comparison["absolute_difference"].fillna(float("inf"))
        > MATCH_TOLERANCE
    ].copy()

    exact_matches = (
        comparison["absolute_difference"]
        .fillna(float("inf"))
        .le(MATCH_TOLERANCE)
        .sum()
    )

    print("\n" + "=" * 60)
    print("FULL RECONCILIATION")
    print("=" * 60)
    print(f"Date/channel groups: {len(comparison)}")
    print(f"Exact matches:       {exact_matches}")
    print(f"Mismatches:          {len(mismatches)}")

    if not mismatches.empty:
        print("\n=== FULL DATASET MISMATCHES ===")
        display = mismatches[
            [
                "date",
                "channel",
                "revenue_usd",
                "reconciled_revenue_usd",
                "difference",
            ]
        ].rename(columns={"revenue_usd": "finance_revenue_usd"})
        print(display.sort_values(["date", "channel"]).to_string(index=False))


def export_reconciled_table(reconciled: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output = (
        reconciled[
            ["date", "channel", "reconciled_revenue_usd"]
        ]
        .sort_values(["date", "channel"])
        .copy()
    )

    output.to_csv(
        OUTPUT_PATH,
        index=False,
        float_format="%.2f",
    )

    print("\n" + "=" * 60)
    print("FINAL OUTPUT")
    print("=" * 60)
    print(f"Created: {OUTPUT_PATH.relative_to(ROOT)}")
    print(f"Rows written: {len(output)}")


# =========================================================
# MAIN
# =========================================================


def main() -> None:
    orders_raw, finance = load_data()
    validate_sources(orders_raw, finance)
    profile_sources(orders_raw, finance)

    orders = prepare_orders(orders_raw)
    print_channel_mapping(orders)

    usd_only_groups = get_usd_only_groups(orders)
    results, summary = compare_candidate_definitions(
        orders,
        finance,
        usd_only_groups,
    )
    inspect_best_variant(results, summary)
    inspect_usd_mismatch_orders(orders, results, summary)

    infer_cad_conversion_rate(orders, finance)

    reconciled, comparison = build_working_reconciliation(
        orders,
        finance,
    )
    print_full_reconciliation(comparison)
    export_reconciled_table(reconciled)


if __name__ == "__main__":
    main()
