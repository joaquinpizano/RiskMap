"""Audit 2024 ZIP 33706 claims alongside provisional policy exposure.

Standard library only. Does not change raw data or calculate claims rates.
Run from RiskMap after calculate_provisional_exposure.py.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

PAYMENTS = ('amountPaidOnBuildingClaim', 'amountPaidOnContentsClaim',
            'amountPaidOnIncreasedCostOfComplianceClaim')
CODES = ('A', 'H', 'L', 'N', 'U')

def fingerprint(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def normalize_zip(value):
    value = (value or '').strip()
    if re.fullmatch(r'\d{5}', value):
        return value
    if re.fullmatch(r'\d{5}-\d{4}', value):
        return value[:5]
    if re.fullmatch(r'\d{5}\.0', value):
        return value[:5]
    return None

def parse_date(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timestamp lacks timezone')
    return result.astimezone(timezone.utc)

def numeric(value):
    if value is None or not str(value).strip():
        return None
    try:
        result = Decimal(str(value).strip())
    except InvalidOperation as error:
        raise ValueError(f'Invalid numeric value: {value!r}') from error
    if not result.is_finite():
        raise ValueError('Nonfinite numeric value')
    return result

def positive_integer(value):
    return value is not None and value > 0 and value == value.to_integral_value()

def payments(row):
    values = [numeric(row[field]) for field in PAYMENTS]
    # Missing components remain diagnosed separately; this is a sum of known values.
    reported = sum((x for x in values if x is not None), Decimal(0))
    return values, reported

def new_group():
    return {'claim_records': 0, 'complete_payment_records': 0,
            'partial_payment_records': 0, 'all_payment_components_missing': 0,
            'positive_reported_payment_records': 0, 'zero_complete_payment_records': 0,
            'negative_reported_payment_records': 0,
            'sum_of_reported_gross_components_usd': Decimal(0),
            'complete_record_gross_total_usd': Decimal(0),
            'sum_policy_count': Decimal(0), 'policy_count_invalid': 0,
            'policy_count_above_one': 0, 'number_of_units_invalid': 0,
            'number_of_units_above_one': 0, 'policy_count_vs_number_of_units_differences': 0,
            'events': {}, 'as_of_dates': Counter()}

def audit_claims(rows):
    groups = {c: new_group() for c in CODES}
    checks = Counter()
    checks['all_source_rows'] = 0
    source_ids = set()
    total = Decimal(0)
    snapshots = Counter()
    excluded = []
    for row in rows:
        checks['all_source_rows'] += 1
        identifier = (row.get('id') or '').strip()
        if not identifier or identifier in source_ids:
            raise ValueError('Missing or duplicate source claim ID')
        source_ids.add(identifier)
        if row.get('state') != 'FL' or row.get('countyCode') != '12103':
            raise ValueError('Unexpected state/county in source claims file')
        snapshots[row.get('asOfDate') or 'MISSING'] += 1
        values, reported = payments(row)
        total += reported
        if normalize_zip(row.get('reportedZipCode')) != '33706':
            continue
        try:
            loss_date = parse_date(row.get('dateOfLoss') or '')
        except (ValueError, TypeError):
            checks['target_zip_invalid_loss_dates_all_years'] += 1
            continue
        if loss_date.year != 2024:
            continue
        checks['target_zip_2024_records'] += 1
        if (row.get('yearOfLoss') or '').strip() != '2024':
            raise ValueError('Loss date and yearOfLoss disagree in target cohort')
        if row['reportedZipCode'].strip() != '33706':
            checks['normalized_zip_variant_records'] += 1
        geoid = (row.get('censusGeoid') or '').strip()
        if not geoid:
            reason = 'missing_geoid'
        elif not re.fullmatch(r'\d{12}', geoid):
            reason = 'malformed_geoid'
        elif not geoid.startswith('12103'):
            reason = 'other_county_geoid'
        else:
            reason = None
        if reason:
            checks[reason] += 1
            excluded.append({'id': identifier, 'reason': reason,
                             'condominium_code': row.get('condominiumCoverageTypeCode'),
                             'sum_of_reported_gross_components_usd': reported,
                             'missing_payment_components': sum(v is None for v in values)})
            continue
        checks['matched_claim_records'] += 1
        code = (row.get('condominiumCoverageTypeCode') or '').strip()
        if code not in groups:
            raise ValueError(f'Unknown condominium code: {code!r}')
        group = groups[code]
        group['claim_records'] += 1
        group['as_of_dates'][row.get('asOfDate') or 'MISSING'] += 1
        missing = sum(v is None for v in values)
        if missing == 0:
            group['complete_payment_records'] += 1
            group['complete_record_gross_total_usd'] += reported
            group['zero_complete_payment_records'] += int(reported == 0)
        elif missing == len(PAYMENTS):
            group['all_payment_components_missing'] += 1
        else:
            group['partial_payment_records'] += 1
        group['sum_of_reported_gross_components_usd'] += reported
        group['positive_reported_payment_records'] += int(reported > 0)
        group['negative_reported_payment_records'] += int(reported < 0)
        policy_count = numeric(row.get('policyCount'))
        unit_count = numeric(row.get('numberOfUnits'))
        if positive_integer(policy_count):
            group['sum_policy_count'] += policy_count
            group['policy_count_above_one'] += int(policy_count > 1)
        else:
            group['policy_count_invalid'] += 1
        if positive_integer(unit_count):
            group['number_of_units_above_one'] += int(unit_count > 1)
        else:
            group['number_of_units_invalid'] += 1
        if positive_integer(policy_count) and positive_integer(unit_count) and policy_count != unit_count:
            group['policy_count_vs_number_of_units_differences'] += 1
        event = (row.get('floodEvent') or '').strip() or 'NOT REPORTED'
        event_group = group['events'].setdefault(event, {'claim_records': 0,
            'sum_of_reported_gross_components_usd': Decimal(0)})
        event_group['claim_records'] += 1
        event_group['sum_of_reported_gross_components_usd'] += reported
    if checks['target_zip_2024_records'] != checks['matched_claim_records'] + len(excluded):
        raise AssertionError('Geographic reconciliation failed')
    for group in groups.values():
        if group['claim_records'] != sum(group[k] for k in ('complete_payment_records',
                'partial_payment_records', 'all_payment_components_missing')):
            raise AssertionError('Payment reconciliation failed')
    return {'source_rows': checks['all_source_rows'],
            'source_reported_gross_total_usd': total,
            'source_as_of_dates': dict(snapshots), 'checks': dict(checks),
            'geography_exclusions': excluded, 'groups': groups}

def compare(claims, exposure):
    if (exposure.get('calendar_year') != 2024 or exposure.get('zip') != '33706'
        or exposure.get('county_geoid_prefix') != '12103'):
        raise ValueError('Exposure report scope does not match claims audit')
    policy_dates = set(exposure['source_as_of_dates'])
    claim_dates = set(claims['source_as_of_dates'])
    aligned = claim_dates == policy_dates and 'MISSING' not in claim_dates
    by_code = {g['code']: g for g in exposure['groups']}
    if set(by_code) != set(CODES):
        raise ValueError('Missing or unexpected exposure groups')
    rows = []
    for code in CODES:
        group = dict(claims['groups'][code])
        policy_group = by_code[code]
        for field in ('record_years_excluding_exceptions', 'insured_unit_years_excluding_exceptions'):
            value = numeric(policy_group[field])
            if value is None or value < 0:
                raise ValueError('Invalid exposure duration')
        group.update({'condominium_code': code,
            'provisional_record_years': policy_group['record_years_excluding_exceptions'],
            'provisional_insured_unit_years': policy_group['insured_unit_years_excluding_exceptions'],
            'excluded_policy_date_exceptions': policy_group['exception_records'],
            'claim_frequency_per_1000_policy_years': None,
            'paid_loss_per_policy_year': None})
        rows.append(group)
    return {'status': 'COMPATIBILITY AUDIT - rates not validated',
            'scope': {'calendar_year': 2024, 'zip': '33706', 'county_geoid_prefix': '12103'},
            'source_dates_align': aligned,
            'claims_audit': {k: v for k, v in claims.items() if k != 'groups'},
            'comparison_by_code': rows,
            'exposure_record_reconciliation': exposure['record_reconciliation'],
            'limitations': [
                'The comparison joins aggregates by calendar year, ZIP and condominium code; it is not a record-level policy/claim link.',
                'Claims IDs and policy IDs identify source rows, not shared contract or property keys.',
                'Record duration is not yet validated as unique contract exposure; transaction interpretation is unresolved.',
                'Do not weight claim counts or dollar payments by policyCount or numberOfUnits.',
                'Same asOfDate does not certify identical processing histories or final settlement.',
                'Missing payment components are unknown, not reported zero.',
                'Gross payment sums preserve signed reported components; recovery and net-payment fields are not combined.',
                'Missing claim GEOIDs and missing policy GEOIDs cannot be assigned to matched exposure.',
                'Master and individual-unit coverage may overlap; groups are kept separate.',
                'Rates are left null until counting and exposure semantics are validated.',
            ]}

def json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(type(value).__name__)

def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--claims', type=Path, default=root / 'data/raw/NFIP_Claims_Pinellas.csv')
    parser.add_argument('--exposure', type=Path, default=root / 'reports/provisional_exposure_33706_2024.json')
    parser.add_argument('--output', type=Path, default=root / 'reports/claims_policy_compatibility_33706_2024.json')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; use --output with a new filename to preserve it')
    if args.output.resolve() in (args.claims.resolve(), args.exposure.resolve()):
        parser.error('Output must differ from input paths')
    exposure = json.loads(args.exposure.read_text(encoding='utf-8'))
    with args.claims.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        required = {'id', 'state', 'countyCode', 'reportedZipCode', 'censusGeoid',
            'yearOfLoss', 'dateOfLoss', 'asOfDate', 'condominiumCoverageTypeCode',
            'policyCount', 'numberOfUnits', 'floodEvent', *PAYMENTS}
        if required - set(reader.fieldnames or []):
            raise ValueError('Missing required claims columns: ' + str(sorted(required - set(reader.fieldnames or []))))
        claims = audit_claims(reader)
    result = compare(claims, exposure)
    result['input_sha256'] = {'claims': fingerprint(args.claims), 'exposure': fingerprint(args.exposure)}
    result['generated_at_utc'] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, default=json_default)
    print('CLAIMS / POLICY COMPATIBILITY - ZIP 33706, 2024')
    print('Source claims:', claims['source_rows'])
    print('Matched claims:', claims['checks'].get('matched_claim_records', 0))
    print('Geography exclusions:', len(claims['geography_exclusions']))
    print('Source as-of dates align:', result['source_dates_align'])
    for group in result['comparison_by_code']:
        print(f"{group['condominium_code']}: {group['claim_records']} claim records; "
              f"{group['all_payment_components_missing']} with all gross payment components missing")
    print('Saved:', args.output)
    print('Rates remain unvalidated. Dashboard unchanged.')

if __name__ == '__main__':
    main()
