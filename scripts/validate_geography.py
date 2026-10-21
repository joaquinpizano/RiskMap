"""RiskMap | Audit geographic consistency in the original Pinellas NFIP claims.

Run in VS Code: open this file and choose 'Run Python File'.
Uses only Python's standard library. Never modifies the source CSV.

This is a screening audit, NOT authoritative ZIP-to-county validation.
A ZIP can cross county boundaries; 346xx ZIPs can belong to Pinellas.
FEMA coordinates may be generalized and are not property locations.
"""

from collections import Counter, defaultdict
from csv import DictReader, DictWriter
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "raw" / "NFIP_Claims_Pinellas.csv"
REPORT = ROOT / "reports" / "nfip_geography_audit.txt"
FLAGGED = ROOT / "data" / "processed" / "nfip_geography_review.csv"

if not SOURCE.is_file():
    raise SystemExit(f"Cannot find original FEMA CSV: {SOURCE}")

counts = Counter()
zip_counts = Counter()
zip_flags = defaultdict(Counter)
examples = defaultdict(list)

with SOURCE.open(newline="", encoding="utf-8-sig") as handle:
    reader = DictReader(handle)
    required = {"id", "state", "countyCode", "reportedZipCode", "censusGeoid"}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise SystemExit(f"Missing expected columns: {sorted(missing)}")

    for row in reader:
        counts["total"] += 1
        zip_code = (row.get("reportedZipCode") or "").strip()
        geoid = (row.get("censusGeoid") or "").strip()
        state = (row.get("state") or "").strip().upper()
        county = (row.get("countyCode") or "").strip()
        zip_label = zip_code or "UNKNOWN"
        zip_counts[zip_label] += 1
        flags = []

        if state != "FL" or county != "12103":
            flags.append("county_or_state_mismatch")
        if not zip_code:
            flags.append("missing_zip")
        elif not re.fullmatch(r"\d{5}", zip_code):
            flags.append("malformed_zip")
        elif not zip_code.startswith(("337", "346")):
            # Screening heuristic only: does NOT prove a ZIP is outside Pinellas.
            flags.append("unusual_zip_prefix_review")

        if not geoid:
            flags.append("missing_census_geoid")
        elif not geoid.isdigit():
            flags.append("malformed_census_geoid")
        elif not geoid.startswith("12103"):
            # Census GEOIDs can reflect source processing, not exact locations.
            flags.append("census_geoid_county_mismatch")

        if flags:
            counts["flagged_records"] += 1
            for flag in flags:
                counts[flag] += 1
                zip_flags[zip_label][flag] += 1
                if len(examples[flag]) < 5:
                    examples[flag].append(row.get("id", ""))

REPORT.parent.mkdir(parents=True, exist_ok=True)
FLAGGED.parent.mkdir(parents=True, exist_ok=True)

with FLAGGED.open("w", newline="", encoding="utf-8") as handle:
    writer = DictWriter(handle, fieldnames=["reported_zip", "claim_records", "review_reasons"])
    writer.writeheader()
    for zip_label, total in sorted(zip_counts.items(), key=lambda item: (-item[1], item[0])):
        reasons = zip_flags[zip_label]
        if reasons:
            # Reasons can overlap on the same record; counts per reason are not additive.
            writer.writerow({
                "reported_zip": zip_label,
                "claim_records": total,
                "review_reasons": "; ".join(f"{reason}={n}" for reason, n in sorted(reasons.items())),
            })

lines = [
    "RiskMap | FEMA NFIP geographic consistency screening",
    f"Source: {SOURCE.name}",
    f"Total claim records: {counts['total']:,}",
    f"Distinct reported ZIP categories (including UNKNOWN): {len(zip_counts):,}",
    f"Records flagged for at least one review reason: {counts['flagged_records']:,}",
    "",
    "Review flags (one claim may have multiple flags):",
]
for flag in [
    "county_or_state_mismatch", "missing_zip", "malformed_zip",
    "unusual_zip_prefix_review", "missing_census_geoid",
    "malformed_census_geoid", "census_geoid_county_mismatch",
]:
    lines.append(f"  {flag}: {counts[flag]:,}" +
                 (f" | example IDs: {', '.join(examples[flag])}" if examples[flag] else ""))
lines += [
    "", "IMPORTANT LIMITATIONS:",
    "- This script does not establish which ZIP codes lie in Pinellas County.",
    "- 337xx and 346xx are screening prefixes, not an authoritative ZIP list.",
    "- ZIPs may span county boundaries and change over time.",
    "- Census GEOID and county fields can disagree in source data.",
    "- FEMA coordinates are generalized; do not use as exact property locations.",
    "- Never delete claims based solely on these flags.",
    "- Before mapping, compare against an authoritative geographic crosswalk/boundary.",
    "", f"ZIP-level review list: {FLAGGED}",
]
REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
print(f"\nFull report saved to: {REPORT}")
