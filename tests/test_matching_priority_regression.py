"""Black-box price/time priority checks with explicit expected maker sequences."""
import unittest
from decimal import Decimal as D

from services.matching.model import CancelRequest, LimitOrder, MatchingEngine


def order(oid, side, price, qty='1', market='BTC-USD'):
    return LimitOrder(oid, market, side, D(price), D(qty))


class MatchingPriorityRegressionTests(unittest.TestCase):
    def test_buy_taker_best_ask_then_fifo_with_partial_maker(self):
        actions = [order('expensive', 'sell', '102'),
                   order('cheap-first', 'sell', '100', '2'),
                   order('cheap-second', 'sell', '100', '2'),
                   order('mid', 'sell', '101'),
                   order('buyer', 'buy', '103', '4')]
        engine = MatchingEngine.replay(actions)
        self.assertEqual([(e.maker_order_id, e.price, e.quantity) for e in engine.executions()],
                         [('cheap-first', D('100'), D('2')),
                          ('cheap-second', D('100'), D('2'))])
        self.assertEqual(engine.remaining('mid'), D('1'))
        self.assertEqual(engine.remaining('expensive'), D('1'))
        self.assertEqual(MatchingEngine.replay(actions).executions(), engine.executions())

    def test_sell_taker_best_bid_then_fifo(self):
        actions = [order('low', 'buy', '99'), order('best-first', 'buy', '102', '2'),
                   order('best-second', 'buy', '102', '2'), order('middle', 'buy', '101'),
                   order('seller', 'sell', '99', '3')]
        engine = MatchingEngine.replay(actions)
        self.assertEqual([(e.maker_order_id, e.price, e.quantity) for e in engine.executions()],
                         [('best-first', D('102'), D('2')),
                          ('best-second', D('102'), D('1'))])
        self.assertEqual(engine.remaining('best-second'), D('1'))

    def test_cancel_first_maker_promotes_next_fifo_without_reusing_id(self):
        actions = [order('first', 'sell', '100', '2'), order('second', 'sell', '100', '2'),
                   CancelRequest('first'), order('buyer', 'buy', '100', '1')]
        engine = MatchingEngine.replay_actions(actions)
        self.assertEqual([(e.maker_order_id, e.quantity) for e in engine.executions()],
                         [('second', D('1'))])
        self.assertEqual(engine.remaining('first'), D('0'))
        self.assertEqual(engine.remaining('second'), D('1'))
        self.assertEqual(MatchingEngine.replay_actions(actions).executions(), engine.executions())

    def test_partial_maker_retains_priority_after_first_taker(self):
        actions = [order('first', 'sell', '100', '3'), order('second', 'sell', '100', '2'),
                   order('buyer-1', 'buy', '100', '1'), order('buyer-2', 'buy', '100', '3')]
        engine = MatchingEngine.replay(actions)
        self.assertEqual([(e.maker_order_id, e.taker_order_id, e.quantity) for e in engine.executions()],
                         [('first', 'buyer-1', D('1')),
                          ('first', 'buyer-2', D('2')),
                          ('second', 'buyer-2', D('1'))])

    def test_non_crossing_and_other_market_do_not_steal_priority(self):
        actions = [order('ask', 'sell', '101'),
                   order('eth-ask', 'sell', '99', market='ETH-USD'),
                   order('low-buyer', 'buy', '100'),
                   order('cross-buyer', 'buy', '101')]
        engine = MatchingEngine.replay(actions)
        self.assertEqual([(e.maker_order_id, e.taker_order_id) for e in engine.executions()],
                         [('ask', 'cross-buyer')])
        self.assertEqual(engine.remaining('low-buyer'), D('1'))
        self.assertEqual(engine.remaining('eth-ask'), D('1'))


if __name__ == '__main__':
    unittest.main()
