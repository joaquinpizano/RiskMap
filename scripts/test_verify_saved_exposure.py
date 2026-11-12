import unittest
from verify_saved_exposure import TARGET, check_result, check_snapshot


class SavedExposureTests(unittest.TestCase):
    def test_snapshot_must_match_every_record(self):
        check_snapshot([{'asOfDate': TARGET}])
        for bad in ({}, {'asOfDate':'2026-10-01T00:00:00.000Z'}):
            with self.assertRaises(ValueError):
                check_snapshot([{'asOfDate':TARGET},bad])

    def test_same_totals_do_not_hide_changed_coverage_groups(self):
        saved = dict(groups=[{'code':'N','record_years':'1'}], record_reconciliation={},
                     date_exceptions=[], unique_records=1, source_as_of_dates=[TARGET])
        check_result(saved,saved)
        for altered in (dict(saved,groups=[{'code':'U','record_years':'1'}]),
                        dict(saved,date_exceptions=[{'id':99}])):
            with self.assertRaises(ValueError):
                check_result(altered,saved)


if __name__ == '__main__':
    unittest.main()
