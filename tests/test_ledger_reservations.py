import unittest
from concurrent.futures import ThreadPoolExecutor
from services.exchange.ledger import Ledger, LedgerError, Posting


class ReservationTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger(protected_accounts={'alice', 'bob'})
        self.ledger.post('fund', (Posting('issuer', 'BTC', -10), Posting('alice', 'BTC', 10)))

    def test_reserve_and_release_idempotent(self):
        self.assertTrue(self.ledger.reserve('r', 'alice', 'BTC', 7))
        self.assertFalse(self.ledger.reserve('r', 'alice', 'BTC', 7))
        self.assertEqual(self.ledger.balance('alice', 'BTC'), 10)
        self.assertEqual(self.ledger.available('alice', 'BTC'), 3)
        self.assertTrue(self.ledger.release('r'))
        self.assertFalse(self.ledger.release('r'))
        self.assertEqual(self.ledger.available('alice', 'BTC'), 10)

    def test_settle_exactly_once(self):
        self.ledger.reserve('r', 'alice', 'BTC', 8)
        self.assertTrue(self.ledger.settle('r', 'bob'))
        self.assertFalse(self.ledger.settle('r', 'bob'))
        self.assertEqual(self.ledger.balance('bob', 'BTC'), 8)
        self.assertEqual(self.ledger.available('alice', 'BTC'), 2)
        self.assertEqual(len(self.ledger.transactions()), 2)

    def test_hold_blocks_direct_spend(self):
        self.ledger.reserve('r', 'alice', 'BTC', 8)
        with self.assertRaises(LedgerError):
            self.ledger.post('spend', (Posting('alice', 'BTC', -3), Posting('bob', 'BTC', 3)))
        self.assertNotIn('spend', self.ledger.transactions())

    def test_invalid_and_conflicting_retry(self):
        self.ledger.reserve('r', 'alice', 'BTC', 5)
        with self.assertRaises(LedgerError):
            self.ledger.reserve('r', 'alice', 'BTC', 6)
        with self.assertRaises(LedgerError):
            self.ledger.settle('r', 'alice')
        self.assertEqual(self.ledger.available('alice', 'BTC'), 5)

    def test_release_then_settle_rejected(self):
        self.ledger.reserve('r', 'alice', 'BTC', 5)
        self.ledger.release('r')
        with self.assertRaises(LedgerError):
            self.ledger.settle('r', 'bob')

    def test_settle_then_release_rejected(self):
        self.ledger.reserve('r', 'alice', 'BTC', 5)
        self.ledger.settle('r', 'bob')
        with self.assertRaises(LedgerError):
            self.ledger.release('r')
        with self.assertRaises(LedgerError):
            self.ledger.settle('r', 'issuer')

    def test_insufficient_and_bad_inputs(self):
        for amount in (0, -1, True, 11):
            with self.subTest(amount=amount), self.assertRaises(LedgerError):
                self.ledger.reserve('r', 'alice', 'BTC', amount)
        with self.assertRaises(LedgerError):
            self.ledger.reserve('r', 'issuer', 'BTC', 1)
        with self.assertRaises(LedgerError):
            self.ledger.release('missing')

    def test_concurrent_reservations_cannot_overbook(self):
        def reserve(i):
            try:
                return self.ledger.reserve(f'r{i}', 'alice', 'BTC', 6)
            except LedgerError:
                return False
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(reserve, range(30)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.ledger.available('alice', 'BTC'), 4)

    def test_concurrent_settle_exactly_once(self):
        self.ledger.reserve('r', 'alice', 'BTC', 7)
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(lambda _: self.ledger.settle('r', 'bob'), range(30)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.ledger.balance('bob', 'BTC'), 7)

    def test_transaction_id_collision_restores_hold(self):
        self.ledger.reserve('r', 'alice', 'BTC', 4)
        self.ledger.post('reservation-settle:r', (Posting('issuer', 'ETH', -1), Posting('bob', 'ETH', 1)))
        with self.assertRaises(LedgerError):
            self.ledger.settle('r', 'bob')
        self.assertEqual(self.ledger.available('alice', 'BTC'), 6)
        self.assertTrue(self.ledger.release('r'))


if __name__ == '__main__':
    unittest.main()
