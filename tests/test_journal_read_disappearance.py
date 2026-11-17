"""A journal unlinked after a successful open must never look initially absent."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.exchange.command_log import CommandJournal, JournalError


class JournalReadDisappearanceTests(unittest.TestCase):
    def test_initially_missing_journal_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = CommandJournal(Path(tmp) / "journal")
            self.assertEqual(journal.entries(), ())

    def test_unlinked_after_open_during_initial_read_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal"
            path.write_bytes(b"")
            original_open = os.open

            def remove_after_open(file, flags, *args):
                fd = original_open(file, flags, *args)
                if str(file) == str(path) and flags & os.O_RDONLY == os.O_RDONLY and not flags & os.O_WRONLY:
                    path.unlink()
                return fd

            # Simulate a file appearing after the constructor's exists() check.
            with patch.object(Path, "exists", return_value=False):
                with patch("services.exchange.command_log.os.open", side_effect=remove_after_open):
                    with self.assertRaises(JournalError):
                        CommandJournal(path)

    def test_unlinked_during_read_after_existing_entry_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal"
            journal = CommandJournal(path)
            self.assertTrue(journal.append(1, {"id": "one"}))
            original_open = os.open

            def remove_after_open(file, flags, *args):
                fd = original_open(file, flags, *args)
                if str(file) == str(path) and not flags & os.O_WRONLY:
                    path.unlink()
                return fd

            with patch("services.exchange.command_log.os.open", side_effect=remove_after_open):
                with self.assertRaises(JournalError):
                    journal.entries()

    def test_normal_append_and_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal"
            journal = CommandJournal(path)
            self.assertTrue(journal.append(1, {"id": "one"}))
            self.assertFalse(journal.append(1, {"id": "one"}))
            self.assertEqual(len(CommandJournal(path).entries()), 1)
