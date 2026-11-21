import unittest
from concurrent.futures import ThreadPoolExecutor
from services.exchange.ledger import Ledger, LedgerError, Posting

class ReservationRetryStateTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger(protected_accounts={'alice'})
        self.ledger.post('fund', (Posting('issuer', 'BTC', -20), Posting('alice', 'BTC', 20)))
        self.ledger.reserve('r', 'alice', 'BTC', 10)

    def snapshot(self):
        return (self.ledger.balance('alice', 'BTC'), self.ledger.available('alice', 'BTC'), self.ledger.transactions())

    def assert_closed_retry_rejected(self):
        before = self.snapshot()
        with self.assertRaisesRegex(LedgerError, 'no longer an untouched hold'):
            self.ledger.reserve('r', 'alice', 'BTC', 10)
        self.assertEqual(self.snapshot(), before)

    def test_active_identical_retry_is_idempotent(self):
        self.assertFalse(self.ledger.reserve('r', 'alice', 'BTC', 10))
        self.assertEqual(self.ledger.available('alice', 'BTC'), 10)

    def test_released_reservation_cannot_be_reused(self):
        self.ledger.release('r')
        self.assert_closed_retry_rejected()

    def test_settled_reservation_cannot_be_reused(self):
        self.ledger.settle('r', 'bob')
        self.assert_closed_retry_rejected()

    def test_partial_reservation_cannot_be_reused(self):
        self.ledger.settle_partial('r', 'bob', 3, 'fill-1')
        self.assert_closed_retry_rejected()

    def test_fully_filled_reservation_cannot_be_reused(self):
        self.ledger.settle_partial('r', 'bob', 10, 'fill-1')
        self.assert_closed_retry_rejected()

    def test_partial_then_released_reservation_cannot_be_reused(self):
        self.ledger.settle_partial('r', 'bob', 3, 'fill-1')
        self.ledger.release('r')
        self.assert_closed_retry_rejected()

    def test_conflicting_retry_still_rejected(self):
        with self.assertRaisesRegex(LedgerError, 'conflicting reservation id'):
            self.ledger.reserve('r', 'alice', 'BTC', 9)

    def test_concurrent_closed_retries_all_fail(self):
        self.ledger.release('r')
        before = self.snapshot()
        def attempt(_):
            try:
                self.ledger.reserve('r', 'alice', 'BTC', 10)
                return False
            except LedgerError:
                return True
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertTrue(all(pool.map(attempt, range(32))))
        self.assertEqual(self.snapshot(), before)

if __name__ == '__main__':
    unittest.main()
