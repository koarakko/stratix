"""Reject hard-linked lock sidecars without writing journal commands."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from services.exchange.command_log import CommandJournal, JournalError

@unittest.skipUnless(os.name == 'posix' and hasattr(os, 'O_NOFOLLOW'), 'POSIX required')
class JournalLockHardlinkTests(unittest.TestCase):
    def test_existing_hardlink_rejected_without_journal_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'journal'
            other = Path(tmp) / 'other'
            other.write_bytes(b'untouched')
            os.link(other, str(path) + '.lock')
            with self.assertRaisesRegex(JournalError, 'exactly one hard link'):
                CommandJournal(path).append(1, {'id': 'one'})
            self.assertEqual(other.read_bytes(), b'untouched')
            self.assertFalse(path.exists())

    def test_link_created_after_open_detected_under_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'journal'
            sidecar = Path(str(path) + '.lock')
            alias = Path(tmp) / 'alias'
            real_flock = __import__('fcntl').flock
            def link_on_lock(fd, operation):
                if operation == __import__('fcntl').LOCK_EX:
                    os.link(sidecar, alias)
                return real_flock(fd, operation)
            with patch('services.exchange.command_log.fcntl.flock', side_effect=link_on_lock):
                with self.assertRaisesRegex(JournalError, 'multiple hard links'):
                    CommandJournal(path).append(1, {'id': 'one'})
            self.assertFalse(path.exists())

    def test_regular_lock_still_appends_and_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'journal'
            journal = CommandJournal(path)
            self.assertTrue(journal.append(1, {'id': 'one'}))
            self.assertFalse(journal.append(1, {'id': 'one'}))
            self.assertEqual(len(CommandJournal(path).entries()), 1)

if __name__ == '__main__':
    unittest.main()
