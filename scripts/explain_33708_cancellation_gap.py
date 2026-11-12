"""Read-only saved-input tracing of the N-code cancellation/termination gap."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path

from audit_policy_cohorts import digest, protected_files
from calculate_provisional_exposure import overlap_seconds, parse_date
from verify_saved_exposure import require, verify_33708

YEAR_SECONDS = Decimal(366 * 86400)
START = datetime(2024, 1, 1, tzinfo=timezone.utc)
END = datetime(2025, 1, 1, tzinfo=timezone.utc)


def trace(row, source):
    effective = parse_date(row['policyEffectiveDate'])
    term = parse_date(row['policyTerminationDate'])
    cancel = parse_date(row['cancellationDateOfFloodPolicy']) if row.get('cancellationDateOfFloodPolicy') else None
    flagged = bool(cancel and cancel < effective)
    if not cancel:
        timing = 'No cancellation'
    elif flagged:
        timing = 'Before effective date; excluded from both'
    elif cancel == effective:
        timing = 'At effective date'
    elif cancel < START:
        timing = 'After effective, before 2024'
    elif cancel == START:
        timing = 'After effective, at 2024 start'
    elif cancel < END:
        timing = 'After effective, during 2024'
    else:
        timing = 'After effective, on/after 2025 start'
    baseline = Decimal(0) if flagged else Decimal(str(overlap_seconds(effective, min(term,cancel) if cancel else term, 2024)))
    term_only = Decimal(0) if flagged else Decimal(str(overlap_seconds(effective,term,2024)))
    delta = term_only - baseline
    require(delta >= 0, 'Negative cancellation truncation difference')
    conflict = bool(cancel and cancel != term)
    if flagged:
        support = 'Chronology unresolved; no duration assigned in either main scenario'
    elif cancel == effective:
        support = 'Cancellation marks going out of force; equal effective/cancellation implies zero recorded duration'
    elif cancel and cancel < START:
        support = 'Cancellation marks going out of force before 2024; zero baseline 2024 duration'
    elif cancel and cancel < END:
        support = 'Cancellation marks going out of force; baseline ends at cancellation'
    else:
        support = 'Cancellation convention does not change 2024 duration for this row'
    return {'id':row['id'], 'effective_year':effective.year, 'timing':timing,
        'policyEffectiveDate':row['policyEffectiveDate'], 'cancellationDateOfFloodPolicy':row.get('cancellationDateOfFloodPolicy'),
        'policyTerminationDate':row['policyTerminationDate'], 'endorsementEffectiveDate':row.get('endorsementEffectiveDate'),
        'censusGeoid':row['censusGeoid'], 'policyCount':row['policyCount'], 'asOfDate':row['asOfDate'],
        'baseline_seconds':str(baseline), 'termination_only_seconds':str(term_only), 'delta_seconds':str(delta),
        'delta_days':str(delta/86400), 'delta_record_years':str(delta/YEAR_SECONDS),
        'flagged_before_effective':flagged, 'termination_cancellation_disagree':conflict,
        'documented_rule_application':support,
        'coverage_ambiguity':('Conflicting end-date fields; correctness/transaction history not independently verified' if conflict else 'No cancellation/end-date conflict identified'),
        'source_file':source}


def run(root, output):
    require(not output.exists(), 'Choose a new directory; prior reports are preserved')
    protected = protected_files(root, output)
    verify_33708(root)
    parent = root/'reports/noncondo_denominator_validation_33708_2024_2026-11-11'
    saved = json.loads((parent/'calculation_evidence.json').read_text())
    for name,h in saved['input_sha256'].items():
        require(digest(root/name)==h, f'Changed input: {name}')
    folder=root/'reports/exposure_sensitivity_33708_2024_2026-11-11'
    sensitivity=json.loads((folder/'evidence.json').read_text())
    prior=(root/sensitivity['prior_audit']['path']).parent
    sourced=[]
    for page in sorted((prior/'downloaded/2024').glob('page_*.json')):
        sourced.extend((row,str(page.relative_to(root))) for row in json.loads(page.read_text())['records'])
    for query in sensitivity['requests']:
        for attempt in query['attempts']:
            if 'path' in attempt and 'error' not in attempt:
                path=folder/attempt['path']; data=json.loads(path.read_text())
                if data['metadata']['top']==10000:
                    sourced.extend((row,str(path.relative_to(root))) for row in data['NfipPolicies'])
    entries=[trace(row,source) for row,source in sourced if row['condominiumCoverageTypeCode']=='N'
             and str(row.get('censusGeoid') or '').startswith('12103')]
    require(len({r['id'] for r in entries})==len(entries)==6191, 'Confirmed N row count/IDs differ')
    require(all(r['asOfDate']==saved['snapshot'] and r['policyCount']==1 for r in entries), 'Unexpected source date or weight')
    cancellations=[r for r in entries if r['cancellationDateOfFloodPolicy']]
    contributors=[r for r in entries if Decimal(r['delta_seconds'])>0]
    groups=defaultdict(lambda:{'rows':0,'contributors':0,'delta_seconds':Decimal(0)})
    for r in entries:
        g=groups[(r['effective_year'],r['timing'])]
        g['rows']+=1;g['contributors']+=int(Decimal(r['delta_seconds'])>0)
        g['delta_seconds']+=Decimal(r['delta_seconds'])
    total_seconds=sum((Decimal(r['delta_seconds']) for r in entries),Decimal(0))
    baseline=sum((Decimal(r['baseline_seconds']) for r in entries),Decimal(0))/YEAR_SECONDS
    term_only=sum((Decimal(r['termination_only_seconds']) for r in entries),Decimal(0))/YEAR_SECONDS
    difference=total_seconds/YEAR_SECONDS
    require(abs(baseline-Decimal(saved['scenarios'][0]['record_years']))<Decimal('1e-20'), 'Baseline differs')
    require(abs(term_only-Decimal(saved['confirmed_term_only_excluding_flagged']))<Decimal('1e-20'), 'Termination-only total differs')
    require(abs(difference-Decimal(saved['additional_years_without_valid_cancellation_truncation']))<Decimal('1e-20'), 'Gap differs')
    require(sum(g['delta_seconds'] for g in groups.values())==total_seconds, 'Breakdown does not reconcile')
    output.mkdir(parents=True)
    def write_csv(name,rows):
        with (output/name).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(entries[0]))
            writer.writeheader();writer.writerows(sorted(rows,key=lambda r:(r['effective_year'],r['timing'],r['id'])))
    write_csv('contributors.csv',contributors)
    write_csv('all_cancellation_records.csv',cancellations)
    lines=['# Addendum: ZIP 33708 non-condominium cancellation/termination difference', '',
        'This traces the saved confirmed-Pinellas, code-N comparison only. Missing-GEOID records are outside both '
        'scenarios here. The same 11 cancellation-before-effective records are excluded from both; this is not the '
        'separate sensitivity that ignores their cancellations.', '',
        f'**{len(contributors)} records account for exactly {total_seconds/86400:,.0f} record-days / 366 = '
        f'{difference:.8f} record-years**, reported as 105.2787. Baseline: {baseline:.8f}; termination-only: {term_only:.8f}. '
        'All weights equal one, so the insured-unit-year difference is identical. Every input row has asOfDate '
        f"{saved['snapshot']}.", '',
        'The added interval for each non-flagged row is the part of [max(effective, cancellation, 2024-01-01), '
        'min(termination, 2025-01-01)) retained by termination-only selection after cancellation truncation. '
        'The ledger calculates both scenario durations separately; negative/empty intervals contribute zero.', '',
        '| Effective cohort | Cancellation timing | Rows | Contributing rows | Added record-days | Added record-years |',
        '|---|---|---:|---:|---:|---:|']
    grouped=[]
    for (year,timing),g in sorted(groups.items()):
        lines.append(f"| {year} | {timing} | {g['rows']} | {g['contributors']} | {g['delta_seconds']/86400:,.0f} | {g['delta_seconds']/YEAR_SECONDS:.8f} |")
        grouped.append({'effective_year':year,'timing':timing,'rows':g['rows'],'contributing_rows':g['contributors'],
                        'delta_seconds':str(g['delta_seconds']),'delta_days':str(g['delta_seconds']/86400),'delta_record_years':str(g['delta_seconds']/YEAR_SECONDS)})
    for year in (2023,2024):
        selected=[r for r in entries if r['effective_year']==year]
        sec=sum((Decimal(r['delta_seconds']) for r in selected),Decimal(0))
        lines.append(f"| **{year} subtotal** | | **{len(selected)}** | **{sum(Decimal(r['delta_seconds'])>0 for r in selected)}** | **{sec/86400:,.0f}** | **{sec/YEAR_SECONDS:.8f}** |")
    lines += [f'| **Total** | | **{len(entries)}** | **{len(contributors)}** | **{total_seconds/86400:,.0f}** | **{difference:.8f}** |', '',
        'The five positive cells above reconcile without rounding residual at the second/day level. There are no '
        'cancellations exactly at 2024-01-01 after an earlier effective date. All 408 recorded cancellations precede their termination dates.', '',
        '## Documentation support versus unresolved coverage', '',
        'The [FEMA v3 field definitions](../noncondo_denominator_validation_33708_2024_2026-11-11/sources/nfip_policy_fields_v3.json) '
        'already collected define cancellation as going out of force, termination as ending through cancellation or lapse, '
        'and policyCount as insured units in active status. The [collected FEMA FAQ reference](https://agents.floodsmart.gov/flood-maps-and-data/faqs-about-nfip-data) '
        'uses effective <= observation date < termination for point-in-time selection.', '',
        '- **99 same-effective-date cancellations** (54 from 2023; 45 from 2024): applying the documented cancellation '
        'meaning yields a zero-length recorded coverage interval. Termination-only retains 17,854 days (48.78142077 years). '
        'This supports excluding those intervals under the cancellation convention, but does not prove the cancellation '
        'date is correct or that the records represent a specific voidance/rewrite reason.',
        '- **50 later cancellations before 2024**, all effective in 2023: cancellation-based coverage ends before the study '
        'year; termination-only retains 5,781 days (15.79508197 years).',
        '- **144 later cancellations during 2024** (65 from 2023; 79 from 2024): the cancellation field supports truncating '
        'coverage there; termination-only retains another 14,897 days (40.70218579 years).',
        '- **104 cancellations on/after 2025-01-01**, all effective in 2024: both conventions retain the same 2024 duration. '
        'Their field disagreements have no effect on this particular annual comparison.',
        '- **11 cancellations before effective** (3 from 2023; 8 from 2024): chronology/coverage remains unresolved. '
        'Both compared scenarios exclude them, so they explain **zero** of the 105.2787-year difference. Their separate '
        'hypothetical uncancelled contribution is 3.04644809 record-years, already reported elsewhere.', '',
        '**Documentation support is not record-level validation.** Every one of the 293 contributors has a cancellation '
        'date earlier than a different termination date, even though both fields describe ending coverage. Thus the '
        'documented cancellation meaning supports the baseline operation, while a literal FAQ termination-only selection '
        'produces the reported alternative. The collected documentation does not specify a conflict-resolution hierarchy '
        'or certify actual coverage for these records. All 293 contributors retain this ambiguity; there is no subset '
        'independently verified as actual coverage to termination. Endorsement dates alone do not resolve duplicate, '
        'cancel/rewrite, voidance or renewal history; cancellation reason and shared contract/property keys were not '
        'collected. No reason code is inferred from timing alone.', '',
        '## Exact record identification and reproducibility', '',
        '[contributors.csv](contributors.csv) identifies every one of the 293 contributing IDs, effective-year cohort, '
        'timing bucket, effective/cancellation/termination dates, source file, both scenario durations, exact added seconds/days '
        'and record-year contribution. [all_cancellation_records.csv](all_cancellation_records.csv) additionally includes '
        'the 104 zero-effect and 11 excluded exceptions, for 408 cancellation records. The remaining 5,783 confirmed N '
        'rows have no cancellation and contribute zero difference.', '',
        'Source hashes and the exact reconciliation are in evidence.json. The existing exposure verifier was rerun. '
        'No live API requests, new coverage assumptions, claim rates or edits to dashboards/prior reports were made. '
        'Retain the denominator as provisional pending a documented resolution of conflicting dates and an independent benchmark.']
    require(all(digest(root/n)==h for n,h in protected.items()), 'Prior report or dashboard changed')
    evidence={'created_at_utc':datetime.now(timezone.utc).isoformat(),'scope':{'zip':'33708','calendar_year':2024,'coverage':'N','geography':'Pinellas GEOID prefix 12103'},
        'input_sha256':{str(parent.relative_to(root)/'calculation_evidence.json'):digest(parent/'calculation_evidence.json'),
                         str(folder.relative_to(root)/'evidence.json'):digest(folder/'evidence.json')},
        'baseline_record_years':str(baseline),'termination_only_record_years':str(term_only),'delta_seconds':str(total_seconds),
        'delta_record_days':str(total_seconds/86400),'delta_record_years':str(difference),'breakdown':grouped,
        'contributing_ids':sorted(r['id'] for r in contributors),'all_cancellation_ids':sorted(r['id'] for r in cancellations),
        'ledger_sha256':{name:digest(output/name) for name in ('contributors.csv','all_cancellation_records.csv')},
        'preservation':{'sha256_before':protected,'all_unchanged':True}}
    (output/'evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    (output/'addendum.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Saved:',output/'addendum.md');print('Contributors:',len(contributors),'days:',total_seconds/86400,'years:',difference)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(Path(__file__).resolve().parents[1],args.output.resolve())
