# ZIP 33708: validation of the provisional 2024 non-condominium denominator

Checked (UTC): 2026-11-11T23:13:09.217345+00:00. **PROVISIONAL - no fully comparable independent benchmark verified**.

## Verdict

The saved inputs, recorded-duration arithmetic, source-date alignment and sensitivity calculations reproduce. The evidence does not establish an independently benchmarked unique-contract or unique-property exposure denominator. Keep the output labelled **provisional recorded-policy-duration exposure**. No claim rates are calculated.

## FEMA counting rules versus RiskMap assumptions

Primary documentation: [FEMA v3 data dictionary API](https://www.fema.gov/api/open/v1/OpenFemaDataSetFields?%24filter=openFemaDataSet+eq+%27NfipPolicies%27+and+datasetVersion+eq+3&%24top=200&%24count=true), saved as sources/nfip_policy_fields_v3.json; [FEMA dataset metadata](https://www.fema.gov/api/open/v1/OpenFemaDataSets?%24filter=name+eq+%27NfipPolicies%27&%24top=5), saved as sources/datasets.json; [FEMA NFIP data FAQ](https://agents.floodsmart.gov/flood-maps-and-data/faqs-about-nfip-data), read through the web reader on 2026-11-11.

| Topic | Confirmed by FEMA | What remains an assumption or unresolved |
|---|---|---|
| IDs | id identifies a record; the dataset describes policy transactions. | Unique IDs do not prove unique contracts, properties, or non-overlapping exposure. No shared public contract/property key permits a contract-level duplicate/overlap test. |
| Renewals | The FAQ states a renewal produces another record and gives effective <= observation date < termination for point-in-time selection. | Successive records should contribute their own recorded intervals; the public identifiers do not independently establish complete renewal chains or distinguish all transaction duplication. |
| Endorsements | endorsementEffectiveDate records when an endorsement takes effect. | The dictionary does not establish whether every endorsement is a separate v3 row, whether a row is a latest-state representation, or how changes to coverage/units should be integrated. A non-null endorsement date alone is not evidence of duplicate rows. |
| Cancellations | cancellationDateOfFloodPolicy marks going out of force; termination describes ending by cancellation or lapse. policyCount definition ties active status to cancellation or expiration. | Using min(termination, cancellation) is a conservative operational reconciliation, not an expressly documented resolution rule for inconsistent fields. A cancellation before effective date is not automatically proven to be a data error: voidance/cancel-rewrite history may matter. |
| policyCount | FEMA defines insured units in active status, with condominium contracts potentially representing multiple units. | It is not a unique-building count. Holding the reported weight constant over a row interval is an integration assumption; all 6,201 observed N rows have weight 1, so that weighting choice has no numerical effect here. N is not synonymous with single-family homes. |
| Source dates | asOfDate describes creation/last update in the source system. | Shared 2026-09-08 row dates support temporal consistency, not an immutable processing revision or final historical coverage. Dataset metadata modified/refresh dates differ and must not be treated as PIF dates. |
| Geography | reportedZipCode is partner-reported insured-property ZIP; censusGeoid is address-based block-group geography. | A missing GEOID is not proof of Pinellas membership. Keep it in a separate sensitivity. |
| Annual exposure | The FAQ supports point-in-time active-term selection. | Integrating rows into 366-day record-years and treating that as unique-contract exposure is RiskMap methodology, not a FEMA-certified annual denominator. Midnight timestamp defaults do not recover unreported real-world time-of-day details. |

## Specific-group reconciliation and sensitivities

All rows are code N, FL, ZIP 33708, at row asOfDate 2026-09-08T00:00:00.000Z. Earlier-term completeness was checked across all pre-2024 effective years; the retrieved candidates were all effective in 2023. Coverage is clipped to [2024-01-01, 2025-01-01), divided by 366 days. Main scenarios exclude cancellation-before-effective rows.

| Geography | Source rows | 2023 effective | 2024 effective | Positive overlap rows | No elapsed coverage | Flagged date rows |
|---|---:|---:|---:|---:|---:|---:|
| confirmed | 6191 | 3109 | 3082 | 6031 | 149 | 11 |
| missing_geoid | 10 | 8 | 2 | 10 | 0 | 0 |

| Scenario | Record-years | Insured-unit-years | Absolute change from confirmed | Percentage change |
|---|---:|---:|---:|---:|
| Confirmed; flagged dates excluded | 2,982.62841530 | 2,982.62841530 | +0.00000000 | +0.000000% |
| Confirmed + missing GEOIDs; flagged dates excluded | 2,985.75136612 | 2,985.75136612 | +3.12295082 | +0.104705% |
| Confirmed; ignore flagged cancellation dates | 2,985.67486339 | 2,985.67486339 | +3.04644809 | +0.102140% |
| Confirmed + missing GEOIDs; ignore flagged cancellation dates | 2,988.79781421 | 2,988.79781421 | +6.16939891 | +0.206844% |

The missing-GEOID effect here comes from **10 N rows** (8 effective in 2023 and 2 in 2024), not all 514 missing-GEOID records in the 2024 all-coverage audit. All have positive elapsed coverage and none has a flagged pre-effective cancellation. There are 11 flagged N date records, all in the confirmed scenario. Ignoring their cancellations is a separate hypothetical sensitivity, not a correction, confidence interval or verified upper bound. The combined scenario adds both geographic and flagged-date sensitivities.

Among confirmed N rows, 408 have cancellation dates, all differing from termination; 397 are not pre-effective exceptions. Omitting cancellation truncation while still excluding the 11 flagged rows would produce 3087.90710383 record-years, +105.27868852 (+3.529729%) above the main estimate. This diagnoses the consequence of a literal termination-only interpretation; it does not resolve which date is correct.

Non-null endorsement dates occur on 2849 confirmed and 6 missing-GEOID rows. No automatic deduplication was attempted using dates/GEOIDs, because unrelated properties can share those attributes. Exposure uncertainty from unobservable contract duplication or endorsement history remains unquantified.

All inspected N policyCount values are valid positive integers equal to 1; no missing/invalid count values or additional unparseable exposure dates were found in this saved scope. Known outside-county records remain excluded from both scenarios. The input-cohort verification is not partial; independent denominator validation remains incomplete.

## Independent policies-in-force benchmark search

Acceptance criteria: an independently produced NFIP PIF aggregate for the same observation date, ZIP 33708 with the same Pinellas restriction (or separately an explicitly comparable ZIP-only scope), code N, and an explicit record/contract/insured-unit counting definition. Source extraction dates and retrospective revisions must also be reconciled.

| Candidate inspected | Comparability and result |
|---|---|
| [Pinellas LMS 2023-2024 assessment, municipal-hosted PDF](https://cms5.revize.com/revize/stpete/LMS_Annual_Update%20_2024.pdf#page=148) | Saved locally and text inspected, especially PDF pages 147-155. Independently compiled jurisdiction/geocoded-community summaries use 2021-2023 observations and land-use classifications, not ZIP 33708/code N on an exact 2024 date. The PDF discusses community assignment and unmatched addresses. No defensible numerical comparison. |
| Local data/raw/MarketShareTsExternal.xlsx | Workbook headers identify a Florida OIR Pinellas market-share report for December 2025, all policy types, ordered by wind-covered direct premium. It is not a matched 2024 NFIP code-N ZIP benchmark; no comparison. |
| [FEMA single-family pricing tables](https://www.fema.gov/flood-insurance/work-with-nfip/risk-rating/single-family-home) | A single-family table is not all non-condominium coverage. The official page returned HTTP 403; no downloadable matching table/count/date could be verified. No benchmark number adopted. |
| [FEMA published-report portal](https://nfipservices.floodsmart.gov/reports-flood-insurance-data) and [Watermark](https://www.fema.gov/flood-insurance/work-with-nfip/watermark) | Access/redirect/reader failures prevented verification of a matching historic ZIP/type/date table. The legacy home/reports link redirects to the FAQ. This does not establish that such a report does not exist. |
| Public ZIP aggregators found during search | These describe their statistics as reconstructions from OpenFEMA and use other 2026 dates, all-coverages or single-family filters. They are not independent source validation or a matching 2024 N benchmark; no numbers imported. |

**No fully comparable independent benchmark was verified. No numerical external PIF comparison was performed.** There is therefore no point-in-time benchmark pass to report. A future PIF comparison must use effective <= t < termination with an explicit cancellation/flagged-record convention and separately report row and insured-unit counts. Even exact agreement at one date would validate only that stock count, not the full-year integral, transaction history or claim-count compatibility.

## What remains provisional and next verification

Confirmed: saved-input hashes, consistent row dates, earlier-term candidate counts, row ID uniqueness, clipping arithmetic, N weights of one, and quantified geographic/date sensitivities. Not confirmed: unique-contract continuity and overlap handling, endorsement representation, correct resolution of the 11 flagged cancellations and differing termination/cancellation fields, county membership of the 10 missing-GEOID N records, or an independently benchmarked stock/annual denominator.

Next: obtain a documented insurer/program-produced PIF extract for a specified 2024 date with ZIP 33708, code N, counting-unit and county definitions; reconcile that stock separately. Seek documented v3 endorsement/cancel-rewrite semantics before promoting the integrated denominator. Do not calculate additional claim rates.

## Reproducibility and evidence

Reused scripts/verify_saved_exposure.py and the saved 33708 audit/sensitivity inputs. This packet recomputes N duration and reproduces saved values within their eight-decimal rounding. Underlying source records were not re-downloaded. Official metadata was retrieved separately; no new policy cohort or claim-rate analysis was run.

Run: `.\.venv-pilot\Scripts\python.exe scripts/validate_noncondo_denominator_33708.py --output reports/noncondo_denominator_validation_33708_2024_2026-11-11` (refuses to overwrite a completed report).

The FAQ was accessible via web search/open, but direct Python retrieval encountered certificate verification failure; TLS verification was not disabled. The v3 landing page and single-family table page were blocked by HTTP 403. The county PDF downloaded successfully; web PDF screenshots failed with cache-miss, so no tabulated benchmark numbers were transcribed. sources/retrieval_log.json records direct-fetch failures. Official v3 metadata JSON, the county PDF, source hashes, specific exception records and calculations are saved alongside this single report.

Both dashboards and prior reports are unchanged. This is one new validation report with supporting evidence.
