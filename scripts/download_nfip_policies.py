"""Download a Census-GEOID-screened Pinellas NFIP policy cohort.
Standard library only. Run from RiskMap; existing claims files are never changed.
Raw pages are cached atomically. Re-running resumes verified pages.
This is ingestion and quality control, NOT an exposure estimator.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = 'https://www.fema.gov/api/open/v3/NfipPolicies'
FIELDS = ('id,propertyState,reportedZipCode,censusGeoid,policyEffectiveDate,'
          'policyTerminationDate,cancellationDateOfFloodPolicy,policyCount,'
          'condominiumCoverageTypeCode,asOfDate,endorsementEffectiveDate,policyTermIndicator')

def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temp.replace(path)

def fetch(params, attempts=4):
    url = API + '?' + urlencode(params)
    for attempt in range(attempts):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'RiskMap Research/1.0'}), timeout=60) as response:
                data = json.load(response)
            if not isinstance(data.get('NfipPolicies'), list):
                raise ValueError('FEMA response has no NfipPolicies array')
            return data
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
        except (URLError, TimeoutError, ConnectionError):
            if attempt == attempts - 1:
                raise
        time.sleep(min(2 ** attempt, 8))

def cohort_filter(year):
    return ("propertyState eq 'FL' and startswith(censusGeoid,'12103') "
            f"and policyEffectiveDate ge '{year}-01-01' "
            f"and policyEffectiveDate lt '{year + 1}-01-01'")

def date(value):
    if not value:
        return None
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result
    except ValueError:
        return None

def inspect(rows):
    counts = Counter()
    for row in rows:
        counts['records'] += 1
        if row.get('propertyState') != 'FL' or not str(row.get('censusGeoid') or '').startswith('12103'):
            counts['geography_failures'] += 1
        try:
            weight = Decimal(str(row.get('policyCount')))
            if not weight.is_finite() or weight <= 0 or weight != weight.to_integral_value():
                raise ValueError()
            counts['sum_policy_count'] += int(weight)
            counts['records_policy_count_above_one'] += int(weight > 1)
        except (InvalidOperation, ValueError):
            counts['invalid_policy_counts'] += 1
        start, end = date(row.get('policyEffectiveDate')), date(row.get('policyTerminationDate'))
        counts['missing_or_invalid_effective_dates'] += int(start is None)
        counts['missing_or_invalid_termination_dates'] += int(end is None)
        counts['invalid_term_intervals'] += int(start is not None and end is not None and end <= start)
        cancel_raw = row.get('cancellationDateOfFloodPolicy')
        cancel = date(cancel_raw)
        if cancel_raw:
            counts['records_with_cancellation'] += 1
            counts['invalid_cancellation_dates'] += int(cancel is None)
            counts['cancellation_before_effective'] += int(cancel is not None and start is not None and cancel < start)
    return dict(counts)

def download_year(year, root, page_size, max_pages=0, request=fetch, zip_code=None):
    folder = root / str(year)
    base = {'$filter': cohort_filter(year), '$select': FIELDS, '$orderby': 'id', '$top': page_size}
    if zip_code:
        base['$filter'] += f" and reportedZipCode eq '{zip_code}'"
    expected = request(dict(base, **{'$top': 1, '$count': 'true'})).get('metadata', {}).get('count')
    if expected is None:
        raise ValueError('FEMA did not return a record count; cannot verify completeness')
    expected = int(expected)
    config = {'api': API, 'filter': base['$filter'], 'fields': FIELDS, 'page_size': page_size}
    config_path = folder / 'query.json'
    if config_path.exists() and json.loads(config_path.read_text()) != config:
        raise ValueError(f'Cached query changed: use a new --output directory ({folder})')
    atomic_json(config_path, config)
    seen, totals, snapshots = set(), Counter(), set()
    last_id = None
    page_number = 0
    while True:
        params = dict(base)
        if last_id is not None:
            params['$filter'] += f' and id gt {last_id}'
        path = folder / f'page_{page_number:06d}.json'
        if path.exists():
            payload = json.loads(path.read_text())
            if payload['params'] != params:
                raise ValueError(f'Cache query mismatch: {path}')
            rows = payload['records']
        else:
            rows = request(params)['NfipPolicies']
            atomic_json(path, {'params': params, 'records': rows})
        if not rows:
            complete = True
            break
        for row in rows:
            identifier = int(row['id'])
            if identifier in seen or (last_id is not None and identifier <= last_id):
                raise ValueError('Duplicate or nonascending FEMA IDs; download halted')
            effective = date(row.get('policyEffectiveDate'))
            if effective is None or effective.year != year:
                raise ValueError('Record outside requested effective-year partition')
            seen.add(identifier)
            last_id = identifier
            snapshots.add(str(row.get('asOfDate')))
        totals.update(inspect(rows))
        page_number += 1
        print(f'{year}: {len(seen):,} / {expected:,} records', flush=True)
        if max_pages and page_number >= max_pages:
            complete = False
            break
    final_expected = None
    if complete:
        final_expected = int(request(dict(base, **{'$top': 1, '$count': 'true'}))['metadata']['count'])
    verified = complete and expected == final_expected == len(seen)
    report = {'effective_year': year, 'initial_server_count': expected,
              'final_server_count': final_expected, 'unique_records': len(seen),
              'download_complete': verified, 'as_of_dates': sorted(snapshots),
              'quality': dict(totals), 'retrieved_at': datetime.now(timezone.utc).isoformat(),
              'scope': 'FL records with Census GEOID prefix 12103; missing GEOIDs excluded by query',
              'exposure_ready': False,
              'limitations': ['Count agreement does not guarantee an immutable source snapshot.',
                              'County coverage requires an independent check for missing/misassigned GEOIDs.',
                              'Policy count measures insured units, including condominium units.',
                              'Transaction semantics and claims unit compatibility require review.',
                              'Effective-year partitions are not calendar-year exposure totals.']}
    atomic_json(folder / 'quality_report.json', report)
    if complete and not verified:
        raise ValueError(f'{year}: downloaded count differs from server count; see quality_report.json')
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', dest='zip_code', help='Optional five-digit ZIP to narrow a smoke test')
    parser.add_argument('--start-year', type=int, default=2009)
    parser.add_argument('--end-year', type=int, default=2026)
    parser.add_argument('--page-size', type=int, default=1000)
    parser.add_argument('--max-pages', type=int, default=0, help='Per-year smoke-test limit; 0 downloads all')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'data/raw/nfip_policies_geoid_pinellas')
    args = parser.parse_args()
    if not 2009 <= args.start_year <= args.end_year <= datetime.now().year:
        parser.error('Choose effective years from 2009 through the current year')
    if not 1 <= args.page_size <= 10000 or args.max_pages < 0:
        parser.error('page-size must be 1–10000; max-pages must be nonnegative')
    if args.zip_code and (len(args.zip_code) != 5 or not args.zip_code.isdigit()):
        parser.error("--zip must have five digits")
    reports = []
    for year in range(args.start_year, args.end_year + 1):
        reports.append(download_year(year, args.output, args.page_size, args.max_pages, zip_code=args.zip_code))
    atomic_json(args.output / 'download_summary.json', reports)
    print('Download checks complete. Exposure calculations remain pending.')

if __name__ == '__main__':
    main()
