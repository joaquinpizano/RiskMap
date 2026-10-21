"""RiskMap | First visualization: historical NFIP payments by Pinellas-linked ZIP.

Run from anywhere with: python scripts/visualize_nfip_zip_payments.py
Requires Python standard library only. Does not modify input data.
"""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data' / 'processed' / 'nfip_payments_by_zip_hud.csv'
OUTPUT = ROOT / 'reports' / 'nfip_top_zip_payments.svg'
TOP_N = 12
EXPECTED_COLUMNS = {
    'hud_status', 'reported_zip_5', 'claim_records',
    'gross_reported_payments_usd'
}


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f'Missing input: {SOURCE}')

    with SOURCE.open('r', newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        missing = EXPECTED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f'Missing columns: {sorted(missing)}')
        rows = list(reader)

    matched = []
    for row in rows:
        if row['hud_status'] != 'hud_pinellas_link':
            continue
        try:
            amount = Decimal(row['gross_reported_payments_usd'])
            count = int(row['claim_records'])
        except (InvalidOperation, ValueError) as exc:
            raise SystemExit(f'Invalid numeric value for ZIP {row["reported_zip_5"]}: {exc}')
        zip_code = row['reported_zip_5'].strip()
        if len(zip_code) != 5 or not zip_code.isdigit():
            raise SystemExit(f'Unexpected ZIP in matched group: {zip_code!r}')
        if amount < 0 or count < 0:
            raise SystemExit(f'Negative aggregate for ZIP {zip_code}')
        matched.append((zip_code, count, amount))

    if not matched:
        raise SystemExit('No HUD Pinellas-linked ZIP rows found.')

    matched.sort(key=lambda r: (-r[2], r[0]))
    total_claims = sum(r[1] for r in matched)
    total_payments = sum((r[2] for r in matched), Decimal(0))
    top = matched[:TOP_N]
    top_total = sum((r[2] for r in top), Decimal(0))
    max_amount = top[0][2]

    # SVG is a browser-viewable vector graphic; no plotting packages needed.
    width = 1100
    height = 220 + 49 * len(top) + 125
    left = 160
    bar_width = 685
    top_y = 220
    max_bar = 660
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Historical NFIP claim payments by ZIP code, Pinellas-linked ZIPs">',
        '<rect width="100%" height="100%" fill="#F7FAFC"/>',
        '<rect x="35" y="28" width="1030" height="90" rx="14" fill="#10283F"/>',
        '<text x="60" y="65" fill="#8ED4D0" font-family="Arial,sans-serif" font-size="14" '
        'font-weight="700" letter-spacing="2">RISKMAP  /  PINELLAS COUNTY</text>',
        '<text x="60" y="99" fill="#FFFFFF" font-family="Arial,sans-serif" font-size="27" '
        'font-weight="700">Historical NFIP Payments by Reported ZIP</text>',
        f'<text x="48" y="151" fill="#31475A" font-family="Arial,sans-serif" font-size="17">'
        f'Top {len(top)} ZIPs with a 2025 HUD–USPS Pinellas County relationship</text>',
        '<text x="48" y="179" fill="#607387" font-family="Arial,sans-serif" font-size="14">'
        'Cumulative nominal building + contents + ICC payments; not a flood-risk rate</text>',
    ]

    for index, (zip_code, count, amount) in enumerate(top):
        y = top_y + index * 49
        fill = '#087E8B' if index < 3 else '#497C9B'
        length = float(amount / max_amount) * max_bar
        label = f'${float(amount) / 1_000_000:,.1f}M'
        parts.extend([
            f'<text x="50" y="{y + 21}" fill="#142C42" font-family="Arial,sans-serif" '
            f'font-size="17" font-weight="700">{escape(zip_code)}</text>',
            f'<rect x="{left}" y="{y}" width="{max_bar}" height="28" rx="5" fill="#E6EDF2"/>',
            f'<rect x="{left}" y="{y}" width="{length:.2f}" height="28" rx="5" fill="{fill}"/>',
            f'<text x="{left + max_bar + 20}" y="{y + 21}" fill="#142C42" '
            f'font-family="Arial,sans-serif" font-size="16" font-weight="700">{label}</text>',
            f'<text x="{left + max_bar + 115}" y="{y + 21}" fill="#607387" '
            f'font-family="Arial,sans-serif" font-size="13">{count:,} claims</text>',
        ])

    footer_y = top_y + 49 * len(top) + 10
    top_pct = float(top_total / total_payments * 100) if total_payments else 0
    parts.extend([
        f'<line x1="48" x2="1052" y1="{footer_y}" y2="{footer_y}" stroke="#D5E0E8"/>',
        f'<text x="48" y="{footer_y + 29}" fill="#142C42" font-family="Arial,sans-serif" '
        f'font-size="15" font-weight="700">Pinellas-linked total: ${float(total_payments)/1e9:,.3f}B '
        f'· {total_claims:,} claims</text>',
        f'<text x="48" y="{footer_y + 55}" fill="#607387" font-family="Arial,sans-serif" '
        f'font-size="13">Top {len(top)} ZIPs represent {top_pct:.1f}% of payments in this group. '
        'ZIP counts are not adjusted for number of insured properties.</text>',
        f'<text x="48" y="{footer_y + 79}" fill="#607387" font-family="Arial,sans-serif" '
        'font-size="12">Source: FEMA NFIP historical claims; ZIP screening: HUD–USPS ZIP–County, Q4 2025. '
        '2025 links do not verify historical claim locations.</text>',
        '</svg>',
    ])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text('\n'.join(parts), encoding='utf-8')
    print('RiskMap | First historical NFIP ZIP payment visualization')
    print(f'Input: {SOURCE}')
    print(f'Pinellas-linked ZIPs: {len(matched)}')
    print(f'Claims: {total_claims:,}')
    print(f'Gross historical payments: ${total_payments:,.2f}')
    print(f'Top {len(top)} share of Pinellas-linked payments: {top_pct:.1f}%')
    print(f'Saved chart: {OUTPUT}')
    print('Open the SVG in a browser to view it. No original files were changed.')
    print('NOTE: Historical nominal NFIP payments are not predictive flood risk rates.')


if __name__ == '__main__':
    main()
