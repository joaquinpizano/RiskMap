"""Reproduce saved 33706/33708 exposure offline, without writing any files.

Run: .venv-pilot/Scripts/python.exe scripts/verify_saved_exposure.py
PASS establishes saved-input integrity and computational reproducibility only;
it does not validate unique-contract exposure, county membership or claim rates.
"""
import json
from pathlib import Path
from urllib.parse import unquote

from audit_policy_cohorts import digest
from calculate_provisional_exposure import analyze, load_inputs
from compare_policy_zip_audits import geography

TARGET = '2026-09-08T00:00:00.000Z'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_snapshot(rows):
    require(all(row.get('asOfDate') == TARGET for row in rows), 'Missing or mismatched source snapshot')


def check_result(actual, saved):
    for key in ('groups', 'record_reconciliation', 'date_exceptions', 'unique_records', 'source_as_of_dates'):
        require(actual[key] == saved[key], f'Reproduced exposure differs: {key}')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def check_hash(root, name, expected):
    require(digest(root / name) == expected, f'Input hash changed: {name}')


def verify_33706(root):
    saved = read_json(root / 'reports/provisional_exposure_33706_2024.json')
    require((saved['zip'], saved['calendar_year'], saved['county_geoid_prefix']) == ('33706', 2024, '12103'),
            'Unexpected 33706 scope')
    for cohort in saved['input_evidence']:
        for item in cohort['page_hashes']:
            check_hash(root / 'data/raw' / cohort['folder'], item['page'], item['sha256'])
    rows, _ = load_inputs(root / 'data/raw', 2024, '33706', '12103')
    check_snapshot(rows)
    check_result(analyze(rows), saved)


def verify_33708(root):
    folder = root / 'reports/exposure_sensitivity_33708_2024_2026-11-11'
    saved = read_json(folder / 'evidence.json')
    require(not saved['cohort_verification_partial'] and not saved['issues'], '33708 exposure is partial or has unresolved input issues')
    require(saved['target_snapshot'] == TARGET, 'Unexpected target snapshot')
    check_hash(root, saved['prior_audit']['path'], saved['prior_audit']['sha256'])
    for name, expected in saved['reused_2024_included']['files_sha256'].items():
        check_hash(root, name, expected)
    prior_folder = (root / saved['prior_audit']['path']).parent
    prior = read_json(root / saved['prior_audit']['path'])
    for key in ('api_pinellas', 'api_zip_only'):
        check_hash(prior_folder / 'api', prior[key]['response_file'], prior[key]['response_sha256'])
    rows = [r for p in sorted((prior_folder / 'downloaded/2024').glob('page_*.json'))
            for r in read_json(p)['records']]
    counts = []
    for query in saved['requests']:
        require(query['status'] == 'verified', 'Unverified exposure input request')
        successful = None
        for attempt in query['attempts']:
            if 'path' not in attempt:
                continue
            check_hash(folder, attempt['path'], attempt['sha256'])
            if 'error' not in attempt:
                successful = read_json(folder / attempt['path'])
        require(successful is not None, 'No saved successful API response')
        meta, batch = successful['metadata'], successful['NfipPolicies']
        require(unquote(meta['filter']) == query['filter'], 'Response filter differs from request')
        require(meta['count'] == query['count'], 'Response count differs from evidence')
        check_snapshot(batch)
        if meta['top'] == 10000:
            require(len(batch) == meta['count'], 'Incomplete saved API response')
            require(all(r['propertyState'] == 'FL' and r['reportedZipCode'] == '33708' for r in batch),
                    'Exposure response has out-of-scope rows')
            rows.extend(batch)
        elif 'policyEffectiveDate eq null' in query['filter']:
            require(meta['count'] == 0, 'Unknown effective dates remain unresolved')
        if "policyEffectiveDate lt '2024-01-01'" in query['filter']:
            counts.append(meta['count'])
    require(len(counts) == 2 and counts[0] == counts[1], 'Earlier-term count reconciliation failed')
    check_snapshot(rows)
    require(len({r['id'] for r in rows}) == len(rows), 'Duplicate exposure source IDs')
    by_id = {r['id']: r for r in rows}
    geo = geography(rows)['records']
    confirmed = [by_id[r['id']] for r in geo['pinellas']]
    missing = [by_id[r['id']] for r in geo['missing']]
    for name, sample, allow_missing in (('confirmed_only', confirmed, False),
            ('missing_only', missing, True), ('plus_missing_geoid', confirmed + missing, True)):
        check_result(analyze(sample, zip_code='33708', allow_missing_geoid=allow_missing), saved[name])


def main():
    root = Path(__file__).resolve().parents[1]
    verify_33706(root)
    print('PASS: 33706 saved source hashes and exposure reproduced.')
    verify_33708(root)
    print('PASS: 33708 hashes, snapshots, earlier-term counts and all exposure scenarios reproduced.')
    print('Not verified: independent coverage benchmark, unique-contract/unit interpretation, or valid claim rates.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f'FAIL: {error}')
