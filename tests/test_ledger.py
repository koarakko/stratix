import unittest
from concurrent.futures import ThreadPoolExecutor
from services.exchange.ledger import Ledger, LedgerError, Posting


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()
        self.entries = (Posting('alice', 'BTC', -5), Posting('bob', 'BTC', 5))

    def test_balanced_transfer(self):
        self.assertTrue(self.ledger.post('t1', self.entries))
        self.assertEqual(self.ledger.balance('alice', 'BTC'), -5)
        self.assertEqual(self.ledger.balance('bob', 'BTC'), 5)

    def test_identical_retry(self):
        self.ledger.post('t1', self.entries)
        self.assertFalse(self.ledger.post('t1', self.entries))
        self.assertEqual(len(self.ledger.transactions()), 1)

    def test_conflicting_retry(self):
        self.ledger.post('t1', self.entries)
        with self.assertRaises(LedgerError):
            self.ledger.post('t1', (Posting('alice', 'BTC', -6), Posting('bob', 'BTC', 6)))
        self.assertEqual(self.ledger.balance('bob', 'BTC'), 5)

    def test_unbalanced_rejected_atomically(self):
        with self.assertRaises(LedgerError):
            self.ledger.post('t1', (Posting('alice', 'BTC', -5), Posting('bob', 'BTC', 4)))
        self.assertEqual(self.ledger.transactions(), {})

    def test_cross_asset_netting_rejected(self):
        with self.assertRaises(LedgerError):
            self.ledger.post('t1', (Posting('a', 'BTC', 1), Posting('b', 'ETH', -1)))

    def test_bad_posting_types(self):
        for amount in (0, True, 1.2, '1'):
            with self.subTest(amount=amount), self.assertRaises(LedgerError):
                Posting('a', 'BTC', amount)

    def test_mutating_input_does_not_change_committed_entries(self):
        entries = list(self.entries)
        self.ledger.post('t1', entries)
        entries.clear()
        self.assertFalse(self.ledger.post('t1', self.entries))

    def test_concurrent_same_id_only_once(self):
        with ThreadPoolExecutor(max_workers=12) as pool:
            outcomes = list(pool.map(lambda _: self.ledger.post('t1', self.entries), range(100)))
        self.assertEqual(sum(outcomes), 1)
        self.assertEqual(self.ledger.balance('bob', 'BTC'), 5)

    def test_invalid_id(self):
        with self.assertRaises(LedgerError):
            self.ledger.post(' ', self.entries)

    def test_invalid_entries(self):
        with self.assertRaises(LedgerError):
            self.ledger.post('t1', None)
        with self.assertRaises(LedgerError):
            self.ledger.post('t1', (self.entries[0],))


if __name__ == '__main__':
    unittest.main()
