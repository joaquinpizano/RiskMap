# Policy cohort count audit

ZIP 33706, Florida; effective-year cohorts, not calendar-year exposure or unique properties.
Audit retrieval (UTC): 2026-11-11T20:57:35.402372+00:00
[OpenFEMA source endpoint](https://www.fema.gov/api/open/v3/NfipPolicies). Exact filters, successful response bodies, metadata and SHA-256 hashes are saved alongside this report; failed requests retain their error details.

| Effective year | Local Pinellas rows | API Pinellas rows | API ZIP-only rows | Snapshot comparison |
|---|---:|---:|---:|---|
| 2023 | 4,920 | 4920 | 4936 | same single asOfDate |
| 2024 | 4,915 | 4915 | 5514 | same single asOfDate |

- 2023: ZIP-only includes 16 null, 0 blank and 0 other-prefix GEOIDs; Pinellas subset IDs match the separate query.
- 2023: local snapshots {'2026-09-08T00:00:00.000Z': 4920}; API Pinellas {'2026-09-08T00:00:00.000Z': 4920}; API ZIP-only {'2026-09-08T00:00:00.000Z': 4936}. Pinellas comparison: {'status': 'same_as_of_date', 'count_delta': 0, 'local_ids_absent_remotely': 0, 'remote_ids_absent_locally': 0}.
- 2024: ZIP-only includes 599 null, 0 blank and 0 other-prefix GEOIDs; Pinellas subset IDs match the separate query.
- 2024: local snapshots {'2026-09-08T00:00:00.000Z': 4915}; API Pinellas {'2026-09-08T00:00:00.000Z': 4915}; API ZIP-only {'2026-09-08T00:00:00.000Z': 5514}. Pinellas comparison: {'status': 'same_as_of_date', 'count_delta': 0, 'local_ids_absent_remotely': 0, 'remote_ids_absent_locally': 0}.

**Decision:** Supports one additional ZIP as a bounded ingestion/geography test; not validated exposure or claim frequency.

The prior geography report claims ZIP-only counts of 4,936 (2023) and 5,514 (2024), with 16 and 599 null GEOIDs. Those are historical narrative claims; this audit independently rechecks available API data rather than treating the narrative as a saved API response.

Remaining limits: matching row asOfDate values do not prove an immutable database revision. This checks the same OpenFEMA source, not an independent coverage-in-force benchmark. Null GEOIDs do not establish county membership; correct county assignment, contract/renewal semantics, calendar-year exposure and claim frequency remain unresolved. No differences are attributed to missing downloads when API evidence or source snapshots do not support that conclusion.

Both dashboards, all pre-existing reports and both cached cohorts passed before/after SHA-256 preservation checks.
