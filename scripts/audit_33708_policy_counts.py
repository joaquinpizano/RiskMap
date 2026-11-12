"""2024 ZIP 33708 ID, source-snapshot, geography and policyCount audit."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from audit_policy_cohorts import API, FIELDS, PREFIX, compare, digest, fetch_cohort, local_cohort, protected_files
from compare_policy_zip_audits import geography
from download_nfip_policies import download_year
from screen_policy_zip_counts import SNAPSHOT


def policy_counts(rows):
    total, valid, missing, invalid = 0, 0, [], []
    for row in rows:
        value = row.get('policyCount')
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append({'id': row['id'], 'policyCount': value})
            continue
        try:
            n = Decimal(str(value))
            if isinstance(value, bool) or not n.is_finite() or n <= 0 or n != n.to_integral_value():
                raise ValueError('policyCount must be a finite positive integer')
        except (InvalidOperation, ValueError):
            invalid.append({'id': row['id'], 'policyCount': value})
            continue
        total += int(n)
        valid += 1
    return {'row_count': len(rows), 'valid_policy_count_rows': valid, 'sum_valid_policy_count': total,
            'missing_policy_count_rows': len(missing), 'invalid_policy_count_rows': len(invalid),
            'sum_is_complete': not missing and not invalid, 'missing': missing, 'invalid': invalid}


def group_rows(zip_rows, included_ids):
    by_id = {row['id']: row for row in zip_rows}
    excluded = [r for r in zip_rows if r['id'] not in included_ids]
    classified = geography(excluded)
    groups = {'included': [r for r in zip_rows if r['id'] in included_ids]}
    for label, keys in (('excluded_missing_geoid', ('missing',)),
                        ('excluded_outside_pinellas', ('outside_pinellas',)),
                        ('excluded_other', ('invalid', 'pinellas'))):
        groups[label] = [by_id[r['id']] for key in keys for r in classified['records'][key]]
    assert sum(len(rows) for rows in groups.values()) == len(zip_rows)
    return groups


def run(root, output):
    if output.exists():
        raise ValueError('Use a new output folder; existing evidence is never overwritten')
    protected = protected_files(root, output)
    screen_folder = root / 'reports/policy_zip_screening_2024_2026-11-11'
    screen_path = screen_folder / 'evidence.json'
    screening = json.loads(screen_path.read_text())
    prior = next(r for r in screening['results'] if r['summary']['zip'] == '33708')
    for query in prior['queries'].values():
        for attempt in query['attempts']:
            if 'response_file' in attempt:
                path = screen_folder / 'responses/33708' / attempt['response_file']
                if digest(path) != attempt['sha256']:
                    raise ValueError('Saved screening response hash changed')
    output.mkdir(parents=True)
    audit = {'created_at_utc': datetime.now(timezone.utc).isoformat(), 'zip': '33708', 'effective_year': 2024,
             'target_snapshot': SNAPSHOT, 'screening': {'path': str(screen_path.relative_to(root)),
             'sha256': digest(screen_path), 'result': prior}, 'download_requests': []}
    requests_folder = output / 'download_requests'
    requests_folder.mkdir()

    def request(params):
        url = API + '?' + urlencode(params)
        for attempt in (1, 2):
            record = {'url': url, 'params': params, 'attempt': attempt,
                      'requested_at_utc': datetime.now(timezone.utc).isoformat()}
            audit['download_requests'].append(record)
            try:
                with urlopen(Request(url, headers={'User-Agent': 'RiskMap Policy Count Audit/1.0'}), timeout=25) as response:
                    raw = response.read()
                path = requests_folder / f'response_{len(audit["download_requests"]):03d}.json'
                path.write_bytes(raw)
                record.update(response_file=str(path.relative_to(output)), sha256=digest(path))
                data = json.loads(raw)
                if not isinstance(data.get('NfipPolicies'), list):
                    raise ValueError('Missing NfipPolicies array')
                return data
            except (OSError, ValueError) as error:
                record['error'] = f'{type(error).__name__}: {error}'
                print(f'Download attempt {attempt}: {record["error"]}', flush=True)
                if attempt == 2:
                    raise

    local, ids, local_rows = {'snapshots': {}, 'count': 0}, set(), []
    try:
        download_year(2024, output / 'downloaded', 10000, request=request, zip_code='33708')
        local, ids = local_cohort(root, 2024, '33708', output / 'downloaded/2024')
        audit['downloaded_cohort'] = local
        local_rows = [r for p in sorted((output / 'downloaded/2024').glob('page_*.json'))
                      for r in json.loads(p.read_text())['records']]
    except (OSError, ValueError, KeyError) as error:
        audit['download_error'] = f'{type(error).__name__}: {error}'
    api_folder = output / 'api'
    api_folder.mkdir()
    filter_text = (f"propertyState eq 'FL' and {PREFIX} and policyEffectiveDate ge '2024-01-01' "
                   "and policyEffectiveDate lt '2025-01-01' and reportedZipCode eq '33708'")
    p, prows, pids = fetch_cohort(filter_text, 2024, True, api_folder, '33708', fields=FIELDS + ',policyCount')
    z, zrows, zids = fetch_cohort(filter_text.replace(PREFIX + ' and ', ''), 2024, False,
                                 api_folder, '33708', fields=FIELDS + ',policyCount')
    audit.update(api_pinellas=p, api_zip_only=z)
    audit['download_vs_pinellas'] = compare(local, ids, p, pids)
    audit['download_vs_zip_only'] = compare(local, ids, z, zids)
    target_match = (all(set(r.get('snapshots', {})) == {SNAPSHOT} for r in (local, p, z))
                    and p.get('status') == z.get('status') == 'verified')
    audit['target_snapshot_verified'] = target_match
    audit['id_reconciliation'] = {'download_only_vs_pinellas': sorted(ids - pids),
        'pinellas_only_vs_download': sorted(pids - ids), 'pinellas_absent_from_zip_only': sorted(pids - zids)}
    id_match = False
    if p.get('status') == z.get('status') == 'verified':
        zip_pinellas_ids = {r['id'] for r in zrows if str(r.get('censusGeoid') or '').startswith('12103')}
        audit['id_reconciliation']['pinellas_vs_zip_subset_symmetric_difference'] = sorted(pids ^ zip_pinellas_ids)
        id_match = ids == pids == zip_pinellas_ids and pids <= zids
        audit['id_reconciliation']['excluded_ids'] = sorted(zids - pids)
    audit['id_reconciliation']['verified'] = target_match and id_match
    if target_match and id_match:
        groups = group_rows(zrows, pids)
        audit['groups'] = {name: {'statistics': policy_counts(rows), 'records': rows} for name, rows in groups.items()}
        audit['zip_only_policy_counts'] = policy_counts(zrows)
        audit['downloaded_policy_counts'] = policy_counts(local_rows)
        local_by_id = {r['id']: r for r in local_rows}
        p_by_id = {r['id']: r for r in prows}
        audit['included_policy_count_value_mismatches'] = [r['id'] for r in groups['included']
            if r.get('policyCount') != p_by_id[r['id']].get('policyCount')
            or r.get('policyCount') != local_by_id[r['id']].get('policyCount')]
        audit['screening_agreement'] = {'zip_only': z['count'] == prior['summary']['zip_only_count'],
                                       'pinellas': p['count'] == prior['summary']['pinellas_count']}
        assert sum(g['statistics']['sum_valid_policy_count'] for g in audit['groups'].values()) == audit['zip_only_policy_counts']['sum_valid_policy_count']
    lines = ['# ZIP 33708 — 2024 effective-year policy audit', '', f"Retrieved (UTC): {audit['created_at_utc']}", '',
        "Scope: propertyState = FL, reportedZipCode = 33708, policyEffectiveDate >= 2024-01-01 and < 2025-01-01. "
        "Pinellas filter: startswith(censusGeoid,'12103'). Existing screening evidence was reused and hash-checked; "
        'new full records were needed for IDs, GEOIDs and policyCount.', '',
        f"Downloaded rows: {audit.get('downloaded_cohort', {}).get('count', 'unavailable')}; "
        f"FEMA Pinellas rows: {p.get('count', 'unavailable')}; FEMA ZIP-only rows: {z.get('count', 'unavailable')}.", '',
        f"Target September 8, 2026 snapshot verified across all records: **{target_match}**. "
        f"Exact downloaded/FEMA Pinellas/ZIP-only Pinellas-subset IDs reconcile: **{target_match and id_match}**.", '',
        'Observed row asOfDate distributions:',
        f"- Downloaded: {local.get('snapshots', {})}", f"- FEMA Pinellas: {p.get('snapshots', {})}",
        f"- FEMA ZIP-only: {z.get('snapshots', {})}", '']
    if 'groups' in audit:
        lines += ['| Group | Rows | Sum valid policyCount | Missing counts | Invalid counts | Sum complete |',
                  '|---|---:|---:|---:|---:|---|']
        stats = [(k, v['statistics']) for k, v in audit['groups'].items()] + [('ZIP-only total', audit['zip_only_policy_counts'])]
        for name, s in stats:
            lines.append(f"| {name} | {s['row_count']:,} | {s['sum_valid_policy_count']:,} | {s['missing_policy_count_rows']} | {s['invalid_policy_count_rows']} | {s['sum_is_complete']} |")
        extra = z['count'] - p['count']
        lines += ['', f"Excluded: {extra:,} rows ({100 * extra / z['count']:.2f}% of ZIP-only rows). "
                  f"Matches prior screening counts: {audit['screening_agreement']}.", '',
                  f"Included policyCount values agree across downloaded, FEMA Pinellas and ZIP-only records: "
                  f"{not audit['included_policy_count_value_mismatches']}."]
    else:
        lines += ['Classification and policyCount reconciliation remain unresolved because complete, target-snapshot ID reconciliation failed.']
    lines += ['', 'Definitions: included rows are the FEMA Pinellas-filtered IDs. Among excluded rows, missing GEOID means null, '
              'empty or whitespace; outside Pinellas means a valid 12-digit GEOID with a county prefix other than 12103; '
              'other contains malformed/unexpected GEOIDs or valid Pinellas GEOIDs absent from the filtered query.', '',
              'policyCount is accepted only as a finite positive integer (numeric strings allowed; booleans rejected). '
              'Null/blank values are missing; zero, negative, fractional, nonnumeric or nonfinite values are invalid. '
              'Sums omit missing/invalid values and are explicitly partial if flagged; unknowns are not silently counted as zero. '
              'Empty groups have zero rows and a zero sum.', '',
              'These are effective-year policy record and reported policyCount totals, not unique properties, contracts, '
              'calendar-year exposure or validated claim-frequency denominators. Matching asOfDate labels do not guarantee '
              'an immutable database revision. Missing GEOIDs do not establish county membership.', '', 'Request failures and unresolved checks:']
    errors = [r['error'] for r in audit['download_requests'] if 'error' in r]
    errors += [error for r in (p,z) for error in r.get('attempt_errors', [])]
    errors += [audit[k] for k in ('download_error',) if k in audit]
    lines += ['- '+e for e in errors] or ['- None.']
    after = {name: digest(root / name) for name in protected}
    audit['preservation'] = {'sha256_before': protected, 'sha256_after': after, 'all_unchanged': protected == after}
    if protected != after:
        raise ValueError('Protected files changed during audit')
    lines += ['', 'Both dashboards and all prior reports passed before/after SHA-256 checks. Raw downloaded pages, '
              'API responses, exact filters, attempts, classified records, count anomalies and hashes are saved alongside this report.']
    (output / 'evidence.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    (output / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(Path(__file__).resolve().parents[1], args.output.resolve())
