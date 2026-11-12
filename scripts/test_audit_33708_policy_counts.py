import unittest
from audit_33708_policy_counts import group_rows, policy_counts


class PolicyCountTests(unittest.TestCase):
    def test_missing_invalid_and_large_valid_counts(self):
        values = [1, '250', '2.0', None, '', ' ', True, 0, -1, 1.5, 'NaN', 'Infinity', 'bad']
        s = policy_counts([{'id':i, 'policyCount':v} for i,v in enumerate(values)])
        self.assertEqual(s['row_count'],13)
        self.assertEqual(s['sum_valid_policy_count'],253)
        self.assertEqual(s['valid_policy_count_rows'],3)
        self.assertEqual(s['missing_policy_count_rows'],3)
        self.assertEqual(s['invalid_policy_count_rows'],7)
        self.assertFalse(s['sum_is_complete'])

    def test_empty_group_has_complete_zero_sum(self):
        s = policy_counts([])
        self.assertEqual(s['sum_valid_policy_count'],0)
        self.assertTrue(s['sum_is_complete'])

    def test_excluded_partition_preserves_ids_and_policy_counts(self):
        geoids = ['121030001001', None, '', '120570001001', 'bad', '121030001002']
        rows = [{'id':i, 'censusGeoid':g, 'policyCount':i+1} for i,g in enumerate(geoids)]
        groups = group_rows(rows,{0})
        self.assertEqual({k:len(v) for k,v in groups.items()}, {
            'included':1,'excluded_missing_geoid':2,'excluded_outside_pinellas':1,'excluded_other':2})
        self.assertEqual(sum(policy_counts(v)['sum_valid_policy_count'] for v in groups.values()),21)
        self.assertEqual({r['id'] for v in groups.values() for r in v},set(range(6)))


if __name__ == '__main__':
    unittest.main()
