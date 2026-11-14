import unittest
from decimal import Decimal as D
from services.matching.model import LimitOrder, MatchingEngine, MatchingError


def order(oid, side, price, qty="1", market="BTC-USD"):
    return LimitOrder(oid, market, side, D(price), D(qty))


class MatchingTests(unittest.TestCase):
    def test_price_priority_and_maker_price(self):
        m = MatchingEngine()
        m.submit(order("ask-high", "sell", "102"))
        m.submit(order("ask-low", "sell", "100"))
        fills = m.submit(order("buy", "buy", "105", "2"))
        self.assertEqual([(f.maker_order_id, f.price) for f in fills],
                         [("ask-low", D("100")), ("ask-high", D("102"))])
        self.assertEqual([f.execution_id for f in fills], ["exec-1", "exec-2"])

    def test_time_priority_partial_fill_and_replay(self):
        commands = [order("a", "sell", "100", "2"), order("b", "sell", "100"),
                    order("c", "buy", "100", "2.5")]
        m = MatchingEngine()
        for command in commands:
            m.submit(command)
        self.assertEqual([(f.maker_order_id, f.quantity) for f in m.executions()],
                         [("a", D("2")), ("b", D("0.5"))])
        self.assertEqual(m.remaining("b"), D("0.5"))
        self.assertEqual(MatchingEngine.replay(commands).executions(), m.executions())

    def test_market_isolation_and_non_crossing(self):
        m = MatchingEngine()
        m.submit(order("ask", "sell", "101"))
        self.assertEqual(m.submit(order("buy", "buy", "100")), ())
        self.assertEqual(m.submit(order("other", "buy", "200", market="ETH-USD")), ())
        self.assertEqual(m.remaining("ask"), D("1"))

    def test_sell_taker_chooses_highest_bid(self):
        m = MatchingEngine()
        m.submit(order("low", "buy", "99"))
        m.submit(order("high", "buy", "101"))
        self.assertEqual(m.submit(order("sell", "sell", "98"))[0].maker_order_id, "high")

    def test_invalid_and_duplicate_do_not_change_state(self):
        m = MatchingEngine()
        m.submit(order("a", "sell", "100"))
        bad = [order("a", "buy", "101"), order("bad", "buy", "NaN"),
               order("bad", "buy", "Infinity"), order("bad", "buy", "0"),
               order("bad", "hold", "100"), order(" ", "buy", "100")]
        for item in bad:
            with self.subTest(item=item), self.assertRaises(MatchingError):
                m.submit(item)
        self.assertEqual(m.executions(), ())
        self.assertEqual(m.remaining("a"), D("1"))
        self.assertEqual(m.submit(order("b", "buy", "100"))[0].execution_id, "exec-1")


if __name__ == "__main__":
    unittest.main()
