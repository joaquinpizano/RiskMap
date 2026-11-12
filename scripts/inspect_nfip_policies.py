
# ============================================================
# RISKMAP — FEMA NFIP POLICY DATA QUALITY INSPECTION
# ============================================================
# Purpose:
# Inspect FEMA NFIP policy records for geographic coverage,
# policy counts, date quality, and missing information.
#
# This script does NOT modify any existing RiskMap datasets.
# ============================================================

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import pandas as pd


# ------------------------------------------------------------
# 1. FEMA API CONFIGURATION
# ------------------------------------------------------------

API = "https://www.fema.gov/api/open/v3/NfipPolicies"

# Small, manageable sample from ZIP 33706.
# No year filter: this is a geographic and field-quality test.

params = {
    "$filter": (
        "propertyState eq 'FL' "
        "and reportedZipCode eq '33706'"
    ),
    "$select": (
        "id,propertyState,reportedZipCode,censusGeoid,"
        "policyEffectiveDate,policyTerminationDate,"
        "cancellationDateOfFloodPolicy,policyCount,"
        "condominiumCoverageTypeCode"
    ),
    "$top": 50,
}

url = API + "?" + urlencode(params)


# ------------------------------------------------------------
# 2. DOWNLOAD SAMPLE RECORDS
# ------------------------------------------------------------

print("\nRISKMAP — NFIP POLICY QUALITY INSPECTION")
print("=" * 60)

try:
    request = Request(
        url,
        headers={"User-Agent": "RiskMap Research/1.0"},
    )

    with urlopen(request, timeout=60) as response:
        data = json.load(response)

except HTTPError as error:
    print(f"\nFEMA HTTP Error: {error.code}")
    print(
        error.read().decode(
            "utf-8", errors="replace"
        )[:3000]
    )
    raise SystemExit(1)

except (URLError, TimeoutError) as error:
    print("\nConnection failed:", error)
    raise SystemExit(1)


# ------------------------------------------------------------
# 3. CONVERT RECORDS TO DATAFRAME
# ------------------------------------------------------------

records = data.get("NfipPolicies", [])

df = pd.DataFrame(records)

if df.empty:
    print("No policy records returned.")
    print("Response keys:", list(data.keys()))
    raise SystemExit(1)

print(f"\nSample records: {len(df):,}")


# ------------------------------------------------------------
# 4. GEOGRAPHIC VALIDATION
# ------------------------------------------------------------

print("\nGEOGRAPHIC VALIDATION")
print("-" * 60)

geoids = (
    df["censusGeoid"]
    .astype("string")
    .fillna("")
    .str.strip()
)

missing_geoid = geoids.eq("")

# Pinellas County Census GEOID prefix = 12103
pinellas_match = geoids.str.startswith("12103")

other_county = ~missing_geoid & ~pinellas_match

print("Pinellas GEOID records:", int(pinellas_match.sum()))
print("Missing Census GEOIDs:", int(missing_geoid.sum()))
print("Other county GEOIDs:", int(other_county.sum()))

print(
    "Missing GEOID percentage:",
    f"{missing_geoid.mean() * 100:.2f}%"
)

print("\nCensus county prefix distribution:")

county_prefix = geoids.str[:5].replace("", "MISSING")

print(
    county_prefix.value_counts().to_string()
)


# ------------------------------------------------------------
# 5. POLICY COUNT VALIDATION
# ------------------------------------------------------------

print("\nPOLICY COUNT VALIDATION")
print("-" * 60)

policy_counts = pd.to_numeric(
    df["policyCount"],
    errors="coerce"
)

print("Total policyCount:", policy_counts.sum())
print(
    "Records with policyCount > 1:",
    int((policy_counts > 1).sum())
)
print(
    "Missing policy counts:",
    int(policy_counts.isna().sum())
)
print(
    "Zero or negative policy counts:",
    int((policy_counts <= 0).sum())
)

print("\nPolicy count distribution:")
print(
    policy_counts.value_counts()
    .head(10)
    .to_string()
)


# ------------------------------------------------------------
# 6. POLICY DATE VALIDATION
# ------------------------------------------------------------

print("\nPOLICY DATE VALIDATION")
print("-" * 60)

effective = pd.to_datetime(
    df["policyEffectiveDate"],
    errors="coerce",
    utc=True
)

termination = pd.to_datetime(
    df["policyTerminationDate"],
    errors="coerce",
    utc=True
)

valid_dates = effective.notna() & termination.notna()

invalid_intervals = (
    valid_dates & (termination <= effective)
)

print(
    "Missing effective dates:",
    int(effective.isna().sum())
)
print(
    "Missing termination dates:",
    int(termination.isna().sum())
)
print(
    "Invalid date intervals:",
    int(invalid_intervals.sum())
)

print(
    "Records with cancellation dates:",
    int(
        df["cancellationDateOfFloodPolicy"]
        .notna()
        .sum()
    )
)

print("\nEffective year distribution:")
print(
    effective.dt.year
    .value_counts()
    .sort_index()
    .to_string()
)


# ------------------------------------------------------------
# 7. CONDOMINIUM COVERAGE INSPECTION
# ------------------------------------------------------------

print("\nCONDOMINIUM COVERAGE TYPES")
print("-" * 60)

print(
    df["condominiumCoverageTypeCode"]
    .fillna("MISSING")
    .value_counts()
    .to_string()
)


# ------------------------------------------------------------
# 8. DUPLICATE RECORD CHECK
# ------------------------------------------------------------

print("\nRECORD VALIDATION")
print("-" * 60)

print(
    "Duplicate record IDs:",
    int(df["id"].duplicated().sum())
)


# ------------------------------------------------------------
# 9. FINAL INSPECTION SUMMARY
# ------------------------------------------------------------

print("\n" + "=" * 60)
print("RISKMAP — INSPECTION COMPLETE")
print("=" * 60)

print("FEMA API connection: SUCCESS")
print("Sample records processed:", len(df))
print("Pinellas GEOID matches:", int(pinellas_match.sum()))
print("Missing geographic identifiers:", int(missing_geoid.sum()))
print("Invalid date intervals:", int(invalid_intervals.sum()))

print(
    "\nIMPORTANT: This is a small, nonrandom sample."
)
print(
    "No existing RiskMap datasets were modified."
)
print(
    "Countywide exposure calculations require further validation."
)
