import unittest
from dataclasses import replace
from decimal import Decimal as D

from services.exchange.invariants import ExecutionInvariantError, verify_execution_invariants
from services.exchange.sequenced import SequencedExchange
from services.matching.model import Execution
from services.orders.model import CancelOrder, Command, PlaceOrder


def place(seq, oid, side, qty='1', price='100', market='BTC-USD'):
    return Command(seq, PlaceOrder(oid, 'acct', market, side, D(price), D(qty)))


class ExecutionInvariantTests(unittest.TestCase):
    def test_valid_partial_cancel_and_replay(self):
        exchange = SequencedExchange()
        for command in (place(1, 'ask', 'sell', '3'), place(2, 'bid', 'buy'),
                        Command(3, CancelOrder('ask'))):
            exchange.apply(command)
        verify_execution_invariants(exchange.history(), exchange.executions())
        self.assertEqual(SequencedExchange.replay(exchange.history()).lifecycle(), exchange.lifecycle())

    def test_rejects_invalid_event_fields(self):
        commands = (place(1, 'ask', 'sell'), place(2, 'bid', 'buy'))
        valid = Execution('exec-1', 'ask', 'bid', 'BTC-USD', D('100'), D('1'))
        changes = ({'maker_order_id': 'bid'}, {'maker_order_id': 'unknown'},
                   {'market': 'ETH-USD'}, {'price': D('99')},
                   {'quantity': D('2')}, {'quantity': D('NaN')},
                   {'quantity': D('0')}, {'execution_id': ''})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ExecutionInvariantError):
                verify_execution_invariants(commands, (replace(valid, **change),))

    def test_rejects_wrong_side_and_taker_limit(self):
        for commands, event in (
            ((place(1, 'ask', 'buy'), place(2, 'bid', 'buy')),
             Execution('exec-1', 'ask', 'bid', 'BTC-USD', D('100'), D('1'))),
            ((place(1, 'ask', 'sell', price='101'), place(2, 'bid', 'buy', price='100')),
             Execution('exec-1', 'ask', 'bid', 'BTC-USD', D('101'), D('1'))),
        ):
            with self.assertRaises(ExecutionInvariantError):
                verify_execution_invariants(commands, (event,))

    def test_rejects_duplicate_id_and_fills_after_cancel(self):
        commands = (place(1, 'ask', 'sell', '3'), place(2, 'bid', 'buy'),
                    place(3, 'bid2', 'buy'))
        a = Execution('exec-1', 'ask', 'bid', 'BTC-USD', D('100'), D('1'))
        b = replace(a, taker_order_id='bid2')
        with self.assertRaises(ExecutionInvariantError):
            verify_execution_invariants(commands, (a, b))
        cancelled = (commands[0], Command(2, CancelOrder('ask')), place(3, 'bid', 'buy'))
        with self.assertRaises(ExecutionInvariantError):
            verify_execution_invariants(cancelled, (a,))

    def test_rejects_wrong_event_order_and_future_maker(self):
        commands = (place(1, 'ask', 'sell'), place(2, 'bid', 'buy'))
        event = Execution('exec-1', 'ask', 'bid', 'BTC-USD', D('100'), D('1'))
        with self.assertRaises(ExecutionInvariantError):
            verify_execution_invariants(commands, (replace(event, taker_order_id='unknown'),))
        with self.assertRaises(ExecutionInvariantError):
            verify_execution_invariants(commands, (replace(event, maker_order_id='future'),))

    def test_no_event_and_empty_stream(self):
        verify_execution_invariants((), ())
        verify_execution_invariants((place(1, 'ask', 'sell'),), ())


if __name__ == '__main__':
    unittest.main()
