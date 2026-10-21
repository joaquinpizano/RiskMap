"""RiskMap | First Census ZCTA map of historical NFIP payments.

Run: python scripts/map_nfip_zcta.py
Dependency: pyshp (install once with: python -m pip install pyshp)
Inputs are read-only; output is an SVG map and a plain-text coverage report.

Important: ZCTAs are Census approximations, not USPS ZIP boundaries. A ZIP's
2025 HUD association with Pinellas does not prove a historical claim location.
The map does NOT clip ZCTAs to Pinellas County and is NOT a flood-risk map.
"""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path
import tempfile
import zipfile

try:
    import shapefile  # package name: pyshp
except ImportError:
    raise SystemExit(
        "Missing Python package 'pyshp'. Install it in your selected Python "
        "environment, then rerun: python -m pip install pyshp"
    )

ROOT = Path(__file__).resolve().parents[1]
ZIP_ARCHIVE = ROOT / 'data' / 'raw' / 'tl_2025_us_zcta520.zip'
PAYMENTS_CSV = ROOT / 'data' / 'processed' / 'nfip_payments_by_zip_hud.csv'
MAP_SVG = ROOT / 'reports' / 'nfip_pinellas_zcta_map.svg'
REPORT_TXT = ROOT / 'reports' / 'nfip_zcta_map_coverage.txt'

W, H = 1360, 1060
MAP_LEFT, MAP_TOP, MAP_RIGHT, MAP_BOTTOM = 64, 235, 1025, 916
# Use a common longitude scale corrected for the latitude of Pinellas County.
LON_FACTOR = 0.884
BINS = [
    (Decimal('5000000'), '#dbe9ee'),
    (Decimal('25000000'), '#a7d2d9'),
    (Decimal('75000000'), '#66afbf'),
    (Decimal('200000000'), '#247b97'),
    (Decimal('Infinity'), '#10445e'),
]


def load_payments():
    if not PAYMENTS_CSV.is_file():
        raise SystemExit(f'Missing processed input: {PAYMENTS_CSV}')
    by_zip = {}
    with PAYMENTS_CSV.open('r', encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f)
        required = {'hud_status', 'reported_zip_5', 'claim_records', 'gross_reported_payments_usd'}
        if not required.issubset(set(r.fieldnames or [])):
            raise SystemExit(f'Missing CSV columns: {sorted(required - set(r.fieldnames or []))}')
        for row in r:
            if row['hud_status'] != 'hud_pinellas_link':
                continue
            zip5 = row['reported_zip_5'].strip()
            if len(zip5) != 5 or not zip5.isdigit():
                raise SystemExit(f'Unexpected Pinellas-linked ZIP: {zip5!r}')
            if zip5 in by_zip:
                raise SystemExit(f'Duplicate Pinellas-linked ZIP in input: {zip5}')
            try:
                by_zip[zip5] = {
                    'payments': Decimal(row['gross_reported_payments_usd']),
                    'claims': int(row['claim_records']),
                }
            except (InvalidOperation, ValueError) as e:
                raise SystemExit(f'Invalid numeric data for ZIP {zip5}: {e}')
    return by_zip


def get_geometries(wanted):
    """Extract only the shapefile components to temporary disk space.

    The nationwide .shp is large (~823 MB uncompressed); avoid loading it all
    into RAM. Temporary extracted files are automatically removed afterward.
    """
    if not ZIP_ARCHIVE.is_file():
        raise SystemExit(f'Missing Census archive: {ZIP_ARCHIVE}')
    base = 'tl_2025_us_zcta520'
    with zipfile.ZipFile(ZIP_ARCHIVE) as archive:
        required = [base + ext for ext in ('.shp', '.shx', '.dbf')]
        missing = set(required) - set(archive.namelist())
        if missing:
            raise SystemExit(f'Archive missing shapefile components: {sorted(missing)}')
        with tempfile.TemporaryDirectory(prefix='riskmap_zcta_') as temp:
            for member in required:
                print(f'  Reading Census archive: {member}', flush=True)
                # Stream the large shapefile to temporary disk; no permanent extraction.
                archive.extract(member, temp)
            reader = shapefile.Reader(str(Path(temp) / base), encoding='utf-8')
            try:
                field_names = [field[0] for field in reader.fields[1:]]
                if 'ZCTA5CE20' not in field_names:
                    raise SystemExit(f'Expected ZCTA5CE20 field; found {field_names}')
                zip_index = field_names.index('ZCTA5CE20')
                found = {}
                # DBF records are small; avoid reading geometry for nonmatching ZCTAs.
                for index, record in enumerate(reader.iterRecords()):
                    zcta = str(record[zip_index]).strip()
                    if zcta in wanted:
                        if zcta in found:
                            raise SystemExit(f'Duplicate ZCTA geometry: {zcta}')
                        found[zcta] = reader.shape(index)
                return found
            finally:
                reader.close()


