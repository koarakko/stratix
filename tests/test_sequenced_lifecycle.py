"""Integration checks use the real sequenced orders, matching and lifecycle modules."""
import unittest
from decimal import Decimal as D

from services.exchange.sequenced import LifecycleConsistencyError, SequencedExchange
from services.matching.model import MatchingError
from services.orders.model import CancelOrder, Command, PlaceOrder, SequenceError


def place(seq, oid, side, quantity="1", price="100"):
    return Command(seq, PlaceOrder(oid, "acct", "BTC-USD", side, D(price), D(quantity)))


class SequencedLifecycleTests(unittest.TestCase):
    def test_open_partial_filled_and_deterministic_replay(self):
        exchange = SequencedExchange()
        exchange.apply(place(1, "ask", "sell", "3"))
        self.assertEqual(exchange.lifecycle()["ask"].status, "open")
        exchange.apply(place(2, "bid", "buy", "1"))
        state = exchange.lifecycle()
        self.assertEqual((state["ask"].status, state["ask"].filled, state["ask"].remaining),
                         ("partially_filled", D("1"), D("2")))
        self.assertEqual(state["bid"].status, "filled")
        self.assertEqual(state, SequencedExchange.replay(exchange.history()).lifecycle())

    def test_cancel_keeps_fill_and_tracks_unfilled_amount(self):
        exchange = SequencedExchange()
        exchange.apply(place(1, "ask", "sell", "3"))
        exchange.apply(place(2, "bid", "buy", "1"))
        exchange.apply(Command(3, CancelOrder("ask")))
        state = exchange.lifecycle()["ask"]
        self.assertEqual((state.status, state.quantity, state.filled, state.remaining, state.cancelled),
                         ("cancelled", D("3"), D("1"), D("0"), D("2")))
        self.assertEqual(exchange.lifecycle(), SequencedExchange.replay(exchange.history()).lifecycle())

    def test_rejected_cancel_and_retry_do_not_change_projection(self):
        exchange = SequencedExchange()
        exchange.apply(place(1, "ask", "sell"))
        exchange.apply(place(2, "bid", "buy"))
        before = exchange.lifecycle()
        with self.assertRaises(MatchingError):
            exchange.apply(Command(3, CancelOrder("ask")))
        self.assertEqual(exchange.lifecycle(), before)
        self.assertEqual(len(exchange.history()), 2)
        self.assertEqual(exchange.apply(place(2, "bid", "buy")), ())
        self.assertEqual(exchange.lifecycle(), before)
        with self.assertRaises(SequenceError):
            exchange.apply(place(2, "other", "buy"))
        self.assertEqual(exchange.lifecycle(), before)

    def test_external_snapshot_cannot_mutate_internal_state(self):
        exchange = SequencedExchange()
        exchange.apply(place(1, "ask", "sell"))
        snap = exchange.lifecycle()
        snap.clear()
        self.assertEqual(exchange.lifecycle()["ask"].status, "open")

    def test_detects_corrupt_matching_remaining_and_refuses_new_commit(self):
        exchange = SequencedExchange()
        exchange.apply(place(1, "ask", "sell", "3"))
        # Intentional fault injection in the prototype's private in-memory state.
        exchange._matching._remaining["ask"] = D("2")
        with self.assertRaises(LifecycleConsistencyError):
            exchange.lifecycle()
        with self.assertRaises(LifecycleConsistencyError):
            exchange.apply(place(2, "bid", "buy", "1"))
        self.assertEqual(len(exchange.history()), 1)
        self.assertEqual(exchange.executions(), ())


if __name__ == "__main__":
    unittest.main()
