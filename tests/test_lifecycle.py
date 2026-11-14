import unittest
from decimal import Decimal as D
from services.exchange.lifecycle import project_lifecycle
from services.orders.model import Command, PlaceOrder, CancelOrder
from services.matching.model import Execution


def place(seq, oid, qty):
    return Command(seq, PlaceOrder(oid, 'acct', 'BTC-USD', 'buy', D('100'), D(qty)))


def fill(qty):
    return Execution('exec-1', 'a', 'b', 'BTC-USD', D('100'), D(qty))


class LifecycleTests(unittest.TestCase):
    def test_open_partial_filled(self):
        commands = [place(1, 'a', '2'), place(2, 'b', '1')]
        self.assertEqual(project_lifecycle(commands, ())['a'].status, 'open')
        projected = project_lifecycle(commands, [fill('1')])
        self.assertEqual((projected['a'].status, projected['a'].filled, projected['a'].remaining),
                         ('partially_filled', D('1'), D('1')))
        self.assertEqual(projected['b'].status, 'filled')

    def test_cancel_preserves_filled_and_records_cancelled_quantity(self):
        commands = [place(1, 'a', '3'), place(2, 'b', '1'), Command(3, CancelOrder('a'))]
        projected = project_lifecycle(commands, [fill('1')])
        self.assertEqual((projected['a'].status, projected['a'].filled, projected['a'].cancelled, projected['a'].remaining),
                         ('cancelled', D('1'), D('2'), D('0')))
        self.assertEqual(projected, project_lifecycle(iter(commands), iter([fill('1')])))

    def test_reject_overfill_and_invalid_cancel(self):
        commands = [place(1, 'a', '1'), place(2, 'b', '1')]
        with self.assertRaises(ValueError):
            project_lifecycle(commands, [fill('2')])
        with self.assertRaises(ValueError):
            project_lifecycle(commands + [Command(3, CancelOrder('b'))], [fill('1')])
        with self.assertRaises(ValueError):
            project_lifecycle([Command(1, CancelOrder('unknown'))], ())

    def test_reject_unknown_execution_and_duplicate(self):
        with self.assertRaises(ValueError):
            project_lifecycle([place(1, 'a', '2')], [fill('1')])
        with self.assertRaises(ValueError):
            project_lifecycle([place(1, 'a', '2'), place(2, 'a', '2')], ()


if __name__ == '__main__':
    unittest.main()
