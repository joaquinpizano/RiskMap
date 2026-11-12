"""Read-only inputs for the fixed 2024 claims comparison and 33708 exposure panel."""
import csv
from decimal import Decimal
import json
from pathlib import Path

from scripts.audit_policy_cohorts import digest

ZIPS = ('33703', '33706', '33708')


def claims_comparison(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        rows = [r for r in csv.DictReader(stream) if r['year_of_loss'] == '2024' and r['reported_zip_code'] in ZIPS]
    if len(rows) != 3 or {r['reported_zip_code'] for r in rows} != set(ZIPS):
        raise ValueError('Expected exactly one 2024 summary for each comparison ZIP.')
    result = []
    for r in sorted(rows, key=lambda r:r['reported_zip_code']):
        n, missing, reported = (int(r[k]) for k in ('claim_records', 'records_with_no_payment_values', 'records_with_any_payment_reported'))
        dollars = Decimal(r['gross_reported_payments_usd'])
        if min(n, missing, reported) < 0 or missing + reported != n or not dollars.is_finite():
            raise ValueError('Claim/payment completeness counts do not reconcile.')
        result.append({'ZIP':r['reported_zip_code'], 'Claim records':n,
            'All gross payment components missing':missing,
            'Nominal reported payments ($)':float(dollars)})
    return result


def noncondo_exposure(root):
    root = Path(root)
    folder = root/'reports/noncondo_cancellation_gap_addendum_33708_2024_2026-11-11'
    addendum = json.loads((folder/'evidence.json').read_text(encoding='utf-8'))
    if addendum['scope'] != {'zip':'33708','calendar_year':2024,'coverage':'N','geography':'Pinellas GEOID prefix 12103'}:
        raise ValueError('Unexpected exposure addendum scope.')
    for name, expected in addendum['input_sha256'].items():
        if digest(root/name) != expected:
            raise ValueError('Exposure evidence comes from different saved inputs.')
    source = json.loads((root/'reports/noncondo_denominator_validation_33708_2024_2026-11-11/calculation_evidence.json').read_text(encoding='utf-8'))
    baseline = Decimal(addendum['baseline_record_years'])
    alternative = Decimal(addendum['termination_only_record_years'])
    delta = Decimal(addendum['delta_record_years'])
    if (not all(v.is_finite() for v in (baseline,alternative,delta)) or baseline <= 0 or delta < 0
            or abs(alternative-baseline-delta) > Decimal('1e-20')
            or baseline != Decimal(source['scenarios'][0]['record_years'])
            or alternative != Decimal(source['confirmed_term_only_excluding_flagged'])):
        raise ValueError('Exposure scenario values do not reconcile.')
    if source['snapshot'] != '2026-09-08T00:00:00.000Z':
        raise ValueError('Unexpected exposure source snapshot.')
    return {'baseline':float(baseline),'termination_only':float(alternative),'delta':float(delta),
            'percent_change':float(delta*100/baseline),'date_exceptions':len(source['flagged_date_records']),
            'snapshot':source['snapshot'][:10]}
