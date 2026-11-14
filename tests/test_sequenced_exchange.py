import unittest
from decimal import Decimal as D

from services.exchange.sequenced import SequencedExchange
from services.matching.model import MatchingError
from services.orders.model import CancelOrder, Command, PlaceOrder, SequenceError


def place(seq, oid, side, price, qty="1"):
    return Command(seq, PlaceOrder(oid, "acct", "BTC-USD", side, D(price), D(qty)))


class SequencedExchangeTests(unittest.TestCase):
    def test_matching_and_deterministic_replay(self):
        exchange = SequencedExchange()
        exchange.apply(place(1, "ask", "sell", "100", "2"))
        fills = exchange.apply(place(2, "bid", "buy", "101", "1"))
        self.assertEqual([(x.maker_order_id, x.price, x.quantity) for x in fills],
                         [("ask", D("100"), D("1"))])
        self.assertEqual(exchange.remaining("ask"), D("1"))
        rebuilt = SequencedExchange.replay(exchange.history())
        self.assertEqual(rebuilt.executions(), exchange.executions())
        self.assertEqual(rebuilt.remaining("ask"), exchange.remaining("ask"))

    def test_cancel_replay_and_retry(self):
        exchange = SequencedExchange()
        exchange.apply(place(1, "ask", "sell", "100", "2"))
        exchange.apply(Command(2, CancelOrder("ask")))
        self.assertEqual(exchange.apply(Command(2, CancelOrder("ask"))), ())
        self.assertEqual(exchange.remaining("ask"), D("0"))
        self.assertEqual(SequencedExchange.replay(exchange.history()).remaining("ask"), D("0"))
        self.assertEqual(len(exchange.history()), 2)

    def test_filled_cancel_rolls_back_sequence(self):
        exchange = SequencedExchange()
        exchange.apply(place(1, "ask", "sell", "100"))
        exchange.apply(place(2, "bid", "buy", "100"))
        with self.assertRaises(MatchingError):
            exchange.apply(Command(3, CancelOrder("ask")))
        self.assertEqual(len(exchange.history()), 2)
        exchange.apply(place(3, "next", "buy", "99"))
        self.assertEqual(len(exchange.history()), 3)

    def test_gap_conflict_and_duplicate_replay(self):
        exchange = SequencedExchange()
        first = place(1, "ask", "sell", "100")
        exchange.apply(first)
        self.assertEqual(exchange.apply(first), ())
        for invalid in (place(1, "different", "sell", "100"),
                        place(3, "gap", "sell", "100")):
            with self.assertRaises(SequenceError):
                exchange.apply(invalid)
        self.assertEqual(exchange.history(), (first,))
        with self.assertRaises(SequenceError):
            SequencedExchange.replay((first, first))


if __name__ == "__main__":
    unittest.main()
