import unittest
from concurrent.futures import ThreadPoolExecutor
from services.exchange.ledger import Ledger, LedgerError, Posting


class ReservedNamespaceTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger(protected_accounts={'alice'})
        self.ledger.post('fund', (Posting('issuer', 'BTC', -10), Posting('alice', 'BTC', 10)))
        self.ledger.reserve('r', 'alice', 'BTC', 8)

    def test_external_settlement_namespace_rejected(self):
        with self.assertRaisesRegex(LedgerError, 'reserved transaction id namespace'):
            self.ledger.post('reservation-settle:r', (Posting('issuer', 'ETH', -1), Posting('bob', 'ETH', 1)))
        self.assertTrue(self.ledger.settle('r', 'bob'))
        self.assertFalse(self.ledger.settle('r', 'bob'))
        self.assertEqual(self.ledger.available('alice', 'BTC'), 2)

    def test_external_fill_namespace_rejected(self):
        with self.assertRaisesRegex(LedgerError, 'reserved transaction id namespace'):
            self.ledger.post('reservation-fill:f1', (Posting('issuer', 'ETH', -1), Posting('bob', 'ETH', 1)))
        self.assertTrue(self.ledger.settle_partial('r', 'bob', 3, 'f1'))
        self.assertFalse(self.ledger.settle_partial('r', 'bob', 3, 'f1'))
        self.assertEqual(self.ledger.available('alice', 'BTC'), 2)

    def test_rejected_id_does_not_consume_history_or_hold(self):
        before = self.ledger.transactions()
        for namespace in ('reservation-settle:', 'reservation-fill:'):
            with self.assertRaises(LedgerError):
                self.ledger.post(namespace + 'x', (Posting('alice', 'BTC', -1), Posting('bob', 'BTC', 1)))
        self.assertEqual(before, self.ledger.transactions())
        self.assertEqual(self.ledger.available('alice', 'BTC'), 2)

    def test_ordinary_id_with_similar_text_remains_allowed(self):
        entries = (Posting('issuer', 'ETH', -1), Posting('bob', 'ETH', 1))
        self.assertTrue(self.ledger.post('other:reservation-fill:f1', entries))
        self.assertFalse(self.ledger.post('other:reservation-fill:f1', entries))

    def test_concurrent_collision_attempts_do_not_block_fill(self):
        def attempt(_):
            try:
                self.ledger.post('reservation-fill:f1', (Posting('issuer', 'ETH', -1), Posting('bob', 'ETH', 1)))
                return False
            except LedgerError:
                return True
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertTrue(all(pool.map(attempt, range(40))))
        self.assertTrue(self.ledger.settle_partial('r', 'bob', 4, 'f1'))
        self.assertEqual(self.ledger.balance('bob', 'BTC'), 4)


if __name__ == '__main__':
    unittest.main()
