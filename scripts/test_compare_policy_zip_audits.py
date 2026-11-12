"""Regression checks for cross-ZIP geography classification and snapshot gates."""
import unittest
from audit_policy_cohorts import validate_rows
from compare_policy_zip_audits import geography, reconcile


class ComparisonTests(unittest.TestCase):
    def test_missing_outside_and_invalid_are_distinct(self):
        values = [None, '', '  ', '121030001001', '120570001001', 'invalid']
        result = geography([{'id': i, 'censusGeoid': v} for i, v in enumerate(values)])
        self.assertEqual(result['counts'], {'pinellas': 1, 'missing': 3,
                                           'outside_pinellas': 1, 'invalid': 1})
        self.assertEqual(result['missing_share_pct'], 50)

    def test_parameterized_zip_is_checked(self):
        row = {'id': 1, 'propertyState': 'FL', 'reportedZipCode': '33703',
               'policyEffectiveDate': '2024-01-01T00:00:00Z',
               'asOfDate': '2026-09-08', 'censusGeoid': '121030001001'}
        self.assertEqual(validate_rows([row], 2024, True, '33703'), {1})
        with self.assertRaises(ValueError):
            validate_rows([row], 2024, True)

    def test_exact_ids_and_classified_extras_reconcile(self):
        local = {'count': 1, 'snapshots': {'same': 1}}
        pinellas = dict(local, status='verified')
        zip_result = {'count': 3, 'snapshots': {'same': 3}, 'status': 'verified'}
        rows = [{'id': 1, 'censusGeoid': '121030001001'},
                {'id': 2, 'censusGeoid': None}, {'id': 3, 'censusGeoid': '120570001001'}]
        result = reconcile(local, {1}, pinellas, {1}, zip_result, rows, {1, 2, 3})
        self.assertTrue(result['verified'])
        self.assertEqual([r['id'] for r in result['zip_only_extras']], [2, 3])

    def test_snapshot_mismatch_prevents_reconciliation(self):
        local = {'count': 1, 'snapshots': {'old': 1}}
        remote = {'count': 1, 'snapshots': {'new': 1}, 'status': 'verified'}
        result = reconcile(local, {1}, remote, {1}, remote,
                           [{'id': 1, 'censusGeoid': '121030001001'}], {1})
        self.assertFalse(result['verified'])
        self.assertNotIn('zip_only_extras', result)


if __name__ == '__main__':
    unittest.main()
