import unittest
from decimal import Decimal

from services.ledger.model import DuplicateTransactionError, Entry, Ledger


def transfer(amount="1.25", asset="BTC"):
    value = Decimal(amount)
    return (Entry("buyer", asset, -value), Entry("seller", asset, value))


class LedgerTests(unittest.TestCase):
    def test_balanced_transfer_and_idempotent_retry(self):
        ledger = Ledger()
        self.assertTrue(ledger.post("trade-1", transfer()))
        self.assertFalse(ledger.post("trade-1", transfer()))
        self.assertEqual(ledger.balance("buyer", "BTC"), Decimal("-1.25"))
        self.assertEqual(ledger.balance("seller", "BTC"), Decimal("1.25"))
        self.assertEqual(len(ledger.journal()), 1)

    def test_duplicate_id_with_different_payload_is_rejected_without_mutation(self):
        ledger = Ledger()
        ledger.post("trade-1", transfer())
        with self.assertRaises(DuplicateTransactionError):
            ledger.post("trade-1", transfer("2"))
        self.assertEqual(ledger.balance("seller", "BTC"), Decimal("1.25"))

    def test_cross_asset_imbalance_rejected(self):
        ledger = Ledger()
        with self.assertRaises(ValueError):
            ledger.post("invalid", (Entry("a", "BTC", Decimal("-1")), Entry("b", "ETH", Decimal("1"))))
        self.assertEqual(ledger.journal(), ())

    def test_invalid_amounts_are_rejected(self):
        for value in (Decimal("NaN"), Decimal("Infinity"), Decimal("0")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Ledger().post("bad", (Entry("a", "BTC", value), Entry("b", "BTC", Decimal("1"))))

    def test_replay_is_deterministic(self):
        ledger = Ledger()
        ledger.post("trade-1", transfer())
        ledger.post("trade-2", transfer("0.75"))
        rebuilt = Ledger.replay(ledger.journal())
        self.assertEqual(rebuilt.journal(), ledger.journal())
        self.assertEqual(rebuilt.balance("seller", "BTC"), Decimal("2.00"))

    def test_failed_validation_does_not_mutate_balances(self):
        ledger = Ledger()
        with self.assertRaises(ValueError):
            ledger.post("bad", (Entry("a", "BTC", Decimal("-1")), Entry("b", "BTC", Decimal("0.5"))))
        self.assertEqual(ledger.balance("a", "BTC"), Decimal(0))
        self.assertEqual(ledger.journal(), ())


if __name__ == "__main__":
    unittest.main()