def bucket(amount):
    for upper, color in BINS:
        if amount < upper:
            return color
    return BINS[-1][1]


def project(lon, lat, xmin, ymax, scale, offset_x, offset_y):
    return (MAP_LEFT + offset_x + (lon * LON_FACTOR - xmin) * scale,
            MAP_TOP + offset_y + (ymax - lat) * scale)


def make_svg(payments, shapes):
    # Bounding extent of *matched* polygons; these are not county-clipped.
    bounds = [s.bbox for s in shapes.values()]
    if not bounds:
        raise SystemExit('No ZCTA shapes matched. Cannot create map.')
    xmin = min(b[0] * LON_FACTOR for b in bounds)
    xmax = max(b[2] * LON_FACTOR for b in bounds)
    ymin = min(b[1] for b in bounds)
    ymax = max(b[3] for b in bounds)
    padding_x, padding_y = (xmax-xmin)*0.035, (ymax-ymin)*0.035
    xmin -= padding_x; xmax += padding_x
    ymin -= padding_y; ymax += padding_y
    scale = min((MAP_RIGHT-MAP_LEFT)/(xmax-xmin), (MAP_BOTTOM-MAP_TOP)/(ymax-ymin))
    offset_x = ((MAP_RIGHT - MAP_LEFT) - (xmax - xmin) * scale) / 2
    offset_y = ((MAP_BOTTOM - MAP_TOP) - (ymax - ymin) * scale) / 2

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
             'aria-label="Historical NFIP payments by Census ZCTA, Pinellas-linked ZIP codes">',
             '<rect width="1360" height="1060" fill="#f4f8fa"/>',
             '<rect x="32" y="28" width="1296" height="106" rx="17" fill="#112d43"/>',
             '<text x="60" y="68" fill="#8de1e0" font-family="Arial,sans-serif" '
             'font-size="17" font-weight="bold" letter-spacing="2">RISKMAP / PINELLAS COUNTY</text>',
             '<text x="60" y="107" fill="#fff" font-family="Arial,sans-serif" '
             'font-size="31" font-weight="bold">Historical NFIP Payments by Census ZCTA</text>',
             '<text x="62" y="172" fill="#163a50" font-family="Arial,sans-serif" '
             'font-size="20">Reported ZIPs linked to Pinellas in the HUD–USPS 2025 Q4 crosswalk</text>',
             '<text x="62" y="200" fill="#56718a" font-family="Arial,sans-serif" '
             'font-size="16">Cumulative nominal payments (building + contents + ICC); not a flood-risk rate</text>',
             '<rect x="46" y="220" width="1000" height="715" rx="16" fill="#e7f0f4"/>']

    # Draw lower-payment polygons first so outlines stay visible.
    for zcta in sorted(shapes, key=lambda z: (payments[z]['payments'], z)):
        shp = shapes[zcta]
        coordinates = shp.points
        indices = list(shp.parts) + [len(coordinates)]
        commands = []
        for start, end in zip(indices, indices[1:]):
            # Pixel-quantize and skip consecutive duplicate points. This shrinks
            # output while preserving useful visual detail at this map scale.
            last = None
            path_points = []
            for lon, lat in coordinates[start:end]:
                x, y = project(lon, lat, xmin, ymax, scale, offset_x, offset_y)
                point = (round(x, 1), round(y, 1))
                if point != last:
                    path_points.append(point)
                    last = point
            if len(path_points) >= 3:
                commands.append('M' + ' L'.join(f'{x},{y}' for x,y in path_points) + ' Z')
        if not commands:
            continue
        color = bucket(payments[zcta]['payments'])
        amount = payments[zcta]['payments']
        title = escape(f'ZCTA {zcta} | ${amount:,.2f} reported payments | '
                       f'{payments[zcta]["claims"]:,} claim records')
        parts.append(f'<path d="{" ".join(commands)}" fill="{color}" fill-rule="evenodd" '
                     f'stroke="#ffffff" stroke-width="1.2" stroke-linejoin="round">'
                     f'<title>{title}</title></path>')

    # Right-hand legend and explanation.
    parts += [
        '<text x="1080" y="275" font-family="Arial,sans-serif" font-size="19" '
        'font-weight="bold" fill="#173c52">Reported payments</text>',
    ]
    legend = [('< $5M', BINS[0][1]), ('$5M–$25M', BINS[1][1]),
              ('$25M–$75M', BINS[2][1]), ('$75M–$200M', BINS[3][1]),
              ('$200M+', BINS[4][1])]
    for i, (label, color) in enumerate(legend):
        y = 308 + i * 53
        parts.append(f'<rect x="1082" y="{y}" width="34" height="28" rx="5" fill="{color}" '
                     'stroke="#d2e1e8"/>')
        parts.append(f'<text x="1128" y="{y+20}" font-family="Arial,sans-serif" '
                     f'font-size="17" fill="#173c52">{escape(label)}</text>')
    total = sum((payments[z]['payments'] for z in shapes), Decimal('0'))
    parts += [
        '<text x="1082" y="645" font-family="Arial,sans-serif" font-size="16" '
        'font-weight="bold" fill="#173c52">Mapped payments</text>',
        f'<text x="1082" y="677" font-family="Arial,sans-serif" font-size="24" '
        f'font-weight="bold" fill="#173c52">${total/Decimal("1000000000"):,.3f}B</text>',
        '<text x="1082" y="729" font-family="Arial,sans-serif" font-size="15" '
        'fill="#56718a">ZCTAs may extend</text>',
        '<text x="1082" y="750" font-family="Arial,sans-serif" font-size="15" '
        'fill="#56718a">outside Pinellas.</text>',
        '<text x="1082" y="786" font-family="Arial,sans-serif" font-size="15" '
        'fill="#56718a">ZIP ≠ ZCTA.</text>',
        '<line x1="55" x2="1304" y1="955" y2="955" stroke="#d0dfe6"/>',
        '<text x="58" y="986" font-family="Arial,sans-serif" font-size="16" '
        'font-weight="bold" fill="#173c52">Geographic screening: HUD–USPS ZIP–County, 2025 Q4</text>',
        '<text x="58" y="1012" font-family="Arial,sans-serif" font-size="14" '
        'fill="#56718a">Source: FEMA NFIP historical claims; boundaries: Census 2025 TIGER/Line 2020-vintage ZCTAs.</text>',
        '<text x="58" y="1034" font-family="Arial,sans-serif" font-size="14" '
        'fill="#56718a">Illustrative geography only. ZIP–ZCTA matches are approximate; not county-clipped or predictive flood risk.</text>',
        '</svg>',
    ]
    return '\n'.join(parts)


