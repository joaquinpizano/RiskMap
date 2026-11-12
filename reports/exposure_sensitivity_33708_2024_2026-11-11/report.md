# ZIP 33708 provisional calendar-year 2024 exposure sensitivity

Status: **PROVISIONAL - overlapping candidate cohorts verified at target snapshot**. Retrieved (UTC): 2026-11-11T21:53:47.273608+00:00.

Rules reused from ZIP 33706: clip each recorded policy term to [2024-01-01, 2025-01-01), divide elapsed seconds by 366 days, truncate at recorded cancellation, exclude cancellations before effective date as unresolved date exceptions. Insured-unit-years weight elapsed duration by positive integral policyCount. No claim rates are calculated.

Scenario 1 includes valid Pinellas-prefix GEOIDs only. Scenario 2 adds missing-GEOID rows as a sensitivity scenario. Known out-of-county and malformed GEOIDs remain outside both.

Reused 3,790 audited 2024 confirmed rows; retrieved 514 missing-GEOID 2024 rows and 3,849 earlier-term candidates. Earlier effective-year distribution: {'2023': 3849}.
The earlier query has no lower effective-year limit: it selects all pre-2024 terms ending after 2024 begins (or missing termination), without filtering cancellation dates, so flagged cancellations remain visible. Policies ending by 2024-01-01 cannot contribute under these rules and were not downloaded.

Target snapshot: 2026-09-08T00:00:00.000Z. New response row dates: [("propertyState eq 'FL' and reportedZipCode eq '33708' and policyEffectiveDate lt '2024-01-01' and (policyTerminationDate gt '2024-01-01' or policyTerminationDate eq null)", {'2026-09-08T00:00:00.000Z': 3849}), ("propertyState eq 'FL' and reportedZipCode eq '33708' and policyEffectiveDate ge '2024-01-01' and policyEffectiveDate lt '2025-01-01' and (censusGeoid eq null or censusGeoid eq '')", {'2026-09-08T00:00:00.000Z': 514}), ("propertyState eq 'FL' and reportedZipCode eq '33708' and policyEffectiveDate eq null", {}), ("propertyState eq 'FL' and reportedZipCode eq '33708' and policyEffectiveDate lt '2024-01-01' and (policyTerminationDate gt '2024-01-01' or policyTerminationDate eq null)", {'2026-09-08T00:00:00.000Z': 1})].
Earlier candidate first/final counts agree: True; 2024 missing IDs match the prior audit: True.

| Coverage | Confirmed record-years | Plus missing record-years | Change | Change % | Confirmed insured-unit-years | Plus missing insured-unit-years | Change | Change % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A — Condominium association | 260.7213 | 260.7213 | +0.0000 | +0.00% | 6,176.4945 | 6,176.4945 | +0.0000 | +0.00% |
| H — RCBAP high-rise master policy | 1.0000 | 1.0000 | +0.0000 | +0.00% | 47.0000 | 47.0000 | +0.0000 | +0.00% |
| L — RCBAP low-rise master policy | 0.0000 | 33.1011 | +33.1011 | N/A (zero baseline) | 0.0000 | 33.1011 | +33.1011 | N/A (zero baseline) |
| N — Not a condominium | 2,982.6284 | 2,985.7514 | +3.1230 | +0.10% | 2,982.6284 | 2,985.7514 | +3.1230 | +0.10% |
| U — Individual condominium unit | 423.7705 | 423.7705 | +0.0000 | +0.00% | 423.7705 | 423.7705 | +0.0000 | +0.00% |

Coverage types remain separate; totals must not be interpreted as unique properties.

## Date exceptions and cancellation sensitivity

| Coverage | Confirmed flagged records | Plus missing flagged records | Additional record-years if flagged cancellations ignored (confirmed / plus missing) | Additional insured-unit-years (confirmed / plus missing) |
|---|---:|---:|---|---|
| A | 4 | 4 | 1.32786885 / 1.32786885 | 43.64480874 / 43.64480874 |
| H | 0 | 0 | 0.00000000 / 0.00000000 | 0.00000000 / 0.00000000 |
| L | 0 | 0 | 0.00000000 / 0.00000000 | 0.00000000 / 0.00000000 |
| N | 11 | 11 | 3.04644809 / 3.04644809 | 3.04644809 / 3.04644809 |
| U | 3 | 3 | 0.81147541 / 0.81147541 | 0.81147541 / 0.81147541 |

Flagged cancellations remain unresolved; ignoring them is a separate hypothetical sensitivity, not a correction or a proven bound. Their duration is excluded from the main comparison.

Record reconciliations: confirmed {'overlapping_records': 7410, 'no_elapsed_coverage': 193, 'date_exceptions': 18}; plus missing {'overlapping_records': 7930, 'no_elapsed_coverage': 205, 'date_exceptions': 18}.
Known outside-Pinellas rows excluded: 0; other GEOID rows excluded: 0.

## Unresolved issues

- No cohort/date-validity/snapshot gaps identified beyond the flagged cancellation exceptions above.

All figures remain provisional. Source asOfDate equality and count stability do not prove an immutable database revision or independent coverage completeness. Missing-GEOID records are not established as Pinellas properties. No claims rates, premiums or property-risk estimates were produced.

Both dashboards and all prior reports passed SHA-256 preservation checks. Exact filters, raw responses, source hashes, record-level issues and scenario reconciliations are retained in evidence.json and responses/.
