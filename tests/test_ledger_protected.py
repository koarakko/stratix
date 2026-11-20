import unittest
from concurrent.futures import ThreadPoolExecutor
from services.exchange.ledger import Ledger, LedgerError, Posting


class ProtectedLedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger(protected_accounts={'alice', 'bob'})
        self.ledger.post('fund', (Posting('issuance', 'BTC', -10), Posting('alice', 'BTC', 10)))

    def test_funded_transfer(self):
        self.assertTrue(self.ledger.post('transfer', (Posting('alice', 'BTC', -7), Posting('bob', 'BTC', 7))))
        self.assertEqual((self.ledger.balance('alice', 'BTC'), self.ledger.balance('bob', 'BTC')), (3, 7))

    def test_overdraft_rejected_without_consuming_id(self):
        entries = (Posting('alice', 'BTC', -11), Posting('bob', 'BTC', 11))
        with self.assertRaises(LedgerError):
            self.ledger.post('transfer', entries)
        self.assertNotIn('transfer', self.ledger.transactions())
        self.assertTrue(self.ledger.post('transfer', (Posting('alice', 'BTC', -10), Posting('bob', 'BTC', 10))))

    def test_multi_posting_net_effect_not_intermediate(self):
        self.assertTrue(self.ledger.post('net', (Posting('alice', 'BTC', -15), Posting('alice', 'BTC', 5), Posting('bob', 'BTC', 10))))
        self.assertEqual(self.ledger.balance('alice', 'BTC'), 0)

    def test_cross_asset_balance_cannot_cover_deficit(self):
        with self.assertRaises(LedgerError):
            self.ledger.post('bad', (Posting('alice', 'ETH', -1), Posting('bob', 'ETH', 1)))
        self.assertEqual(self.ledger.balance('alice', 'BTC'), 10)

    def test_concurrent_spends_only_one_wins(self):
        def spend(i):
            try:
                return self.ledger.post(f'spend-{i}', (Posting('alice', 'BTC', -8), Posting('bob', 'BTC', 8)))
            except LedgerError:
                return False
        with ThreadPoolExecutor(max_workers=12) as pool:
            outcomes = list(pool.map(spend, range(20)))
        self.assertEqual(sum(outcomes), 1)
        self.assertEqual(self.ledger.balance('alice', 'BTC'), 2)
        self.assertEqual(len(self.ledger.transactions()), 2)

    def test_retry_after_success(self):
        entries = (Posting('alice', 'BTC', -10), Posting('bob', 'BTC', 10))
        self.assertTrue(self.ledger.post('transfer', entries))
        self.assertFalse(self.ledger.post('transfer', entries))
        with self.assertRaises(LedgerError):
            self.ledger.post('transfer', (Posting('alice', 'BTC', -1), Posting('bob', 'BTC', 1)))

    def test_invalid_configuration(self):
        for accounts in (None, [''], ['alice', 3], [['alice']]):
            with self.subTest(accounts=accounts), self.assertRaises(LedgerError):
                Ledger(protected_accounts=accounts)

    def test_legacy_unrestricted_default(self):
        unrestricted = Ledger()
        self.assertTrue(unrestricted.post('x', (Posting('alice', 'BTC', -1), Posting('bob', 'BTC', 1))))
        self.assertEqual(unrestricted.balance('alice', 'BTC'), -1)


if __name__ == '__main__':
    unittest.main()
