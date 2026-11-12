"""Download/audit ZIP 33703 and compare with preserved ZIP 33706 evidence.

Only a new output directory is written. Uses the existing download and audit
helpers; records request failures and refuses snapshot-mismatched inferences.
"""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from audit_policy_cohorts import (
    API, PREFIX, compare, digest, fetch_cohort, local_cohort,
    protected_files, snapshots, validate_rows,
)
from download_nfip_policies import download_year


def geography(rows):
    groups = {'pinellas': [], 'missing': [], 'outside_pinellas': [], 'invalid': []}
    for row in rows:
        value = row.get('censusGeoid')
        text = str(value).strip() if value is not None else ''
        if not text:
            key = 'missing'
        elif len(text) != 12 or not text.isdigit():
            key = 'invalid'
        else:
            key = 'pinellas' if text.startswith('12103') else 'outside_pinellas'
        groups[key].append({'id': row['id'], 'censusGeoid': value})
    return {'counts': {k: len(v) for k, v in groups.items()}, 'records': groups,
            'missing_share_pct': 100 * len(groups['missing']) / len(rows) if rows else None}


def reconcile(local, local_ids, pinellas, pinellas_ids, zip_result, zip_rows, zip_ids):
    first = compare(local, local_ids, pinellas, pinellas_ids)
    second = compare(local, local_ids, zip_result, zip_ids)
    result = {'download_vs_pinellas': first, 'download_vs_zip_only': second,
              'verified': False}
    if pinellas.get('status') == 'verified':
        result['id_differences'] = {
            'download_only': sorted(local_ids - pinellas_ids),
            'api_pinellas_only': sorted(pinellas_ids - local_ids)}
    if zip_result.get('status') == 'verified':
        result['geography'] = geography(zip_rows)
    if first['status'] == second['status'] == 'same_as_of_date':
        classified = {r['id'] for r in result['geography']['records']['pinellas']}
        result['zip_only_extras'] = [r for r in zip_rows if r['id'] not in pinellas_ids]
        result['api_pinellas_ids_absent_from_zip_only'] = sorted(pinellas_ids - zip_ids)
        result['pinellas_subset_ids_match'] = classified == pinellas_ids
        result['verified'] = (local_ids == pinellas_ids == classified
                              and pinellas_ids <= zip_ids
                              and not result['geography']['counts']['invalid'])
    return result


def claims_rationale(root):
    claims = root / 'data/processed/nfip_claims_by_year_zip.csv'
    crosswalk = root / 'data/processed/nfip_payments_by_zip_hud.csv'
    with crosswalk.open(newline='') as stream:
        linked = {r['reported_zip_5'] for r in csv.DictReader(stream)
                  if r['hud_status'] == 'hud_pinellas_link'}
    with claims.open(newline='') as stream:
        ranked = sorted((r for r in csv.DictReader(stream)
                         if r['year_of_loss'] == '2024' and r['reported_zip_code'] in linked),
                        key=lambda r: (-int(r['claim_records']), r['reported_zip_code']))
    selected = next(r for r in ranked if r['reported_zip_code'] == '33703')
    return {'selected': selected, 'rank_among_pinellas_linked': ranked.index(selected) + 1,
            'top_five': ranked[:5], 'input_sha256': {
                str(p.relative_to(root)): digest(p) for p in (claims, crosswalk)},
            'reason': '33703 has the most 2024 claim records among Pinellas-linked ZIPs other than 33706; '
                      'selection is descriptive and does not establish county membership for every claim.'}


def baseline(root, output):
    folder = root / 'reports/policy_cohort_audit_2026-11-11_retry'
    evidence = json.loads((folder / 'evidence.json').read_text())
    results = []
    dest = output / 'api_33706'
    dest.mkdir()
    for entry in evidence['cohorts']:
        year = entry['local']['year']
        local, ids = local_cohort(root, year)
        loaded = {}
        for key, screened in (('api_pinellas', True), ('api_zip_only', False)):
            saved = dict(entry[key])
            source = folder / saved['response_file']
            if digest(source) != saved['response_sha256']:
                raise ValueError('Baseline API response hash changed')
            data = json.loads(source.read_text())
            rows = data['NfipPolicies']
            remote_ids = validate_rows(rows, year, screened)
            if data['metadata']['count'] != len(rows) or saved['snapshots'] != snapshots(rows):
                raise ValueError('Invalid saved baseline count or snapshot')
            saved['baseline_source'] = str(source.relative_to(root))
            (dest / source.name).write_bytes(source.read_bytes())
            loaded[key] = (saved, rows, remote_ids)
        p, _, pids = loaded['api_pinellas']
        z, zrows, zids = loaded['api_zip_only']
        results.append({'zip': '33706', 'year': year, 'local': local,
                        'api_pinellas': p, 'api_zip_only': z,
                        'reconciliation': reconcile(local, ids, p, pids, z, zrows, zids)})
    return results


