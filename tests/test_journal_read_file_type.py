"""Reject unsafe journal paths without following links or waiting on FIFOs."""
import os
import tempfile
import unittest
from pathlib import Path

from services.exchange.command_log import CommandJournal, JournalError


@unittest.skipUnless(os.name == "posix" and hasattr(os, "O_NOFOLLOW"), "POSIX O_NOFOLLOW required")
class JournalReadFileTypeTests(unittest.TestCase):
    def test_symlink_to_valid_journal_is_rejected_without_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "real"
            CommandJournal(target).append(1, {"id": "one"})
            original = target.read_bytes()
            alias = Path(tmp) / "alias"
            alias.symlink_to(target)
            with self.assertRaises(JournalError):
                CommandJournal(alias)
            self.assertEqual(target.read_bytes(), original)

    def test_fifo_is_rejected_without_waiting_for_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            fifo = Path(tmp) / "fifo"
            os.mkfifo(fifo)
            with self.assertRaisesRegex(JournalError, "regular file"):
                CommandJournal(fifo)

    def test_directory_rejected_and_regular_file_roundtrips(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(JournalError):
                CommandJournal(tmp)
            path = Path(tmp) / "journal"
            journal = CommandJournal(path)
            self.assertTrue(journal.append(1, {"id": "one"}))
            self.assertFalse(journal.append(1, {"id": "one"}))
            self.assertEqual(CommandJournal(path).entries(), ({"sequence": 1, "payload": {"id": "one"}},))


if __name__ == "__main__":
    unittest.main()
