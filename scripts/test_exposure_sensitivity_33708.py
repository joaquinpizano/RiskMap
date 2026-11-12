import unittest
from decimal import Decimal
from calculate_provisional_exposure import analyze, validate_row
from exposure_sensitivity_33708 import change


class ExposureTests(unittest.TestCase):
    def row(self, **values):
        r={'id':1,'propertyState':'FL','reportedZipCode':'33708','censusGeoid':'121030001001',
           'condominiumCoverageTypeCode':'N','policyCount':5,'asOfDate':'2026-09-08T00:00:00.000Z',
           'policyEffectiveDate':'2024-01-01T00:00:00Z','policyTerminationDate':'2025-01-01T00:00:00Z',
           'cancellationDateOfFloodPolicy':None}
        return dict(r,**values)

    def n(self,result):
        return next(g for g in result['groups'] if g['code']=='N')

    def test_missing_geoids_only_allowed_for_sensitivity(self):
        r=self.row(censusGeoid=None)
        with self.assertRaises(ValueError): validate_row(r,'33708','12103')
        result=analyze([r],zip_code='33708',allow_missing_geoid=True)
        self.assertEqual(self.n(result)['record_years_excluding_exceptions'],'1.00000000')
        self.assertEqual(self.n(result)['insured_unit_years_excluding_exceptions'],'5.00000000')
        for geoid in ('120570001001','malformed'):
            with self.assertRaises(ValueError): validate_row(self.row(censusGeoid=geoid),'33708','12103',True)

    def test_pre_2023_term_can_contribute_and_cancellation_truncates(self):
        r=self.row(policyEffectiveDate='2022-01-01T00:00:00Z',cancellationDateOfFloodPolicy='2024-07-01T00:00:00Z')
        group=self.n(analyze([r],zip_code='33708'))
        self.assertLess(abs(Decimal(group['record_years_excluding_exceptions'])-Decimal(182)/366),Decimal('0.00000001'))

    def test_flagged_cancellations_excluded_with_separate_sensitivity(self):
        r=self.row(cancellationDateOfFloodPolicy='2023-12-01T00:00:00Z')
        group=self.n(analyze([r],zip_code='33708'))
        self.assertEqual(group['record_years_excluding_exceptions'],'0.00000000')
        self.assertEqual(group['exception_records'],1)
        self.assertEqual(group['added_insured_unit_years_if_flagged_cancellation_ignored'],'5.00000000')

    def test_changes_and_zero_baselines(self):
        self.assertEqual(change('10','12'),{'absolute':'2','percent':'20'})
        self.assertIsNone(change('0','1')['percent'])


if __name__=='__main__': unittest.main()
