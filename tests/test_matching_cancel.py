import unittest
from decimal import Decimal as D
from services.matching.model import CancelRequest, LimitOrder, MatchingEngine, MatchingError


def order(oid, side, price, qty="1"):
    return LimitOrder(oid, "BTC-USD", side, D(price), D(qty))


class CancelTests(unittest.TestCase):
    def test_cancel_removes_liquidity_without_changing_history(self):
        m = MatchingEngine()
        m.submit(order("ask", "sell", "100", "3"))
        m.submit(order("buy", "buy", "100", "1"))
        before = m.executions()
        self.assertEqual(m.cancel("ask"), D("2"))
        self.assertEqual(m.remaining("ask"), D("0"))
        self.assertEqual(m.submit(order("later", "buy", "100")), ())
        self.assertEqual(m.executions(), before)

    def test_cancel_unknown_filled_and_repeated_rejected_without_mutation(self):
        m = MatchingEngine()
        m.submit(order("ask", "sell", "100"))
        for oid in ("missing", "", " "):
            with self.assertRaises(MatchingError):
                m.cancel(oid)
        m.submit(order("buy", "buy", "100"))
        with self.assertRaises(MatchingError):
            m.cancel("ask")
        m.submit(order("open", "sell", "101"))
        m.cancel("open")
        with self.assertRaises(MatchingError):
            m.cancel("open")
        self.assertEqual(m.executions()[0].execution_id, "exec-1")
        self.assertEqual(m.submit(order("next", "buy", "101")), ())

    def test_cancel_replay_deterministic_and_identity_not_reusable(self):
        actions = [order("a", "sell", "100", "2"), order("b", "buy", "100"),
                   CancelRequest("a"), order("c", "buy", "100")]
        m = MatchingEngine.replay_actions(actions)
        n = MatchingEngine.replay_actions(iter(actions))
        self.assertEqual(m.executions(), n.executions())
        self.assertEqual(m.remaining("a"), D(0))
        self.assertEqual(m.remaining("c"), D(1))
        with self.assertRaises(MatchingError):
            m.submit(order("a", "sell", "100"))

    def test_replay_rejects_invalid_cancellation(self):
        with self.assertRaises(MatchingError):
            MatchingEngine.replay_actions([CancelRequest("missing")])
        with self.assertRaises(MatchingError):
            MatchingEngine.replay_actions([object()])


if __name__ == "__main__":
    unittest.main()
