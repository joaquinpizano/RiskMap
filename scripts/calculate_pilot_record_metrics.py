"""Exploratory 2024 ZIP 33706 claims per recorded coverage-year.

These are aggregate record-based ratios, not validated unique-contract or
property risk rates. No raw data or existing reports are changed.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

FAQ = 'https://agents.floodsmart.gov/flood-maps-and-data/faqs-about-nfip-data'
CODES = {'A': 'Condominium association', 'H': 'High-rise master policy',
         'L': 'Low-rise master policy', 'N': 'Not a condominium',
         'U': 'Individual condominium unit'}

def number(value):
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError('Missing or invalid numeric input') from error
    if not result.is_finite():
        raise ValueError('Nonfinite input')
    return result

def ratio(numerator, denominator, scale=1):
    denominator = number(denominator)
    if denominator < 0:
        raise ValueError('Negative exposure')
    if denominator == 0:
        return None
    return format(number(numerator) * scale / denominator, '.8f')

def build_metrics(comparison, exposure):
    expected = {'calendar_year': 2024, 'zip': '33706', 'county_geoid_prefix': '12103'}
    if comparison.get('scope') != expected:
        raise ValueError('Unexpected comparison scope')
    if (exposure.get('calendar_year'), exposure.get('zip'), exposure.get('county_geoid_prefix')) != (2024, '33706', '12103'):
        raise ValueError('Unexpected exposure scope')
    if comparison.get('source_dates_align') is not True:
        raise ValueError('Source dates must align for this pilot')
    if comparison.get('exposure_record_reconciliation') != exposure.get('record_reconciliation'):
        raise ValueError('Exposure reconciliation differs between reports')
    policy_groups = {g['code']: g for g in exposure['groups']}
    claim_groups = {g['condominium_code']: g for g in comparison['comparison_by_code']}
    if len(exposure['groups']) != 5 or len(comparison['comparison_by_code']) != 5 or set(policy_groups) != set(CODES) or set(claim_groups) != set(CODES):
        raise ValueError('Missing, duplicate or unexpected condominium groups')
    rows = []
    for code, label in CODES.items():
        c, e = claim_groups[code], policy_groups[code]
        baseline = number(e['record_years_excluding_exceptions'])
        if baseline != number(c['provisional_record_years']):
            raise ValueError('Exposure duration mismatch')
        extra = number(e['added_record_years_if_flagged_cancellation_ignored'])
        if extra < 0:
            raise ValueError('Invalid sensitivity duration')
        counts = [c[k] for k in ('claim_records', 'complete_payment_records',
            'partial_payment_records', 'all_payment_components_missing', 'positive_reported_payment_records')]
        if any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in counts):
            raise ValueError('Invalid claim count')
        if c['claim_records'] != sum(c[k] for k in ('complete_payment_records',
                'partial_payment_records', 'all_payment_components_missing')):
            raise ValueError('Claim/payment count mismatch')
        if c['positive_reported_payment_records'] > c['claim_records']:
            raise ValueError('Positive-payment count exceeds claim records')
        rows.append({
            'code': code, 'description': label,
            'claim_records': c['claim_records'],
            'records_with_positive_reported_payments': c['positive_reported_payment_records'],
            'records_with_all_gross_payment_fields_missing': c['all_payment_components_missing'],
            'records_with_partial_gross_payments': c['partial_payment_records'],
            'record_years_excluding_flagged_dates': str(baseline),
            'claim_records_per_1000_record_years': ratio(c['claim_records'], baseline, 1000),
            'positive_reported_payment_records_per_1000_record_years': ratio(c['positive_reported_payment_records'], baseline, 1000),
            'sum_of_reported_gross_components_usd': c['sum_of_reported_gross_components_usd'],
            'reported_gross_components_usd_per_record_year': ratio(c['sum_of_reported_gross_components_usd'], baseline),
            'excluded_policy_date_exceptions': e['exception_records'],
            'sensitivity_if_flagged_cancellations_ignored': {
                'record_years': str(baseline + extra),
                'claim_records_per_1000_record_years': ratio(c['claim_records'], baseline + extra, 1000),
                'reported_gross_components_usd_per_record_year': ratio(c['sum_of_reported_gross_components_usd'], baseline + extra),
            },
            'small_denominator_note': 'Interpret cautiously: fewer than 10 record-years.' if baseline < 10 else None,
        })
    return {
        'status': 'EXPLORATORY RECORD-BASED PILOT - not validated contract/property risk',
        'scope': expected, 'source_as_of_dates': exposure['source_as_of_dates'],
        'metrics_by_condominium_code': rows,
        'method': 'Claim rows / clipped recorded policy-duration years; condominium codes kept separate.',
        'documentation': {
            'source_url': FAQ,
            'checked_on': '2026-10-23',
            'findings': [
                'FEMA describes separate renewal records and effective/termination date selection for in-force coverage.',
                'FEMA does not supply a shared public identifier for linking individual claims and policy records.',
            ],
            'inference': 'Integrating recorded coverage intervals supports exploratory aggregate record-year ratios. The FAQ does not certify this v3 pilot as unique-contract exposure or resolve all endorsement behavior.',
        },
        'limitations': [
            'Not the percentage or probability of properties flooded; multiple loss events can generate claims in one year.',
            'Do not call record-years unique contracts, properties, households or people.',
            'Do not combine code groups into unique-property exposure.',
            'Four missing-GEOID claims are excluded; missing policy GEOIDs are outside the downloaded cohort.',
            'Nineteen policy cancellation-before-effective exceptions remain unresolved.',
            'Sensitivity ignores flagged cancellation dates only; it is not a correction or confidence interval.',
            'Payment sums omit unknown components and are not final losses or dollars disbursed during 2024.',
            '2024-loss payments are reported through the source as-of date, not limited to payment transactions in 2024.',
            'Small master-policy groups are unstable and should not be ranked against larger groups.',
            'Not suitable for predicted flood risk, pricing or countywide conclusions.',
        ],
    }

def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison', type=Path, default=root / 'reports/claims_policy_compatibility_33706_2024.json')
    parser.add_argument('--exposure', type=Path, default=root / 'reports/provisional_exposure_33706_2024.json')
    parser.add_argument('--output', type=Path, default=root / 'reports/pilot_record_metrics_33706_2024.json')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; use --output with a new filename to preserve it')
    comparison = json.loads(args.comparison.read_text(encoding='utf-8'))
    exposure_bytes = args.exposure.read_bytes()
    expected_hash = comparison.get('input_sha256', {}).get('exposure')
    if not expected_hash or hashlib.sha256(exposure_bytes).hexdigest() != expected_hash:
        raise ValueError('Exposure file differs from the file used for the comparison. Rebuild the comparison first.')
    result = build_metrics(comparison, json.loads(exposure_bytes))
    result['input_sha256'] = {'comparison': hashlib.sha256(args.comparison.read_bytes()).hexdigest(),
                              'exposure': expected_hash}
    result['generated_at_utc'] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2)
    print('EXPLORATORY 2024 RECORD METRICS - ZIP 33706')
    for row in result['metrics_by_condominium_code']:
        print(f"{row['code']}: {row['claim_records_per_1000_record_years']} claim records per 1,000 record-years")
    print('Saved:', args.output)
    print('Not a percentage of properties flooded. Dashboard unchanged.')

if __name__ == '__main__':
    main()
