# 2024 Pinellas-linked ZIP policy filter screening

Started (UTC): 2026-11-11T21:30:53.860456+00:00. Target source snapshot: 2026-09-08T00:00:00.000Z.

Universe: all 59 HUD Pinellas-linked ZIPs present in the local claims data in any loss year. Reused full audits for 33703/33706; queried 57 remaining ZIPs. ZIPs without 2024 claims are retained.

Method: count queries only, with FL, reported ZIP and policyEffectiveDate >= 2024-01-01 and < 2025-01-01; the second scope adds startswith(censusGeoid,'12103'). Each request returns at most one asOfDate and no IDs/GEOIDs. For each scope, a second count tests (asOfDate ne target OR asOfDate eq null). Zero exceptions plus a matching sample verifies the target date under API filter semantics. Empty scopes have no date to verify. Requests retry once. No full policy downloads or new GEOID classification queries were made.

Excluded = ZIP-only minus Pinellas-filtered count; percentage = excluded / ZIP-only × 100. Zero ZIP-only totals have undefined percentages. New gaps are **unclassified**: counts alone cannot distinguish missing GEOIDs from valid outside-county GEOIDs or malformed values. Prior full-audit gaps retain their verified missing-GEOID label.

Ranks are descriptive count differences; flagged snapshot/API results must not be interpreted as comparable coverage. Row asOfDate checks do not guarantee an immutable source revision, correct county assignment or policy/claim unit compatibility.

## Ranked by excluded count