def run(root, output):
    if output.exists():
        raise ValueError('Use a new output folder; existing reports are never overwritten')
    before = protected_files(root, output)
    output.mkdir(parents=True)
    audit = {'created_at_utc': datetime.now(timezone.utc).isoformat(),
             'selection': claims_rationale(root), 'cohorts': [], 'download_requests': []}
    audit['cohorts'].extend(baseline(root, output))
    api_folder = output / 'api_33703'
    api_folder.mkdir()
    request_folder = output / 'download_requests'
    request_folder.mkdir()

    def logged_request(params):
        url = API + '?' + urlencode(params)
        for attempt in (1, 2):
            record = {'url': url, 'params': params, 'attempt': attempt,
                      'requested_at_utc': datetime.now(timezone.utc).isoformat()}
            audit['download_requests'].append(record)
            try:
                with urlopen(Request(url, headers={'User-Agent': 'RiskMap Cohort Audit/1.0'}), timeout=25) as response:
                    raw = response.read()
                path = request_folder / f'response_{len(audit["download_requests"]):03d}.json'
                path.write_bytes(raw)
                record.update(response_file=str(path.relative_to(output)), sha256=digest(path))
                data = json.loads(raw)
                if not isinstance(data.get('NfipPolicies'), list):
                    raise ValueError('Missing policy array')
                return data
            except (OSError, ValueError) as error:
                record['error'] = f'{type(error).__name__}: {error}'
                print(f'Request attempt {attempt} failed: {record["error"]}', flush=True)
                if attempt == 2:
                    raise

    for year in (2023, 2024):
        print(f'Downloading 33703 effective-year {year}', flush=True)
        entry = {'zip': '33703', 'year': year}
        try:
            download_year(year, output / 'downloaded_33703', 10000,
                          request=logged_request, zip_code='33703')
            local, ids = local_cohort(root, year, '33703', output / f'downloaded_33703/{year}')
            entry['local'] = local
        except (OSError, ValueError, KeyError) as error:
            entry['download_error'] = f'{type(error).__name__}: {error}'
            local, ids = {'snapshots': {}, 'count': 0}, set()
        filter_text = (f"propertyState eq 'FL' and {PREFIX} "
                       f"and policyEffectiveDate ge '{year}-01-01' "
                       f"and policyEffectiveDate lt '{year + 1}-01-01' and reportedZipCode eq '33703'")
        p, _, pids = fetch_cohort(filter_text, year, True, api_folder, '33703')
        z, zrows, zids = fetch_cohort(filter_text.replace(PREFIX + ' and ', ''), year, False, api_folder, '33703')
        entry.update(api_pinellas=p, api_zip_only=z,
                     reconciliation=reconcile(local, ids, p, pids, z, zrows, zids))
        audit['cohorts'].append(entry)
        print(f'{year} ID reconciliation verified: {entry["reconciliation"]["verified"]}', flush=True)

    lines = ['# ZIP 33703 vs 33706 policy cohort audit', '',
             f"Audit started (UTC): {audit['created_at_utc']}", '',
             '33703 was selected because its 3,207 local 2024 claim records rank second among '
             'Pinellas-linked ZIPs, after 33706 (4,060). It is the largest available comparison by claim count.', '',
             'Scope: Florida, reported ZIP, policy effective date >= January 1 of the cohort year and '
             '< January 1 of the next year; Pinellas filter is startswith(censusGeoid,\'12103\'). '
             'Counts are policy records, not policyCount sums, unique properties or calendar-year exposure.', '',
             '33703 uses newly downloaded pages and separate verification queries. 33706 uses the prior '
             'successful audit responses, copied here after hash validation, plus revalidated cached cohorts.', '',
             '| ZIP | Effective year | Downloaded | API Pinellas | ZIP-only | Missing GEOID | Missing share | Outside Pinellas | Invalid GEOID | IDs reconcile |',
             '|---|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for e in sorted(audit['cohorts'], key=lambda e: (e['year'], e['zip'])):
        r = e['reconciliation']
        g = r.get('geography', {})
        c = g.get('counts', {})
        pct = f"{g['missing_share_pct']:.2f}%" if g.get('missing_share_pct') is not None else 'unavailable'
        lines.append(f"| {e['zip']} | {e['year']} | {e.get('local', {}).get('count', 'unavailable')} | "
                     f"{e['api_pinellas'].get('count', 'unavailable')} | {e['api_zip_only'].get('count', 'unavailable')} | "
                     f"{c.get('missing', 'unavailable')} | {pct} | {c.get('outside_pinellas', 'unavailable')} | "
                     f"{c.get('invalid', 'unavailable')} | {'yes' if r['verified'] else 'UNRESOLVED'} |")
    lines += ['', 'Missing means null, empty or whitespace GEOID; outside Pinellas means a valid 12-digit '
              'GEOID with another county prefix. Malformed nonempty values remain separately unresolved.', '',
              'Snapshot dates (row asOfDate, not request time):']
    for e in audit['cohorts']:
        dates = {k: e.get(k, {}).get('snapshots', {}) for k in ('local', 'api_pinellas', 'api_zip_only')}
        lines.append(f"- ZIP {e['zip']}, {e['year']}: {json.dumps(dates, sort_keys=True)}")
    audit['year_comparisons'] = []
    for year in (2023, 2024):
        pair = [e for e in audit['cohorts'] if e['year'] == year]
        dates = [set(e.get(k, {}).get('snapshots', {})) for e in pair
                 for k in ('local', 'api_pinellas', 'api_zip_only')]
        comparable = all(len(d) == 1 and d == dates[0] for d in dates) and all(e['reconciliation']['verified'] for e in pair)
        comparison = {'year': year, 'snapshots_and_ids_verified': comparable}
        if comparable:
            shares = {e['zip']: e['reconciliation']['geography']['missing_share_pct'] for e in pair}
            comparison['missing_share_difference_pp_33703_minus_33706'] = shares['33703'] - shares['33706']
            lines.append(f"\n{year}: snapshots match; 33703 minus 33706 missing-GEOID share is "
                         f"{comparison['missing_share_difference_pp_33703_minus_33706']:+.2f} percentage points.")
        else:
            lines.append(f'\n{year}: cross-ZIP interpretation remains unresolved because snapshot or ID verification failed.')
        audit['year_comparisons'].append(comparison)
    verified = all(c['snapshots_and_ids_verified'] for c in audit['year_comparisons'])
    audit['recommendation'] = ('A staged rollout of this ingestion/geography audit is justified, with ZIP/year snapshot and ID gates. '
        'A broader exposure or claims-rate rollout is not justified: two selected ZIPs do not establish county coverage '
        'or representative missingness, and null GEOIDs do not establish county membership.' if verified else
        'Defer broader rollout until unresolved API, snapshot or ID checks are resolved.')
    lines += ['', '**Recommendation:** ' + audit['recommendation'], '',
              'Matching asOfDate labels do not prove an immutable source revision. This is a same-source '
              'OpenFEMA reconciliation, not independent validation of insurance coverage, contract semantics or claim frequency.', '',
              'Request failures and unresolved checks:']
    failures = [f"- Download request attempt {r['attempt']}: {r['error']} ({r['url']})"
                for r in audit['download_requests'] if 'error' in r]
    for e in audit['cohorts']:
        if 'download_error' in e:
            failures.append(f"- {e['zip']} {e['year']} download: {e['download_error']}")
        for k in ('api_pinellas', 'api_zip_only'):
            failures.extend(f"- {e['zip']} {e['year']} {k} attempt failed: {error}"
                            for error in e[k].get('attempt_errors', []))
            if e[k].get('status') != 'verified':
                failures.append(f"- {e['zip']} {e['year']} {k} unresolved: {e[k].get('error')}")
    lines += failures or ['- None. All requested count, ID, snapshot and geography checks were verified.']
    after = {name: digest(root / name) for name in before}
    audit['preservation'] = {'sha256_before': before, 'sha256_after': after, 'all_unchanged': before == after}
    if before != after:
        raise ValueError('Protected files changed during audit')
    lines += ['', f'Preservation: both dashboards and all {len(before)} protected pre-existing files passed SHA-256 checks. '
              'Full API responses, downloaded pages, ID differences, classified extra records, request URLs and hashes '
              'are retained in this folder and evidence.json.']
    (output / 'evidence.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    (output / 'comparison.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(Path(__file__).resolve().parents[1], args.output.resolve())
