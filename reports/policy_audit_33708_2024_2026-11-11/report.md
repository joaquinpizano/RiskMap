# ZIP 33708 — 2024 effective-year policy audit

Retrieved (UTC): 2026-11-11T21:46:43.203064+00:00

Scope: propertyState = FL, reportedZipCode = 33708, policyEffectiveDate >= 2024-01-01 and < 2025-01-01. Pinellas filter: startswith(censusGeoid,'12103'). Existing screening evidence was reused and hash-checked; new full records were needed for IDs, GEOIDs and policyCount.

Downloaded rows: 3790; FEMA Pinellas rows: 3790; FEMA ZIP-only rows: 4304.

Target September 8, 2026 snapshot verified across all records: **True**. Exact downloaded/FEMA Pinellas/ZIP-only Pinellas-subset IDs reconcile: **True**.

Observed row asOfDate distributions:
- Downloaded: {'2026-09-08T00:00:00.000Z': 3790}
- FEMA Pinellas: {'2026-09-08T00:00:00.000Z': 3790}
- FEMA ZIP-only: {'2026-09-08T00:00:00.000Z': 4304}

| Group | Rows | Sum valid policyCount | Missing counts | Invalid counts | Sum complete |
|---|---:|---:|---:|---:|---|
| included | 3,790 | 10,047 | 0 | 0 | True |
| excluded_missing_geoid | 514 | 514 | 0 | 0 | True |
| excluded_outside_pinellas | 0 | 0 | 0 | 0 | True |
| excluded_other | 0 | 0 | 0 | 0 | True |
| ZIP-only total | 4,304 | 10,561 | 0 | 0 | True |

Excluded: 514 rows (11.94% of ZIP-only rows). Matches prior screening counts: {'zip_only': True, 'pinellas': True}.

Included policyCount values agree across downloaded, FEMA Pinellas and ZIP-only records: True.

Definitions: included rows are the FEMA Pinellas-filtered IDs. Among excluded rows, missing GEOID means null, empty or whitespace; outside Pinellas means a valid 12-digit GEOID with a county prefix other than 12103; other contains malformed/unexpected GEOIDs or valid Pinellas GEOIDs absent from the filtered query.

policyCount is accepted only as a finite positive integer (numeric strings allowed; booleans rejected). Null/blank values are missing; zero, negative, fractional, nonnumeric or nonfinite values are invalid. Sums omit missing/invalid values and are explicitly partial if flagged; unknowns are not silently counted as zero. Empty groups have zero rows and a zero sum.

These are effective-year policy record and reported policyCount totals, not unique properties, contracts, calendar-year exposure or validated claim-frequency denominators. Matching asOfDate labels do not guarantee an immutable database revision. Missing GEOIDs do not establish county membership.

Request failures and unresolved checks:
- None.

Both dashboards and all prior reports passed before/after SHA-256 checks. Raw downloaded pages, API responses, exact filters, attempts, classified records, count anomalies and hashes are saved alongside this report.
