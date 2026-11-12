
from pathlib import Path

import pandas as pd

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = (
    BASE_DIR
    / "data"
    / "processed"
    / "nfip_payments_by_year_hud_status.csv"
)

OUTPUT_PATH = (
    BASE_DIR
    / "data"
    / "processed"
    / "nfip_loss_concentration_by_year.csv"
)

# Load the processed FEMA data
df = pd.read_csv(DATA_PATH)

# Focus on Pinellas-linked ZIP codes
df = df[df["hud_status"] == "hud_pinellas_link"].copy()

# Calculate annual payments and claims
annual = (
    df.groupby("year_of_loss", as_index=False)
    .agg(
        total_payments=("gross_reported_payments_usd", "sum"),
        claim_records=("claim_records", "sum"),
        positive_payment_claims=("positive_payment_claims", "sum"),
    )
)

# Rank years by total reported payments
annual = annual.sort_values(
    "total_payments", ascending=False
).reset_index(drop=True)

total_payments = annual["total_payments"].sum()

# Calculate each year's share of all historical payments
annual["payment_share_pct"] = (
    annual["total_payments"] / total_payments * 100
)

# Calculate cumulative concentration
annual["cumulative_payment_share_pct"] = (
    annual["payment_share_pct"].cumsum()
)

# Add rank
annual.insert(0, "payment_rank", range(1, len(annual) + 1))

# Save results
annual.to_csv(OUTPUT_PATH, index=False)

# Print summary
print("\nRIS KMAP — HISTORICAL LOSS CONCENTRATION")
print("=" * 55)

print(f"\nTotal reported payments: ${total_payments:,.2f}")
print(f"Total claim records: {annual['claim_records'].sum():,}")

print("\nTOP 5 LOSS YEARS")
print(
    annual[
        [
            "payment_rank",
            "year_of_loss",
            "total_payments",
            "payment_share_pct",
        ]
    ].head(5).to_string(index=False)
)

for n in [1, 3, 5]:
    share = annual["payment_share_pct"].head(n).sum()
    print(f"\nTop {n} year(s) account for {share:.2f}% of payments")

print(f"\nSaved results to: {OUTPUT_PATH}")
