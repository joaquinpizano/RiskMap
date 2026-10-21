"""RiskMap: summarize historical NFIP claim payments by HUD ZIP-to-county screening status.

Standard library only. Run from RiskMap/scripts. Does not modify source files.
Uses 2025 Q4 ZIP-to-county crosswalk classifications from nfip_zip_hud_audit.csv.
A ZIP-county relationship does not verify exact historical claim locations.
"""
from collections import defaultdict
from csv import DictReader, DictWriter
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
CLAIMS = ROOT / 'data' / 'raw' / 'NFIP_Claims_Pinellas.csv'
AUDIT = ROOT / 'data' / 'processed' / 'nfip_zip_hud_audit.csv'
OUTPUT = ROOT / 'data' / 'processed'
REPORTS = ROOT / 'reports'
FIELDS = ('amountPaidOnBuildingClaim', 'amountPaidOnContentsClaim',
          'amountPaidOnIncreasedCostOfComplianceClaim')
STATUSES = ('hud_pinellas_link', 'hud_other_counties_only',
            'not_in_hud_crosswalk', 'missing_zip', 'malformed_zip')
ZIP_PATTERN = re.compile(r'^(\d{5})(?:-\d{4})?$')


def blank():
    return {'claim_records': 0, 'positive_payment_claims': 0,
            'records_with_no_payment_values': 0, 'gross_reported_payments_usd': Decimal('0')}


def add(t, payment, has_values):
    t['claim_records'] += 1
    t['positive_payment_claims'] += int(payment > 0)
    t['records_with_no_payment_values'] += int(not has_values)
    t['gross_reported_payments_usd'] += payment


def write_csv(path, groups, keys):
    columns = list(keys) + ['claim_records', 'positive_payment_claims',
                             'records_with_no_payment_values', 'gross_reported_payments_usd']
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for group_key, values in sorted(groups.items()):
            if not isinstance(group_key, tuple):
                group_key = (group_key,)
            data = dict(zip(keys, group_key))
            data.update({k: f'{v:.2f}' if isinstance(v, Decimal) else v
                         for k, v in values.items()})
            writer.writerow(data)


def main():
    for path in (CLAIMS, AUDIT):
        if not path.is_file():
            raise SystemExit(f'Missing required input: {path}')

    audit = {}
    expected = {}
    with AUDIT.open(newline='', encoding='utf-8-sig') as f:
        for row in DictReader(f):
            zip_code = row['reported_zip_5'].strip()
            if zip_code in audit:
                raise SystemExit(f'Duplicate ZIP in audit: {zip_code}')
            audit[zip_code] = row['hud_status'].strip()
            expected[zip_code] = int(row['claim_count'])

    by_status = defaultdict(blank)
    by_zip = defaultdict(blank)
    by_year_status = defaultdict(blank)
    seen = defaultdict(int)
    total = 0
    with CLAIMS.open(newline='', encoding='utf-8-sig') as f:
        reader = DictReader(f)
        required = {'reportedZipCode', 'yearOfLoss', 'state', 'countyCode', *FIELDS}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f'Missing FEMA columns: {sorted(missing)}')
        for row in reader:
            if row['state'].strip() != 'FL' or row['countyCode'].strip() != '12103':
                raise SystemExit('Claim outside source county/state; investigate.')
            raw_zip = row['reportedZipCode'].strip()
            if not raw_zip:
                zip5 = 'UNKNOWN'
            else:
                match = ZIP_PATTERN.fullmatch(raw_zip)
                zip5 = match.group(1) if match else 'MALFORMED'
            status = audit.get(zip5)
            if status is None:
                raise SystemExit(f'ZIP {zip5!r} not present in HUD audit. Re-run match_nfip_hud.py.')
            if status not in STATUSES:
                raise SystemExit(f'Unexpected HUD status: {status!r}')
            payment = Decimal('0')
            has_values = False
            for field in FIELDS:
                value = row[field].strip()
                if value:
                    try:
                        payment += Decimal(value)
                    except InvalidOperation:
                        raise SystemExit(f'Invalid payment: {field}={value!r}')
                    has_values = True
            year = row['yearOfLoss'].strip()
            add(by_status[status], payment, has_values)
            add(by_zip[(status, zip5)], payment, has_values)
            add(by_year_status[(year, status)], payment, has_values)
            seen[zip5] += 1
            total += 1

    discrepancies = [(z, n, seen[z]) for z, n in expected.items() if seen[z] != n]
    if discrepancies:
        raise SystemExit(f'ZIP counts disagree with HUD audit: {discrepancies[:5]}')
    if total != sum(expected.values()):
        raise SystemExit('Total claim count disagrees with HUD audit.')

    OUTPUT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT / 'nfip_payments_by_hud_status.csv', by_status, ('hud_status',))
    write_csv(OUTPUT / 'nfip_payments_by_zip_hud.csv', by_zip, ('hud_status', 'reported_zip_5'))
    write_csv(OUTPUT / 'nfip_payments_by_year_hud_status.csv', by_year_status,
              ('year_of_loss', 'hud_status'))

    gross = sum((v['gross_reported_payments_usd'] for v in by_status.values()), Decimal('0'))
    excluded = gross - by_status['hud_pinellas_link']['gross_reported_payments_usd']
    lines = [
        'RiskMap | Historical NFIP payments by 2025 Q4 HUD ZIP-county status',
        f'Claims reconciled: {total:,}',
        f'Gross reported payments: ${gross:,.2f}',
        '',
    ]
    for status in STATUSES:
        v = by_status[status]
        lines.append(f"{status}: {v['claim_records']:,} claims | ${v['gross_reported_payments_usd']:,.2f}")
    lines += [
        '', f'Payments outside Pinellas-linked ZIP group: ${excluded:,.2f}',
        'NOTE: These are historical nominal NFIP claim payments, not flood-risk rates.',
        'NOTE: Missing payment fields are not treated as reported zero payments.',
        'NOTE: HUD 2025 Q4 ZIP-county association does not verify historical claim location.',
        'NOTE: No original FEMA claims were removed or modified.',
    ]
    (REPORTS / 'nfip_geographic_payment_report.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    print('\nSaved:')
    for path in ('nfip_payments_by_hud_status.csv', 'nfip_payments_by_zip_hud.csv',
                 'nfip_payments_by_year_hud_status.csv'):
        print(' ', OUTPUT / path)
    print(' ', REPORTS / 'nfip_geographic_payment_report.txt')


if __name__ == '__main__':
    main()
