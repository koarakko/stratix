"""Append refuses unsafe journal path substitution after read validation."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.exchange.command_log import CommandJournal, JournalError


@unittest.skipUnless(os.name == 'posix' and hasattr(os, 'O_NOFOLLOW'), 'POSIX O_NOFOLLOW required')
class JournalAppendPathTypeTests(unittest.TestCase):
    def test_symlink_swap_before_write_rejected_without_touching_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'journal'
            target = Path(tmp) / 'target'
            target.write_bytes(b'unchanged')
            journal = CommandJournal(path)
            original_open = os.open

            def swap(file, flags, *args):
                if str(file) == str(path) and flags & os.O_WRONLY:
                    path.symlink_to(target)
                return original_open(file, flags, *args)

            with patch('services.exchange.command_log.os.open', side_effect=swap):
                with self.assertRaises(JournalError):
                    journal.append(1, {'x': 1})
            self.assertEqual(target.read_bytes(), b'unchanged')
            with self.assertRaisesRegex(JournalError, 'poisoned'):
                journal.append(1, {'x': 1})

    def test_fifo_swap_before_write_rejected_without_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'journal'
            journal = CommandJournal(path)
            original_open = os.open

            def swap(file, flags, *args):
                if str(file) == str(path) and flags & os.O_WRONLY:
                    os.mkfifo(path)
                return original_open(file, flags, *args)

            with patch('services.exchange.command_log.os.open', side_effect=swap):
                with self.assertRaises(JournalError):
                    journal.append(1, {'x': 1})
            self.assertTrue(path.is_fifo())

    def test_normal_append_and_idempotent_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'journal'
            journal = CommandJournal(path)
            self.assertTrue(journal.append(1, {'x': 1}))
            self.assertFalse(journal.append(1, {'x': 1}))
            self.assertEqual(CommandJournal(path).entries(), ({'sequence': 1, 'payload': {'x': 1}},))


if __name__ == '__main__':
    unittest.main()
