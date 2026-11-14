import unittest
from decimal import Decimal
from services.ledger.model import (
    DuplicateJournalEntryError, DuplicateTransactionError, Entry, Ledger, Posting,
)


def posting(txid, amount="1"):
    n = Decimal(amount)
    return Posting(txid, (Entry("buyer", "BTC", -n), Entry("seller", "BTC", n)))


class ReplayIntegrityTests(unittest.TestCase):
    def test_unique_journal_replays_exactly(self):
        entries = (posting("tx-1"), posting("tx-2", "2"))
        ledger = Ledger.replay(iter(entries))
        self.assertEqual(ledger.journal(), entries)
        self.assertEqual(ledger.balance("seller", "BTC"), Decimal("3"))

    def test_identical_duplicate_in_recovery_stream_is_rejected(self):
        p = posting("tx-1")
        with self.assertRaises(DuplicateJournalEntryError):
            Ledger.replay((p, p))

    def test_conflicting_duplicate_in_recovery_stream_is_rejected(self):
        with self.assertRaises(DuplicateJournalEntryError):
            Ledger.replay((posting("tx-1"), posting("tx-1", "2")))

    def test_online_identical_retry_remains_idempotent(self):
        ledger = Ledger()
        p = posting("tx-1")
        self.assertTrue(ledger.post(p.transaction_id, p.entries))
        self.assertFalse(ledger.post(p.transaction_id, p.entries))
        self.assertEqual(ledger.journal(), (p,))
        with self.assertRaises(DuplicateTransactionError):
            ledger.post("tx-1", posting("tx-1", "2").entries)


if __name__ == "__main__":
    unittest.main()
