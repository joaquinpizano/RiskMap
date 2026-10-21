"""RiskMap | Compare FEMA Pinellas NFIP claim ZIPs to the 2025 Q4 HUD-USPS ZIP-County crosswalk.

Uses only Python's standard library. Does not modify raw data.
HUD ZIP-county links reflect December 2025 addresses, NOT historical property locations.
"""
from collections import Counter, defaultdict
from csv import DictReader, DictWriter
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent.parent
CLAIMS = ROOT / 'data' / 'raw' / 'NFIP_Claims_Pinellas.csv'
HUD = ROOT / 'data' / 'raw' / 'ZIP-COUNTY_122025.xlsx'
OUTPUT = ROOT / 'data' / 'processed' / 'nfip_zip_hud_audit.csv'
REPORT = ROOT / 'reports' / 'nfip_hud_crosswalk_report.txt'
PINELLAS = '12103'
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def read_hud_rows(path):
    """Read first XLSX worksheet via streaming XML; no third-party packages needed."""
    with ZipFile(path) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            with archive.open('xl/sharedStrings.xml') as fh:
                tree = ET.parse(fh)
                for si in tree.getroot().iter(NS + 'si'):
                    strings.append(''.join(t.text or '' for t in si.iter(NS + 't')))
        with archive.open('xl/worksheets/sheet1.xml') as fh:
            context = ET.iterparse(fh, events=('end',))
            for _, element in context:
                if element.tag != NS + 'row':
                    continue
                cells = {}
                for cell in element.findall(NS + 'c'):
                    ref = cell.attrib.get('r', '')
                    col = re.match(r'[A-Z]+', ref)
                    if not col:
                        continue
                    kind = cell.attrib.get('t')
                    if kind == 'inlineStr':
                        val = ''.join(t.text or '' for t in cell.iter(NS + 't'))
                    else:
                        value = cell.find(NS + 'v')
                        val = value.text if value is not None and value.text else ''
                        if kind == 's' and val:
                            val = strings[int(val)]
                    cells[col.group()] = val.strip()
                yield cells
                element.clear()


def normalize_zip(value):
    value = (value or '').strip()
    if not value:
        return 'UNKNOWN', 'missing'
    if re.fullmatch(r'\d{5}', value):
        return value, 'five_digit'
    if re.fullmatch(r'\d{5}-\d{4}', value):
        return value[:5], 'zip_plus_four'
    return 'INVALID', 'malformed'


def main():
    for path in (CLAIMS, HUD):
        if not path.is_file():
            raise SystemExit(f'Missing required file: {path}')

    hud_counties = defaultdict(set)
    hud_pinellas_ratios = {}
    rows = read_hud_rows(HUD)
    headers = next(rows)
    if [headers.get(c, '').lower() for c in ('A', 'B')] != ['zip', 'geoid']:
        raise SystemExit('Unexpected HUD workbook structure: expected zip and geoid in columns A and B.')
    for r in rows:
        zip_code, geoid = r.get('A', ''), r.get('B', '')
        if re.fullmatch(r'\d{5}', zip_code) and re.fullmatch(r'\d{5}', geoid):
            hud_counties[zip_code].add(geoid)
            if geoid == PINELLAS:
                hud_pinellas_ratios[zip_code] = r.get('H', '')

    categories = Counter()
    formats = Counter()
    per_zip = defaultdict(lambda: Counter())
    with CLAIMS.open('r', encoding='utf-8-sig', newline='') as fh:
        reader = DictReader(fh)
        required = {'id', 'state', 'countyCode', 'reportedZipCode'}
        if not required.issubset(reader.fieldnames or []):
            raise SystemExit(f'FEMA file missing columns: {sorted(required - set(reader.fieldnames or []))}')
        for claim in reader:
            if claim['state'] != 'FL' or claim['countyCode'] != PINELLAS:
                raise SystemExit(f'Unexpected claim outside Pinellas: {claim.get("id")}')
            zip_code, fmt = normalize_zip(claim['reportedZipCode'])
            formats[fmt] += 1
            if fmt == 'missing':
                status = 'missing_zip'
            elif fmt == 'malformed':
                status = 'malformed_zip'
            elif PINELLAS in hud_counties.get(zip_code, set()):
                status = 'hud_pinellas_link'
            elif zip_code in hud_counties:
                status = 'hud_other_counties_only'
            else:
                status = 'not_in_hud_crosswalk'
            categories[status] += 1
            per_zip[(zip_code, status)]['claims'] += 1
            if fmt == 'zip_plus_four':
                per_zip[(zip_code, status)]['zip_plus_four_claims'] += 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open('w', encoding='utf-8', newline='') as fh:
        writer = DictWriter(fh, fieldnames=[
            'reported_zip_5', 'hud_status', 'claim_count', 'zip_plus_four_claims',
            'hud_county_fips', 'hud_pinellas_total_address_ratio_2025q4'])
        writer.writeheader()
        for (zip_code, status), counts in sorted(per_zip.items()):
            writer.writerow({
                'reported_zip_5': zip_code,
                'hud_status': status,
                'claim_count': counts['claims'],
                'zip_plus_four_claims': counts['zip_plus_four_claims'],
                'hud_county_fips': ';'.join(sorted(hud_counties.get(zip_code, set()))),
                'hud_pinellas_total_address_ratio_2025q4': hud_pinellas_ratios.get(zip_code, ''),
            })

    total = sum(categories.values())
    lines = [
        'RiskMap | FEMA NFIP ZIP-to-County crosswalk audit',
        f'FEMA records checked: {total:,}',
        'HUD reference: ZIP-COUNTY_122025.xlsx (2025 Q4)',
        '', 'Classification of claim records:',
    ]
    for status in ('hud_pinellas_link', 'hud_other_counties_only',
                   'not_in_hud_crosswalk', 'missing_zip', 'malformed_zip'):
        lines.append(f'  {status}: {categories[status]:,}')
    lines.extend([
        f'ZIP+4 values normalized to five digits: {formats["zip_plus_four"]:,}',
        f'Distinct normalized ZIP categories: {len(set(z for z, _ in per_zip)):,}',
        '', 'INTERPRETATION:',
        '- A HUD Pinellas link is evidence of a ZIP-county relationship in 2025, not proof of a claim property location.',
        '- A ZIP associated only with other counties in 2025 warrants review; it does not prove a historical claim is invalid.',
        '- A ZIP may span counties. HUD address ratios are NOT claim probabilities or flood risk rates.',
        '- This comparison does not establish historical ZIP boundaries or validate precise FEMA claim coordinates.',
        '- All original claim records are retained unchanged.',
    ])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    print(f'\nZIP audit saved: {OUTPUT}')
    print(f'Report saved: {REPORT}')


if __name__ == '__main__':
    main()
