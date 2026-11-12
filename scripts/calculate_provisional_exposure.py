"""Reproduce provisional calendar-year exposure from RiskMap cached policy pages.

No third-party packages or network access required. Raw files are read-only.
This measures record duration and policyCount-weighted duration, not unique
properties, validated contracts, or claim frequency.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

CODES = {
    'A': 'Condominium association', 'H': 'RCBAP high-rise master policy',
    'L': 'RCBAP low-rise master policy', 'N': 'Not a condominium',
    'U': 'Individual condominium unit',
}

def parse_date(value):
    if not isinstance(value, str) or not value:
        raise ValueError('Missing or invalid date')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Date must have a timezone')
    return result.astimezone(timezone.utc)

def validate_row(row, zip_code, prefix, allow_missing_geoid=False):
    if row.get('propertyState') != 'FL':
        raise ValueError('Unexpected state')
    if row.get('reportedZipCode') != zip_code:
        raise ValueError('Unexpected ZIP')
    geoid = str(row.get('censusGeoid') or '')
    missing_geoid = row.get('censusGeoid') is None or not str(row.get('censusGeoid')).strip()
    if not (allow_missing_geoid and missing_geoid) and (len(geoid) != 12 or not geoid.isdigit() or not geoid.startswith(prefix)):
        raise ValueError('Invalid or unexpected Census GEOID')
    if row.get('condominiumCoverageTypeCode') not in CODES:
        raise ValueError('Unknown condominium coverage code')
    try:
        units = Decimal(str(row.get('policyCount')))
    except InvalidOperation as error:
        raise ValueError('Invalid policyCount') from error
    if not units.is_finite() or units <= 0 or units != units.to_integral_value():
        raise ValueError('policyCount must be a positive integer')
    effective = parse_date(row.get('policyEffectiveDate'))
    termination = parse_date(row.get('policyTerminationDate'))
    if termination <= effective:
        raise ValueError('Invalid term interval')
    raw = row.get('cancellationDateOfFloodPolicy')
    cancellation = parse_date(raw) if raw else None
    return effective, termination, cancellation, int(units)

def overlap_seconds(effective, stop, year):
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    delta = min(stop, end) - max(effective, start)
    return max(0, delta.days * 86400 + delta.seconds + delta.microseconds / 1_000_000)

def analyze(rows, year=2024, zip_code='33706', prefix='12103', allow_missing_geoid=False):
    seconds_in_year = Decimal(str((datetime(year + 1, 1, 1) - datetime(year, 1, 1)).total_seconds()))
    totals = {c: {'overlapping_records': 0, 'record_seconds': Decimal(0),
                  'unit_seconds': Decimal(0), 'exception_record_seconds': Decimal(0),
                  'exception_unit_seconds': Decimal(0), 'exception_records': 0}
              for c in CODES}
    seen, audit, exceptions, snapshots = set(), Counter(), [], set()
    for row in rows:
        identifier = row.get('id')
        if identifier is None or identifier in seen:
            raise ValueError('Missing or duplicate ID')
        seen.add(identifier)
        effective, termination, cancellation, units = validate_row(row, zip_code, prefix, allow_missing_geoid)
        snapshots.add(row.get('asOfDate'))
        code = row['condominiumCoverageTypeCode']
        group = totals[code]
        if cancellation and cancellation < effective:
            audit['date_exceptions'] += 1
            seconds = Decimal(str(overlap_seconds(effective, termination, year)))
            group['exception_record_seconds'] += seconds
            group['exception_unit_seconds'] += seconds * units
            group['exception_records'] += 1
            exceptions.append({k: row.get(k) for k in (
                'id', 'policyEffectiveDate', 'policyTerminationDate',
                'cancellationDateOfFloodPolicy', 'policyCount',
                'condominiumCoverageTypeCode', 'endorsementEffectiveDate')})
            continue
        stop = min(termination, cancellation) if cancellation else termination
        seconds = Decimal(str(overlap_seconds(effective, stop, year)))
        if not seconds:
            audit['no_elapsed_coverage'] += 1
            continue
        audit['overlapping_records'] += 1
        group['overlapping_records'] += 1
        group['record_seconds'] += seconds
        group['unit_seconds'] += seconds * units
    if len(seen) != sum(audit.values()):
        raise AssertionError('Record reconciliation failed')
    output_groups = []
    def years(seconds):
        return format(seconds / seconds_in_year, '.8f')
    for code, group in sorted(totals.items()):
        output_groups.append({
            'code': code, 'description': CODES[code],
            'overlapping_records': group['overlapping_records'],
            'record_years_excluding_exceptions': years(group['record_seconds']),
            'insured_unit_years_excluding_exceptions': years(group['unit_seconds']),
            'exception_records': group['exception_records'],
            'added_record_years_if_flagged_cancellation_ignored': years(group['exception_record_seconds']),
            'added_insured_unit_years_if_flagged_cancellation_ignored': years(group['exception_unit_seconds']),
        })
    return {
        'status': 'PROVISIONAL - not approved for claims rates',
        'calendar_year': year, 'days_in_year': int(seconds_in_year / 86400),
        'zip': zip_code, 'county_geoid_prefix': prefix,
        'source_as_of_dates': sorted(str(x) for x in snapshots),
        'unique_records': len(seen),
        'record_reconciliation': {k: audit[k] for k in (
            'overlapping_records', 'no_elapsed_coverage', 'date_exceptions')},
        'groups': output_groups, 'date_exceptions': exceptions,
        'limitations': [
            'GEOID-screened ZIP cohort only; missing or misassigned GEOIDs are not assessed.',
            'Unique record IDs do not establish unique contracts, buildings, or insured units.',
            'Individual-unit and master coverage can overlap; do not add groups as unique exposure.',
            'Ignoring flagged cancellations is a sensitivity scenario, not a correction or a proven upper bound.',
            'Excluded exceptions do not imply known zero coverage.',
            'Transaction behavior and claims counting compatibility remain unresolved.',
            'Earlier-cohort overlap is not independently verified by this offline script.',
            'No claims rates or dashboard changes are produced.',
        ],
    }

def load_inputs(root, year, zip_code, prefix):
    rows, evidence, effective_years = [], [], set()
    for query_path in sorted(root.rglob('query.json')):
        config = json.loads(query_path.read_text(encoding='utf-8'))
        filter_text = config.get('filter', '')
        if f"reportedZipCode eq '{zip_code}'" not in filter_text:
            continue
        if f"startswith(censusGeoid,'{prefix}')" not in filter_text:
            continue
        folder = query_path.parent
        report_path = folder / 'quality_report.json'
        if not report_path.is_file():
            raise ValueError(f'Missing quality report: {folder}')
        report = json.loads(report_path.read_text(encoding='utf-8'))
        cohort_year = report['effective_year']
        if cohort_year not in (year - 1, year):
            continue
        if report.get('download_complete') is not True:
            print(f'Skipping incomplete download: {folder}')
            continue
        if cohort_year in effective_years:
            raise ValueError(f'Multiple matching folders for {cohort_year}; choose a narrower input root')
        effective_years.add(cohort_year)
        pages = sorted(folder.glob('page_*.json'))
        if not pages or [p.name for p in pages] != [f'page_{n:06d}.json' for n in range(len(pages))]:
            raise ValueError(f'Missing or nonconsecutive pages: {folder}')
        batch, hashes = [], []
        for page in pages:
            raw = page.read_bytes()
            payload = json.loads(raw)
            params = payload['params']
            actual_filter = params.get('$filter', '')
            if actual_filter != filter_text and not actual_filter.startswith(filter_text + ' and id gt '):
                raise ValueError(f'Unexpected page filter: {page}')
            if params.get('$select') != config['fields']:
                raise ValueError(f'Unexpected fields: {page}')
            page_rows = payload['records']
            if not page_rows and page != pages[-1]:
                raise ValueError('Empty page before final page')
            batch.extend(page_rows)
            hashes.append({'page': page.name, 'sha256': hashlib.sha256(raw).hexdigest()})
        if json.loads(pages[-1].read_text())['records']:
            raise ValueError('Missing terminal empty page')
        expected = report['unique_records']
        if (report.get('download_complete') is not True or len(batch) != expected
            or report['initial_server_count'] != expected or report['final_server_count'] != expected
            or len({r['id'] for r in batch}) != expected):
            raise ValueError(f'Input count verification failed: {folder}')
        if any(parse_date(r['policyEffectiveDate']).year != cohort_year for r in batch):
            raise ValueError('Record outside effective-year cohort')
        rows.extend(batch)
        evidence.append({'folder': str(folder.relative_to(root)), 'effective_year': cohort_year,
                         'records': len(batch), 'page_hashes': hashes})
    if effective_years != {year - 1, year}:
        raise ValueError('Both prior-year and target-year completed ZIP cohorts are required')
    return rows, evidence

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root', type=Path, default=Path(__file__).resolve().parents[1] / 'data/raw')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'reports/provisional_exposure_33706_2024.json')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; use --output with a new filename to preserve it')
    rows, evidence = load_inputs(args.input_root, 2024, '33706', '12103')
    result = analyze(rows)
    result['input_evidence'] = evidence
    result['generated_at_utc'] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2)
    print('PROVISIONAL 2024 EXPOSURE - ZIP 33706')
    print('Unique records:', result['unique_records'])
    print('Reconciliation:', result['record_reconciliation'])
    for group in result['groups']:
        print(f"{group['code']}: {group['record_years_excluding_exceptions']} record-years; "
              f"{group['insured_unit_years_excluding_exceptions']} insured-unit-years")
    print('Saved:', args.output)
    print('Provisional only. No claims rates calculated.')

if __name__ == '__main__':
    main()