| Count rank | % rank | ZIP | ZIP-only | Pinellas | Excluded | Excluded % | 2024 claims | Classification | Snapshot status |
|---:|---:|---|---:|---:|---:|---:|---:|---|---|
| 1 | 6 | 33706 | 5514 | 4915 | 599 | 10.86% | 4060 | verified missing GEOID | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 2 | 4 | 33708 | 4304 | 3790 | 514 | 11.94% | 3048 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 3 | 9 | 33702 | 6343 | 5938 | 405 | 6.38% | 2070 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 4 | 5 | 33707 | 3397 | 3003 | 394 | 11.60% | 1617 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 5 | 12 | 33703 | 6059 | 5711 | 348 | 5.74% | 3207 | verified missing GEOID | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 6 | 7 | 34698 | 2721 | 2499 | 222 | 8.16% | 816 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 7 | 3 | 33716 | 1475 | 1295 | 180 | 12.20% | 178 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 8 | 11 | 33785 | 2353 | 2216 | 137 | 5.82% | 1549 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 9 | 10 | 33767 | 1853 | 1744 | 109 | 5.88% | 1182 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 10 | 15 | 34683 | 2364 | 2255 | 109 | 4.61% | 726 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 11 | 14 | 33711 | 1864 | 1773 | 91 | 4.88% | 567 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 12 | 22 | 33705 | 2852 | 2761 | 91 | 3.19% | 756 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 13 | 18 | 33704 | 2071 | 1999 | 72 | 3.48% | 879 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 14 | 17 | 33764 | 1499 | 1444 | 55 | 3.67% | 366 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 15 | 8 | 33786 | 757 | 705 | 52 | 6.87% | 468 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 16 | 23 | 33762 | 1194 | 1157 | 37 | 3.10% | 542 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 17 | 16 | 33759 | 677 | 647 | 30 | 4.43% | 76 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 18 | 20 | 33772 | 911 | 881 | 30 | 3.29% | 170 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 19 | 27 | 33709 | 1117 | 1089 | 28 | 2.51% | 174 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 20 | 31 | 33710 | 2128 | 2102 | 26 | 1.22% | 346 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 21 | 19 | 33770 | 753 | 728 | 25 | 3.32% | 263 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 22 | 33 | 33715 | 2174 | 2151 | 23 | 1.06% | 300 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 23 | 32 | 33777 | 2013 | 1991 | 22 | 1.09% | 217 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 24 | 13 | 34681 | 419 | 398 | 21 | 5.01% | 219 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 25 | 28 | 33760 | 1103 | 1082 | 21 | 1.90% | 74 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 26 | 21 | 33755 | 617 | 597 | 20 | 3.24% | 98 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 27 | 24 | 33771 | 647 | 628 | 19 | 2.94% | 135 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 28 | 26 | 33701 | 619 | 603 | 16 | 2.58% | 89 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 29 | 29 | 33756 | 937 | 923 | 14 | 1.49% | 153 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 30 | 30 | 33774 | 779 | 768 | 11 | 1.41% | 104 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 31 | 25 | 33714 | 343 | 333 | 10 | 2.92% | 26 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 32 | 34 | 33712 | 915 | 907 | 8 | 0.87% | 85 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 33 | 35 | 34695 | 1007 | 1000 | 7 | 0.70% | 59 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 34 | 36 | 33776 | 1140 | 1133 | 7 | 0.61% | 111 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 35 | 38 | 33782 | 1392 | 1385 | 7 | 0.50% | 173 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 36 | 39 | 33781 | 1338 | 1332 | 6 | 0.45% | 65 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 37 | 2 | 34660 | 15 | 12 | 3 | 20.00% | 6 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 38 | 37 | 34688 | 577 | 574 | 3 | 0.52% | 12 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 39 | 40 | 33713 | 460 | 458 | 2 | 0.43% | 13 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 40 | 42 | 33773 | 1131 | 1129 | 2 | 0.18% | 39 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 41 | 1 | 33742 | 1 | 0 | 1 | 100.00% | 0 | unclassified | zip_only: verified target snapshot; pinellas: empty cohort; no snapshot date |
| 42 | 41 | 33763 | 359 | 358 | 1 | 0.28% | 9 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 43 | 43 | 34684 | 964 | 963 | 1 | 0.10% | 17 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 44 | 44 | 34685 | 1770 | 1769 | 1 | 0.06% | 21 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 45 | N/A | 33731 | 0 | 0 | 0 | N/A | 0 | unclassified | zip_only: empty cohort; no snapshot date; pinellas: empty cohort; no snapshot date |
| 46 | 45 | 33733 | 4 | 4 | 0 | 0.00% | 0 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 47 | N/A | 33736 | 0 | 0 | 0 | N/A | 0 | unclassified | zip_only: empty cohort; no snapshot date; pinellas: empty cohort; no snapshot date |
| 48 | N/A | 33738 | 0 | 0 | 0 | N/A | 0 | unclassified | zip_only: empty cohort; no snapshot date; pinellas: empty cohort; no snapshot date |
| 49 | N/A | 33741 | 0 | 0 | 0 | N/A | 0 | unclassified | zip_only: empty cohort; no snapshot date; pinellas: empty cohort; no snapshot date |
| 50 | N/A | 33744 | 0 | 0 | 0 | N/A | 0 | unclassified | zip_only: empty cohort; no snapshot date; pinellas: empty cohort; no snapshot date |
| 51 | N/A | 33757 | 0 | 0 | 0 | N/A | 0 | unclassified | zip_only: empty cohort; no snapshot date; pinellas: empty cohort; no snapshot date |
| 52 | N/A | 33758 | 0 | 0 | 0 | N/A | 0 | unclassified | zip_only: empty cohort; no snapshot date; pinellas: empty cohort; no snapshot date |
| 53 | 46 | 33761 | 392 | 392 | 0 | 0.00% | 8 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 54 | 47 | 33765 | 260 | 260 | 0 | 0.00% | 13 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 55 | 48 | 33778 | 235 | 235 | 0 | 0.00% | 15 | unclassified | zip_only: verified target snapshot; pinellas: verified target snapshot |
| 56 | N/A | 34682 | 0 | 0 | 0 | N/A | 0 | unclassified | zip_only: empty cohort; no snapshot date; pinellas: empty cohort; no snapshot date |
| 57 | N/A | 34697 | 0 | 0 | 0 | N/A | 0 | unclassified | zip_only: empty cohort; no snapshot date; pinellas: empty cohort; no snapshot date |
| N/A | N/A | 34677 | unavailable | 4151 | unavailable | N/A | 494 | unclassified | zip_only: unverified; pinellas: verified target snapshot |
| N/A | N/A | 34689 | unavailable | 2700 | unavailable | N/A | 746 | unclassified | zip_only: unverified; pinellas: verified target snapshot |

