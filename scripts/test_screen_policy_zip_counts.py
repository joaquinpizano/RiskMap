import unittest
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from screen_policy_zip_counts import SNAPSHOT, count_query, rank_rows, snapshot_status, summarize


class ScreeningTests(unittest.TestCase):
    def test_fema_escaped_filter_metadata_is_validated(self):
        query = "asOfDate ne '2026-09-08T00:00:00.000Z'"
        raw = json.dumps({'metadata':{'count':0,'filter':query.replace(':','%3A')},'NfipPolicies':[]}).encode()
        with tempfile.TemporaryDirectory() as folder:
            with patch('screen_policy_zip_counts.urlopen',return_value=io.BytesIO(raw)):
                r = count_query(query,'snapshot',Path(folder))
            self.assertEqual(r['status'],'verified_count')
            self.assertEqual(len(r['attempts']),1)

    def result(self, n, dates=None):
        return {'status': 'verified_count', 'count': n, 'sampled_dates': [SNAPSHOT] if dates is None else dates}

    def test_snapshot_proof_requires_exception_count(self):
        self.assertEqual(snapshot_status(self.result(10), {'status':'unavailable'}), 'unverified')
        self.assertEqual(snapshot_status(self.result(10), self.result(0, [])), 'verified target snapshot')
        self.assertEqual(snapshot_status(self.result(10), self.result(1)), 'snapshot mismatch or missing dates')
        self.assertEqual(snapshot_status(self.result(0, []), self.result(0, [])), 'empty cohort; no snapshot date')

    def test_count_gap_is_unclassified_even_with_matching_snapshot(self):
        queries = {'zip_only':self.result(100), 'pinellas':self.result(70),
                   'zip_only_snapshot_exceptions':self.result(0, []), 'pinellas_snapshot_exceptions':self.result(0, [])}
        r = summarize('33708', 500, queries)
        self.assertEqual((r['excluded_count'],r['excluded_pct'],r['classification']), (30,30,'unclassified'))
        self.assertTrue(r['comparable_to_baseline'])
        queries['pinellas'] = self.result(101)
        r = summarize('33708', 500, queries)
        self.assertIsNone(r['excluded_count'])
        self.assertFalse(r['comparable_to_baseline'])

    def test_zero_denominator_and_two_rankings(self):
        queries = {k:self.result(0, []) for k in ('zip_only','pinellas','zip_only_snapshot_exceptions','pinellas_snapshot_exceptions')}
        r = summarize('33731', 0, queries)
        self.assertEqual(r['excluded_count'],0)
        self.assertIsNone(r['excluded_pct'])
        count,pct = rank_rows([r,dict(zip='a',excluded_count=10,excluded_pct=50),dict(zip='b',excluded_count=20,excluded_pct=25)])
        self.assertEqual([x['zip'] for x in count],['b','a','33731'])
        self.assertEqual([x['zip'] for x in pct],['a','b'])


if __name__ == '__main__':
    unittest.main()
