"""Fault injection for local journal I/O; no real disk faults required."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.exchange.command_log import CommandJournal, JournalError


class JournalIOFailureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "commands.journal"
        self.journal = CommandJournal(self.path)

    def test_short_write_poison_and_torn_tail_rejected_on_reopen(self):
        original_write = os.write

        def short_write(fd, data):
            return original_write(fd, data[:-1])

        with patch("services.exchange.command_log.os.write", side_effect=short_write):
            with self.assertRaisesRegex(OSError, "short journal write"):
                self.journal.append(1, {"id": "a"})
        with self.assertRaisesRegex(JournalError, "poisoned"):
            self.journal.append(1, {"id": "a"})
        with self.assertRaisesRegex(JournalError, "incomplete trailing record"):
            CommandJournal(self.path)

    def test_fsync_failure_poison_even_if_full_record_was_written(self):
        with patch("services.exchange.command_log.os.fsync", side_effect=OSError("injected fsync failure")):
            with self.assertRaisesRegex(OSError, "injected fsync failure"):
                self.journal.append(1, {"id": "a"})
        with self.assertRaisesRegex(JournalError, "poisoned"):
            self.journal.append(1, {"id": "a"})
        # A complete record may exist, but durability/acknowledgement is UNKNOWN.
        reopened = CommandJournal(self.path)
        self.assertEqual(len(reopened.entries()), 1)
        self.assertFalse(reopened.append(1, {"id": "a"}))

    def test_write_failure_before_any_bytes_allows_clean_reopen(self):
        with patch("services.exchange.command_log.os.write", side_effect=OSError("injected write failure")):
            with self.assertRaisesRegex(OSError, "injected write failure"):
                self.journal.append(1, {"id": "a"})
        with self.assertRaisesRegex(JournalError, "poisoned"):
            self.journal.append(1, {"id": "a"})
        reopened = CommandJournal(self.path)
        self.assertEqual(reopened.entries(), ())
        self.assertTrue(reopened.append(1, {"id": "a"}))

    def test_successful_append_survives_reopen_and_retry(self):
        self.assertTrue(self.journal.append(1, {"id": "a"}))
        reopened = CommandJournal(self.path)
        self.assertFalse(reopened.append(1, {"id": "a"}))
        self.assertEqual(reopened.entries(), ({"sequence": 1, "payload": {"id": "a"}},))


if __name__ == "__main__":
    unittest.main()
