"""Reject aliases of the journal inode; POSIX local defense, not fencing."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.exchange.command_log import CommandJournal, JournalError


@unittest.skipUnless(os.name == "posix" and hasattr(os, "link"), "POSIX hard links required")
class JournalHardlinkTests(unittest.TestCase):
    def test_existing_hardlink_rejected_on_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal"
            alias = Path(tmp) / "alias"
            self.assertTrue(CommandJournal(path).append(1, {"id": "one"}))
            original = path.read_bytes()
            os.link(path, alias)
            with self.assertRaises(JournalError):
                CommandJournal(path)
            self.assertEqual(path.read_bytes(), original)

    def test_link_added_after_validation_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal"
            alias = Path(tmp) / "alias"
            journal = CommandJournal(path)
            original_open = os.open

            def inject(file, flags, *args):
                if str(file) == str(path) and flags & os.O_WRONLY:
                    os.link(path, alias)
                return original_open(file, flags, *args)

            # The first append creates the file, then the second is attacked.
            self.assertTrue(journal.append(1, {"id": "one"}))
            before = path.read_bytes()
            with patch("services.exchange.command_log.os.open", side_effect=inject):
                with self.assertRaises(JournalError):
                    journal.append(2, {"id": "two"})
            self.assertEqual(path.read_bytes(), before)
            with self.assertRaisesRegex(JournalError, "poisoned"):
                journal.append(2, {"id": "two"})

    def test_normal_append_reopen_and_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal"
            journal = CommandJournal(path)
            self.assertTrue(journal.append(1, {"id": "one"}))
            reopened = CommandJournal(path)
            self.assertFalse(reopened.append(1, {"id": "one"}))
            self.assertTrue(reopened.append(2, {"id": "two"}))
            self.assertEqual(len(CommandJournal(path).entries()), 2)


if __name__ == "__main__":
    unittest.main()
