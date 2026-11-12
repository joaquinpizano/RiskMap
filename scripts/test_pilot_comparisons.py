import csv
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.pilot_comparisons import claims_comparison, noncondo_exposure

ROOT = Path(__file__).resolve().parents[1]


class ComparisonInputTests(unittest.TestCase):
    def test_comparison_reconciles_directly_to_raw_claims(self):
        actual = {r['ZIP']:r for r in claims_comparison(ROOT/'data/processed/nfip_claims_by_year_zip.csv')}
        expected = {z:[0,0,Decimal(0)] for z in actual}
        with (ROOT/'data/raw/NFIP_Claims_Pinellas.csv').open(newline='',encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                z = row['reportedZipCode'].strip()[:5]
                if row['yearOfLoss']!='2024' or z not in expected:
                    continue
                values = [row[k].strip() for k in ('amountPaidOnBuildingClaim',
                    'amountPaidOnContentsClaim','amountPaidOnIncreasedCostOfComplianceClaim')]
                expected[z][0]+=1
                expected[z][1]+=not any(values)
                expected[z][2]+=sum((Decimal(v) for v in values if v),Decimal(0))
        for z,(n,missing,dollars) in expected.items():
            self.assertEqual(actual[z]['Claim records'],n)
            self.assertEqual(actual[z]['All gross payment components missing'],missing)
            self.assertEqual(Decimal(str(actual[z]['Nominal reported payments ($)'])),dollars)

    def test_exposure_sensitivity_reconciles_and_rejects_changed_inputs(self):
        result = noncondo_exposure(ROOT)
        self.assertAlmostEqual(result['delta'],105.27868852,places=7)
        self.assertAlmostEqual(result['percent_change'],3.52972861,places=7)
        self.assertEqual(result['date_exceptions'],11)
        with patch('scripts.pilot_comparisons.digest',return_value='changed'):
            with self.assertRaisesRegex(ValueError,'different saved inputs'):
                noncondo_exposure(ROOT)


class PilotUITests(unittest.TestCase):
    def app(self):
        from streamlit.testing.v1 import AppTest
        from streamlit import cache_data
        cache_data.clear()
        return AppTest.from_file(str(ROOT/'dashboard_pilot.py'),default_timeout=30)

    def comparison(self,app):
        return next(d.value for d in app.dataframe if 'All gross payment components missing' in d.value.columns)

    def test_fixed_comparison_and_separate_exposure_panel(self):
        app=self.app().run()
        self.assertEqual(len(app.exception),0)
        self.assertIn('2024 ZIP Comparison',[tab.label for tab in app.tabs])
        frame=self.comparison(app)
        self.assertEqual(frame['Claim records'].tolist(),[3207,4060,3048])
        self.assertEqual(frame['All gross payment components missing'].tolist(),[70,113,101])
        metrics={m.label:m.value for m in app.metric}
        self.assertEqual(metrics['Baseline record-years'],'2,982.6284')
        self.assertEqual(metrics['Termination-only record-years'],'3,087.9071')
        self.assertTrue(any('+105.2787 record-years (+3.53%)' in m.value for m in app.markdown))
        app.sidebar.slider[0].set_value((2023,2023)).run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(self.comparison(app).equals(frame))

    def test_unavailable_exposure_keeps_claims_comparison_available(self):
        with patch('scripts.pilot_comparisons.noncondo_exposure',side_effect=ValueError('Evidence unavailable')):
            app=self.app().run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(len(self.comparison(app)),3)
        self.assertTrue(any('33708 exposure sensitivity is unavailable' in w.value for w in app.warning))


if __name__=='__main__': unittest.main()
