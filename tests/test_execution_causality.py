"""Replay-based execution integrity checks against real exchange modules."""
import unittest
from dataclasses import replace
from decimal import Decimal as D
from services.exchange.sequenced import SequencedExchange, LifecycleConsistencyError
from services.orders.model import Command, PlaceOrder, CancelOrder


def place(seq, oid, side, qty="1"):
    return Command(seq, PlaceOrder(oid, "acct", "BTC-USD", side, D("100"), D(qty)))


class ExecutionCausalityTests(unittest.TestCase):
    def test_partial_cancel_replay(self):
        x = SequencedExchange()
        x.apply(place(1, "ask", "sell", "3"))
        x.apply(place(2, "bid", "buy", "1"))
        x.apply(Command(3, CancelOrder("ask")))
        self.assertEqual(x.lifecycle()["ask"].cancelled, D("2"))
        self.assertEqual(x.lifecycle(), SequencedExchange.replay(x.history()).lifecycle())

    def test_forged_price_rejected_without_new_commit(self):
        x = SequencedExchange()
        x.apply(place(1, "ask", "sell"))
        x.apply(place(2, "bid", "buy"))
        x._matching._executions[0] = replace(x.executions()[0], price=D("99"))
        with self.assertRaises(LifecycleConsistencyError):
            x.lifecycle()
        with self.assertRaises(LifecycleConsistencyError):
            x.apply(place(3, "next", "sell"))
        self.assertEqual(len(x.history()), 2)

    def test_forged_maker_or_id_rejected(self):
        for field, value in (("maker_order_id", "bid"), ("execution_id", "forged")):
            with self.subTest(field=field):
                x = SequencedExchange()
                x.apply(place(1, "ask", "sell"))
                x.apply(place(2, "bid", "buy"))
                x._matching._executions[0] = replace(x.executions()[0], **{field: value})
                with self.assertRaises(LifecycleConsistencyError):
                    x.lifecycle()

    def test_corrupt_remaining_rejected(self):
        x = SequencedExchange()
        x.apply(place(1, "ask", "sell", "3"))
        x._matching._remaining["ask"] = D("2")
        with self.assertRaises(LifecycleConsistencyError):
            x.lifecycle()

    def test_identical_retry_does_not_duplicate_fills(self):
        x = SequencedExchange()
        a = place(1, "ask", "sell")
        b = place(2, "bid", "buy")
        x.apply(a)
        x.apply(b)
        self.assertEqual(x.apply(b), ())
        self.assertEqual(len(x.executions()), 1)
        self.assertEqual(x.lifecycle()["ask"].status, "filled")


if __name__ == "__main__":
    unittest.main()
