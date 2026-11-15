"""Fail-closed handling when an observed empty journal disappears."""
import tempfile
import unittest
from pathlib import Path

from services.exchange.command_log import CommandJournal, JournalError


class EmptyJournalDeletionTests(unittest.TestCase):
    def test_existing_empty_file_removed_before_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            path.touch()
            journal = CommandJournal(path)
            path.unlink()
            with self.assertRaises(JournalError):
                journal.entries()

    def test_existing_empty_file_removed_before_append(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            path.touch()
            journal = CommandJournal(path)
            path.unlink()
            with self.assertRaises(JournalError):
                journal.append(1, {"kind": "place"})
            self.assertFalse(path.exists())

    def test_initially_missing_file_can_be_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = CommandJournal(path)
            self.assertEqual(journal.entries(), ())
            self.assertTrue(journal.append(1, {"kind": "place"}))
            self.assertEqual(len(journal.entries()), 1)

    def test_newly_created_empty_file_then_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            journal = CommandJournal(path)
            path.touch()
            self.assertEqual(journal.entries(), ())
            path.unlink()
            with self.assertRaises(JournalError):
                journal.entries()


if __name__ == "__main__":
    unittest.main()
