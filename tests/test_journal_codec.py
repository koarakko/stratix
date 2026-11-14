import tempfile
import unittest
from decimal import Decimal as D
from pathlib import Path

from services.exchange.command_log import CommandJournal, JournalError
from services.exchange.journal_codec import (CommandCodecError, decode_command,
                                             encode_command, recover_order_state)
from services.orders.model import CancelOrder, Command, PlaceOrder


def place(seq=1, oid="ask", qty="2"):
    return Command(seq, PlaceOrder(oid, "acct", "BTC-USD", "sell", D("100.00"), D(qty)))


class JournalCodecTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "orders.journal"

    def test_canonical_roundtrip_and_recovery(self):
        journal = CommandJournal(self.path)
        commands = (place(), Command(2, CancelOrder("ask")))
        for command in commands:
            self.assertTrue(journal.append(command.sequence, encode_command(command)))
        recovered = recover_order_state(CommandJournal(self.path))
        self.assertEqual(recovered.history(), commands)
        self.assertEqual(recovered.order("ask").status, "cancelled")
        self.assertEqual(encode_command(decode_command(1, encode_command(commands[0]))), encode_command(commands[0]))

    def test_idempotent_retry_and_conflict(self):
        journal = CommandJournal(self.path)
        command = place()
        self.assertTrue(journal.append(1, encode_command(command)))
        self.assertFalse(journal.append(1, encode_command(command)))
        with self.assertRaises(JournalError):
            journal.append(1, encode_command(place(qty="3")))
        self.assertEqual(len(recover_order_state(journal).history()), 1)

    def test_reject_schema_and_decimal_ambiguity(self):
        payload = encode_command(place())
        bad = [dict(payload, version=2), dict(payload, extra=1),
               dict(payload, quantity="NaN"), dict(payload, quantity="1e2"),
               dict(payload, quantity=2), dict(payload, side="hold"),
               dict(payload, order_id=" ")]
        for item in bad:
            with self.subTest(item=item), self.assertRaises(CommandCodecError):
                decode_command(1, item)
        with self.assertRaises(CommandCodecError):
            decode_command(True, payload)
        with self.assertRaises(CommandCodecError):
            decode_command(1, {"version": 1, "type": "unknown"})

    def test_recovery_rejects_invalid_order_history_without_mutation(self):
        journal = CommandJournal(self.path)
        journal.append(1, encode_command(place()))
        journal.append(2, encode_command(place(2, "ask")))
        before = self.path.read_bytes()
        with self.assertRaises(CommandCodecError):
            recover_order_state(journal)
        self.assertEqual(self.path.read_bytes(), before)

    def test_recovery_rechecks_disk_and_fails_on_truncation(self):
        journal = CommandJournal(self.path)
        journal.append(1, encode_command(place()))
        self.path.write_bytes(self.path.read_bytes()[:-1])
        with self.assertRaises(JournalError):
            recover_order_state(journal)

    def test_recovery_rejects_cancel_of_filled_or_missing_order(self):
        journal = CommandJournal(self.path)
        journal.append(1, encode_command(Command(1, CancelOrder("missing"))))
        with self.assertRaises(CommandCodecError):
            recover_order_state(journal)


if __name__ == "__main__":
    unittest.main()