## Ranked by excluded percentage

| % rank | ZIP | Excluded % | Excluded count | Comparable snapshot/count checks |
|---:|---|---:|---:|---|
| 1 | 33742 | 100.00% | 1 | True |
| 2 | 34660 | 20.00% | 3 | True |
| 3 | 33716 | 12.20% | 180 | True |
| 4 | 33708 | 11.94% | 514 | True |
| 5 | 33707 | 11.60% | 394 | True |
| 6 | 33706 | 10.86% | 599 | True |
| 7 | 34698 | 8.16% | 222 | True |
| 8 | 33786 | 6.87% | 52 | True |
| 9 | 33702 | 6.38% | 405 | True |
| 10 | 33767 | 5.88% | 109 | True |
| 11 | 33785 | 5.82% | 137 | True |
| 12 | 33703 | 5.74% | 348 | True |
| 13 | 34681 | 5.01% | 21 | True |
| 14 | 33711 | 4.88% | 91 | True |
| 15 | 34683 | 4.61% | 109 | True |
| 16 | 33759 | 4.43% | 30 | True |
| 17 | 33764 | 3.67% | 55 | True |
| 18 | 33704 | 3.48% | 72 | True |
| 19 | 33770 | 3.32% | 25 | True |
| 20 | 33772 | 3.29% | 30 | True |
| 21 | 33755 | 3.24% | 20 | True |
| 22 | 33705 | 3.19% | 91 | True |
| 23 | 33762 | 3.10% | 37 | True |
| 24 | 33771 | 2.94% | 19 | True |
| 25 | 33714 | 2.92% | 10 | True |
| 26 | 33701 | 2.58% | 16 | True |
| 27 | 33709 | 2.51% | 28 | True |
| 28 | 33760 | 1.90% | 21 | True |
| 29 | 33756 | 1.49% | 14 | True |
| 30 | 33774 | 1.41% | 11 | True |
| 31 | 33710 | 1.22% | 26 | True |
| 32 | 33777 | 1.09% | 22 | True |
| 33 | 33715 | 1.06% | 23 | True |
| 34 | 33712 | 0.87% | 8 | True |
| 35 | 34695 | 0.70% | 7 | True |
| 36 | 33776 | 0.61% | 7 | True |
| 37 | 34688 | 0.52% | 3 | True |
| 38 | 33782 | 0.50% | 7 | True |
| 39 | 33781 | 0.45% | 6 | True |
| 40 | 33713 | 0.43% | 2 | True |
| 41 | 33763 | 0.28% | 1 | True |
| 42 | 33773 | 0.18% | 2 | True |
| 43 | 34684 | 0.10% | 1 | True |
| 44 | 34685 | 0.06% | 1 | True |
| 45 | 33733 | 0.00% | 0 | True |
| 46 | 33761 | 0.00% | 0 | True |
| 47 | 33765 | 0.00% | 0 | True |
| 48 | 33778 | 0.00% | 0 | True |

## Recommended full audits

Select the largest absolute gap, the highest relative gap, then the next largest absolute gap among new ZIPs with verified comparable snapshots and at least 100 local 2024 claim records. This is a workload prioritization rule, not a risk score.
- **33708**: 514 unclassified excluded records (11.94%); 3,048 local 2024 claims.
- **33716**: 180 unclassified excluded records (12.20%); 178 local 2024 claims.
- **33702**: 405 unclassified excluded records (6.38%); 2,070 local 2024 claims.

Next step: run full ID and GEOID reconciliation only for these candidates, including investigation of county assignment. Stop screening here; no full audits have been initiated.

## Flags and request failures

