"""File identity substitution checks for the local journal."""
import os
import tempfile
import unittest
from pathlib import Path

from services.exchange.command_log import CommandJournal, JournalError


class JournalIdentityTests(unittest.TestCase):
    def test_replace_identical_nonempty_file_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'journal'
            journal = CommandJournal(path)
            journal.append(1, {'kind': 'place'})
            replacement = path.with_suffix('.replacement')
            replacement.write_bytes(path.read_bytes())
            os.replace(replacement, path)
            with self.assertRaisesRegex(JournalError, 'identity'):
                journal.entries()
            with self.assertRaises(JournalError):
                journal.append(2, {'kind': 'cancel'})

    def test_replace_identical_empty_file_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'journal'
            path.touch()
            journal = CommandJournal(path)
            replacement = path.with_suffix('.replacement')
            replacement.touch()
            os.replace(replacement, path)
            with self.assertRaisesRegex(JournalError, 'identity'):
                journal.entries()

    def test_rename_original_away_and_restore_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'journal'
            journal = CommandJournal(path)
            journal.append(1, {'kind': 'place'})
            moved = path.with_suffix('.moved')
            os.replace(path, moved)
            os.replace(moved, path)
            self.assertEqual(len(journal.entries()), 1)
            self.assertFalse(journal.append(1, {'kind': 'place'}))

    def test_new_journal_and_reopen_after_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'journal'
            journal = CommandJournal(path)
            journal.append(1, {'kind': 'place'})
            replacement = path.with_suffix('.replacement')
            replacement.write_bytes(path.read_bytes())
            os.replace(replacement, path)
            with self.assertRaises(JournalError):
                journal.entries()
            reopened = CommandJournal(path)
            self.assertFalse(reopened.append(1, {'kind': 'place'}))
            self.assertTrue(reopened.append(2, {'kind': 'cancel'}))


if __name__ == '__main__':
    unittest.main()
