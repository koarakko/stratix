"""Independent FIFO price-level oracle; deterministic generated order streams."""
import random
import unittest
from collections import deque
from decimal import Decimal as D

from services.matching.model import CancelRequest, LimitOrder, MatchingEngine


class ReferenceBook:
    """Small test-only model using price-level FIFO queues, not matcher replay."""
    def __init__(self):
        self.levels = {}
        self.remaining = {}
        self.events = []
        self.orders = {}

    def submit(self, order):
        self.orders[order.order_id] = order
        left = order.quantity
        opposite = 'sell' if order.side == 'buy' else 'buy'
        keys = [key for key in self.levels if key[:2] == (order.market, opposite)
                and (key[2] <= order.price if order.side == 'buy' else key[2] >= order.price)]
        # Explicit best-price ordering; FIFO is maintained by deque per price level.
        for key in sorted(keys, key=lambda x: x[2], reverse=order.side == 'sell'):
            queue = self.levels[key]
            while queue and left:
                maker = queue[0]
                qty = min(left, self.remaining[maker])
                self.events.append((maker, order.order_id, order.market, key[2], qty))
                self.remaining[maker] -= qty
                left -= qty
                if self.remaining[maker] == 0:
                    queue.popleft()
            if left == 0:
                break
        self.remaining[order.order_id] = left
        if left:
            self.levels.setdefault((order.market, order.side, order.price), deque()).append(order.order_id)

    def cancel(self, order_id):
        order = self.orders[order_id]
        key = (order.market, order.side, order.price)
        self.levels[key].remove(order_id)
        self.remaining[order_id] = D(0)


class ReferenceOracleTests(unittest.TestCase):
    def test_generated_price_time_and_cancellation_streams(self):
        # Fixed seeds guarantee reproducible failures without external dependencies.
        for seed in range(40):
            with self.subTest(seed=seed):
                rng = random.Random(seed)
                actual = MatchingEngine()
                expected = ReferenceBook()
                for n in range(80):
                    active = [oid for oid, qty in expected.remaining.items() if qty > 0]
                    if active and rng.randrange(5) == 0:
                        oid = rng.choice(active)
                        actual.cancel(oid)
                        expected.cancel(oid)
                    else:
                        order = LimitOrder(f'{seed}-{n}', rng.choice(('BTC-USD', 'ETH-USD')),
                                           rng.choice(('buy', 'sell')), D(rng.randrange(97, 104)),
                                           D(rng.randrange(1, 5)))
                        actual.submit(order)
                        expected.submit(order)
                    self.assertEqual(
                        [(e.maker_order_id, e.taker_order_id, e.market, e.price, e.quantity)
                         for e in actual.executions()], expected.events)
                    self.assertEqual({oid: actual.remaining(oid) for oid in expected.orders},
                                     expected.remaining)

    def test_replay_actions_matches_oracle_after_partial_cancellation(self):
        actions = [LimitOrder('ask1', 'BTC-USD', 'sell', D(100), D(3)),
                   LimitOrder('bid1', 'BTC-USD', 'buy', D(100), D(1)),
                   CancelRequest('ask1'),
                   LimitOrder('bid2', 'BTC-USD', 'buy', D(100), D(2))]
        oracle = ReferenceBook()
        for action in actions:
            if isinstance(action, LimitOrder):
                oracle.submit(action)
            else:
                oracle.cancel(action.order_id)
        actual = MatchingEngine.replay_actions(actions)
        self.assertEqual([(e.maker_order_id, e.taker_order_id, e.market, e.price, e.quantity)
                          for e in actual.executions()], oracle.events)
        self.assertEqual(actual.remaining('ask1'), D(0))
        self.assertEqual(actual.remaining('bid2'), D(2))


if __name__ == '__main__':
    unittest.main()
