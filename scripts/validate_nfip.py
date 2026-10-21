"""RiskMap | Validate the original FEMA NFIP Pinellas County claims export.

Run from VS Code with Python 3. No third-party packages required.
Raw data is never modified. Report is saved to reports/nfip_quality_report.txt.
"""
from collections import Counter
from csv import DictReader
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'data' / 'raw' / 'NFIP_Claims_Pinellas.csv'
REPORT = ROOT / 'reports' / 'nfip_quality_report.txt'

if not SOURCE.is_file():
    raise SystemExit(f'Missing dataset: {SOURCE}\nCheck the filename and data/raw folder.')

counts = Counter()
years = Counter()
missing = Counter()
ids = set()
paid = Decimal('0')
columns = []
with SOURCE.open('r', newline='', encoding='utf-8-sig') as handle:
    reader = DictReader(handle)
    columns = reader.fieldnames or []
    required = {'id', 'state', 'countyCode', 'yearOfLoss', 'dateOfLoss',
                'reportedZipCode', 'censusGeoid', 'originalConstructionDate',
                'amountPaidOnBuildingClaim', 'amountPaidOnContentsClaim',
                'amountPaidOnIncreasedCostOfComplianceClaim'}
    if not required.issubset(columns):
        raise SystemExit(f'Missing required columns: {sorted(required - set(columns))}')

    for row in reader:
        counts['records'] += 1
        if row['state'] != 'FL' or row['countyCode'] != '12103':
            counts['outside_pinellas'] += 1
        identifier = row['id']
        if not identifier or identifier in ids:
            counts['missing_or_duplicate_ids'] += 1
        else:
            ids.add(identifier)
        yr = row['yearOfLoss'].strip()
        if yr.isdigit():
            years[int(yr)] += 1
        else:
            counts['invalid_loss_year'] += 1
        for field in ('reportedZipCode', 'censusGeoid', 'dateOfLoss',
                      'originalConstructionDate', 'amountPaidOnBuildingClaim',
                      'amountPaidOnContentsClaim', 'amountPaidOnIncreasedCostOfComplianceClaim'):
            if not row[field].strip():
                missing[field] += 1
        construction = row['originalConstructionDate'][:4]
        if construction.isdigit() and (int(construction) < 1800 or int(construction) > date.today().year):
            counts['suspicious_construction_year'] += 1
        for field in ('amountPaidOnBuildingClaim', 'amountPaidOnContentsClaim',
                      'amountPaidOnIncreasedCostOfComplianceClaim'):
            value = row[field].strip()
            if value:
                try:
                    paid += Decimal(value)
                except InvalidOperation:
                    counts['invalid_payment_values'] += 1

lines = [
    'RiskMap | FEMA NFIP Pinellas County data quality check',
    f'Source: {SOURCE.name}',
    'Source coverage: NFIP flood insurance claims only (not all property claims)',
    f'Records: {counts["records"]:,}',
    f'Columns: {len(columns)}',
    f'Outside Pinellas: {counts["outside_pinellas"]:,}',
    f'Missing or duplicate IDs: {counts["missing_or_duplicate_ids"]:,}',
    f'Invalid loss years: {counts["invalid_loss_year"]:,}',
    f'Suspicious construction years (<1800 or future): {counts["suspicious_construction_year"]:,}',
    f'Invalid payment values: {counts["invalid_payment_values"]:,}',
    f'Sum of available gross claim-payment fields (building + contents + ICC): ${paid:,.2f}',
    'NOTE: Gross payments are historical nominal dollars; missing values are not assumed to be zero.',
    'NOTE: Claim counts alone are NOT flood risk rates. Policy exposure denominators are needed.',
    'NOTE: FEMA latitude/longitude are generalized, not exact property locations.',
    '', 'Missing values in selected fields:',
]
lines += [f'  {field}: {number:,}' for field, number in sorted(missing.items())]
lines += ['', 'Claims by year of loss:']
lines += [f'  {year}: {number:,}' for year, number in sorted(years.items())]
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('\n'.join(lines[:15]))
print(f'\nFull report saved to: {REPORT}')
