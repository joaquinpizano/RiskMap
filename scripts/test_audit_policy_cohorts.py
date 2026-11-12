"""Offline tests for comparison gates and cached cohort integrity."""
from pathlib import Path
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from audit_policy_cohorts import compare, fetch_cohort, local_cohort, validate_rows


class AuditTests(unittest.TestCase):
    def test_same_count_different_ids_is_detected(self):
        local = {'snapshots': {'2026-09-08': 2}, 'count': 2}
        remote = dict(local, status='verified')
        result = compare(local, {1, 2}, remote, {1, 3})
        self.assertEqual(result['count_delta'], 0)
        self.assertEqual(result['local_ids_absent_remotely'], 1)
        self.assertEqual(result['remote_ids_absent_locally'], 1)

    def test_snapshot_mismatch_blocks_interpretation(self):
        result = compare({'snapshots': {'old': 1}, 'count': 1}, {1},
                         {'status': 'verified', 'snapshots': {'new': 2}, 'count': 2}, {1, 2})
        self.assertEqual(result['status'], 'unresolved')
        self.assertNotIn('count_delta', result)

    def test_mixed_snapshot_and_unavailable_are_unresolved(self):
        for remote in ({'status': 'unresolved'},
                       {'status': 'verified', 'snapshots': {'a': 1, 'b': 1}}):
            self.assertEqual(compare({'snapshots': {'a': 1}}, {1}, remote, set())['status'], 'unresolved')

    def test_duplicate_ids_and_out_of_scope_rejected(self):
        row = dict(id=1, propertyState='FL', reportedZipCode='33706', censusGeoid='121030001001',
                   policyEffectiveDate='2024-01-01T00:00:00Z', asOfDate='2026-09-08')
        self.assertEqual(validate_rows([row], 2024, True), {1})
        for rows in ([row, row], [dict(row, reportedZipCode='33703')],
                     [dict(row, asOfDate=None)], [dict(row, censusGeoid=None)]):
            with self.assertRaises(ValueError):
                validate_rows(rows, 2024, True)

    def test_real_cached_cohorts(self):
        root = Path(__file__).resolve().parents[1]
        for year, count in ((2023, 4920), (2024, 4915)):
            result, ids = local_cohort(root, year)
            self.assertEqual(result['count'], count)
            self.assertEqual(len(ids), count)
            self.assertEqual(list(result['snapshots']), ['2026-09-08T00:00:00.000Z'])

    def test_partial_api_response_is_not_comparable(self):
        payload = json.dumps({'metadata': {'count': 2}, 'NfipPolicies': []}).encode()
        with tempfile.TemporaryDirectory() as folder:
            with patch('audit_policy_cohorts.urlopen', return_value=io.BytesIO(payload)):
                result, rows, ids = fetch_cohort('test filter', 2024, True, Path(folder))
            self.assertEqual(result['status'], 'unresolved')
            self.assertNotIn('count', result)
            self.assertTrue((Path(folder) / result['response_file']).is_file())
            self.assertEqual((rows, ids), ([], set()))

    def test_api_failure_is_recorded(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('audit_policy_cohorts.urlopen', side_effect=TimeoutError('test timeout')):
                result, _, _ = fetch_cohort('test filter', 2023, False, Path(folder))
            self.assertEqual(result['status'], 'unresolved')
            self.assertIn('TimeoutError', result['error'])
            self.assertIn('url', result)


if __name__ == '__main__':
    unittest.main()
