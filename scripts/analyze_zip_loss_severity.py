
from pathlib import Path

import pandas as pd

# --------------------------------------------------
# FILE PATHS
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data" / "processed"

YEARLY_ZIP_PATH = DATA_DIR / "nfip_claims_by_year_zip.csv"
ZIP_STATUS_PATH = DATA_DIR / "nfip_payments_by_zip_hud.csv"

OUTPUT_PATH = DATA_DIR / "nfip_zip_loss_severity.csv"


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

yearly = pd.read_csv(
    YEARLY_ZIP_PATH,
    dtype={"reported_zip_code": str},
)

zip_status = pd.read_csv(
    ZIP_STATUS_PATH,
    dtype={"reported_zip_5": str},
)

# Identify ZIP codes linked to Pinellas County

pinellas_zips = set(
    zip_status.loc[
        zip_status["hud_status"] == "hud_pinellas_link",
        "reported_zip_5",
    ].dropna()
)

yearly = yearly.loc[
    yearly["reported_zip_code"].isin(pinellas_zips)
].copy()


# --------------------------------------------------
# DEFINE COMPARISON PERIODS
# --------------------------------------------------

periods = {
    "All Years": yearly,
    "2024 Only": yearly[yearly["year_of_loss"] == 2024],
    "Excluding 2024": yearly[yearly["year_of_loss"] != 2024],
}


# --------------------------------------------------
# ANALYZE EACH PERIOD
# --------------------------------------------------

results = []

for period_name, period_data in periods.items():

    summary = (
        period_data.groupby(
            "reported_zip_code", as_index=False
        )
        .agg(
            claim_records=("claim_records", "sum"),
            positive_payment_claims=(
                "records_with_positive_payments", "sum"
            ),
            total_payments=(
                "gross_reported_payments_usd", "sum"
            ),
        )
    )

    if summary.empty:
        continue

    # Average payment per positive-payment claim

    summary["avg_payment_per_positive_claim"] = (
        summary["total_payments"]
        / summary["positive_payment_claims"].replace(
            0, float("nan")
        )
    )

    # ZIP's share of all payments in the period

    period_total = summary["total_payments"].sum()

    if period_total > 0:
        summary["payment_share_pct"] = (
            summary["total_payments"] / period_total * 100
        )
    else:
        summary["payment_share_pct"] = 0.0

    # Rank ZIP codes by total payments

    summary = summary.sort_values(
        "total_payments", ascending=False
    ).reset_index(drop=True)

    summary.insert(
        0, "payment_rank", range(1, len(summary) + 1)
    )

    summary.insert(0, "period", period_name)

    results.append(summary)


# --------------------------------------------------
# SAVE AND DISPLAY RESULTS
# --------------------------------------------------

final = pd.concat(results, ignore_index=True)

final.to_csv(OUTPUT_PATH, index=False)

print("\nRISKMAP — ZIP LOSS SEVERITY ANALYSIS")
print("=" * 60)

for period_name in periods:

    subset = final.loc[
        final["period"] == period_name
    ]

    if subset.empty:
        continue

    print(f"\n{period_name.upper()}")
    print("-" * 60)

    print(
        subset[
            [
                "payment_rank",
                "reported_zip_code",
                "claim_records",
                "total_payments",
                "avg_payment_per_positive_claim",
                "payment_share_pct",
            ]
        ].head(10).to_string(
            index=False,
            float_format=lambda x: f"{x:,.2f}",
        )
    )

print(f"\nSaved results to: {OUTPUT_PATH}")
