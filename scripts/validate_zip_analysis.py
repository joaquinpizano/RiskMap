
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"

ANNUAL_PATH = DATA_DIR / "nfip_loss_concentration_by_year.csv"
ZIP_PATH = DATA_DIR / "nfip_zip_loss_severity.csv"

annual = pd.read_csv(ANNUAL_PATH)
zip_data = pd.read_csv(
    ZIP_PATH,
    dtype={"reported_zip_code": str}
)

print("\nRISKMAP — ZIP ANALYSIS VALIDATION")
print("=" * 55)

checks = []

# CHECK 1: Annual totals vs ZIP totals
annual_total = annual["total_payments"].sum()

all_years = zip_data[
    zip_data["period"] == "All Years"
]

zip_total = all_years["total_payments"].sum()

difference = abs(annual_total - zip_total)

passed = difference < 0.01
checks.append(passed)

print("\nCHECK 1 — ANNUAL VS ZIP PAYMENT TOTALS")
print(f"Annual total: ${annual_total:,.2f}")
print(f"ZIP total:    ${zip_total:,.2f}")
print(f"Difference:   ${difference:,.2f}")
print("PASS" if passed else "FAIL")


# CHECK 2: All years = 2024 + excluding 2024
wide = zip_data.pivot(
    index="reported_zip_code",
    columns="period",
    values="total_payments"
).fillna(0)

wide["reconstructed_total"] = (
    wide["2024 Only"] + wide["Excluding 2024"]
)

wide["difference"] = (
    wide["All Years"] - wide["reconstructed_total"]
).abs()

max_difference = wide["difference"].max()

passed = max_difference < 0.01
checks.append(passed)

print("\nCHECK 2 — PERIOD RECONCILIATION")
print(f"Maximum ZIP difference: ${max_difference:,.6f}")
print("PASS" if passed else "FAIL")


# CHECK 3: Positive claims cannot exceed claim records
invalid = zip_data[
    zip_data["positive_payment_claims"]
    > zip_data["claim_records"]
]

passed = invalid.empty
checks.append(passed)

print("\nCHECK 3 — CLAIM COUNT CONSISTENCY")
print(f"Invalid rows: {len(invalid)}")
print("PASS" if passed else "FAIL")


# CHECK 4: Payment shares total 100% per period
print("\nCHECK 4 — PAYMENT SHARE TOTALS")

for period, group in zip_data.groupby("period"):
    total_share = group["payment_share_pct"].sum()
    period_payments = group["total_payments"].sum()

    if period_payments > 0:
        passed = abs(total_share - 100) < 0.01
    else:
        passed = abs(total_share) < 0.01

    checks.append(passed)

    print(
        f"{period}: {total_share:.4f}% — "
        f"{'PASS' if passed else 'FAIL'}"
    )


# FINAL RESULT
print("\n" + "=" * 55)

if all(checks):
    print("ALL VALIDATION CHECKS PASSED")
else:
    print("VALIDATION FAILED — INVESTIGATE BEFORE MODELING")