- ZIP 34677: unavailable; {'zip_only': 'unverified', 'pinellas': 'verified target snapshot'}
- ZIP 34689: unavailable; {'zip_only': 'unverified', 'pinellas': 'verified target snapshot'}
- ZIP 33731: empty scope has no row snapshot date to verify ({'zip_only': 'empty cohort; no snapshot date', 'pinellas': 'empty cohort; no snapshot date'}); zero ZIP-only totals have no defined exclusion percentage.
- ZIP 33736: empty scope has no row snapshot date to verify ({'zip_only': 'empty cohort; no snapshot date', 'pinellas': 'empty cohort; no snapshot date'}); zero ZIP-only totals have no defined exclusion percentage.
- ZIP 33738: empty scope has no row snapshot date to verify ({'zip_only': 'empty cohort; no snapshot date', 'pinellas': 'empty cohort; no snapshot date'}); zero ZIP-only totals have no defined exclusion percentage.
- ZIP 33741: empty scope has no row snapshot date to verify ({'zip_only': 'empty cohort; no snapshot date', 'pinellas': 'empty cohort; no snapshot date'}); zero ZIP-only totals have no defined exclusion percentage.
- ZIP 33742: empty scope has no row snapshot date to verify ({'zip_only': 'verified target snapshot', 'pinellas': 'empty cohort; no snapshot date'}); zero ZIP-only totals have no defined exclusion percentage.
- ZIP 33744: empty scope has no row snapshot date to verify ({'zip_only': 'empty cohort; no snapshot date', 'pinellas': 'empty cohort; no snapshot date'}); zero ZIP-only totals have no defined exclusion percentage.
- ZIP 33757: empty scope has no row snapshot date to verify ({'zip_only': 'empty cohort; no snapshot date', 'pinellas': 'empty cohort; no snapshot date'}); zero ZIP-only totals have no defined exclusion percentage.
- ZIP 33758: empty scope has no row snapshot date to verify ({'zip_only': 'empty cohort; no snapshot date', 'pinellas': 'empty cohort; no snapshot date'}); zero ZIP-only totals have no defined exclusion percentage.
- ZIP 34682: empty scope has no row snapshot date to verify ({'zip_only': 'empty cohort; no snapshot date', 'pinellas': 'empty cohort; no snapshot date'}); zero ZIP-only totals have no defined exclusion percentage.
- ZIP 34697: empty scope has no row snapshot date to verify ({'zip_only': 'empty cohort; no snapshot date', 'pinellas': 'empty cohort; no snapshot date'}); zero ZIP-only totals have no defined exclusion percentage.
- ZIP 33710 zip_only, attempt 1: TimeoutError: The read operation timed out; final status verified_count.
- ZIP 33711 zip_only, attempt 1: TimeoutError: The read operation timed out; final status verified_count.
- ZIP 33708 zip_only, attempt 1: TimeoutError: The read operation timed out; final status verified_count.
- ZIP 33715 zip_only, attempt 1: TimeoutError: The read operation timed out; final status verified_count.
- ZIP 33760 zip_only, attempt 1: TimeoutError: The read operation timed out; final status verified_count.
- ZIP 33762 zip_only, attempt 1: TimeoutError: The read operation timed out; final status verified_count.
- ZIP 33764 zip_only, attempt 1: TimeoutError: The read operation timed out; final status verified_count.
- ZIP 33767 zip_only, attempt 1: TimeoutError: The read operation timed out; final status verified_count.
- ZIP 33773 zip_only, attempt 1: TimeoutError: The read operation timed out; final status verified_count.
- ZIP 33777 zip_only, attempt 1: TimeoutError: The read operation timed out; final status verified_count.
- ZIP 33785 zip_only, attempt 1: TimeoutError: The read operation timed out; final status verified_count.
- ZIP 34683 zip_only, attempt 1: TimeoutError: The read operation timed out; final status verified_count.
- ZIP 34677 zip_only, attempt 1: TimeoutError: The read operation timed out; final status unavailable.
- ZIP 34677 zip_only, attempt 2: TimeoutError: The read operation timed out; final status unavailable.
- ZIP 34698 zip_only, attempt 1: TimeoutError: The read operation timed out; final status verified_count.
- ZIP 34689 zip_only, attempt 1: TimeoutError: The read operation timed out; final status unavailable.
- ZIP 34689 zip_only, attempt 2: TimeoutError: The read operation timed out; final status unavailable.

FEMA URI-escapes time colons in metadata.filter. Saved responses were validated after decoding that metadata; no new requests were needed.

Both dashboards and all prior reports passed SHA-256 preservation checks. Raw count responses, exact filters, request attempts, ranks and source hashes are saved in this folder. No claim frequencies or exposure measures were calculated.
