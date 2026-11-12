"""Count-only 2024 screening of claims-linked Pinellas ZIPs; no policy downloads.

Each count request returns at most one asOfDate, never IDs or GEOIDs. An extra
count query tests for rows outside the target snapshot (including null dates).
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode, unquote
from urllib.request import Request, urlopen

from audit_policy_cohorts import API, PREFIX, digest, protected_files

SNAPSHOT = '2026-09-08T00:00:00.000Z'


def scope(zip_code, pinellas=False):
    text = (f"propertyState eq 'FL' and reportedZipCode eq '{zip_code}' "
            "and policyEffectiveDate ge '2024-01-01' and policyEffectiveDate lt '2025-01-01'")
    return text + (f' and {PREFIX}' if pinellas else '')


def count_query(filter_text, name, folder):
    params = {'$filter': filter_text, '$count': 'true', '$top': 1, '$select': 'asOfDate'}
    url = API + '?' + urlencode(params)
    result = {'url': url, 'filter': filter_text, 'attempts': []}
    for attempt in (1, 2):
        item = {'attempt': attempt, 'requested_at_utc': datetime.now(timezone.utc).isoformat()}
        result['attempts'].append(item)
        try:
            with urlopen(Request(url, headers={'User-Agent': 'RiskMap Count Screening/1.0'}), timeout=20) as response:
                raw = response.read()
            path = folder / f'{name}_attempt_{attempt}.json'
            path.write_bytes(raw)
            item.update(response_file=str(path.name), sha256=digest(path))
            data = json.loads(raw)
            count = data['metadata']['count']
            rows = data['NfipPolicies']
            if (isinstance(count, bool) or not isinstance(count, int) or count < 0
                    or unquote(data['metadata']['filter']) != filter_text or len(rows) > 1
                    or any(set(row) - {'asOfDate'} for row in rows)
                    or (count == 0 and rows) or (count > 0 and len(rows) != 1)):
                raise ValueError('Invalid count, filter, select or top response')
            result.update(status='verified_count', count=count,
                          sampled_dates=[r.get('asOfDate') for r in rows], metadata=data['metadata'])
            return result
        except (OSError, ValueError, KeyError, TypeError) as error:
            item['error'] = f'{type(error).__name__}: {error}'
    result['status'] = 'unavailable'
    return result


def snapshot_status(base, exceptions):
    if base.get('status') != 'verified_count' or exceptions.get('status') != 'verified_count':
        return 'unverified'
    if exceptions['count'] > base['count']:
        return 'inconsistent counts'
    if exceptions['count'] or any(d != SNAPSHOT for d in base['sampled_dates']):
        return 'snapshot mismatch or missing dates'
    return 'verified target snapshot' if base['count'] else 'empty cohort; no snapshot date'


def summarize(zip_code, claims, queries):
    z, p = queries['zip_only'], queries['pinellas']
    status = {k: snapshot_status(queries[k], queries[k + '_snapshot_exceptions'])
              for k in ('zip_only', 'pinellas')}
    row = {'zip': zip_code, 'claims_2024': claims, 'source': 'new count-only queries',
           'classification': 'unclassified', 'snapshot_status': status,
           'zip_only_count': z.get('count'), 'pinellas_count': p.get('count'),
           'excluded_count': None, 'excluded_pct': None}
    if z.get('count') is not None and p.get('count') is not None:
        if p['count'] > z['count']:
            row['count_status'] = 'inconsistent: Pinellas exceeds ZIP-only'
        else:
            row.update(count_status='counts available', excluded_count=z['count'] - p['count'],
                       excluded_pct=100 * (z['count'] - p['count']) / z['count'] if z['count'] else None)
    else:
        row['count_status'] = 'unavailable'
    row['comparable_to_baseline'] = (row['count_status'] == 'counts available'
        and all(v in ('verified target snapshot', 'empty cohort; no snapshot date') for v in status.values()))
    return row


def screen(zip_code, claims, output):
    folder = output / 'responses' / zip_code
    folder.mkdir(parents=True)
    queries = {}
    for name, pinellas in (('zip_only', False), ('pinellas', True)):
        base = scope(zip_code, pinellas)
        queries[name] = count_query(base, name, folder)
        exceptions = base + f" and (asOfDate ne '{SNAPSHOT}' or asOfDate eq null)"
        queries[name + '_snapshot_exceptions'] = count_query(exceptions, name + '_snapshot_exceptions', folder)
    return {'summary': summarize(zip_code, claims, queries), 'queries': queries}


def rank_rows(rows):
    by_count = sorted((r for r in rows if r['excluded_count'] is not None),
                      key=lambda r: (-r['excluded_count'], -(r['excluded_pct'] or 0), r['zip']))
    by_pct = sorted((r for r in rows if r['excluded_pct'] is not None),
                    key=lambda r: (-r['excluded_pct'], -r['excluded_count'], r['zip']))
    for index, row in enumerate(by_count, 1):
        row['count_rank'] = index
    for index, row in enumerate(by_pct, 1):
        row['percentage_rank'] = index
    return by_count, by_pct


def run(root, output):
    if output.exists():
        raise ValueError('Choose a new output folder')
    protected = protected_files(root, output)
    claims_path = root / 'data/processed/nfip_claims_by_year_zip.csv'
    linked_path = root / 'data/processed/nfip_payments_by_zip_hud.csv'
    with linked_path.open(newline='') as stream:
        linked = {r['reported_zip_5'] for r in csv.DictReader(stream) if r['hud_status'] == 'hud_pinellas_link'}
    with claims_path.open(newline='') as stream:
        claims_rows = list(csv.DictReader(stream))
    universe = linked & {r['reported_zip_code'] for r in claims_rows}
    claims = {z: sum(int(r['claim_records']) for r in claims_rows
                     if r['year_of_loss'] == '2024' and r['reported_zip_code'] == z) for z in universe}
    final_path = root / 'reports/policy_cohort_comparison_33703_33706_2026-11-11_final/verification.json'
    final = json.loads(final_path.read_text())
    evidence_path = root / final['reused_evidence_path']
    if digest(evidence_path) != final['reused_evidence_sha256']:
        raise ValueError('Prior evidence changed')
    evidence = json.loads(evidence_path.read_text())
    results = []
    for cohort in evidence['cohorts']:
        if cohort['year'] != 2024:
            continue
        z = cohort['zip']
        for key in ('api_pinellas', 'api_zip_only'):
            response = evidence_path.parent / f'api_{z}' / cohort[key]['response_file']
            if digest(response) != cohort[key]['response_sha256']:
                raise ValueError('Prior response changed')
            data = json.loads(response.read_text())
            rows = data['NfipPolicies']
            if len(rows) != cohort[key]['count'] or {r['asOfDate'] for r in rows} != {SNAPSHOT}:
                raise ValueError('Prior count or snapshot failed validation')
        g = cohort['reconciliation']['geography']['counts']
        assert cohort['reconciliation']['verified'] and not g['outside_pinellas'] and not g['invalid']
        total, included = cohort['api_zip_only']['count'], cohort['api_pinellas']['count']
        assert total - included == g['missing']
        results.append({'summary': {'zip': z, 'claims_2024': claims[z], 'source': 'reused full audit',
            'zip_only_count': total, 'pinellas_count': included, 'excluded_count': total-included,
            'excluded_pct': 100*(total-included)/total, 'classification': 'verified missing GEOID',
            'snapshot_status': {'zip_only': 'verified target snapshot', 'pinellas': 'verified target snapshot'},
            'count_status': 'counts available', 'comparable_to_baseline': True},
            'prior_evidence_path': str(evidence_path.relative_to(root)), 'prior_evidence_sha256': digest(evidence_path)})
    assert {r['summary']['zip'] for r in results} == {'33703', '33706'}
    output.mkdir(parents=True)
    audit = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'target_snapshot': SNAPSHOT,
             'scope': '2024 effective-year, FL, ZIP; optional Pinellas GEOID prefix 12103',
             'input_sha256': {str(p.relative_to(root)): digest(p) for p in (claims_path, linked_path, final_path)},
             'universe': sorted(universe), 'results': results}
    remaining = sorted(universe - {'33703', '33706'})
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks = {pool.submit(screen, z, claims[z], output): z for z in remaining}
        for task in as_completed(tasks):
            result = task.result()
            results.append(result)
            (output / 'progress.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
            r = result['summary']
            print(f"{len(results)-2}/{len(remaining)} ZIP {r['zip']}: ZIP={r['zip_only_count']} Pinellas={r['pinellas_count']} snapshot={r['snapshot_status']}", flush=True)
    finalize(root, output, audit, protected)


def finalize(root, output, audit, protected):
    results = audit['results']
    universe = audit['universe']
    remaining = set(universe) - {'33703', '33706'}
    rows = [r['summary'] for r in results]
    by_count, by_pct = rank_rows(rows)
    # Recommendations balance absolute/relative gaps with useful claim volume.
    eligible = [r for r in by_count if r['source'] != 'reused full audit'
                and r['comparable_to_baseline'] and r['claims_2024'] >= 100 and r['excluded_count'] > 0]
    picks = eligible[:1]
    relative = sorted(eligible, key=lambda r: (-r['excluded_pct'], -r['excluded_count'], r['zip']))
    picks += [r for r in relative if r not in picks][:1]
    picks += [r for r in eligible if r not in picks][:3-len(picks)]
    audit['recommendations'] = [r['zip'] for r in picks]
    lines = ['# 2024 Pinellas-linked ZIP policy filter screening', '',
             f"Started (UTC): {audit['started_at_utc']}. Target source snapshot: {SNAPSHOT}.", '',
             f'Universe: all {len(universe)} HUD Pinellas-linked ZIPs present in the local claims data in any loss year. '
             f'Reused full audits for 33703/33706; queried {len(remaining)} remaining ZIPs. ZIPs without 2024 claims are retained.', '',
             'Method: count queries only, with FL, reported ZIP and policyEffectiveDate >= 2024-01-01 and < 2025-01-01; '
             "the second scope adds startswith(censusGeoid,'12103'). Each request returns at most one asOfDate and no IDs/GEOIDs. "
             'For each scope, a second count tests (asOfDate ne target OR asOfDate eq null). Zero exceptions plus a '
             'matching sample verifies the target date under API filter semantics. Empty scopes have no date to verify. '
             'Requests retry once. No full policy downloads or new GEOID classification queries were made.', '',
             'Excluded = ZIP-only minus Pinellas-filtered count; percentage = excluded / ZIP-only × 100. '
             'Zero ZIP-only totals have undefined percentages. New gaps are **unclassified**: counts alone cannot distinguish '
             'missing GEOIDs from valid outside-county GEOIDs or malformed values. Prior full-audit gaps retain their verified missing-GEOID label.', '',
             'Ranks are descriptive count differences; flagged snapshot/API results must not be interpreted as comparable coverage. '
             'Row asOfDate checks do not guarantee an immutable source revision, correct county assignment or policy/claim unit compatibility.', '',
             '## Ranked by excluded count', '',
             '| Count rank | % rank | ZIP | ZIP-only | Pinellas | Excluded | Excluded % | 2024 claims | Classification | Snapshot status |',
             '|---:|---:|---|---:|---:|---:|---:|---:|---|---|']
    def table_line(r):
        pct = f"{r['excluded_pct']:.2f}%" if r['excluded_pct'] is not None else 'N/A'
        status = '; '.join(k + ': ' + v for k,v in r['snapshot_status'].items())
        counts = [str(r[k]) if r[k] is not None else 'unavailable' for k in ('zip_only_count','pinellas_count','excluded_count')]
        return f"| {r.get('count_rank','N/A')} | {r.get('percentage_rank','N/A')} | {r['zip']} | {counts[0]} | {counts[1]} | {counts[2]} | {pct} | {r['claims_2024']} | {r['classification']} | {status} |"
    lines += [table_line(r) for r in by_count]
    unresolved = [r for r in rows if r['excluded_count'] is None]
    lines += [table_line(r) for r in unresolved]
    lines += ['', '## Ranked by excluded percentage', '',
              '| % rank | ZIP | Excluded % | Excluded count | Comparable snapshot/count checks |',
              '|---:|---|---:|---:|---|']
    lines += [f"| {r['percentage_rank']} | {r['zip']} | {r['excluded_pct']:.2f}% | {r['excluded_count']} | {r['comparable_to_baseline']} |" for r in by_pct]
    lines += ['', '## Recommended full audits', '',
              'Select the largest absolute gap, the highest relative gap, then the next largest absolute gap among '
              'new ZIPs with verified comparable snapshots and at least 100 local 2024 claim records. This is a workload '
              'prioritization rule, not a risk score.']
    lines += [f"- **{r['zip']}**: {r['excluded_count']:,} unclassified excluded records ({r['excluded_pct']:.2f}%); {r['claims_2024']:,} local 2024 claims." for r in picks]
    if not picks:
        lines.append('- No candidates meet the snapshot/count/claim-volume requirements; resolve flagged checks first.')
    lines += ['', 'Next step: run full ID and GEOID reconciliation only for these candidates, including investigation of '
              'county assignment. Stop screening here; no full audits have been initiated.', '', '## Flags and request failures', '']
    flags = [f"- ZIP {r['zip']}: {r['count_status']}; {r['snapshot_status']}" for r in rows if not r['comparable_to_baseline']]
    flags += [f"- ZIP {r['zip']}: empty scope has no row snapshot date to verify ({r['snapshot_status']}); zero ZIP-only totals have no defined exclusion percentage."
              for r in rows if any(v == 'empty cohort; no snapshot date' for v in r['snapshot_status'].values())]
    for result in results:
        for name, query in result.get('queries', {}).items():
            for attempt in query['attempts']:
                if 'error' in attempt and not attempt.get('validated_after_uri_normalization'):
                    flags.append(f"- ZIP {result['summary']['zip']} {name}, attempt {attempt['attempt']}: {attempt['error']}; final status {query['status']}.")
    lines += flags or ['- None.']
    if audit.get('offline_revalidation'):
        lines += ['', audit['offline_revalidation']]
    after = {name: digest(root / name) for name in protected}
    audit['preservation'] = {'sha256_before': protected, 'sha256_after': after, 'all_unchanged': protected == after}
    if protected != after:
        raise ValueError('Protected file changed during screening')
    lines += ['', 'Both dashboards and all prior reports passed SHA-256 preservation checks. '
              'Raw count responses, exact filters, request attempts, ranks and source hashes are saved in this folder. '
              'No claim frequencies or exposure measures were calculated.']
    (output / 'evidence.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    (output / 'progress.json').write_text(json.dumps({'status': 'complete', 'new_zips_screened': len(remaining),
        'authoritative_evidence': 'evidence.json', 'recommendations': audit['recommendations']}, indent=2), encoding='utf-8')
    (output / 'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    fields = ['zip','count_rank','percentage_rank','zip_only_count','pinellas_count','excluded_count','excluded_pct',
              'claims_2024','classification','count_status','comparable_to_baseline','source']
    with (output / 'ranking.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(by_count + unresolved)
    print('Saved report:', output / 'report.md', 'Recommended:', audit['recommendations'], flush=True)


def revalidate_saved(root, output):
    """Reprocess saved responses only; FEMA escapes colons in metadata.filter."""
    audit = json.loads((output / 'evidence.json').read_text())
    for result in audit['results']:
        if 'queries' not in result:
            continue
        for query in result['queries'].values():
            for attempt in query['attempts']:
                if 'response_file' not in attempt:
                    continue
                path = output / 'responses' / result['summary']['zip'] / attempt['response_file']
                if digest(path) != attempt['sha256']:
                    raise ValueError('Cached response hash mismatch')
                data = json.loads(path.read_text())
                count, rows = data['metadata']['count'], data['NfipPolicies']
                if (isinstance(count, bool) or not isinstance(count, int) or count < 0
                        or unquote(data['metadata']['filter']) != query['filter'] or len(rows) > 1
                        or any(set(row) - {'asOfDate'} for row in rows)
                        or (count == 0 and rows) or (count > 0 and len(rows) != 1)):
                    continue
                if 'error' in attempt:
                    attempt['validated_after_uri_normalization'] = True
                query.update(status='verified_count', count=count, sampled_dates=[r.get('asOfDate') for r in rows],
                             metadata=data['metadata'])
        result['summary'] = summarize(result['summary']['zip'], result['summary']['claims_2024'], result['queries'])
    audit['offline_revalidation'] = ('FEMA URI-escapes time colons in metadata.filter. Saved responses were '
                                     'validated after decoding that metadata; no new requests were needed.')
    finalize(root, output, audit, audit['preservation']['sha256_before'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--revalidate-saved', action='store_true', help='Read saved responses only; no network')
    args = parser.parse_args()
    action = revalidate_saved if args.revalidate_saved else run
    action(Path(__file__).resolve().parents[1], args.output.resolve())
