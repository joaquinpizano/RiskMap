# Addendum: ZIP 33708 non-condominium cancellation/termination difference

This traces the saved confirmed-Pinellas, code-N comparison only. Missing-GEOID records are outside both scenarios here. The same 11 cancellation-before-effective records are excluded from both; this is not the separate sensitivity that ignores their cancellations.

**293 records account for exactly 38,532 record-days / 366 = 105.27868852 record-years**, reported as 105.2787. Baseline: 2982.62841530; termination-only: 3087.90710383. All weights equal one, so the insured-unit-year difference is identical. Every input row has asOfDate 2026-09-08T00:00:00.000Z.

The added interval for each non-flagged row is the part of [max(effective, cancellation, 2024-01-01), min(termination, 2025-01-01)) retained by termination-only selection after cancellation truncation. The ledger calculates both scenario durations separately; negative/empty intervals contribute zero.

| Effective cohort | Cancellation timing | Rows | Contributing rows | Added record-days | Added record-years |
|---|---|---:|---:|---:|---:|
| 2023 | After effective, before 2024 | 50 | 50 | 5,781 | 15.79508197 |
| 2023 | After effective, during 2024 | 65 | 65 | 6,658 | 18.19125683 |
| 2023 | At effective date | 54 | 54 | 9,809 | 26.80054645 |
| 2023 | Before effective date; excluded from both | 3 | 0 | 0 | 0.00000000 |
| 2023 | No cancellation | 2937 | 0 | 0 | 0.00000000 |
| 2024 | After effective, during 2024 | 79 | 79 | 8,239 | 22.51092896 |
| 2024 | After effective, on/after 2025 start | 104 | 0 | 0 | 0.00000000 |
| 2024 | At effective date | 45 | 45 | 8,045 | 21.98087432 |
| 2024 | Before effective date; excluded from both | 8 | 0 | 0 | 0.00000000 |
| 2024 | No cancellation | 2846 | 0 | 0 | 0.00000000 |
| **2023 subtotal** | | **3109** | **169** | **22,248** | **60.78688525** |
| **2024 subtotal** | | **3082** | **124** | **16,284** | **44.49180328** |
| **Total** | | **6191** | **293** | **38,532** | **105.27868852** |

The five positive cells above reconcile without rounding residual at the second/day level. There are no cancellations exactly at 2024-01-01 after an earlier effective date. All 408 recorded cancellations precede their termination dates.

## Documentation support versus unresolved coverage

The [FEMA v3 field definitions](../noncondo_denominator_validation_33708_2024_2026-11-11/sources/nfip_policy_fields_v3.json) already collected define cancellation as going out of force, termination as ending through cancellation or lapse, and policyCount as insured units in active status. The [collected FEMA FAQ reference](https://agents.floodsmart.gov/flood-maps-and-data/faqs-about-nfip-data) uses effective <= observation date < termination for point-in-time selection.

- **99 same-effective-date cancellations** (54 from 2023; 45 from 2024): applying the documented cancellation meaning yields a zero-length recorded coverage interval. Termination-only retains 17,854 days (48.78142077 years). This supports excluding those intervals under the cancellation convention, but does not prove the cancellation date is correct or that the records represent a specific voidance/rewrite reason.
- **50 later cancellations before 2024**, all effective in 2023: cancellation-based coverage ends before the study year; termination-only retains 5,781 days (15.79508197 years).
- **144 later cancellations during 2024** (65 from 2023; 79 from 2024): the cancellation field supports truncating coverage there; termination-only retains another 14,897 days (40.70218579 years).
- **104 cancellations on/after 2025-01-01**, all effective in 2024: both conventions retain the same 2024 duration. Their field disagreements have no effect on this particular annual comparison.
- **11 cancellations before effective** (3 from 2023; 8 from 2024): chronology/coverage remains unresolved. Both compared scenarios exclude them, so they explain **zero** of the 105.2787-year difference. Their separate hypothetical uncancelled contribution is 3.04644809 record-years, already reported elsewhere.

**Documentation support is not record-level validation.** Every one of the 293 contributors has a cancellation date earlier than a different termination date, even though both fields describe ending coverage. Thus the documented cancellation meaning supports the baseline operation, while a literal FAQ termination-only selection produces the reported alternative. The collected documentation does not specify a conflict-resolution hierarchy or certify actual coverage for these records. All 293 contributors retain this ambiguity; there is no subset independently verified as actual coverage to termination. Endorsement dates alone do not resolve duplicate, cancel/rewrite, voidance or renewal history; cancellation reason and shared contract/property keys were not collected. No reason code is inferred from timing alone.

## Exact record identification and reproducibility

[contributors.csv](contributors.csv) identifies every one of the 293 contributing IDs, effective-year cohort, timing bucket, effective/cancellation/termination dates, source file, both scenario durations, exact added seconds/days and record-year contribution. [all_cancellation_records.csv](all_cancellation_records.csv) additionally includes the 104 zero-effect and 11 excluded exceptions, for 408 cancellation records. The remaining 5,783 confirmed N rows have no cancellation and contribute zero difference.

Source hashes and the exact reconciliation are in evidence.json. The existing exposure verifier was rerun. No live API requests, new coverage assumptions, claim rates or edits to dashboards/prior reports were made. Retain the denominator as provisional pending a documented resolution of conflicting dates and an independent benchmark.
