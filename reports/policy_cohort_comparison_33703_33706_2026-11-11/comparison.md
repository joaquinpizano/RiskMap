# ZIP 33703 vs 33706 policy cohort audit

Audit started (UTC): 2026-11-11T21:18:06.616548+00:00

33703 was selected because its 3,207 local 2024 claim records rank second among Pinellas-linked ZIPs, after 33706 (4,060). It is the largest available comparison by claim count.

Scope: Florida, reported ZIP, policy effective date >= January 1 of the cohort year and < January 1 of the next year; Pinellas filter is startswith(censusGeoid,'12103'). Counts are policy records, not policyCount sums, unique properties or calendar-year exposure.

33703 uses newly downloaded pages and separate verification queries. 33706 uses the prior successful audit responses, copied here after hash validation, plus revalidated cached cohorts.

| ZIP | Effective year | Downloaded | API Pinellas | ZIP-only | Missing GEOID | Missing share | Outside Pinellas | Invalid GEOID | IDs reconcile |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 33703 | 2023 | 5618 | 5618 | 5647 | 29 | 0.51% | 0 | 0 | yes |
| 33706 | 2023 | 4920 | 4920 | 4936 | 16 | 0.32% | 0 | 0 | yes |
| 33703 | 2024 | 5711 | 5711 | 6059 | 348 | 5.74% | 0 | 0 | yes |
| 33706 | 2024 | 4915 | 4915 | 5514 | 599 | 10.86% | 0 | 0 | yes |

Missing means null, empty or whitespace GEOID; outside Pinellas means a valid 12-digit GEOID with another county prefix. Malformed nonempty values remain separately unresolved.

Snapshot dates (row asOfDate, not request time):
- ZIP 33706, 2023: {"api_pinellas": {"2026-09-08T00:00:00.000Z": 4920}, "api_zip_only": {"2026-09-08T00:00:00.000Z": 4936}, "local": {"2026-09-08T00:00:00.000Z": 4920}}
- ZIP 33706, 2024: {"api_pinellas": {"2026-09-08T00:00:00.000Z": 4915}, "api_zip_only": {"2026-09-08T00:00:00.000Z": 5514}, "local": {"2026-09-08T00:00:00.000Z": 4915}}
- ZIP 33703, 2023: {"api_pinellas": {"2026-09-08T00:00:00.000Z": 5618}, "api_zip_only": {"2026-09-08T00:00:00.000Z": 5647}, "local": {"2026-09-08T00:00:00.000Z": 5618}}
- ZIP 33703, 2024: {"api_pinellas": {"2026-09-08T00:00:00.000Z": 5711}, "api_zip_only": {"2026-09-08T00:00:00.000Z": 6059}, "local": {"2026-09-08T00:00:00.000Z": 5711}}

2023: snapshots match; 33703 minus 33706 missing-GEOID share is +0.19 percentage points.

2024: snapshots match; 33703 minus 33706 missing-GEOID share is -5.12 percentage points.

**Recommendation:** A staged rollout of this ingestion/geography audit is justified, with ZIP/year snapshot and ID gates. A broader exposure or claims-rate rollout is not justified: two selected ZIPs do not establish county coverage or representative missingness, and null GEOIDs do not establish county membership.

Matching asOfDate labels do not prove an immutable source revision. This is a same-source OpenFEMA reconciliation, not independent validation of insurance coverage, contract semantics or claim frequency.

Request failures and unresolved checks:
- Download request attempt 1: TimeoutError: The read operation timed out (https://www.fema.gov/api/open/v3/NfipPolicies?%24filter=propertyState+eq+%27FL%27+and+startswith%28censusGeoid%2C%2712103%27%29+and+policyEffectiveDate+ge+%272023-01-01%27+and+policyEffectiveDate+lt+%272024-01-01%27+and+reportedZipCode+eq+%2733703%27&%24select=id%2CpropertyState%2CreportedZipCode%2CcensusGeoid%2CpolicyEffectiveDate%2CpolicyTerminationDate%2CcancellationDateOfFloodPolicy%2CpolicyCount%2CcondominiumCoverageTypeCode%2CasOfDate%2CendorsementEffectiveDate%2CpolicyTermIndicator&%24orderby=id&%24top=1&%24count=true)

Preservation: both dashboards and all 40 protected pre-existing files passed SHA-256 checks. Full API responses, downloaded pages, ID differences, classified extra records, request URLs and hashes are retained in this folder and evidence.json.
