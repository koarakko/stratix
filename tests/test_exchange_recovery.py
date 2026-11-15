import tempfile
import unittest
from decimal import Decimal as D
from pathlib import Path

from services.exchange.command_log import CommandJournal, JournalError
from services.exchange.journal_codec import CommandCodecError, encode_command, recover_exchange
from services.exchange.sequenced import SequencedExchange
from services.orders.model import CancelOrder, Command, PlaceOrder


def place(seq, oid, side, qty="1", price="100"):
    return Command(seq, PlaceOrder(oid, "acct", "BTC-USD", side, D(price), D(qty)))


class ExchangeRecoveryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "orders.journal"
        self.journal = CommandJournal(self.path)

    def append(self, *commands):
        for command in commands:
            self.assertTrue(self.journal.append(command.sequence, encode_command(command)))

    def test_empty_journal(self):
        recovered = recover_exchange(self.journal)
        self.assertEqual(recovered.history(), ())
        self.assertEqual(recovered.executions(), ())
        self.assertEqual(recovered.lifecycle(), {})
        self.assertFalse(self.path.exists())

    def test_partial_fill_and_cancel_recover_all_state(self):
        commands = (place(1, "ask", "sell", "3"),
                    place(2, "bid", "buy", "1", "101"),
                    Command(3, CancelOrder("ask")))
        self.append(*commands)
        before = self.path.read_bytes()
        recovered = recover_exchange(CommandJournal(self.path))
        expected = SequencedExchange.replay(commands)
        self.assertEqual(recovered.history(), expected.history())
        self.assertEqual(recovered.executions(), expected.executions())
        self.assertEqual(recovered.lifecycle(), expected.lifecycle())
        self.assertEqual(recovered.remaining("ask"), D(0))
        self.assertEqual(recovered.lifecycle()["ask"].filled, D(1))
        self.assertEqual(recovered.lifecycle()["ask"].cancelled, D(2))
        self.assertEqual(self.path.read_bytes(), before)

    def test_full_fill_and_repeated_read_only_recovery(self):
        self.append(place(1, "ask", "sell"), place(2, "bid", "buy"))
        first = recover_exchange(self.journal)
        second = recover_exchange(self.journal)
        self.assertEqual(first.executions(), second.executions())
        self.assertEqual(first.lifecycle()["ask"].status, "filled")
        self.assertEqual(len(first.executions()), 1)
        self.assertEqual(len(self.journal.entries()), 2)

    def test_invalid_matching_history_fails_without_truncation(self):
        self.append(place(1, "ask", "sell"), place(2, "bid", "buy"),
                    Command(3, CancelOrder("ask")))
        before = self.path.read_bytes()
        with self.assertRaises(CommandCodecError):
            recover_exchange(self.journal)
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_order_history_fails_without_truncation(self):
        self.append(place(1, "ask", "sell"), place(2, "ask", "sell"))
        before = self.path.read_bytes()
        with self.assertRaises(CommandCodecError):
            recover_exchange(self.journal)
        self.assertEqual(self.path.read_bytes(), before)

    def test_corrupt_record_fails_closed(self):
        self.append(place(1, "ask", "sell"))
        self.path.write_bytes(self.path.read_bytes()[:-1])
        with self.assertRaises(JournalError):
            recover_exchange(self.journal)

    def test_invalid_schema_fails_closed(self):
        self.journal.append(1, {"version": 9, "type": "cancel", "order_id": "ask"})
        with self.assertRaises(CommandCodecError):
            recover_exchange(self.journal)

    def test_recovery_does_not_acknowledge_new_orders(self):
        self.append(place(1, "ask", "sell"))
        recovered = recover_exchange(self.journal)
        recovered.apply(place(2, "bid", "buy"))
        self.assertEqual(len(recovered.history()), 2)
        self.assertEqual(len(recover_exchange(self.journal).history()), 1)


if __name__ == "__main__":
    unittest.main()
