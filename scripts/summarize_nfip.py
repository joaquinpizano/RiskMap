"""RiskMap: summarize Pinellas NFIP claims by loss year and reported ZIP code.

Run with Python 3; standard library only. Raw FEMA data is never changed.
Outputs are descriptive historical CLAIM summaries, not flood-risk rates.
"""
from collections import defaultdict
from csv import DictReader, DictWriter
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'data' / 'raw' / 'NFIP_Claims_Pinellas.csv'
OUTPUT = ROOT / 'data' / 'processed'
PAYMENT_FIELDS = (
    'amountPaidOnBuildingClaim',
    'amountPaidOnContentsClaim',
    'amountPaidOnIncreasedCostOfComplianceClaim',
)


def new_totals():
    return {'claim_records': 0, 'records_with_any_payment_reported': 0,
            'records_with_no_payment_values': 0, 'records_with_positive_payments': 0,
            'gross_reported_payments': Decimal('0')}


def add_record(totals, payment, has_reported):
    totals['claim_records'] += 1
    totals['records_with_any_payment_reported'] += int(has_reported)
    totals['records_with_no_payment_values'] += int(not has_reported)
    totals['records_with_positive_payments'] += int(payment > 0)
    totals['gross_reported_payments'] += payment


def write_summary(path, groups, key_field):
    columns = [key_field, 'claim_records', 'records_with_any_payment_reported',
               'records_with_no_payment_values', 'records_with_positive_payments',
               'gross_reported_payments_usd']
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for key in sorted(groups):
            totals = groups[key]
            writer.writerow({key_field: key,
                             'claim_records': totals['claim_records'],
                             'records_with_any_payment_reported': totals['records_with_any_payment_reported'],
                             'records_with_no_payment_values': totals['records_with_no_payment_values'],
                             'records_with_positive_payments': totals['records_with_positive_payments'],
                             'gross_reported_payments_usd': f"{totals['gross_reported_payments']:.2f}"})


def main():
    if not SOURCE.is_file():
        raise SystemExit(f'Missing source: {SOURCE}')
    by_year = defaultdict(new_totals)
    by_zip = defaultdict(new_totals)
    by_year_zip = defaultdict(new_totals)
    records = 0
    with SOURCE.open(newline='', encoding='utf-8-sig') as f:
        reader = DictReader(f)
        required = {'state', 'countyCode', 'yearOfLoss', 'reportedZipCode', *PAYMENT_FIELDS}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f'Missing columns: {sorted(missing)}')
        for row in reader:
            if row['state'] != 'FL' or row['countyCode'] != '12103':
                raise SystemExit('Unexpected record outside Pinellas; review source before analysis.')
            year = (row['yearOfLoss'] or '').strip()
            if not (year.isdigit() and 1900 <= int(year) <= 2026):
                raise SystemExit(f'Invalid yearOfLoss: {year!r}')
            zip_code = (row['reportedZipCode'] or '').strip()
            if not (len(zip_code) == 5 and zip_code.isdigit()):
                zip_code = 'UNKNOWN'
            payment = Decimal('0')
            has_reported = False
            for field in PAYMENT_FIELDS:
                value = (row[field] or '').strip()
                if value:
                    try:
                        payment += Decimal(value)
                    except InvalidOperation:
                        raise SystemExit(f'Invalid payment in {field}: {value!r}')
                    has_reported = True
            add_record(by_year[year], payment, has_reported)
            add_record(by_zip[zip_code], payment, has_reported)
            add_record(by_year_zip[(year, zip_code)], payment, has_reported)
            records += 1

    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_summary(OUTPUT / 'nfip_claims_by_year.csv', by_year, 'year_of_loss')
    write_summary(OUTPUT / 'nfip_claims_by_zip.csv', by_zip, 'reported_zip_code')
    # Write a two-column grouping without inventing a composite geographic ID.
    path = OUTPUT / 'nfip_claims_by_year_zip.csv'
    with path.open('w', newline='', encoding='utf-8') as f:
        fields = ['year_of_loss', 'reported_zip_code', 'claim_records',
                  'records_with_any_payment_reported', 'records_with_no_payment_values',
                  'records_with_positive_payments', 'gross_reported_payments_usd']
        writer = DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for (year, zip_code), t in sorted(by_year_zip.items()):
            writer.writerow({'year_of_loss': year, 'reported_zip_code': zip_code,
                             'claim_records': t['claim_records'],
                             'records_with_any_payment_reported': t['records_with_any_payment_reported'],
                             'records_with_no_payment_values': t['records_with_no_payment_values'],
                             'records_with_positive_payments': t['records_with_positive_payments'],
                             'gross_reported_payments_usd': f"{t['gross_reported_payments']:.2f}"})
    print(f'Processed {records:,} historical NFIP claim records.')
    print(f'Loss years: {len(by_year)}; reported ZIP categories: {len(by_zip)}')
    print(f"Gross reported payments: ${sum((t['gross_reported_payments'] for t in by_year.values()), Decimal('0')):,.2f}")
    print('Saved:')
    for name in ('nfip_claims_by_year.csv', 'nfip_claims_by_zip.csv', 'nfip_claims_by_year_zip.csv'):
        print(f'  {OUTPUT / name}')
    print('NOTE: Counts and dollars describe NFIP claims, not flood risk rates or all property losses.')
    print('NOTE: ZIP codes are reported values; validate inconsistent geographic fields before mapping.')


if __name__ == '__main__':
    main()