def main():
    payments = load_payments()
    print('RiskMap | Census ZCTA historical NFIP payment map', flush=True)
    print(f'Pinellas-linked reported ZIPs in payment summary: {len(payments):,}', flush=True)
    shapes = get_geometries(set(payments))
    missing = sorted(set(payments) - set(shapes))
    mapped_claims = sum(payments[z]['claims'] for z in shapes)
    mapped_dollars = sum((payments[z]['payments'] for z in shapes), Decimal('0'))
    total_claims = sum(v['claims'] for v in payments.values())
    total_dollars = sum((v['payments'] for v in payments.values()), Decimal('0'))
    MAP_SVG.parent.mkdir(parents=True, exist_ok=True)
    MAP_SVG.write_text(make_svg(payments, shapes), encoding='utf-8')
    report = [
        'RiskMap | 2025 Census ZCTA map coverage audit',
        f'Input ZIPs with HUD Pinellas link: {len(payments)}',
        f'ZIPs with a 2025 Census ZCTA polygon: {len(shapes)}',
        f'ZIPs with no matching ZCTA polygon: {len(missing)}',
        f'Unmatched ZIPs: {", ".join(missing) if missing else "none"}',
        f'Mapped historical NFIP claim records: {mapped_claims:,} of {total_claims:,}',
        f'Mapped historical NFIP payments: ${mapped_dollars:,.2f} of ${total_dollars:,.2f}',
        f'Unmapped historical NFIP payments: ${total_dollars-mapped_dollars:,.2f}',
        '',
        'CAUTIONS:',
        '- A reported ZIP with a 2025 HUD Pinellas relationship is not a verified historical claim location.',
        '- USPS ZIPs and Census ZCTAs are different geographic constructs.',
        '- The ZCTA polygons shown are NOT clipped to the Pinellas County boundary.',
        '- Historical payments are nominal dollars and are NOT flood risk rates.',
        '- ZIP/ZCTA values without matching polygons remain in the input and are reported here.',
        '- No source data were altered.',
    ]
    REPORT_TXT.write_text('\n'.join(report) + '\n', encoding='utf-8')
    for line in report[:8]:
        print(line, flush=True)
    print(f'\nSaved map: {MAP_SVG}', flush=True)
    print(f'Saved coverage report: {REPORT_TXT}', flush=True)
    print('Open the SVG in a browser. Original data unchanged.', flush=True)


if __name__ == '__main__':
    main()
