"""Real Ledger -> read-only auditor integration, with no test doubles."""
import unittest
from concurrent.futures import ThreadPoolExecutor

from services.exchange.ledger import Ledger, LedgerError, Posting
from services.exchange.ledger_audit import LedgerAuditError, audit_transactions


class LedgerAuditIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger(protected_accounts={'alice'})
        self.ledger.post('fund-btc', (Posting('issuer', 'BTC', -20), Posting('alice', 'BTC', 20)))
        self.ledger.post('fund-eth', (Posting('issuer', 'ETH', -9), Posting('alice', 'ETH', 9)))

    def reconcile(self):
        snapshot = self.ledger.transactions()
        accounts = {p.account for entries in snapshot.values() for p in entries}
        assets = {p.asset for entries in snapshot.values() for p in entries}
        expected = {(account, asset): self.ledger.balance(account, asset)
                    for account in accounts for asset in assets}
        self.assertEqual(audit_transactions(snapshot, expected),
                         {key: value for key, value in expected.items() if value})
        return snapshot

    def test_reserve_does_not_create_posting(self):
        before = self.reconcile()
        self.assertTrue(self.ledger.reserve('r', 'alice', 'BTC', 12))
        self.assertEqual(self.reconcile(), before)
        self.assertEqual(self.ledger.available('alice', 'BTC'), 8)

    def test_partial_fill_then_cancel_reconciles(self):
        self.ledger.reserve('r', 'alice', 'BTC', 12)
        self.ledger.settle_partial('r', 'bob', 5, 'fill-1')
        self.assertEqual(self.ledger.available('alice', 'BTC'), 8)
        self.reconcile()
        self.ledger.release('r')
        self.assertEqual(self.ledger.available('alice', 'BTC'), 15)
        self.assertEqual(self.ledger.balance('bob', 'BTC'), 5)
        self.assertEqual(len(self.reconcile()), 3)

    def test_full_settlement_and_identical_retry(self):
        self.ledger.reserve('r', 'alice', 'ETH', 4)
        self.assertTrue(self.ledger.settle('r', 'bob'))
        snapshot = self.reconcile()
        self.assertFalse(self.ledger.settle('r', 'bob'))
        self.assertEqual(self.reconcile(), snapshot)
        self.assertEqual(self.ledger.available('alice', 'ETH'), 5)

    def test_two_fills_and_retries_do_not_double_post(self):
        self.ledger.reserve('r', 'alice', 'BTC', 12)
        self.assertTrue(self.ledger.settle_partial('r', 'bob', 5, 'fill-1'))
        self.assertFalse(self.ledger.settle_partial('r', 'bob', 5, 'fill-1'))
        self.assertTrue(self.ledger.settle_partial('r', 'carol', 7, 'fill-2'))
        snapshot = self.reconcile()
        self.assertFalse(self.ledger.settle_partial('r', 'carol', 7, 'fill-2'))
        self.assertEqual(self.reconcile(), snapshot)
        with self.assertRaises(LedgerError):
            self.ledger.settle('r', 'carol')
        self.assertEqual(self.reconcile(), snapshot)

    def test_failed_overfill_and_conflicting_fill_preserve_history(self):
        self.ledger.reserve('r', 'alice', 'BTC', 6)
        self.ledger.settle_partial('r', 'bob', 2, 'fill-1')
        snapshot = self.reconcile()
        for action in (lambda: self.ledger.settle_partial('r', 'bob', 5, 'fill-2'),
                       lambda: self.ledger.settle_partial('r', 'bob', 3, 'fill-1'),
                       lambda: self.ledger.post('spend', (Posting('alice', 'BTC', -15), Posting('bob', 'BTC', 15)))):
            with self.assertRaises(LedgerError):
                action()
            self.assertEqual(self.reconcile(), snapshot)

    def test_concurrent_fill_id_dedup_reconciles(self):
        self.ledger.reserve('r', 'alice', 'BTC', 12)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.ledger.settle_partial('r', 'bob', 5, 'fill-1'), range(24)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.ledger.balance('bob', 'BTC'), 5)
        self.assertEqual(self.ledger.available('alice', 'BTC'), 8)
        self.reconcile()

    def test_auditor_detects_tampered_posting(self):
        snapshot = self.reconcile()
        snapshot['fund-btc'] = (Posting('issuer', 'BTC', -20), Posting('alice', 'BTC', 19))
        with self.assertRaises(LedgerAuditError):
            audit_transactions(snapshot)
        self.reconcile()  # caller-owned snapshot mutation does not change Ledger

    def test_auditor_detects_missing_balanced_transaction_against_expected(self):
        snapshot = self.reconcile()
        expected = {('issuer', 'BTC'): -20, ('alice', 'BTC'): 20,
                    ('issuer', 'ETH'): -9, ('alice', 'ETH'): 9}
        snapshot.pop('fund-eth')
        with self.assertRaises(LedgerAuditError):
            audit_transactions(snapshot, expected)
        self.reconcile()


if __name__ == '__main__':
    unittest.main()
