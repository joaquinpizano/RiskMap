"""Saved-input validation packet for ZIP 33708 non-condominium exposure.

Offline calculations; official documentation captured separately in sources/.
Does not certify an independently benchmarked denominator or calculate rates.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path

from audit_policy_cohorts import digest
from calculate_provisional_exposure import analyze, overlap_seconds, parse_date
from verify_saved_exposure import require, verify_33708

FAQ = 'https://agents.floodsmart.gov/flood-maps-and-data/faqs-about-nfip-data'
DICT = ('https://www.fema.gov/api/open/v1/OpenFemaDataSetFields?'
        '%24filter=openFemaDataSet+eq+%27NfipPolicies%27+and+datasetVersion+eq+3&%24top=200&%24count=true')
COUNTY = 'https://cms5.revize.com/revize/stpete/LMS_Annual_Update%20_2024.pdf'


def duration(rows, ignore_flagged=False, term_only=False):
    seconds = Decimal(0)
    for r in rows:
        start, end = parse_date(r['policyEffectiveDate']), parse_date(r['policyTerminationDate'])
        cancel = parse_date(r['cancellationDateOfFloodPolicy']) if r.get('cancellationDateOfFloodPolicy') else None
        if cancel and cancel < start:
            if not ignore_flagged:
                continue
            cancel = None
        stop = end if term_only or cancel is None else min(end, cancel)
        seconds += Decimal(str(overlap_seconds(start, stop, 2024)))
    return seconds / Decimal(366 * 86400)


def run(root, output):
    require(not (output / 'report.md').exists(), 'Report already exists; preserve completed evidence')
    verify_33708(root)
    folder = root / 'reports/exposure_sensitivity_33708_2024_2026-11-11'
    source = json.loads((folder / 'evidence.json').read_text())
    prior_folder = (root / source['prior_audit']['path']).parent
    all_rows = [r for p in sorted((prior_folder / 'downloaded/2024').glob('page_*.json'))
                for r in json.loads(p.read_text())['records']]
    for q in source['requests']:
        for attempt in q['attempts']:
            if 'path' not in attempt or 'error' in attempt:
                continue
            data = json.loads((folder / attempt['path']).read_text())
            if data['metadata']['top'] == 10000:
                all_rows.extend(data['NfipPolicies'])
    rows = [r for r in all_rows if r['condominiumCoverageTypeCode'] == 'N']
    require(len({r['id'] for r in rows}) == len(rows), 'Duplicate non-condominium IDs')
    require(all(r['asOfDate'] == source['target_snapshot'] for r in rows), 'Source date mismatch')
    confirmed = [r for r in rows if str(r.get('censusGeoid') or '').startswith('12103')]
    missing = [r for r in rows if r.get('censusGeoid') is None or not str(r['censusGeoid']).strip()]
    require(len(confirmed) + len(missing) == len(rows), 'Unexpected other-county/GEOID rows')
    require(all(r['policyCount'] == 1 and not isinstance(r['policyCount'], bool) for r in rows),
            'Non-unit policyCount requires separate weighted calculation')
    fields_path = output / 'sources/nfip_policy_fields_v3.json'
    dictionary = json.loads(fields_path.read_text())
    require(len(dictionary['OpenFemaDataSetFields']) == dictionary['metadata']['count'], 'Incomplete data dictionary')
    fields = {r['name']:r for r in dictionary['OpenFemaDataSetFields']}
    require(all(r['openFemaDataSet'] == 'NfipPolicies' and r['datasetVersion'] == 3 for r in fields.values()),
            'Incorrect data dictionary version')
    baseline = duration(confirmed)
    scenarios = [('Confirmed; flagged dates excluded', confirmed, False),
        ('Confirmed + missing GEOIDs; flagged dates excluded', confirmed + missing, False),
        ('Confirmed; ignore flagged cancellation dates', confirmed, True),
        ('Confirmed + missing GEOIDs; ignore flagged cancellation dates', confirmed + missing, True)]
    results = []
    for label, sample, ignore in scenarios:
        value = duration(sample, ignore)
        results.append({'scenario':label,'record_years':str(value),'insured_unit_years':str(value),
                        'change_from_confirmed':str(value-baseline),'percent_change':str((value-baseline)*100/baseline)})
    for key, sample in [('confirmed_only',confirmed),('missing_only',missing),('plus_missing_geoid',confirmed+missing)]:
        g = next(g for g in source[key]['groups'] if g['code']=='N')
        require(abs(duration(sample)-Decimal(g['record_years_excluding_exceptions'])) <= Decimal('0.000000005'),
                'Duration does not reproduce saved report')
    flagged = [r for r in rows if r.get('cancellationDateOfFloodPolicy') and
               parse_date(r['cancellationDateOfFloodPolicy']) < parse_date(r['policyEffectiveDate'])]
    regular = [r for r in confirmed if r.get('cancellationDateOfFloodPolicy') and r not in flagged]
    term_only = duration(confirmed,term_only=True)
    stats = {}
    for label, sample in [('confirmed',confirmed),('missing_geoid',missing)]:
        r = analyze(sample,zip_code='33708',allow_missing_geoid=label!='confirmed')
        stats[label] = {'rows':len(sample),'effective_years':dict(Counter(x['policyEffectiveDate'][:4] for x in sample)),
            'record_reconciliation':r['record_reconciliation'],
            'with_endorsement_date':sum(bool(x.get('endorsementEffectiveDate')) for x in sample),
            'with_cancellation_date':sum(bool(x.get('cancellationDateOfFloodPolicy')) for x in sample),
            'cancellation_differs_from_termination':sum(bool(x.get('cancellationDateOfFloodPolicy')) and
                 x['cancellationDateOfFloodPolicy']!=x['policyTerminationDate'] for x in sample)}
    audit = {'checked_at_utc':datetime.now(timezone.utc).isoformat(), 'status':'PROVISIONAL - no fully comparable independent benchmark verified',
        'scope':{'calendar_year':2024,'zip':'33708','coverage_code':'N','pinellas_prefix':'12103'},
        'snapshot':source['target_snapshot'], 'input_sha256':{
            str(folder.relative_to(root) / 'evidence.json'):digest(folder / 'evidence.json'),
            str(fields_path.relative_to(root)):digest(fields_path),
            'data/raw/MarketShareTsExternal.xlsx':digest(root / 'data/raw/MarketShareTsExternal.xlsx')},
        'statistics':stats,'scenarios':results,'all_6201_policy_counts_equal_one':True,
        'flagged_date_records':flagged,'missing_geoid_records':missing,
        'confirmed_term_only_excluding_flagged':str(term_only),
        'additional_years_without_valid_cancellation_truncation':str(term_only-baseline),
        'independent_benchmark_comparison':{'performed':False,'reason':'No benchmark verified for ZIP 33708 intersected with Pinellas, code N, insured units/contracts and a specified 2024 date. Partial candidates must not be compared numerically.'}}
    lines = ['# ZIP 33708: validation of the provisional 2024 non-condominium denominator', '',
        f"Checked (UTC): {audit['checked_at_utc']}. **{audit['status']}**.", '',
        '## Verdict', '',
        'The saved inputs, recorded-duration arithmetic, source-date alignment and sensitivity calculations reproduce. '
        'The evidence does not establish an independently benchmarked unique-contract or unique-property exposure denominator. '
        'Keep the output labelled **provisional recorded-policy-duration exposure**. No claim rates are calculated.', '',
        '## FEMA counting rules versus RiskMap assumptions', '',
        f'Primary documentation: [FEMA v3 data dictionary API]({DICT}), saved as sources/nfip_policy_fields_v3.json; '
        f'[FEMA dataset metadata](https://www.fema.gov/api/open/v1/OpenFemaDataSets?%24filter=name+eq+%27NfipPolicies%27&%24top=5), '
        f'saved as sources/datasets.json; [FEMA NFIP data FAQ]({FAQ}), read through the web reader on 2026-11-11.', '',
        '| Topic | Confirmed by FEMA | What remains an assumption or unresolved |',
        '|---|---|---|',
        '| IDs | id identifies a record; the dataset describes policy transactions. | Unique IDs do not prove unique contracts, properties, or non-overlapping exposure. No shared public contract/property key permits a contract-level duplicate/overlap test. |',
        '| Renewals | The FAQ states a renewal produces another record and gives effective <= observation date < termination for point-in-time selection. | Successive records should contribute their own recorded intervals; the public identifiers do not independently establish complete renewal chains or distinguish all transaction duplication. |',
        '| Endorsements | endorsementEffectiveDate records when an endorsement takes effect. | The dictionary does not establish whether every endorsement is a separate v3 row, whether a row is a latest-state representation, or how changes to coverage/units should be integrated. A non-null endorsement date alone is not evidence of duplicate rows. |',
        '| Cancellations | cancellationDateOfFloodPolicy marks going out of force; termination describes ending by cancellation or lapse. policyCount definition ties active status to cancellation or expiration. | Using min(termination, cancellation) is a conservative operational reconciliation, not an expressly documented resolution rule for inconsistent fields. A cancellation before effective date is not automatically proven to be a data error: voidance/cancel-rewrite history may matter. |',
        '| policyCount | FEMA defines insured units in active status, with condominium contracts potentially representing multiple units. | It is not a unique-building count. Holding the reported weight constant over a row interval is an integration assumption; all 6,201 observed N rows have weight 1, so that weighting choice has no numerical effect here. N is not synonymous with single-family homes. |',
        '| Source dates | asOfDate describes creation/last update in the source system. | Shared 2026-09-08 row dates support temporal consistency, not an immutable processing revision or final historical coverage. Dataset metadata modified/refresh dates differ and must not be treated as PIF dates. |',
        '| Geography | reportedZipCode is partner-reported insured-property ZIP; censusGeoid is address-based block-group geography. | A missing GEOID is not proof of Pinellas membership. Keep it in a separate sensitivity. |',
        '| Annual exposure | The FAQ supports point-in-time active-term selection. | Integrating rows into 366-day record-years and treating that as unique-contract exposure is RiskMap methodology, not a FEMA-certified annual denominator. Midnight timestamp defaults do not recover unreported real-world time-of-day details. |', '',
        '## Specific-group reconciliation and sensitivities', '',
        f"All rows are code N, FL, ZIP 33708, at row asOfDate {audit['snapshot']}. "
        'Earlier-term completeness was checked across all pre-2024 effective years; the retrieved candidates were all effective in 2023. '
        'Coverage is clipped to [2024-01-01, 2025-01-01), divided by 366 days. Main scenarios exclude cancellation-before-effective rows.', '',
        '| Geography | Source rows | 2023 effective | 2024 effective | Positive overlap rows | No elapsed coverage | Flagged date rows |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for label,s in stats.items():
        c=s['record_reconciliation']; y=s['effective_years']
        lines.append(f"| {label} | {s['rows']} | {y.get('2023',0)} | {y.get('2024',0)} | {c['overlapping_records']} | {c['no_elapsed_coverage']} | {c['date_exceptions']} |")
    lines += ['', '| Scenario | Record-years | Insured-unit-years | Absolute change from confirmed | Percentage change |',
        '|---|---:|---:|---:|---:|']
    for s in results:
        lines.append(f"| {s['scenario']} | {Decimal(s['record_years']):,.8f} | {Decimal(s['insured_unit_years']):,.8f} | {Decimal(s['change_from_confirmed']):+.8f} | {Decimal(s['percent_change']):+.6f}% |")
    lines += ['', 'The missing-GEOID effect here comes from **10 N rows** (8 effective in 2023 and 2 in 2024), '
        'not all 514 missing-GEOID records in the 2024 all-coverage audit. All have positive elapsed coverage and none has a flagged pre-effective cancellation. '
        'There are 11 flagged N date records, all in the confirmed scenario. Ignoring their cancellations is a separate hypothetical '
        'sensitivity, not a correction, confidence interval or verified upper bound. The combined scenario adds both geographic and flagged-date sensitivities.', '',
        f"Among confirmed N rows, {stats['confirmed']['with_cancellation_date']} have cancellation dates, all differing from termination; "
        f"{len(regular)} are not pre-effective exceptions. Omitting cancellation truncation while still excluding the 11 flagged rows "
        f"would produce {term_only:.8f} record-years, {term_only-baseline:+.8f} ({(term_only-baseline)*100/baseline:+.6f}%) above the main estimate. "
        'This diagnoses the consequence of a literal termination-only interpretation; it does not resolve which date is correct.', '',
        f"Non-null endorsement dates occur on {stats['confirmed']['with_endorsement_date']} confirmed and "
        f"{stats['missing_geoid']['with_endorsement_date']} missing-GEOID rows. No automatic deduplication was attempted using dates/GEOIDs, "
        'because unrelated properties can share those attributes. Exposure uncertainty from unobservable contract duplication or endorsement history remains unquantified.', '',
        'All inspected N policyCount values are valid positive integers equal to 1; no missing/invalid count values or additional '
        'unparseable exposure dates were found in this saved scope. Known outside-county records remain excluded from both scenarios. '
        'The input-cohort verification is not partial; independent denominator validation remains incomplete.', '',
        '## Independent policies-in-force benchmark search', '',
        'Acceptance criteria: an independently produced NFIP PIF aggregate for the same observation date, ZIP 33708 '
        'with the same Pinellas restriction (or separately an explicitly comparable ZIP-only scope), code N, and an explicit '
        'record/contract/insured-unit counting definition. Source extraction dates and retrospective revisions must also be reconciled.', '',
        '| Candidate inspected | Comparability and result |',
        '|---|---|',
        f'| [Pinellas LMS 2023-2024 assessment, municipal-hosted PDF]({COUNTY}#page=148) | Saved locally and text inspected, especially PDF pages 147-155. Independently compiled jurisdiction/geocoded-community summaries use 2021-2023 observations and land-use classifications, not ZIP 33708/code N on an exact 2024 date. The PDF discusses community assignment and unmatched addresses. No defensible numerical comparison. |',
        '| Local data/raw/MarketShareTsExternal.xlsx | Workbook headers identify a Florida OIR Pinellas market-share report for December 2025, all policy types, ordered by wind-covered direct premium. It is not a matched 2024 NFIP code-N ZIP benchmark; no comparison. |',
        '| [FEMA single-family pricing tables](https://www.fema.gov/flood-insurance/work-with-nfip/risk-rating/single-family-home) | A single-family table is not all non-condominium coverage. The official page returned HTTP 403; no downloadable matching table/count/date could be verified. No benchmark number adopted. |',
        '| [FEMA published-report portal](https://nfipservices.floodsmart.gov/reports-flood-insurance-data) and [Watermark](https://www.fema.gov/flood-insurance/work-with-nfip/watermark) | Access/redirect/reader failures prevented verification of a matching historic ZIP/type/date table. The legacy home/reports link redirects to the FAQ. This does not establish that such a report does not exist. |',
        '| Public ZIP aggregators found during search | These describe their statistics as reconstructions from OpenFEMA and use other 2026 dates, all-coverages or single-family filters. They are not independent source validation or a matching 2024 N benchmark; no numbers imported. |', '',
        '**No fully comparable independent benchmark was verified. No numerical external PIF comparison was performed.** '
        'There is therefore no point-in-time benchmark pass to report. A future PIF comparison must use effective <= t < termination '
        'with an explicit cancellation/flagged-record convention and separately report row and insured-unit counts. '
        'Even exact agreement at one date would validate only that stock count, not the full-year integral, transaction history or claim-count compatibility.', '',
        '## What remains provisional and next verification', '',
        'Confirmed: saved-input hashes, consistent row dates, earlier-term candidate counts, row ID uniqueness, clipping arithmetic, '
        'N weights of one, and quantified geographic/date sensitivities. Not confirmed: unique-contract continuity and overlap handling, '
        'endorsement representation, correct resolution of the 11 flagged cancellations and differing termination/cancellation fields, '
        'county membership of the 10 missing-GEOID N records, or an independently benchmarked stock/annual denominator.', '',
        'Next: obtain a documented insurer/program-produced PIF extract for a specified 2024 date with ZIP 33708, code N, '
        'counting-unit and county definitions; reconcile that stock separately. Seek documented v3 endorsement/cancel-rewrite semantics '
        'before promoting the integrated denominator. Do not calculate additional claim rates.', '',
        '## Reproducibility and evidence', '',
        'Reused scripts/verify_saved_exposure.py and the saved 33708 audit/sensitivity inputs. This packet recomputes N duration '
        'and reproduces saved values within their eight-decimal rounding. Underlying source records were not re-downloaded. '
        'Official metadata was retrieved separately; no new policy cohort or claim-rate analysis was run.', '',
        'Run: `.\\.venv-pilot\\Scripts\\python.exe scripts/validate_noncondo_denominator_33708.py --output '
        'reports/noncondo_denominator_validation_33708_2024_2026-11-11` (refuses to overwrite a completed report).', '',
        'The FAQ was accessible via web search/open, but direct Python retrieval encountered certificate verification failure; '
        'TLS verification was not disabled. The v3 landing page and single-family table page were blocked by HTTP 403. '
        'The county PDF downloaded successfully; web PDF screenshots failed with cache-miss, so no tabulated benchmark numbers were transcribed. '
        'sources/retrieval_log.json records direct-fetch failures. Official v3 metadata JSON, the county PDF, source hashes, '
        'specific exception records and calculations are saved alongside this single report.']
    before=json.loads((output/'protected_before.json').read_text())
    require(all(digest(root/name)==expected for name,expected in before.items()), 'Prior report/dashboard changed')
    audit['preservation']={'sha256_before':before,'all_unchanged':True}
    audit['supporting_source_sha256']={str(p.relative_to(output)):digest(p) for p in (output/'sources').iterdir() if p.is_file()}
    lines += ['', 'Both dashboards and prior reports are unchanged. This is one new validation report with supporting evidence.']
    (output/'calculation_evidence.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Saved:',output/'report.md')
    print(json.dumps({'scenarios':results,'confirmed_term_only':str(term_only),'date_exceptions':len(flagged),'independent_benchmark':'not verified'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(Path(__file__).resolve().parents[1],args.output.resolve())
