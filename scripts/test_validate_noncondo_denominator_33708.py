import unittest
from decimal import Decimal
from validate_noncondo_denominator_33708 import duration


class DenominatorTests(unittest.TestCase):
    def row(self, cancel=None):
        return {'policyEffectiveDate':'2024-01-01T00:00:00Z',
                'policyTerminationDate':'2025-01-01T00:00:00Z',
                'cancellationDateOfFloodPolicy':cancel}

    def test_flagged_sensitivity_is_separate(self):
        row=self.row('2023-12-31T00:00:00Z')
        self.assertEqual(duration([row]),0)
        self.assertEqual(duration([row],ignore_flagged=True),1)
        self.assertEqual(duration([row],term_only=True),0)

    def test_term_only_diagnostic_does_not_apply_cancellation(self):
        row=self.row('2024-07-01T00:00:00Z')
        self.assertEqual(duration([row]),Decimal(182)/366)
        self.assertEqual(duration([row],term_only=True),1)
        self.assertEqual(duration([row],ignore_flagged=True),Decimal(182)/366)


if __name__=='__main__': unittest.main()
