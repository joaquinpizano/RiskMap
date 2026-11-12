"""Read-only cohort reconciliation against OpenFEMA; writes only a new audit folder.

Standard library only. API row counts are not policyCount sums or exposure.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = 'https://www.fema.gov/api/open/v3/NfipPolicies'
PREFIX = "startswith(censusGeoid,'12103')"
FIELDS = 'id,asOfDate,propertyState,reportedZipCode,censusGeoid,policyEffectiveDate'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshots(rows):
    values = Counter(row.get('asOfDate') for row in rows)
    if not values or any(not key for key in values):
        raise ValueError('Missing source snapshot dates')
    return dict(sorted(values.items()))


def validate_rows(rows, year, screened, zip_code='33706'):
    ids = [row.get('id') for row in rows]
    if any(value is None for value in ids) or len(set(ids)) != len(ids):
        raise ValueError('Missing or duplicate record IDs')
    for row in rows:
        effective = datetime.fromisoformat(row['policyEffectiveDate'].replace('Z', '+00:00'))
        if (row.get('propertyState') != 'FL' or row.get('reportedZipCode') != zip_code
                or effective.year != year):
            raise ValueError('Record outside requested state, ZIP or effective year')
        if screened and not str(row.get('censusGeoid') or '').startswith('12103'):
            raise ValueError('Record outside requested GEOID prefix')
    snapshots(rows)
    return set(ids)


def local_cohort(root, year, zip_code='33706', folder=None):
    folder = folder or root / f'data/raw/nfip_policy_{zip_code}_{year}/{year}'
    query = json.loads((folder / 'query.json').read_text())
    quality = json.loads((folder / 'quality_report.json').read_text())
    expected_filter = (f"propertyState eq 'FL' and {PREFIX} "
                       f"and policyEffectiveDate ge '{year}-01-01' "
                       f"and policyEffectiveDate lt '{year + 1}-01-01' "
                       f"and reportedZipCode eq '{zip_code}'")
    if query['api'] != API or query['filter'] != expected_filter:
        raise ValueError('Unexpected cached query')
    rows, pages, last_id = [], sorted(folder.glob('page_*.json')), None
    for number, path in enumerate(pages):
        payload = json.loads(path.read_text())
        params = payload['params']
        expected_page_filter = expected_filter
        if last_id is not None:
            expected_page_filter += f' and id gt {last_id}'
        if (path.name != f'page_{number:06d}.json'
                or params['$filter'] != expected_page_filter
                or params['$select'] != query['fields']
                or params['$top'] != query['page_size'] or params['$orderby'] != 'id'):
            raise ValueError('Cached page query or sequence mismatch')
        for row in payload['records']:
            if last_id is not None and int(row['id']) <= last_id:
                raise ValueError('Cached IDs are not increasing')
            last_id = int(row['id'])
        rows.extend(payload['records'])
        if not payload['records'] and number != len(pages) - 1:
            raise ValueError('Unexpected intermediate empty page')
    ids = validate_rows(rows, year, True, zip_code)
    dates = snapshots(rows)
    if (not pages or json.loads(pages[-1].read_text())['records']
            or quality.get('download_complete') is not True
            or any(quality[key] != len(ids) for key in
                   ('initial_server_count', 'final_server_count', 'unique_records'))
            or sorted(dates) != quality['as_of_dates']):
        raise ValueError('Cached completeness or snapshot checks failed')
    return {'year': year, 'filter': expected_filter, 'count': len(rows),
            'snapshots': dates, 'retrieved_at': quality['retrieved_at'],
            'files_sha256': {str(p.relative_to(root)): digest(p)
                             for p in [folder / 'query.json', folder / 'quality_report.json', *pages]}}, ids


def fetch_cohort(filter_text, year, screened, folder, zip_code='33706', fields=FIELDS):
    params = {'$filter': filter_text, '$select': fields, '$orderby': 'id',
              '$top': 10000, '$count': 'true'}
    url = API + '?' + urlencode(params)
    result = {'filter': filter_text, 'url': url,
              'requested_at_utc': datetime.now(timezone.utc).isoformat()}
    try:
        result['attempt_errors'] = []
        for attempt in range(2):
            try:
                with urlopen(Request(url, headers={'User-Agent': 'RiskMap Cohort Audit/1.0'}), timeout=25) as response:
                    raw = response.read()
                break
            except (OSError, TimeoutError) as error:
                result['attempt_errors'].append(f'{type(error).__name__}: {error}')
                if attempt == 1:
                    raise
        name = f'openfema_{year}_{"pinellas" if screened else "zip_only"}.json'
        (folder / name).write_bytes(raw)
        result.update(response_file=name, response_sha256=hashlib.sha256(raw).hexdigest())
        data = json.loads(raw)
        rows = data['NfipPolicies']
        count = data['metadata']['count']
        if isinstance(count, bool) or not isinstance(count, int) or count != len(rows):
            raise ValueError('Response incomplete or count invalid; snapshot coverage cannot be established')
        ids = validate_rows(rows, year, screened, zip_code)
        result.update(status='verified', count=count, snapshots=snapshots(rows), metadata=data['metadata'])
        return result, rows, ids
    except Exception as error:
        result.update(status='unresolved', error=f'{type(error).__name__}: {error}')
        return result, [], set()


def compare(local, local_ids, remote, remote_ids):
    if remote.get('status') != 'verified':
        return {'status': 'unresolved', 'reason': 'API result unavailable or incomplete'}
    # A shared single asOfDate is necessary for interpreting differences. Multiple
    # dates are deliberately not treated as one immutable snapshot.
    if len(local['snapshots']) != 1 or set(local['snapshots']) != set(remote['snapshots']):
        return {'status': 'unresolved', 'reason': 'Source snapshots differ or are mixed; no completeness inference'}
    return {'status': 'same_as_of_date', 'count_delta': remote['count'] - local['count'],
            'local_ids_absent_remotely': len(local_ids - remote_ids),
            'remote_ids_absent_locally': len(remote_ids - local_ids)}


def protected_files(root, output):
    paths = [root / 'dashboard.py', root / 'dashboard_pilot.py']
    paths += [p for p in (root / 'reports').rglob('*') if p.is_file() and output not in p.parents]
    paths += [p for p in (root / 'data/raw').glob('nfip_policy_33706_*/*/*') if p.is_file()]
    return {str(p.relative_to(root)): digest(p) for p in paths}


def run(root, output):
    if output.exists():
        raise ValueError('Choose a new output folder; existing audit outputs are preserved')
    protected = protected_files(root, output)
    locals_by_year = {year: local_cohort(root, year) for year in (2023, 2024)}
    output.mkdir(parents=True)
    audit = {'created_at_utc': datetime.now(timezone.utc).isoformat(), 'endpoint': API,
             'scope': 'FL, ZIP 33706, effective-year [Jan 1, next Jan 1); row counts, not insured units',
             'cohorts': [], 'prior_geography_report': {
                 'path': 'reports/nfip_policy_geoid_coverage_33706_2023_2024.txt',
                 'status': 'Existing narrative only; no ZIP-only raw responses saved with that report'}}
    lines = ['# Policy cohort count audit', '',
             'ZIP 33706, Florida; effective-year cohorts, not calendar-year exposure or unique properties.',
             f"Audit retrieval (UTC): {audit['created_at_utc']}",
             '[OpenFEMA source endpoint](https://www.fema.gov/api/open/v3/NfipPolicies). '
             'Exact filters, successful response bodies, metadata and SHA-256 hashes are saved alongside this report; '
             'failed requests retain their error details.', '',
             '| Effective year | Local Pinellas rows | API Pinellas rows | API ZIP-only rows | Snapshot comparison |',
             '|---|---:|---:|---:|---|']
    findings, all_agree = [], True
    for year, (local, local_ids) in locals_by_year.items():
        pinellas, _, pinellas_ids = fetch_cohort(local['filter'], year, True, output)
        zip_filter = local['filter'].replace(PREFIX + ' and ', '')
        zip_only, zip_rows, zip_ids = fetch_cohort(zip_filter, year, False, output)
        comparison = compare(local, local_ids, pinellas, pinellas_ids)
        zip_comparison = compare(local, local_ids, zip_only, zip_ids)
        entry = {'local': local, 'api_pinellas': pinellas, 'api_zip_only': zip_only,
                 'pinellas_comparison': comparison, 'zip_snapshot_comparison': zip_comparison}
        agree = (comparison.get('status') == 'same_as_of_date'
                 and comparison['count_delta'] == 0
                 and comparison['local_ids_absent_remotely'] == 0
                 and comparison['remote_ids_absent_locally'] == 0
                 and zip_comparison.get('status') == 'same_as_of_date'
                 and not (local_ids - zip_ids))
        if zip_comparison.get('status') == 'same_as_of_date' and comparison.get('status') == 'same_as_of_date':
            classified_ids = {r['id'] for r in zip_rows if str(r.get('censusGeoid') or '').startswith('12103')}
            nulls = sum(r.get('censusGeoid') is None for r in zip_rows)
            blanks = sum(r.get('censusGeoid') == '' for r in zip_rows)
            other = len(zip_rows) - len(classified_ids) - nulls - blanks
            entry['geography_reconciliation'] = {'pinellas_rows': len(classified_ids),
                'null_geoid': nulls, 'blank_geoid': blanks, 'other_geoid': other,
                'pinellas_ids_match_separate_query': classified_ids == pinellas_ids}
            agree = agree and classified_ids == pinellas_ids
            findings.append(f"- {year}: ZIP-only includes {nulls:,} null, {blanks:,} blank and {other:,} other-prefix GEOIDs; "
                            f"Pinellas subset IDs {'match' if classified_ids == pinellas_ids else 'DO NOT match'} the separate query.")
        all_agree = all_agree and agree
        audit['cohorts'].append(entry)
        label = 'same single asOfDate' if zip_comparison.get('status') == comparison.get('status') == 'same_as_of_date' else 'UNRESOLVED'
        lines.append(f"| {year} | {local['count']:,} | {pinellas.get('count', 'unavailable')} | {zip_only.get('count', 'unavailable')} | {label} |")
        findings.append(f"- {year}: local snapshots {local['snapshots']}; API Pinellas {pinellas.get('snapshots', pinellas.get('error'))}; "
                        f"API ZIP-only {zip_only.get('snapshots', zip_only.get('error'))}. Pinellas comparison: {comparison}.")
    audit['recommendation'] = ('Supports one additional ZIP as a bounded ingestion/geography test; not validated exposure or claim frequency.'
                               if all_agree else 'Defer expansion based on validation: API/snapshot/count/ID reconciliation remains unresolved. A further ZIP would be exploratory only.')
    after = {name: digest(root / name) for name in protected}
    audit['preservation'] = {'sha256_before': protected, 'sha256_after': after, 'all_unchanged': protected == after}
    if protected != after:
        raise ValueError('Protected input changed during audit')
    lines += ['', *findings, '', '**Decision:** ' + audit['recommendation'], '',
              'The prior geography report claims ZIP-only counts of 4,936 (2023) and 5,514 (2024), '
              'with 16 and 599 null GEOIDs. Those are historical narrative claims; this audit independently '
              'rechecks available API data rather than treating the narrative as a saved API response.', '',
              'Remaining limits: matching row asOfDate values do not prove an immutable database revision. '
              'This checks the same OpenFEMA source, not an independent coverage-in-force benchmark. '
              'Null GEOIDs do not establish county membership; correct county assignment, contract/renewal semantics, '
              'calendar-year exposure and claim frequency remain unresolved. No differences are attributed to '
              'missing downloads when API evidence or source snapshots do not support that conclusion.', '',
              'Both dashboards, all pre-existing reports and both cached cohorts passed before/after SHA-256 preservation checks.']
    (output / 'evidence.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    (output / 'audit.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New directory; must not already exist')
    args = parser.parse_args()
    run(Path(__file__).resolve().parents[1], args.output.resolve())
