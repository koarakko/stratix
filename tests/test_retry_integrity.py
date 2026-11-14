"""Committed command retries must not silently acknowledge corrupted state."""
import unittest
from dataclasses import replace
from decimal import Decimal as D

from services.exchange.sequenced import LifecycleConsistencyError, SequencedExchange
from services.orders.model import CancelOrder, Command, PlaceOrder


def place(seq, oid, side, qty="1"):
    return Command(seq, PlaceOrder(oid, "acct", "BTC-USD", side, D("100"), D(qty)))


class RetryIntegrityTests(unittest.TestCase):
    def test_identical_place_retry_is_noop_on_valid_state(self):
        x = SequencedExchange()
        ask, bid = place(1, "ask", "sell"), place(2, "bid", "buy")
        x.apply(ask)
        x.apply(bid)
        before = (x.history(), x.executions(), x.lifecycle())
        self.assertEqual(x.apply(ask), ())
        self.assertEqual(x.apply(bid), ())
        self.assertEqual((x.history(), x.executions(), x.lifecycle()), before)

    def test_identical_cancel_retry_is_noop_on_valid_state(self):
        x = SequencedExchange()
        x.apply(place(1, "ask", "sell", "2"))
        cancel = Command(2, CancelOrder("ask"))
        x.apply(cancel)
        self.assertEqual(x.apply(cancel), ())
        self.assertEqual(x.lifecycle()["ask"].cancelled, D("2"))
        self.assertEqual(len(x.history()), 2)

    def test_corrupt_execution_rejects_identical_retry(self):
        x = SequencedExchange()
        ask, bid = place(1, "ask", "sell"), place(2, "bid", "buy")
        x.apply(ask)
        x.apply(bid)
        x._matching._executions[0] = replace(x.executions()[0], price=D("99"))
        with self.assertRaises(LifecycleConsistencyError):
            x.apply(ask)
        self.assertEqual(len(x.history()), 2)
        self.assertEqual(x.executions()[0].price, D("99"))

    def test_corrupt_remainder_rejects_identical_cancel_retry(self):
        x = SequencedExchange()
        ask = place(1, "ask", "sell", "3")
        cancel = Command(2, CancelOrder("ask"))
        x.apply(ask)
        x.apply(cancel)
        x._matching._remaining["ask"] = D("1")
        with self.assertRaises(LifecycleConsistencyError):
            x.apply(cancel)
        self.assertEqual(len(x.history()), 2)


if __name__ == "__main__":
    unittest.main()
