import unittest
from decimal import Decimal
from explain_33708_cancellation_gap import trace


class GapTraceTests(unittest.TestCase):
    def row(self, effective, cancel, term='2025-01-01T00:00:00Z'):
        return dict(id=1,policyEffectiveDate=effective,cancellationDateOfFloodPolicy=cancel,
            policyTerminationDate=term,censusGeoid='121030001001',policyCount=1,asOfDate='2026-09-08T00:00:00.000Z')

    def test_same_effective_date_zero_baseline_but_positive_gap(self):
        r=trace(self.row('2024-01-01T00:00:00Z','2024-01-01T00:00:00Z'),'test')
        self.assertEqual(Decimal(r['baseline_seconds']),0)
        self.assertEqual(Decimal(r['delta_days']),366)
        self.assertEqual(r['timing'],'At effective date')

    def test_flagged_dates_do_not_contribute_to_either_main_scenario(self):
        r=trace(self.row('2024-01-01T00:00:00Z','2023-12-01T00:00:00Z'),'test')
        self.assertTrue(r['flagged_before_effective'])
        self.assertEqual(Decimal(r['termination_only_seconds']),0)
        self.assertEqual(Decimal(r['delta_days']),0)

    def test_before_during_and_after_year_clipping(self):
        for cancel,term,expected in [('2023-12-31T00:00:00Z','2024-02-01T00:00:00Z',31),
                ('2024-07-01T00:00:00Z','2025-01-01T00:00:00Z',184),
                ('2025-01-01T00:00:00Z','2025-02-01T00:00:00Z',0)]:
            r=trace(self.row('2023-02-01T00:00:00Z',cancel,term),'test')
            self.assertEqual(Decimal(r['delta_days']),expected)


if __name__=='__main__': unittest.main()
