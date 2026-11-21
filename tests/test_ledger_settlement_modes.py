import unittest
from services.exchange.ledger import Ledger, Posting, LedgerError

class SettlementModeTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger(protected_accounts={'alice'})
        self.ledger.post('fund', [Posting('issuer', 'BTC', -10), Posting('alice', 'BTC', 10)])
        self.ledger.reserve('r', 'alice', 'BTC', 8)

    def test_full_partial_fill_rejects_cross_mode_settle(self):
        self.assertTrue(self.ledger.settle_partial('r', 'bob', 8, 'f1'))
        before = self.ledger.transactions()
        with self.assertRaisesRegex(LedgerError, 'partial fills'):
            self.ledger.settle('r', 'bob')
        self.assertEqual(self.ledger.transactions(), before)
        self.assertEqual(self.ledger.available('alice', 'BTC'), 2)
        self.assertFalse(self.ledger.settle_partial('r', 'bob', 8, 'f1'))

    def test_multiple_partial_fills_reject_cross_mode_settle(self):
        self.ledger.settle_partial('r', 'bob', 3, 'f1')
        self.ledger.settle_partial('r', 'bob', 5, 'f2')
        with self.assertRaisesRegex(LedgerError, 'partial fills'):
            self.ledger.settle('r', 'bob')
        self.assertEqual(self.ledger.balance('bob', 'BTC'), 8)

    def test_full_settle_retry_remains_idempotent(self):
        self.assertTrue(self.ledger.settle('r', 'bob'))
        self.assertFalse(self.ledger.settle('r', 'bob'))
        self.assertEqual(self.ledger.balance('bob', 'BTC'), 8)

    def test_different_destination_still_rejected(self):
        self.ledger.settle_partial('r', 'bob', 8, 'f1')
        with self.assertRaisesRegex(LedgerError, 'conflicting settlement destination'):
            self.ledger.settle('r', 'carol')

    def test_rejected_cross_mode_does_not_consume_settle_id(self):
        self.ledger.settle_partial('r', 'bob', 8, 'f1')
        with self.assertRaises(LedgerError):
            self.ledger.settle('r', 'bob')
        self.assertNotIn('reservation-settle:r', self.ledger.transactions())
        self.assertIn('reservation-fill:f1', self.ledger.transactions())

if __name__ == '__main__':
    unittest.main()
