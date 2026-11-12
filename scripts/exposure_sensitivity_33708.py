"""Provisional 2024 record-duration exposure; reuse audited 2024 rows, fetch only
missing-GEOID 2024 rows and all earlier effective-year terms potentially overlapping 2024.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from urllib.parse import urlencode, unquote
from urllib.request import Request, urlopen

from audit_policy_cohorts import API, digest, local_cohort, protected_files
from calculate_provisional_exposure import CODES, analyze, parse_date, validate_row
from compare_policy_zip_audits import geography
from screen_policy_zip_counts import SNAPSHOT

FIELDS = ('id,propertyState,reportedZipCode,censusGeoid,policyEffectiveDate,policyTerminationDate,'
          'cancellationDateOfFloodPolicy,policyCount,condominiumCoverageTypeCode,asOfDate,endorsementEffectiveDate')
BASE = "propertyState eq 'FL' and reportedZipCode eq '33708'"


def change(before, after):
    b, a = Decimal(str(before)), Decimal(str(after))
    return {'absolute': str(a-b), 'percent': str((a-b)*100/b) if b else None}


def run(root, output):
    if output.exists():
        raise ValueError('Choose a new output directory')
    protected = protected_files(root, output)
    prior_dir = root / 'reports/policy_audit_33708_2024_2026-11-11'
    prior_path = prior_dir / 'evidence.json'
    prior = json.loads(prior_path.read_text())
    assert prior['target_snapshot_verified'] and prior['id_reconciliation']['verified']
    local, ids = local_cohort(root, 2024, '33708', prior_dir / 'downloaded/2024')
    for name, h in prior['downloaded_cohort']['files_sha256'].items():
        assert digest(root / name) == h
    for name in ('api_pinellas', 'api_zip_only'):
        assert digest(prior_dir / 'api' / prior[name]['response_file']) == prior[name]['response_sha256']
    cached = [r for p in sorted((prior_dir / 'downloaded/2024').glob('page_*.json'))
              for r in json.loads(p.read_text())['records']]
    output.mkdir(parents=True)
    (output / 'responses').mkdir()
    audit = {'created_at_utc': datetime.now(timezone.utc).isoformat(), 'target_snapshot': SNAPSHOT,
             'prior_audit': {'path': str(prior_path.relative_to(root)), 'sha256': digest(prior_path)},
             'reused_2024_included': local, 'requests': [], 'issues': []}

    def fetch(name, filter_text, count_only=False):
        params = {'$filter': filter_text, '$count': 'true', '$top': 1 if count_only else 10000,
                  '$select': 'asOfDate' if count_only else FIELDS}
        if not count_only:
            params['$orderby'] = 'id'
        result = {'filter': filter_text, 'url': API+'?'+urlencode(params), 'attempts': []}
        audit['requests'].append(result)
        for attempt in (1,2):
            info = {'attempt': attempt, 'at_utc': datetime.now(timezone.utc).isoformat()}
            result['attempts'].append(info)
            try:
                with urlopen(Request(result['url'], headers={'User-Agent':'RiskMap Exposure Research/1.0'}), timeout=25) as response:
                    raw = response.read()
                p = output / 'responses' / f'{name}_{attempt}.json'
                p.write_bytes(raw)
                info.update(path=str(p.relative_to(output)), sha256=digest(p))
                data = json.loads(raw)
                rows, n = data['NfipPolicies'], data['metadata']['count']
                if (isinstance(n,bool) or not isinstance(n,int) or n<0
                        or unquote(data['metadata']['filter']) != filter_text
                        or (not count_only and len(rows)!=n) or (count_only and len(rows)>1)):
                    raise ValueError('Incomplete/invalid count or filter response')
                if not count_only and len({r.get('id') for r in rows})!=n:
                    raise ValueError('Duplicate record IDs')
                result.update(status='verified', count=n, snapshots=dict(Counter(r.get('asOfDate') for r in rows)))
                return rows, result
            except (OSError,ValueError,KeyError,TypeError) as error:
                info['error'] = f'{type(error).__name__}: {error}'
                print(name, 'attempt', attempt, info['error'], flush=True)
        result['status']='unresolved'
        audit['issues'].append({'query':name,'issue':'API request could not be verified after one retry'})
        return [], result

    # Include null term dates so they cannot disappear silently from the overlap check.
    early_filter = BASE + " and policyEffectiveDate lt '2024-01-01' and (policyTerminationDate gt '2024-01-01' or policyTerminationDate eq null)"
    earlier, early_meta = fetch('earlier_potential_overlap', early_filter)
    missing_filter = BASE + " and policyEffectiveDate ge '2024-01-01' and policyEffectiveDate lt '2025-01-01' and (censusGeoid eq null or censusGeoid eq '')"
    missing, missing_meta = fetch('missing_geoid_2024', missing_filter)
    unknown, unknown_meta = fetch('unknown_effective_dates', BASE + ' and policyEffectiveDate eq null', True)
    if unknown_meta.get('count',0):
        audit['issues'].append({'issue':'Rows with unknown effective dates cannot be ruled out as 2024 exposure', 'count':unknown_meta['count']})
    if early_meta.get('status')=='verified':
        audit['earlier_candidate_effective_years'] = dict(Counter(str(r.get('policyEffectiveDate'))[:4] for r in earlier))
        audit['earlier_candidate_geography'] = geography(earlier)['counts']
        for r in earlier:
            if r.get('propertyState')!='FL' or r.get('reportedZipCode')!='33708' or parse_date(r['policyEffectiveDate']).year>=2024:
                raise ValueError('Unexpected earlier-cohort scope')
    expected_missing = {r['id']:r for r in prior['groups']['excluded_missing_geoid']['records']}
    audit['missing_2024_ids_match_prior_audit'] = {r['id'] for r in missing} == set(expected_missing)
    if not audit['missing_2024_ids_match_prior_audit']:
        audit['issues'].append({'issue':'2024 missing-GEOID IDs differ from audited exclusions'})
    missing_differences = [r['id'] for r in missing if r['id'] in expected_missing
                           and r.get('policyCount') != expected_missing[r['id']].get('policyCount')]
    audit['missing_2024_policy_count_mismatches'] = missing_differences
    if missing_differences:
        audit['issues'].append({'issue':'2024 missing-GEOID policyCount differs from prior audit','ids':missing_differences})
    # Terminal-term filter scans all earlier effective years, including pre-2023.
    earlier_check, check_meta = fetch('earlier_overlap_final_count', early_filter, True)
    audit['earlier_candidate_counts_stable'] = (early_meta.get('status')==check_meta.get('status')=='verified'
                                               and early_meta['count']==check_meta['count'])
    if not audit['earlier_candidate_counts_stable']:
        audit['issues'].append({'issue':'Earlier overlap candidate completeness/count stability unresolved'})
    combined, missing_rows, seen = [], [], set()
    excluded = {'outside_pinellas': [], 'other_geoid': []}
    for source, rows in (('reused_2024', cached), ('missing_2024', missing), ('earlier', earlier)):
        for row in rows:
            if row.get('id') in seen:
                audit['issues'].append({'source':source,'id':row.get('id'),'issue':'Duplicate ID; skipped'})
                continue
            seen.add(row.get('id'))
            groups = geography([row])['counts']
            if groups['outside_pinellas']:
                excluded['outside_pinellas'].append(row)
                continue
            if groups['invalid']:
                excluded['other_geoid'].append(row)
                audit['issues'].append({'source':source,'id':row['id'],'issue':'Other GEOID; excluded from both scenarios'})
                continue
            if row.get('asOfDate')!=SNAPSHOT:
                audit['issues'].append({'source':source,'id':row['id'],'issue':'Snapshot differs or missing; excluded from estimates'})
                continue
            try:
                validate_row(row,'33708','12103',allow_missing_geoid=True)
            except (ValueError,TypeError) as error:
                audit['issues'].append({'source':source,'id':row['id'],'issue':str(error),'record':row})
                continue
            if groups['missing']:
                missing_rows.append(row)
            else:
                combined.append(row)
    audit['excluded_from_both'] = excluded
    audit['confirmed_only'] = analyze(combined,zip_code='33708')
    audit['plus_missing_geoid'] = analyze(combined+missing_rows,zip_code='33708',allow_missing_geoid=True)
    audit['missing_only'] = analyze(missing_rows,zip_code='33708',allow_missing_geoid=True)
    # Replace limitations inherited from the older offline-only 33706 loader.
    for key in ('confirmed_only','plus_missing_geoid','missing_only'):
        audit[key]['limitations'] = ['Record durations and policyCount-weighted durations are provisional, not unique properties/contracts.',
            'Master and individual-unit coverage can overlap; do not sum groups as unique-property exposure.',
            'Flagged cancellations are excluded, with their hypothetical uncancelled contribution reported separately.',
            'Missing GEOIDs are an uncertainty scenario, not confirmed Pinellas exposure.']
    audit['cohort_verification_partial'] = bool(audit['issues'])
    audit['status'] = 'PARTIAL - PROVISIONAL' if audit['cohort_verification_partial'] else 'PROVISIONAL - overlapping candidate cohorts verified at target snapshot'
    confirmed = {g['code']:g for g in audit['confirmed_only']['groups']}
    augmented = {g['code']:g for g in audit['plus_missing_geoid']['groups']}
    audit['comparison_by_coverage_type'] = []
    lines = ['# ZIP 33708 provisional calendar-year 2024 exposure sensitivity', '',
        f"Status: **{audit['status']}**. Retrieved (UTC): {audit['created_at_utc']}.", '',
        'Rules reused from ZIP 33706: clip each recorded policy term to [2024-01-01, 2025-01-01), '
        'divide elapsed seconds by 366 days, truncate at recorded cancellation, exclude cancellations before effective date '
        'as unresolved date exceptions. Insured-unit-years weight elapsed duration by positive integral policyCount. '
        'No claim rates are calculated.', '',
        'Scenario 1 includes valid Pinellas-prefix GEOIDs only. Scenario 2 adds missing-GEOID rows as a sensitivity '
        'scenario. Known out-of-county and malformed GEOIDs remain outside both.', '',
        f"Reused {len(cached):,} audited 2024 confirmed rows; retrieved {len(missing):,} missing-GEOID 2024 rows and "
        f"{len(earlier):,} earlier-term candidates. Earlier effective-year distribution: {audit.get('earlier_candidate_effective_years',{})}.",
        'The earlier query has no lower effective-year limit: it selects all pre-2024 terms ending after 2024 begins '
        '(or missing termination), without filtering cancellation dates, so flagged cancellations remain visible. '
        'Policies ending by 2024-01-01 cannot contribute under these rules and were not downloaded.', '',
        f"Target snapshot: {SNAPSHOT}. New response row dates: {[(r['filter'],r.get('snapshots',{})) for r in audit['requests']]}.",
        f"Earlier candidate first/final counts agree: {audit['earlier_candidate_counts_stable']}; "
        f"2024 missing IDs match the prior audit: {audit['missing_2024_ids_match_prior_audit']}.", '',
        '| Coverage | Confirmed record-years | Plus missing record-years | Change | Change % | Confirmed insured-unit-years | Plus missing insured-unit-years | Change | Change % |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for code in sorted(CODES):
        b,a = confirmed[code],augmented[code]
        item = {'code':code,'coverage':CODES[code]}
        values=[]
        for field in ('record_years_excluding_exceptions','insured_unit_years_excluding_exceptions'):
            delta=change(b[field],a[field])
            item[field]={'confirmed':b[field],'plus_missing':a[field],**delta}
            values += [f'{Decimal(b[field]):,.4f}',f'{Decimal(a[field]):,.4f}',f"{Decimal(delta['absolute']):+,.4f}",
                       f"{Decimal(delta['percent']):+.2f}%" if delta['percent'] is not None else 'N/A (zero baseline)']
        audit['comparison_by_coverage_type'].append(item)
        lines.append('| '+code+' — '+CODES[code]+' | '+' | '.join(values)+' |')
    lines += ['', 'Coverage types remain separate; totals must not be interpreted as unique properties.', '',
              '## Date exceptions and cancellation sensitivity', '',
              '| Coverage | Confirmed flagged records | Plus missing flagged records | Additional record-years if flagged cancellations ignored (confirmed / plus missing) | Additional insured-unit-years (confirmed / plus missing) |',
              '|---|---:|---:|---|---|']
    for code in sorted(CODES):
        b,a=confirmed[code],augmented[code]
        lines.append(f"| {code} | {b['exception_records']} | {a['exception_records']} | {b['added_record_years_if_flagged_cancellation_ignored']} / {a['added_record_years_if_flagged_cancellation_ignored']} | {b['added_insured_unit_years_if_flagged_cancellation_ignored']} / {a['added_insured_unit_years_if_flagged_cancellation_ignored']} |")
    lines += ['', 'Flagged cancellations remain unresolved; ignoring them is a separate hypothetical sensitivity, '
              'not a correction or a proven bound. Their duration is excluded from the main comparison.', '',
              f"Record reconciliations: confirmed {audit['confirmed_only']['record_reconciliation']}; "
              f"plus missing {audit['plus_missing_geoid']['record_reconciliation']}.",
              f"Known outside-Pinellas rows excluded: {len(excluded['outside_pinellas'])}; other GEOID rows excluded: {len(excluded['other_geoid'])}.", '',
              '## Unresolved issues', '']
    lines += ['- '+json.dumps(issue) for issue in audit['issues']] or ['- No cohort/date-validity/snapshot gaps identified beyond the flagged cancellation exceptions above.']
    for query in audit['requests']:
        for attempt in query['attempts']:
            if 'error' in attempt:
                lines.append(f"- Request attempt {attempt['attempt']}: {attempt['error']}; final query status {query['status']}.")
    lines += ['', 'All figures remain provisional. Source asOfDate equality and count stability do not prove an immutable database '
              'revision or independent coverage completeness. Missing-GEOID records are not established as Pinellas properties. '
              'No claims rates, premiums or property-risk estimates were produced.']
    after={n:digest(root/n) for n in protected}
    audit['preservation']={'sha256_before':protected,'sha256_after':after,'all_unchanged':protected==after}
    assert protected==after
    lines += ['', 'Both dashboards and all prior reports passed SHA-256 preservation checks. Exact filters, raw responses, '
              'source hashes, record-level issues and scenario reconciliations are retained in evidence.json and responses/.']
    (output/'evidence.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(Path(__file__).resolve().parents[1],args.output.resolve())
