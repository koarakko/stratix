"""Deterministic same-inode append race injection; not cross-process fencing."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from services.exchange.command_log import CommandJournal, JournalError, _record

class JournalAppendRaceTests(unittest.TestCase):
    def test_external_append_between_read_and_open_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'journal'
            journal = CommandJournal(path)
            journal.append(1, {'type': 'first'})
            real_open = os.open
            def racing_open(*args, **kwargs):
                with path.open('ab') as writer:
                    writer.write(_record(2, {'type': 'external'}))
                    writer.flush()
                    os.fsync(writer.fileno())
                return real_open(*args, **kwargs)
            with patch('services.exchange.command_log.os.open', side_effect=racing_open):
                with self.assertRaisesRegex(JournalError, 'size changed'):
                    journal.append(2, {'type': 'local'})
            self.assertTrue(journal._poisoned)
            self.assertEqual(len(CommandJournal(path).entries()), 2)
            with self.assertRaises(JournalError):
                journal.append(3, {'type': 'later'})

    def test_clean_append_and_idempotent_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'journal'
            journal = CommandJournal(path)
            self.assertTrue(journal.append(1, {'type': 'first'}))
            self.assertFalse(journal.append(1, {'type': 'first'}))
            self.assertTrue(journal.append(2, {'type': 'second'}))
            self.assertEqual(len(CommandJournal(path).entries()), 2)

    def test_same_size_rewrite_not_protected_by_size_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'journal'
            journal = CommandJournal(path)
            journal.append(1, {'type': 'first'})
            raw = bytearray(path.read_bytes())
            raw[0] ^= 1
            path.write_bytes(raw)
            with self.assertRaises(JournalError):
                journal.append(2, {'type': 'second'})

if __name__ == '__main__':
    unittest.main()
