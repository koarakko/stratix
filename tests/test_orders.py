import unittest
from decimal import Decimal
from services.orders.model import CancelOrder, Command, OrderError, OrderStateMachine, PlaceOrder, SequenceError

def place(order_id="order-1", quantity="2"):
    return PlaceOrder(order_id, "account-1", "BTC-USD", "buy", Decimal("100"), Decimal(quantity))

class OrderStateMachineTests(unittest.TestCase):
    def test_place_cancel_and_replay(self):
        state = OrderStateMachine()
        self.assertTrue(state.apply(Command(1, place())))
        self.assertTrue(state.apply(Command(2, CancelOrder("order-1"))))
        self.assertEqual(state.order("order-1").status, "cancelled")
        rebuilt = OrderStateMachine.replay(state.history())
        self.assertEqual(rebuilt.history(), state.history())
        self.assertEqual(rebuilt.order("order-1"), state.order("order-1"))

    def test_identical_retry_is_noop(self):
        state = OrderStateMachine()
        command = Command(1, place())
        self.assertTrue(state.apply(command))
        self.assertFalse(state.apply(command))
        self.assertEqual(len(state.history()), 1)

    def test_conflicting_sequence_does_not_mutate(self):
        state = OrderStateMachine()
        state.apply(Command(1, place()))
        with self.assertRaises(SequenceError):
            state.apply(Command(1, place(quantity="3")))
        self.assertEqual(len(state.history()), 1)

    def test_gap_and_invalid_sequence_rejected(self):
        state = OrderStateMachine()
        for sequence in (0, 2, -1, True, 1.0):
            with self.subTest(sequence=sequence), self.assertRaises(SequenceError):
                state.apply(Command(sequence, place()))
        self.assertEqual(state.history(), ())

    def test_duplicate_order_id_even_after_cancel_rejected(self):
        state = OrderStateMachine()
        state.apply(Command(1, place()))
        state.apply(Command(2, CancelOrder("order-1")))
        with self.assertRaises(OrderError):
            state.apply(Command(3, place()))
        self.assertEqual(len(state.history()), 2)

    def test_cancel_missing_or_already_cancelled_rejected(self):
        state = OrderStateMachine()
        with self.assertRaises(OrderError):
            state.apply(Command(1, CancelOrder("missing")))
        state.apply(Command(1, place()))
        state.apply(Command(2, CancelOrder("order-1")))
        with self.assertRaises(OrderError):
            state.apply(Command(3, CancelOrder("order-1")))
        self.assertEqual(len(state.history()), 2)

    def test_invalid_place_rejected_without_sequence_consumption(self):
        invalid = [place(quantity="0"), place(quantity="NaN"), place(quantity="Infinity"),
                   PlaceOrder("x", "a", "BTC-USD", "hold", Decimal("1"), Decimal("1")),
                   PlaceOrder(" ", "a", "BTC-USD", "buy", Decimal("1"), Decimal("1"))]
        state = OrderStateMachine()
        for request in invalid:
            with self.subTest(request=request), self.assertRaises(OrderError):
                state.apply(Command(1, request))
        self.assertEqual(state.history(), ())
        self.assertTrue(state.apply(Command(1, place())))

    def test_replay_rejects_duplicate_sequences(self):
        command = Command(1, place())
        with self.assertRaises(SequenceError):
            OrderStateMachine.replay((command, command))

if __name__ == "__main__":
    unittest.main()
